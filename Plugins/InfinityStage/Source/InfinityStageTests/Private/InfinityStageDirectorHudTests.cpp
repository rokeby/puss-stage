#include "InfinityStageDirectorHud.h"

#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** Sets InfinityStage.DirectorHud for one test and restores it after. */
struct FScopedDirectorHudCVar
{
    IConsoleVariable* Variable = nullptr;
    int32 Previous = -1;

    explicit FScopedDirectorHudCVar(const int32 Value)
    {
        Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("InfinityStage.DirectorHud"));
        if (Variable)
        {
            Previous = Variable->GetInt();
            Variable->Set(Value, ECVF_SetByConsole);
        }
    }
    ~FScopedDirectorHudCVar()
    {
        if (Variable)
        {
            Variable->Set(Previous, ECVF_SetByConsole);
        }
    }
};

UInfinityStageShowAsset* MakeHudShow(const int32 WingCount)
{
    // The shape the transport boundary tests use (24 fps ticks, explicit Passage settings).
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Show->DisplayRate = FFrameRate(24, 1);
    Show->TickResolution = Show->DisplayRate;
    for (int32 Index = 0; Index < WingCount; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 100;
    }
    FInfinityPassageSettings& Settings = Show->PassageSettings.AddDefaulted_GetRef();
    Settings.PassageGuid = FGuid::NewGuid();
    Settings.Label = FText::FromString(TEXT("P01 Test"));
    Settings.FirstCueGuid = Show->Cues[0].CueGuid;
    Settings.LastCueGuid = Show->Cues[WingCount - 1].CueGuid;
    Settings.TailFrames = 100;
    Settings.TailDistanceCm = 500.0;
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Label = FText::FromString(TEXT("S1 Hangar"));
    Scene.Scene.DurationFrames = 100;
    Scene.Scene.bRetainPreviousCamera = true;
    return Show;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDirectorHudPureTest,
    "InfinityStage.DirectorHud.PureRules",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDirectorHudPureTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageDirectorHud;

    // Enable rules: auto is PIE-only; never in editor/preview worlds.
    TestTrue(TEXT("Auto: on in PIE"), IsEnabledFor(-1, EWorldType::PIE));
    TestFalse(TEXT("Auto: off in a packaged/standalone game"), IsEnabledFor(-1, EWorldType::Game));
    TestTrue(TEXT("1: on in a game"), IsEnabledFor(1, EWorldType::Game));
    TestFalse(TEXT("0: off in PIE"), IsEnabledFor(0, EWorldType::PIE));
    TestFalse(TEXT("Never in the editor world"), IsEnabledFor(1, EWorldType::Editor));
    TestFalse(TEXT("Never in a preview world"), IsEnabledFor(1, EWorldType::EditorPreview));

    // Bay: nearest station, 1-based, matching the lighting tools' bay ordinals.
    const TArray<double> Stations = {500.0, 1000.0, 1500.0, 2000.0};
    TestEqual(TEXT("No stations: bay 0"), NearestBay(TArray<double>(), 700.0), 0);
    TestEqual(TEXT("Before the first station: bay 1"), NearestBay(Stations, -300.0), 1);
    TestEqual(TEXT("On station 2: bay 2"), NearestBay(Stations, 1000.0), 2);
    TestEqual(TEXT("Just short of halfway 2->3: bay 2"), NearestBay(Stations, 1249.0), 2);
    TestEqual(TEXT("Halfway: the later bay"), NearestBay(Stations, 1250.0), 3);
    TestEqual(TEXT("Past the last station: last bay"), NearestBay(Stations, 9000.0), 4);

    TestEqual(TEXT("Kind: Passage"), FString(KindLabel(EInfinityCueType::WingPair)), FString(TEXT("Passage")));
    TestEqual(TEXT("Kind: Scene"), FString(KindLabel(EInfinityCueType::Scene)), FString(TEXT("Scene")));
    TestEqual(TEXT("Kind: Sequence prints as Interaction"), FString(KindLabel(EInfinityCueType::Sequence)), FString(TEXT("Interaction")));

    TestEqual(TEXT("Clock 0"), FormatClock(0.0), FString(TEXT("0:00.0")));
    TestEqual(TEXT("Clock 83.46 s"), FormatClock(83.46), FString(TEXT("1:23.4")));
    TestEqual(TEXT("Clock clamps negatives"), FormatClock(-4.0), FString(TEXT("0:00.0")));
    // Regression (suite 6 Oct): 62.3 - 60 in floating point is 2.2999..., which truncated to 1:02.2.
    TestEqual(TEXT("Clock 62.3 s is 1:02.3, not 1:02.2"), FormatClock(62.3), FString(TEXT("1:02.3")));
    TestEqual(TEXT("Clock still truncates: 62.39 s is 1:02.3"), FormatClock(62.39), FString(TEXT("1:02.3")));
    TestEqual(TEXT("Clock past an hour"), FormatClock(3725.0), FString(TEXT("62:05.0")));

    TArray<FInfinityHudShotSpan> Spans;
    Spans.Add({FFrameNumber(0), FFrameNumber(100), TEXT("LS_A")});
    Spans.Add({FFrameNumber(100), FFrameNumber(200), TEXT("LS_B")});
    TestEqual(TEXT("Shot at 50"), ShotAtFrame(Spans, 50), FString(TEXT("LS_A")));
    TestEqual(TEXT("Shot ranges are half-open"), ShotAtFrame(Spans, 100), FString(TEXT("LS_B")));
    TestEqual(TEXT("No shot past the end"), ShotAtFrame(Spans, 200), FString());

    TArray<FInfinityGoCue> Gos;
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityGoCue& Cue = Gos.AddDefaulted_GetRef();
        Cue.Frame = 100 * (Index + 1);
        Cue.Number = FString::FromInt(Index + 1);
        Cue.SegmentIndex = Index < 2 ? 0 : 1;
    }
    int32 Last = 0;
    int32 Next = 0;
    FindGoAround(Gos, 0, 150, Last, Next);
    TestEqual(TEXT("Last GO at or before the playhead"), Last, 0);
    TestEqual(TEXT("Next GO after the playhead"), Next, 1);
    FindGoAround(Gos, 1, 250, Last, Next);
    TestEqual(TEXT("A GO of another segment is never the 'last' one"), Last, INDEX_NONE);
    TestEqual(TEXT("Next GO in the next segment is still shown"), Next, 2);

    FInfinityDirectorHudState State;
    State.bHasShow = true;
    State.SegmentIndex = 3;
    State.SegmentCount = 20;
    State.SegmentLabel = TEXT("P02 Underpass");
    State.SegmentType = EInfinityCueType::WingPair;
    State.Bay = 7;
    State.BayCount = 21;
    State.MasterSeconds = 754.5;
    State.SegmentSeconds = 62.3;
    State.SegmentLengthSeconds = 130.0;
    State.SequenceName = TEXT("LS_Choreo_P02");
    State.ShotName = TEXT("LS_Rain");
    State.bPlaying = true;
    State.PlayRate = 4.0f;
    FString Top;
    FString Bottom;
    FormatLines(State, Top, Bottom);
    TestTrue(TEXT("Top: cue index and label"), Top.Contains(TEXT("Cue 4/20  Passage  'P02 Underpass'")));
    TestTrue(TEXT("Top: bay"), Top.Contains(TEXT("BAY 7/21")));
    TestTrue(TEXT("Bottom: status and rate"), Bottom.StartsWith(TEXT("PLAY x4")));
    TestTrue(TEXT("Bottom: Master and in-cue times"), Bottom.Contains(TEXT("Master 12:34.5   in cue 1:02.3 / 2:10.0")));
    TestTrue(TEXT("Bottom: sequence > sub-sequence"), Bottom.Contains(TEXT("Seq LS_Choreo_P02 > LS_Rain")));

    State.SegmentType = EInfinityCueType::Scene;
    State.bPlaying = false;
    FormatLines(State, Top, Bottom);
    TestFalse(TEXT("A Scene prints no bay"), Top.Contains(TEXT("BAY")));
    TestTrue(TEXT("Paused prints PAUSED"), Bottom.StartsWith(TEXT("PAUSED")));
    State.bHold = true;
    FormatLines(State, Top, Bottom);
    TestTrue(TEXT("A GO hold prints HOLD"), Bottom.StartsWith(TEXT("HOLD")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDirectorHudGatherTest,
    "InfinityStage.DirectorHud.GathersFromTransportAndCachesPerSegment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDirectorHudGatherTest::RunTest(const FString& Parameters)
{
    FScopedDirectorHudCVar CVar(1);
    UWorld* Preview = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    TestNull(TEXT("No HUD subsystem in a preview world"),
        Preview ? Preview->GetSubsystem<UInfinityStageDirectorHudSubsystem>() : nullptr);
    if (Preview)
    {
        Preview->DestroyWorld(false);
    }

    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    UInfinityStageDirectorHudSubsystem* Hud = World ? World->GetSubsystem<UInfinityStageDirectorHudSubsystem>() : nullptr;
    AInfinityStageShowRoot* Root = World ? World->SpawnActor<AInfinityStageShowRoot>() : nullptr;
    if (!TestNotNull(TEXT("Game world has the HUD subsystem"), Hud) || !TestNotNull(TEXT("Show Root"), Root)
        || !TestNotNull(TEXT("Show Root transport"), Root->Transport.Get()))
    {
        if (World) { World->DestroyWorld(false); }
        return false;
    }
    TestTrue(TEXT("The cvar makes it enabled in this game world"), InfinityStageDirectorHud::IsEnabledForWorld(World));

    UInfinityStageShowAsset* Show = MakeHudShow(5);
    Root->ShowAsset = Show;
    const bool bBuilt = Root->Transport->BuildSegments(Show);
    TestTrue(TEXT("Fixture: segments build"), bBuilt);
    Hud->SetShowRootForTests(Root);

    const FInfinityDirectorHudState First = Hud->GatherState();
    TestTrue(TEXT("Has a show"), First.bHasShow);
    TestEqual(TEXT("Playhead (no player: frame 0) is in the Passage"), First.SegmentIndex, 0);
    TestEqual(TEXT("Kind is Passage"), First.SegmentType, EInfinityCueType::WingPair);
    TestEqual(TEXT("Two segments"), First.SegmentCount, 2);
    TestEqual(TEXT("Bay count = compiled wing stations"), First.BayCount, 5);
    TestEqual(TEXT("No rig in the world: bay unknown (0)"), First.Bay, 0);
    TestEqual(TEXT("One cache build for the first segment"), Hud->GetSegmentCacheBuildsForTests(), 1);

    for (int32 Frame = 0; Frame < 10; ++Frame)
    {
        Hud->GatherState();
    }
    TestEqual(TEXT("Per-frame gathers never recompile while the segment is unchanged"),
        Hud->GetSegmentCacheBuildsForTests(), 1);

    // Control: a rebuilt table (new segment GUIDs) is noticed.
    Root->Transport->BuildSegments(MakeHudShow(3));
    Root->ShowAsset = Show;
    const FInfinityDirectorHudState Rebuilt = Hud->GatherState();
    TestEqual(TEXT("A rebuilt segment table rebuilds the cache"), Hud->GetSegmentCacheBuildsForTests(), 2);
    TestTrue(TEXT("Still reports a segment after the rebuild"), Rebuilt.SegmentIndex == 0);

    FString Top;
    FString Bottom;
    InfinityStageDirectorHud::FormatLines(First, Top, Bottom);
    TestTrue(TEXT("Formatted top line names the cue"), Top.StartsWith(TEXT("Cue 1/2  Passage")));

    World->DestroyWorld(false);
    return true;
}

#endif
