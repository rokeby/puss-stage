#include "InfinityStageLightEvents.h"

#include "Components/LocalLightComponent.h"
#include "Engine/PointLight.h"
#include "Engine/SpotLight.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageAttachmentBinding.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageStrobeLight.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageTypes.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** Sets InfinityStage.ShowLightEvents for one test and restores it after. */
struct FShowLightEventsLevel
{
    IConsoleVariable* CVar = nullptr;
    int32 Previous = 0;

    explicit FShowLightEventsLevel(const int32 Value)
    {
        CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("InfinityStage.ShowLightEvents"));
        if (CVar)
        {
            Previous = CVar->GetInt();
            CVar->Set(Value, ECVF_SetByCode);
        }
    }
    void Set(const int32 Value) const
    {
        if (CVar)
        {
            CVar->Set(Value, ECVF_SetByCode);
        }
    }
    int32 Get() const { return CVar ? CVar->GetInt() : -1; }
    ~FShowLightEventsLevel()
    {
        if (CVar)
        {
            CVar->Set(Previous, ECVF_SetByCode);
        }
    }
};

/** Every line the subsystem emits, split by where it went. */
struct FCapturedLines
{
    TArray<FString> Screen;
    TArray<FString> Log;

    void Attach(UInfinityStageLightEventSubsystem& Subsystem)
    {
        Subsystem.LineSinkForTests = [this](const FString& Line, const bool bScreen)
        {
            (bScreen ? Screen : Log).Add(Line);
        };
    }
    int32 CountLog(const TCHAR* Prefix) const
    {
        return Log.FilterByPredicate([Prefix](const FString& Line) { return Line.StartsWith(Prefix); }).Num();
    }
    int32 CountScreen(const TCHAR* Needle, const bool bWith) const
    {
        return Screen.FilterByPredicate([Needle, bWith](const FString& Line) { return Line.Contains(Needle) == bWith; }).Num();
    }
};

ULocalLightComponent* SpawnLamp(UWorld& World, const float Intensity, const bool bVisible)
{
    APointLight* Lamp = World.SpawnActor<APointLight>();
    ULocalLightComponent* Light = Lamp ? Lamp->FindComponentByClass<ULocalLightComponent>() : nullptr;
    if (Light)
    {
        Light->SetIntensityUnits(ELightUnits::Candelas);
        Light->SetIntensity(Intensity);
        Light->SetVisibility(bVisible);
    }
    return Light;
}

