#include "InfinityStageSweepLight.h"
#include "InfinityStageStrobeLight.h"
#include "Misc/AutomationTest.h"
#include "Components/PointLightComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/World.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
InfinityStageSweep::FParams MakeSweepTestParams()
{
    InfinityStageSweep::FParams Params;
    Params.Start = FVector(0.0, -1000.0, 0.0);
    Params.End = FVector(0.0, 1000.0, 0.0);
    Params.Control = FVector(800.0, 0.0, 0.0);
    Params.StartDelaySeconds = 2.0f;
    Params.TravelSeconds = 4.0f;
    Params.RepeatEverySeconds = 10.0f;
    Params.RepeatJitterSeconds = 3.0f;
    Params.Seed = 7;
    Params.FadeInSeconds = 1.0f;
    Params.FadeOutSeconds = 1.0f;
    Params.PeakIntensity = 5000.0f;
    return Params;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSweepPathTest,
    "InfinityStage.SweepLight.PathMaths",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSweepPathTest::RunTest(const FString& Parameters)
{
    using InfinityStageSweep::PathPoint;
    const FVector Start(0.0, -1000.0, 0.0);
    const FVector End(0.0, 1000.0, 200.0);
    const FVector Control(800.0, 0.0, 0.0);
    TestTrue(TEXT("Straight: U=0 is Start"), PathPoint(Start, End, false, Control, 0.0f).Equals(Start, 1.0e-3));
    TestTrue(TEXT("Straight: U=1 is End"), PathPoint(Start, End, false, Control, 1.0f).Equals(End, 1.0e-3));
    TestTrue(TEXT("Straight (mid unset): U=0.5 is the chord midpoint, the control is ignored"),
        PathPoint(Start, End, false, Control, 0.5f).Equals((Start + End) * 0.5, 1.0e-3));
    TestTrue(TEXT("Arc: U=0 is Start"), PathPoint(Start, End, true, Control, 0.0f).Equals(Start, 1.0e-3));
    TestTrue(TEXT("Arc: U=1 is End"), PathPoint(Start, End, true, Control, 1.0f).Equals(End, 1.0e-3));
    const FVector ArcMid = PathPoint(Start, End, true, Control, 0.5f);
    TestTrue(TEXT("Arc: U=0.5 is 0.25 Start + 0.5 Control + 0.25 End"),
        ArcMid.Equals(Start * 0.25 + Control * 0.5 + End * 0.25, 1.0e-3));
    TestFalse(TEXT("Control: the arc midpoint is NOT the chord midpoint"),
        ArcMid.Equals((Start + End) * 0.5, 1.0));
    TestTrue(TEXT("U is clamped: beyond 1 stays at End"), PathPoint(Start, End, true, Control, 1.7f).Equals(End, 1.0e-3));

    // Through the evaluator: position follows time along the path, and ping-pong reverses odd passes.
    InfinityStageSweep::FParams Params = MakeSweepTestParams();
    Params.RepeatJitterSeconds = 0.0f;
    const double Pass0Mid = Params.StartDelaySeconds + 0.5 * Params.TravelSeconds;
    TestTrue(TEXT("Evaluate at mid-pass is the straight midpoint"),
        InfinityStageSweep::Evaluate(Params, Pass0Mid).Position.Equals((Params.Start + Params.End) * 0.5, 1.0e-2));
    const double Pass1Early = Params.StartDelaySeconds + Params.RepeatEverySeconds + 0.25 * Params.TravelSeconds;
    const FVector Forward = InfinityStageSweep::Evaluate(Params, Pass1Early).Position;
    Params.bPingPong = true;
    const FVector Backward = InfinityStageSweep::Evaluate(Params, Pass1Early).Position;
    TestTrue(TEXT("Without ping-pong pass 1 is a quarter of the way from Start"),
        Forward.Equals(FMath::Lerp(Params.Start, Params.End, 0.25), 1.0e-2));
    TestTrue(TEXT("With ping-pong pass 1 runs back: a quarter of the way from End"),
        Backward.Equals(FMath::Lerp(Params.End, Params.Start, 0.25), 1.0e-2));

    // Aim: off keeps the actor's rotation; on looks at the target.
    Params.bPingPong = false;
    TestTrue(TEXT("Aim off: zero local rotation"), InfinityStageSweep::Evaluate(Params, Pass0Mid).Rotation.IsNearlyZero(1.0e-3));
    Params.bAimAtTarget = true;
    Params.AimTarget = FVector(0.0, 0.0, 0.0) + FVector(0.0, 1000.0, 0.0);   // straight along +Y from the midpoint
    TestTrue(TEXT("Aim on: looks at the target (yaw 90)"),
        FMath::IsNearlyEqual(InfinityStageSweep::Evaluate(Params, Pass0Mid).Rotation.Yaw, 90.0, 1.0e-2));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSweepEnvelopeTest,
    "InfinityStage.SweepLight.Envelope",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSweepEnvelopeTest::RunTest(const FString& Parameters)
{
    using InfinityStageSweep::Envelope;
    TestEqual(TEXT("Zero before the pass"), Envelope(-0.01, 4.0f, 1.0f, 1.0f), 0.0f);
    TestEqual(TEXT("Zero after the pass"), Envelope(4.01, 4.0f, 1.0f, 1.0f), 0.0f);
    TestEqual(TEXT("Peak in the middle"), Envelope(2.0, 4.0f, 1.0f, 1.0f), 1.0f);
    TestTrue(TEXT("Control: partway into the fade-in is NOT peak"), Envelope(0.5, 4.0f, 1.0f, 1.0f) < 0.99f);
    TestEqual(TEXT("Control: with no fades the start is already full"), Envelope(0.0, 4.0f, 0.0f, 0.0f), 1.0f);
    TestEqual(TEXT("A non-positive travel never lights"), Envelope(0.5, 0.0f, 0.0f, 0.0f), 0.0f);

    bool bRises = true;
    bool bFalls = true;
    float Last = -1.0f;
    for (int32 Step = 0; Step <= 20; ++Step)
    {
        const float Value = Envelope(Step * 0.05, 4.0f, 1.0f, 1.0f);   // 0..1 s
        bRises &= Value >= Last;
        Last = Value;
    }
    Last = 2.0f;
    for (int32 Step = 0; Step <= 20; ++Step)
    {
        const float Value = Envelope(3.0 + Step * 0.05, 4.0f, 1.0f, 1.0f);   // 3..4 s
        bFalls &= Value <= Last;
        Last = Value;
    }
    TestTrue(TEXT("Fade-in is monotone non-decreasing"), bRises);
    TestTrue(TEXT("Fade-out is monotone non-increasing"), bFalls);
    TestTrue(TEXT("Control: the fade-in actually rises (not flat)"), Envelope(0.9, 4.0f, 1.0f, 1.0f) > Envelope(0.1, 4.0f, 1.0f, 1.0f));

    // Through the evaluator: dark between passes and before the start delay; intensity = peak * alpha.
    const InfinityStageSweep::FParams Params = MakeSweepTestParams();
    TestEqual(TEXT("Dark before the start delay"), InfinityStageSweep::Evaluate(Params, 1.9).Alpha, 0.0f);
    TestEqual(TEXT("No pass before the start delay"), InfinityStageSweep::Evaluate(Params, 1.9).PassIndex, static_cast<int32>(INDEX_NONE));
    const InfinityStageSweep::FSample Mid = InfinityStageSweep::Evaluate(Params, 4.0);
    TestEqual(TEXT("Mid-pass alpha is 1"), Mid.Alpha, 1.0f);
    TestEqual(TEXT("Mid-pass intensity is the peak"), Mid.Intensity, 5000.0f);
    TestEqual(TEXT("Mid-pass is pass 0"), Mid.PassIndex, 0);
    TestEqual(TEXT("Dark in the gap after pass 0"), InfinityStageSweep::Evaluate(Params, 7.0).Alpha, 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSweepRepeatTest,
    "InfinityStage.SweepLight.RepeatJitterDeterministic",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSweepRepeatTest::RunTest(const FString& Parameters)
{
    InfinityStageSweep::FParams Params = MakeSweepTestParams();
    TArray<double> SeedA;
    TArray<double> SeedAAgain;
    for (int32 Pass = 0; Pass < 12; ++Pass)
    {
        SeedA.Add(InfinityStageSweep::PassStartSeconds(Params, Pass));
    }
    for (int32 Pass = 11; Pass >= 0; --Pass)   // reverse order: nothing depends on visit order
    {
        SeedAAgain.Insert(InfinityStageSweep::PassStartSeconds(Params, Pass), 0);
    }
    TestTrue(TEXT("Same seed, same pass starts (any visit order)"), SeedA == SeedAAgain);

    bool bGapsInRange = true;
    for (int32 Pass = 1; Pass < SeedA.Num(); ++Pass)
    {
        const double Gap = SeedA[Pass] - SeedA[Pass - 1];
        bGapsInRange &= Gap >= 10.0 - 1.0e-6 && Gap <= 13.0 + 1.0e-6;
    }
    TestTrue(TEXT("Every gap is RepeatEvery + 0..Jitter"), bGapsInRange);
    TestEqual(TEXT("Pass 0 starts at the start delay"), SeedA[0], 2.0);

    Params.Seed = 8;
    bool bAnyDiffers = false;
    for (int32 Pass = 1; Pass < 12; ++Pass)
    {
        bAnyDiffers |= !FMath::IsNearlyEqual(InfinityStageSweep::PassStartSeconds(Params, Pass), SeedA[Pass], 1.0e-6);
    }
    TestTrue(TEXT("A different seed gives different pass starts"), bAnyDiffers);

    Params.RepeatJitterSeconds = 0.0f;
    const double NoJitter8 = InfinityStageSweep::PassStartSeconds(Params, 5);
    Params.Seed = 7;
    const double NoJitter7 = InfinityStageSweep::PassStartSeconds(Params, 5);
    TestEqual(TEXT("Control: with zero jitter the seed does not matter"), NoJitter8, NoJitter7);
    TestEqual(TEXT("Control: zero jitter is exactly RepeatEvery apart"), NoJitter7, 2.0 + 5 * 10.0);

    // The evaluator agrees with PassStartSeconds, and is order-independent.
    Params = MakeSweepTestParams();
    const double Pass5 = InfinityStageSweep::PassStartSeconds(Params, 5);
    TestEqual(TEXT("Mid pass 5 the evaluator reports pass 5"),
        InfinityStageSweep::Evaluate(Params, Pass5 + 2.0).PassIndex, 5);
    TestEqual(TEXT("Control: just before pass 5 is dark"),
        InfinityStageSweep::Evaluate(Params, Pass5 - 0.01).Alpha, 0.0f);
    TArray<float> Forward;
    for (int32 Step = 0; Step < 300; ++Step)
    {
        Forward.Add(InfinityStageSweep::Evaluate(Params, Step * 0.37).Alpha);
    }
    bool bSame = true;
    for (int32 Step = 299; Step >= 0; --Step)
    {
        bSame &= InfinityStageSweep::Evaluate(Params, Step * 0.37).Alpha == Forward[Step];
    }
    TestTrue(TEXT("Reverse visiting gives identical alphas (scrub-safe)"), bSame);

    // RepeatEvery <= 0: one pass only. RepeatEvery < Travel: clamped so passes never overlap.
    Params.RepeatEverySeconds = 0.0f;
    TestEqual(TEXT("Single pass: lit in pass 0"), InfinityStageSweep::Evaluate(Params, 4.0).Alpha, 1.0f);
    TestEqual(TEXT("Single pass: dark long after"), InfinityStageSweep::Evaluate(Params, 104.0).Alpha, 0.0f);
    Params.RepeatEverySeconds = 1.0f;
    Params.RepeatJitterSeconds = 0.0f;
    TestEqual(TEXT("A repeat shorter than travel is clamped to travel"),
        InfinityStageSweep::PassStartSeconds(Params, 1), 2.0 + 4.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSweepEditorPreviewTest,
    "InfinityStage.SweepLight.EditorPreviewNeverPersists",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// As Strobe.EditorPreviewNeverPersists: the preview moves and drives the lights every frame,
// so a level save must never persist a mid-pass light, and the preview must not dirty the level.
bool FInfinityStageSweepEditorPreviewTest::RunTest(const FString& Parameters)
{
    for (const TCHAR* Name : { TEXT("SpotLight"), TEXT("RectLight") })
    {
        const FProperty* Property = AInfinityStageSweepLight::StaticClass()->FindPropertyByName(Name);
        TestTrue(FString::Printf(TEXT("%s property is Transient (never saved)"), Name),
            Property && Property->HasAnyPropertyFlags(CPF_Transient));
    }
    const FProperty* PeakProperty = AInfinityStageSweepLight::StaticClass()->FindPropertyByName(TEXT("PeakIntensity"));
    const FProperty* StartProperty = AInfinityStageSweepLight::StaticClass()->FindPropertyByName(TEXT("StartOffset"));
    TestTrue(TEXT("Control: the authored peak IS saved"), PeakProperty && !PeakProperty->HasAnyPropertyFlags(CPF_Transient));
    TestTrue(TEXT("Control: the authored path IS saved"), StartProperty && !StartProperty->HasAnyPropertyFlags(CPF_Transient));

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageSweepLight* Sweep = World->SpawnActor<AInfinityStageSweepLight>();
    TestTrue(TEXT("The spot object itself is RF_Transient"), Sweep->SpotLight && Sweep->SpotLight->HasAnyFlags(RF_Transient));
    TestTrue(TEXT("The rect object itself is RF_Transient"), Sweep->RectLight && Sweep->RectLight->HasAnyFlags(RF_Transient));
    TestFalse(TEXT("Control: the root, which carries the placement, is saved"),
        Sweep->GetRootComponent() && Sweep->GetRootComponent()->HasAnyFlags(RF_Transient));

    Sweep->PeakIntensity = 12345.0f;
    Sweep->StartDelaySeconds = 0.0f;
    Sweep->TravelSeconds = 4.0f;
    Sweep->RepeatEverySeconds = 0.0f;
    Sweep->FadeInSeconds = 0.5f;
    Sweep->FadeOutSeconds = 0.5f;
    UPackage* Package = World->GetOutermost();
    Package->SetDirtyFlag(false);
    const FTransform RootBefore = Sweep->GetActorTransform();

    Sweep->ApplyAtSeconds(1.0);
    const FVector Early = Sweep->SpotLight->GetRelativeLocation();
    TestTrue(TEXT("Mid-pass the spot is lit"), Sweep->SpotLight->IsVisible());
    TestEqual(TEXT("Mid-pass intensity is the peak"), Sweep->SpotLight->Intensity, 12345.0f);
    TestFalse(TEXT("Control: the unused rect stays dark"), Sweep->RectLight->IsVisible());
    Sweep->ApplyAtSeconds(3.0);
    const FVector Late = Sweep->SpotLight->GetRelativeLocation();
    TestTrue(TEXT("The lamp moves along the path"), !Early.Equals(Late, 1.0));
    Sweep->ApplyAtSeconds(10.0);
    TestFalse(TEXT("After the single pass the lamp is off"), Sweep->SpotLight->IsVisible());
    for (int32 Tick = 0; Tick < 20; ++Tick)
    {
        Sweep->Tick(0.016f);   // the wall-clock preview path
    }
    TestEqual(TEXT("Preview leaves the authored peak unchanged"), Sweep->PeakIntensity, 12345.0f);
    TestTrue(TEXT("Preview leaves the actor's placement unchanged"), Sweep->GetActorTransform().Equals(RootBefore));
    TestFalse(TEXT("Preview does not dirty the level package"), Package->IsDirty());
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSweepShadowDefaultsTest,
    "InfinityStage.SweepLight.ShadowsOnVolumetricOff",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The effect IS the shadow of the wing edges, so shadows must be on; volumetric shadows on a
// moving light are expensive, so they are off unless asked for.
bool FInfinityStageSweepShadowDefaultsTest::RunTest(const FString& Parameters)
{
    const AInfinityStageSweepLight* Defaults = GetDefault<AInfinityStageSweepLight>();
    TestTrue(TEXT("Default: bCastShadows"), Defaults->bCastShadows);
    TestFalse(TEXT("Default: no volumetric shadow"), Defaults->bCastVolumetricShadow);

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageSweepLight* Sweep = World->SpawnActor<AInfinityStageSweepLight>();
    TestTrue(TEXT("Spot casts shadows"), Sweep->SpotLight && Sweep->SpotLight->CastShadows);
    TestFalse(TEXT("Spot has no volumetric shadow"), Sweep->SpotLight && Sweep->SpotLight->bCastVolumetricShadow);
    TestTrue(TEXT("Rect casts shadows"), Sweep->RectLight && Sweep->RectLight->CastShadows);
    TestFalse(TEXT("Rect has no volumetric shadow"), Sweep->RectLight && Sweep->RectLight->bCastVolumetricShadow);

    // Controls: the check can fail. The Strobe's light does NOT cast shadows, and switching the
    // sweep's flags reaches its live component.
    AInfinityStageStrobeLight* Strobe = World->SpawnActor<AInfinityStageStrobeLight>();
    TestFalse(TEXT("Control: the Strobe's light reads as shadowless"), Strobe->Light && Strobe->Light->CastShadows);
    Sweep->bCastShadows = false;
    Sweep->bCastVolumetricShadow = true;
    Sweep->StartDelaySeconds = 0.0f;
    Sweep->FadeInSeconds = 0.0f;
    Sweep->ApplyAtSeconds(1.0);   // lit, so settings are pushed
    TestFalse(TEXT("Control: bCastShadows=false reaches the spot"), Sweep->SpotLight->CastShadows);
    TestTrue(TEXT("Control: bCastVolumetricShadow=true reaches the spot"), Sweep->SpotLight->bCastVolumetricShadow);
    World->DestroyWorld(false);
    return true;
}

#endif