constexpr double LightEventsFrameSeconds = 1.0 / 60.0;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsOnceTest,
    "InfinityStage.LightEvents.OnCrossingDetectedOnce",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsOnceTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageLightEvents;
    const FInfinityLightEdgeThresholds Thresholds;

    // Pure edge: a 0.5 s strike ramp to 1740 cd, then a hold.
    auto CountOns = [](const FInfinityLightEdgeThresholds& T, FInfinityLightEdgeState State)
    {
        int32 Ons = 0;
        for (int32 Frame = 0; Frame < 180; ++Frame)
        {
            const double Level = 1740.0 * FMath::Clamp(Frame / 30.0, 0.0, 1.0);
            Ons += StepEdge(State, Level, Frame * (1.0 / 60.0), T) == EInfinityLightEdge::On ? 1 : 0;
        }
        return Ons;
    };
    TestEqual(TEXT("A ramp from dark to 1740 cd crosses ON exactly once"), CountOns(Thresholds, FInfinityLightEdgeState()), 1);
    FInfinityLightEdgeThresholds TooHigh;
    TooHigh.OnLevel = 5000.0;
    TooHigh.OffLevel = 1250.0;
    TestEqual(TEXT("Control: an ON level above the peak never fires (the count can be 0)"),
        CountOns(TooHigh, FInfinityLightEdgeState()), 0);
    FInfinityLightEdgeState Seeded;
    SeedEdge(Seeded, 1740.0, Thresholds);
    TestTrue(TEXT("Seeding a lit light marks it ON silently (the baseline at start)"), Seeded.bOn);

    // Through the real subsystem, in a Game world.
    FShowLightEventsLevel Level(2);
    TestEqual(TEXT("The cvar took level 2"), Level.Get(), 2);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    UInfinityStageLightEventSubsystem* Subsystem = World ? World->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr;
    ULocalLightComponent* Light = World ? SpawnLamp(*World, 0.0f, false) : nullptr;
    if (!TestNotNull(TEXT("Game world has the light-event subsystem"), Subsystem) || !TestNotNull(TEXT("Lamp spawned"), Light))
    {
        if (World) { World->DestroyWorld(false); }
        return false;
    }
    FCapturedLines Lines;
    Lines.Attach(*Subsystem);
    double Now = 100.0;
    Subsystem->TickAtForTests(Now);   // baseline: dark
    TestEqual(TEXT("Baseline poll emits nothing"), Lines.Log.Num(), 0);
    TestEqual(TEXT("EffectiveLevel: an invisible lamp counts as dark"), EffectiveLevel(*Light), 0.0);

    Light->SetVisibility(true);
    Light->SetIntensity(1740.0f);
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        Now += LightEventsFrameSeconds;
        Subsystem->TickAtForTests(Now);
    }
    TestEqual(TEXT("One INFINITY_LIGHT_ON line for one crossing"), Lines.CountLog(TEXT("INFINITY_LIGHT_ON|")), 1);
    const FString* OnLine = Lines.Log.FindByPredicate([](const FString& Line) { return Line.StartsWith(TEXT("INFINITY_LIGHT_ON|")); });
    TestTrue(TEXT("The line carries the level it rose to and its units"),
        OnLine && OnLine->Contains(TEXT("|to=1740|units=cd")));
    TestEqual(TEXT("Level 2 is log only: nothing went to the screen"), Lines.Screen.Num(), 0);

    Light->SetVisibility(false);
    Now += LightEventsFrameSeconds;
    Subsystem->TickAtForTests(Now);
    TestEqual(TEXT("Switching it off logs one OFF line"), Lines.CountLog(TEXT("INFINITY_LIGHT_OFF|")), 1);
    Light->SetVisibility(true);
    for (int32 Frame = 0; Frame < 60; ++Frame)
    {
        Now += LightEventsFrameSeconds;
        Subsystem->TickAtForTests(Now);
    }
    TestEqual(TEXT("Control: a second crossing soon after is a repeat, not a second ON line"),
        Lines.CountLog(TEXT("INFINITY_LIGHT_ON|")), 1);

    Subsystem->LineSinkForTests = nullptr;
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsFlickerTest,
    "InfinityStage.LightEvents.FlickerInsideBandDoesNotPrint",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsFlickerTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageLightEvents;
    const FInfinityLightEdgeThresholds Thresholds;   // ON at 1.0, OFF below 0.25
    auto CountEdges = [&Thresholds](const double Low, const double High, FInfinityLightEdgeState State)
    {
        int32 Edges = 0;
        for (int32 Frame = 0; Frame < 600; ++Frame)
        {
            const double Level = (Frame % 4 < 2) ? Low : High;   // 15 Hz flicker
            Edges += StepEdge(State, Level, Frame * (1.0 / 60.0), Thresholds) != EInfinityLightEdge::None ? 1 : 0;
        }
        return Edges;
    };
    TestEqual(TEXT("A dark lamp flickering inside the band (0.3..0.9) never crosses"), CountEdges(0.3, 0.9, FInfinityLightEdgeState()), 0);
    FInfinityLightEdgeState Lit;
    SeedEdge(Lit, 1740.0, Thresholds);
    TestEqual(TEXT("A lit lamp dipping to 0.5 (a stutter) never drops OFF"), CountEdges(0.5, 1740.0, Lit), 0);
    TestTrue(TEXT("Control: the same flicker across the band (0.1..1.5) does cross, many times"),
        CountEdges(0.1, 1.5, FInfinityLightEdgeState()) > 100);

    // And nothing reaches the output for the in-band flicker.
    FShowLightEventsLevel Level(1);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    UInfinityStageLightEventSubsystem* Subsystem = World ? World->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr;
    ULocalLightComponent* Light = World ? SpawnLamp(*World, 0.0f, true) : nullptr;
    if (!TestNotNull(TEXT("Subsystem"), Subsystem) || !TestNotNull(TEXT("Lamp"), Light))
    {
        if (World) { World->DestroyWorld(false); }
        return false;
    }
    FCapturedLines Lines;
    Lines.Attach(*Subsystem);
    double Now = 0.0;
    Subsystem->TickAtForTests(Now);
    for (int32 Frame = 0; Frame < 300; ++Frame)
    {
        Light->SetIntensity((Frame % 4 < 2) ? 0.3f : 0.9f);
        Now += LightEventsFrameSeconds;
        Subsystem->TickAtForTests(Now);
    }
    TestEqual(TEXT("In-band flicker: no screen line"), Lines.Screen.Num(), 0);
    TestEqual(TEXT("In-band flicker: no log line"), Lines.Log.Num(), 0);
    TestTrue(TEXT("Control: the lamp was being sampled all along"), Subsystem->GetLightsSampledForTests() >= 300);
    Subsystem->LineSinkForTests = nullptr;
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsStrobeTest,
    "InfinityStage.LightEvents.StrobePrintsOnceThenCounts",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsStrobeTest::RunTest(const FString& Parameters)
{
    FShowLightEventsLevel Level(1);
    // Runs a 1 Hz strobe (the Strobe's own LevelAt and its switch-off rule) for ten
    // flashes, and returns the captured lines.
    auto RunStrobe = [this](const double RepeatWindowSeconds, FCapturedLines& Lines)
    {
        UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
        UInfinityStageLightEventSubsystem* Subsystem = World ? World->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr;
        ULocalLightComponent* Light = World ? SpawnLamp(*World, 0.0f, false) : nullptr;
        if (!TestNotNull(TEXT("Subsystem"), Subsystem) || !TestNotNull(TEXT("Lamp"), Light))
        {
            if (World) { World->DestroyWorld(false); }
            return;
        }
        FInfinityLightEdgeThresholds Thresholds;
        Thresholds.RepeatWindowSeconds = RepeatWindowSeconds;
        Subsystem->ThresholdsForTests = Thresholds;
        Lines.Attach(*Subsystem);
        Subsystem->TickAtForTests(0.5);   // baseline, between flashes
        for (double T = 0.5 + LightEventsFrameSeconds; T < 10.5; T += LightEventsFrameSeconds)
        {
            const float Strobe = InfinityStageStrobe::LevelAt(T, 1.0f, 0.04f, 0.33f, 0.0f);
            const bool bLit = Strobe > UE_KINDA_SMALL_NUMBER;
            Light->SetVisibility(bLit);
            if (bLit)
            {
                Light->SetIntensity(20000.0f * Strobe);
            }
            Subsystem->TickAtForTests(T);
        }
        Subsystem->LineSinkForTests = nullptr;
        World->DestroyWorld(false);
    };

    FCapturedLines Limited;
    RunStrobe(8.0, Limited);
    TestEqual(TEXT("Ten flashes print ONE fresh ON line"), Limited.CountScreen(TEXT("(x"), false), 1);
    TestEqual(TEXT("...and one INFINITY_LIGHT_ON log line"), Limited.CountLog(TEXT("INFINITY_LIGHT_ON|")), 1);
    TestTrue(TEXT("...then counts on the same line, up to (x10)"),
        !Limited.Screen.IsEmpty() && Limited.Screen.Last().EndsWith(TEXT("(x10)")));
    TestTrue(TEXT("The strobe's ON line names the peak in cd"),
        !Limited.Screen.IsEmpty() && Limited.Screen[0].Contains(TEXT("ON ->20000 cd")));
    TestEqual(TEXT("A repeating light logs no OFF lines after its first"), Limited.CountLog(TEXT("INFINITY_LIGHT_OFF|")), 1);
    TestTrue(TEXT("Its count is logged, rate-limited (well under one line per flash)"),
        Limited.CountLog(TEXT("INFINITY_LIGHT_REPEAT|")) >= 1 && Limited.CountLog(TEXT("INFINITY_LIGHT_REPEAT|")) <= 3);

    FCapturedLines Unlimited;
    RunStrobe(0.0, Unlimited);
    TestEqual(TEXT("Control: with no repeat window every flash is a fresh ON (10)"),
        Unlimited.CountScreen(TEXT("(x"), false), 10);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsOffTest,
    "InfinityStage.LightEvents.CvarZeroDoesNoWork",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsOffTest::RunTest(const FString& Parameters)
{
    FShowLightEventsLevel Level(0);
    if (!TestNotNull(TEXT("InfinityStage.ShowLightEvents is registered"), Level.CVar))
    {
        return false;
    }
    if ((Level.CVar->GetFlags() & ECVF_SetByMask) == ECVF_SetByConstructor)
    {
        TestEqual(TEXT("Off by default"), Level.Previous, 0);
    }
    else
    {
        AddInfo(TEXT("The cvar was set by an ini or the console before this test; its default is not checked."));
    }
    TestEqual(TEXT("The cvar took level 0"), Level.Get(), 0);

    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    UInfinityStageLightEventSubsystem* Subsystem = World ? World->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr;
    ULocalLightComponent* Light = World ? SpawnLamp(*World, 0.0f, false) : nullptr;
    if (!TestNotNull(TEXT("Subsystem"), Subsystem) || !TestNotNull(TEXT("Lamp"), Light))
    {
        if (World) { World->DestroyWorld(false); }
        return false;
    }
    FCapturedLines Lines;
    Lines.Attach(*Subsystem);
    TestFalse(TEXT("At 0 the subsystem is not tickable: the engine never calls Tick"), Subsystem->IsTickable());
    double Now = 0.0;
    for (int32 Frame = 0; Frame < 60; ++Frame)
    {
        Light->SetVisibility(Frame % 2 == 0);
        Light->SetIntensity(Frame % 2 == 0 ? 1740.0f : 0.0f);
        Now += LightEventsFrameSeconds;
        Subsystem->TickAtForTests(Now);
        Subsystem->Tick(static_cast<float>(LightEventsFrameSeconds));
    }
    TestEqual(TEXT("At 0: no polls"), Subsystem->GetPollCountForTests(), int64(0));
    TestEqual(TEXT("At 0: no lights sampled"), Subsystem->GetLightsSampledForTests(), int64(0));
    TestEqual(TEXT("At 0: no lights even gathered"), Subsystem->GetTrackedLightCountForTests(), 0);
    TestEqual(TEXT("At 0: nothing emitted"), Lines.Screen.Num() + Lines.Log.Num(), 0);

    Level.Set(2);
    TestTrue(TEXT("Control: at 2 it is tickable"), Subsystem->IsTickable());
    Subsystem->TickAtForTests(Now + LightEventsFrameSeconds);
    TestEqual(TEXT("Control: at 2 one tick is one poll"), Subsystem->GetPollCountForTests(), int64(1));
    TestTrue(TEXT("Control: at 2 the lamp is gathered and sampled"),
        Subsystem->GetTrackedLightCountForTests() >= 1 && Subsystem->GetLightsSampledForTests() >= 1);

    Subsystem->LineSinkForTests = nullptr;
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsEditorWorldTest,
    "InfinityStage.LightEvents.IgnoredInEditorWorld",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsEditorWorldTest::RunTest(const FString& Parameters)
{
    FShowLightEventsLevel Level(1);
    TestFalse(TEXT("Not in the editor world"), UInfinityStageLightEventSubsystem::SupportsWorldType(EWorldType::Editor));
    TestFalse(TEXT("Not in preview worlds"), UInfinityStageLightEventSubsystem::SupportsWorldType(EWorldType::EditorPreview));
    TestTrue(TEXT("Control: PIE"), UInfinityStageLightEventSubsystem::SupportsWorldType(EWorldType::PIE));
    TestTrue(TEXT("Control: Game (standalone)"), UInfinityStageLightEventSubsystem::SupportsWorldType(EWorldType::Game));

    UWorld* Preview = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    TestNull(TEXT("A non-game world never gets the subsystem, even with the cvar on"),
        Preview ? Preview->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr);
    if (Preview)
    {
        Preview->DestroyWorld(false);
    }
    UWorld* Game = UWorld::CreateWorld(EWorldType::Game, false);
    TestNotNull(TEXT("Control: a Game world does get it"),
        Game ? Game->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr);
    if (Game)
    {
        Game->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsPerformanceTest,
    "InfinityStage.LightEvents.PerformanceModeNeverPrintsToScreen",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightEventsPerformanceTest::RunTest(const FString& Parameters)
{
    FShowLightEventsLevel Level(1);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    AInfinityStageShowRoot* Root = World ? World->SpawnActor<AInfinityStageShowRoot>() : nullptr;
    UInfinityStageLightEventSubsystem* Subsystem = World ? World->GetSubsystem<UInfinityStageLightEventSubsystem>() : nullptr;
    ULocalLightComponent* First = World ? SpawnLamp(*World, 0.0f, false) : nullptr;
    ULocalLightComponent* Second = World ? SpawnLamp(*World, 0.0f, false) : nullptr;
    if (!TestNotNull(TEXT("Show Root"), Root) || !TestNotNull(TEXT("Transport"), Root ? Root->Transport.Get() : nullptr)
        || !TestNotNull(TEXT("Subsystem"), Subsystem) || !TestNotNull(TEXT("Lamps"), Second) || !First)
    {
        if (World) { World->DestroyWorld(false); }
        return false;
    }
    FCapturedLines Lines;
    Lines.Attach(*Subsystem);
    Root->Transport->bPerformanceMode = true;
    double Now = 0.0;
    Subsystem->TickAtForTests(Now);
    First->SetVisibility(true);
    First->SetIntensity(1740.0f);
    for (int32 Frame = 0; Frame < 60; ++Frame)
    {
        Now += LightEventsFrameSeconds;
        Subsystem->TickAtForTests(Now);
    }
    TestEqual(TEXT("Performance mode: nothing on screen"), Lines.Screen.Num(), 0);
    TestEqual(TEXT("Performance mode: the log still has the event"), Lines.CountLog(TEXT("INFINITY_LIGHT_ON|")), 1);

    Root->Transport->bPerformanceMode = false;
    Second->SetVisibility(true);
    Second->SetIntensity(1740.0f);
    Now += LightEventsFrameSeconds;
    Subsystem->TickAtForTests(Now);
    TestEqual(TEXT("Control: rehearsal mode prints the next light on screen"), Lines.Screen.Num(), 1);

    Subsystem->LineSinkForTests = nullptr;
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightEventsLabelTest,
    "InfinityStage.LightEvents.LabelIsShowAttachmentLabel",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The materialise fixture of Cueing.Binding.SurvivesRealMaterialize, with a labelled lamp.
// MaterializePassage refuses game worlds, so labels are resolved in the preview world the
// lamp was materialised in; PIE lamps are duplicates of these.
bool FInfinityStageLightEventsLabelTest::RunTest(const FString& Parameters)
{
    const FString ShowLabel(TEXT("P01 SCORE B07 P01_WARM_THEATRICAL TOP_L"));
    InfinityStageAttachmentBinding::ResetCacheForTests();
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FGuid LampCue;
    FGuid LampAttachment;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
        if (Index == 0)
        {
            FInfinityCueAttachment& Lamp = Cue.WingPair.Attachments.AddDefaulted_GetRef();
            Lamp.AttachmentGuid = FGuid::NewGuid();
            Lamp.Kind = EInfinityAttachmentKind::Light;
            Lamp.Anchor = EInfinityAttachmentAnchor::Station;
            Lamp.Label = FText::FromString(ShowLabel);
            LampCue = Cue.CueGuid;
            LampAttachment = Lamp.AttachmentGuid;
        }
    }
    Show->ReconcilePassageSettings();
    const FName Tag(*FString::Printf(TEXT("InfinityStage.Attachment.%s|%s"),
        *LampCue.ToString(EGuidFormats::Digits), *LampAttachment.ToString(EGuidFormats::Digits)));

    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    TestTrue(TEXT("Fixture materializes"), Passage->MaterializePassage());
    AActor* LampActor = InfinityStageAttachmentBinding::FindAttachmentActor(World, Tag);
    ULocalLightComponent* LampLight = LampActor ? LampActor->FindComponentByClass<ULocalLightComponent>() : nullptr;
    if (!TestNotNull(TEXT("The materialised Show lamp has a local light"), LampLight))
    {
        World->DestroyWorld(false);
        InfinityStageAttachmentBinding::ResetCacheForTests();
        return false;
    }
#if WITH_EDITOR
    // Prove the label comes from the Show, not from the actor label materialise also sets.
    LampActor->SetActorLabel(TEXT("Renamed In Outliner"));
#endif
    const FString Resolved = InfinityStageLightEvents::ResolveLabel(*LampLight);
    TestTrue(FString::Printf(TEXT("A materialised Show lamp resolves to its Show attachment label (got '%s')"), *Resolved),
        Resolved == ShowLabel);

    ASpotLight* LevelLamp = World->SpawnActor<ASpotLight>();
#if WITH_EDITOR
    if (LevelLamp)
    {
        LevelLamp->SetActorLabel(TEXT("Opening Rig - FOH L"));
    }
#endif
    ULocalLightComponent* LevelLight = LevelLamp ? LevelLamp->FindComponentByClass<ULocalLightComponent>() : nullptr;
    TestTrue(TEXT("Control: a level light resolves to its actor label"),
        LevelLight && InfinityStageLightEvents::ResolveLabel(*LevelLight) == LevelLamp->GetActorNameOrLabel());

    LampActor->Tags.Remove(Tag);
    TestFalse(TEXT("Control: without its identity tag the lamp no longer resolves to the Show label"),
        InfinityStageLightEvents::ResolveLabel(*LampLight) == ShowLabel);

    World->DestroyWorld(false);
    InfinityStageAttachmentBinding::ResetCacheForTests();
    return true;
}

#endif
