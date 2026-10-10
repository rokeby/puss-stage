#include "InfinityStageCameraRig.h"
#include "InfinityStageTypes.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace InfinityStageShadowCatActionTests
{
constexpr double ShadowCatActionTolerance = 1.0e-9;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatMasterTimePoseTest,
    "InfinityStage.Editor.ShadowCatActions.MasterTimePose",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatMasterTimePoseTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageShadowCatActionTests;
    const TArray<double> Rates = {0.45, 0.60, 0.80, 0.55, 0.0, 0.25, 0.70};
    const double Direct = AInfinityStageCameraRig::IntegrateShadowCatPlayRates(Rates, 0.04);

    // Two deliberately different scrub histories. The production phase helper
    // accepts no history: re-evaluating the target frame integrates the same
    // Master intervals from the Passage start.
    AInfinityStageCameraRig::IntegrateShadowCatPlayRates({0.45, 0.60}, 0.04);
    AInfinityStageCameraRig::IntegrateShadowCatPlayRates({0.70, 0.25, 0.0}, 0.04);
    const double ViaForwardThenJump = AInfinityStageCameraRig::IntegrateShadowCatPlayRates(Rates, 0.04);
    AInfinityStageCameraRig::IntegrateShadowCatPlayRates({1.25, 1.25, 0.0, 0.0}, 0.04);
    const double ViaReverseThenJump = AInfinityStageCameraRig::IntegrateShadowCatPlayRates(Rates, 0.04);

    TestEqual(TEXT("Forward/jump path lands on the identical phase"), ViaForwardThenJump, Direct, ShadowCatActionTolerance);
    TestEqual(TEXT("Reverse/jump path lands on the identical phase"), ViaReverseThenJump, Direct, ShadowCatActionTolerance);
    TestEqual(TEXT("The known phase integral is exact"), Direct, 0.134, ShadowCatActionTolerance);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatActionBlendContinuityTest,
    "InfinityStage.Editor.ShadowCatActions.BlendContinuity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatActionBlendContinuityTest::RunTest(const FString& Parameters)
{
    constexpr double Epsilon = 1.0e-6;
    const auto Evaluate = [](const double PassageSeconds)
    {
        return AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
            PassageSeconds, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, false);
    };

    const FInfinityShadowCatActionTiming BeforeStart = Evaluate(5.0 - Epsilon);
    const FInfinityShadowCatActionTiming AtStart = Evaluate(5.0);
    const FInfinityShadowCatActionTiming AfterStart = Evaluate(5.0 + Epsilon);
    TestEqual(TEXT("Action is inactive before its start"), BeforeStart.Weight, 0.0);
    TestEqual(TEXT("Action begins at gait weight zero"), AtStart.Weight, 0.0);
    TestTrue(TEXT("Blend-in is continuous across the start"), FMath::Abs(AfterStart.Weight - AtStart.Weight) < 1.0e-4);

    const FInfinityShadowCatActionTiming BeforeEnd = Evaluate(9.0 - Epsilon);
    const FInfinityShadowCatActionTiming AtEnd = Evaluate(9.0);
    const FInfinityShadowCatActionTiming AfterEnd = Evaluate(9.0 + Epsilon);
    TestTrue(TEXT("Blend-out approaches zero continuously"), FMath::Abs(BeforeEnd.Weight - AtEnd.Weight) < 1.0e-4);
    TestEqual(TEXT("Action returns completely to gait at clip end"), AtEnd.Weight, 0.0);
    TestFalse(TEXT("Action is inactive after clip end"), AfterEnd.bActive);

    const FInfinityShadowCatActionTiming Held = AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
        15.0, 20.0, 5.0, 4.0, 1.0, 0.5, 0.75, true);
    TestTrue(TEXT("Hold-last remains active after the clip"), Held.bActive);
    TestEqual(TEXT("Hold-last clamps to the clip's final pose"), Held.PositionSeconds, 4.0);
    TestEqual(TEXT("Hold-last retains full weight before the Passage-end fade"), Held.Weight, 1.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatBobVariationTest,
    "InfinityStage.Editor.ShadowCatActions.BobVariationDeterministicBounded",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatBobVariationTest::RunTest(const FString& Parameters)
{
    constexpr double Bound = 0.05 + 1.0e-9;
    bool bSawVariation = false;
    for (int32 Sample = 0; Sample <= 1000; ++Sample)
    {
        const double Seconds = Sample * 0.04;
        const FInfinityShadowCatVariation First = AInfinityStageCameraRig::EvaluateShadowCatVariation(
            1847, Seconds, 12.0, 0.03, 0.03, 0.02, 0.8, 0.25);
        const FInfinityShadowCatVariation Again = AInfinityStageCameraRig::EvaluateShadowCatVariation(
            1847, Seconds, 12.0, 0.03, 0.03, 0.02, 0.8, 0.25);
        TestEqual(TEXT("Same seed/time repeats play-rate scale"), Again.PlayRateScale, First.PlayRateScale);
        TestEqual(TEXT("Same seed/time repeats bob-gain scale"), Again.BobGainScale, First.BobGainScale);
        TestTrue(TEXT("Play-rate variation stays within +/-5 percent"), FMath::Abs(First.PlayRateScale - 1.0) <= Bound);
        TestTrue(TEXT("Bob-gain variation stays within +/-5 percent"), FMath::Abs(First.BobGainScale - 1.0) <= Bound);
        bSawVariation |= !FMath::IsNearlyEqual(First.PlayRateScale, 1.0, 1.0e-6)
            || !FMath::IsNearlyEqual(First.BobGainScale, 1.0, 1.0e-6);
    }
    TestTrue(TEXT("The enabled defaults produce non-zero variation"), bSawVariation);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatActionMovesWithPassageTest,
    "InfinityStage.Editor.ShadowCatActions.MovesWithPassage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatActionMovesWithPassageTest::RunTest(const FString& Parameters)
{
    const FFrameRate TickResolution(1000, 1);
    const double BeforeMove = AInfinityStageCameraRig::PassageSecondsAtMasterFrame(
        FFrameNumber(43000), FFrameNumber(1000), TickResolution);
    const double AfterMove = AInfinityStageCameraRig::PassageSecondsAtMasterFrame(
        FFrameNumber(57000), FFrameNumber(15000), TickResolution);
    TestEqual(TEXT("Moving Passage and Master frame together preserves +42 s"), AfterMove, BeforeMove);
    TestEqual(TEXT("The rehearsal action remains at Passage +42 s"), AfterMove, 42.0);

    const FInfinityShadowCatActionTiming BeforeTiming = AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
        BeforeMove, 90.0, 42.0, 4.0, 1.0, 0.5, 0.5, false);
    const FInfinityShadowCatActionTiming AfterTiming = AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
        AfterMove, 90.0, 42.0, 4.0, 1.0, 0.5, 0.5, false);
    TestEqual(TEXT("Moved action has the same active state"), AfterTiming.bActive, BeforeTiming.bActive);
    TestEqual(TEXT("Moved action has the same pose"), AfterTiming.PositionSeconds, BeforeTiming.PositionSeconds);
    TestEqual(TEXT("Moved action has the same blend weight"), AfterTiming.Weight, BeforeTiming.Weight);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatCameraModeBlendContinuityTest,
    "InfinityStage.Editor.ShadowCatActions.CameraModeBlendContinuity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatCameraModeBlendContinuityTest::RunTest(const FString& Parameters)
{
    const FTransform Route(FRotator(0.0, 10.0, 0.0), FVector(100.0, 20.0, 180.0));
    const FTransform Head(FRotator(-15.0, 35.0, 2.0), FVector(-80.0, 15.0, 130.0));
    const FVector EyeOffset(12.0, 0.0, 3.0);
    constexpr double Epsilon = 1.0e-6;
    const FTransform AtRoute = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, 0.0);
    const FTransform JustAfterRoute = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, Epsilon);
    const FTransform AtHead = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, 1.0);
    const FTransform JustBeforeHead = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, 1.0 - Epsilon);
    TestTrue(TEXT("HeadPOV begins exactly on the Route camera"), AtRoute.Equals(Route, 1.0e-6));
    TestTrue(TEXT("HeadPOV blend is continuous at Route"),
        FVector::Distance(AtRoute.GetLocation(), JustAfterRoute.GetLocation()) < 1.0e-3);
    TestTrue(TEXT("HeadPOV blend is continuous at the head"),
        FVector::Distance(AtHead.GetLocation(), JustBeforeHead.GetLocation()) < 1.0e-3);
    TestTrue(TEXT("HeadPOV endpoint uses the configured local eye offset"),
        AtHead.GetLocation().Equals(Head.TransformPosition(EyeOffset), 1.0e-6));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatVisibilityModeEdgesTest,
    "InfinityStage.Editor.ShadowCatActions.VisibilityModeEdges",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatVisibilityModeEdgesTest::RunTest(const FString& Parameters)
{
    const FInfinityShadowCatActionTiming Before;
    FInfinityShadowCatActionTiming Active;
    Active.bActive = true;
    Active.Weight = 0.0;
    TestTrue(
        TEXT("Before an action the body is ShadowOnly"),
        AInfinityStageCameraRig::ResolveShadowCatBodyVisibility(
            Before, EInfinityShadowCatBodyVisibility::POVBody)
            == EInfinityShadowCatBodyVisibility::ShadowOnly);
    TestTrue(
        TEXT("At the exact active edge POVBody switches on even while camera weight is zero"),
        AInfinityStageCameraRig::ResolveShadowCatBodyVisibility(
            Active, EInfinityShadowCatBodyVisibility::POVBody)
            == EInfinityShadowCatBodyVisibility::POVBody);
    TestTrue(
        TEXT("ReflectionOnly is retained through the active interval"),
        AInfinityStageCameraRig::ResolveShadowCatBodyVisibility(
            Active, EInfinityShadowCatBodyVisibility::ReflectionOnly)
            == EInfinityShadowCatBodyVisibility::ReflectionOnly);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatPOVDeterminismAndNearClipTest,
    "InfinityStage.Editor.ShadowCatActions.POVDeterminismAndNearClip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatPOVDeterminismAndNearClipTest::RunTest(const FString& Parameters)
{
    const FTransform Route(FRotator(0.0, 10.0, 0.0), FVector(100.0, 20.0, 180.0));
    const FTransform Head(FRotator(-15.0, 35.0, 2.0), FVector(-80.0, 15.0, 130.0));
    const FVector EyeOffset(12.0, 0.0, 3.0);
    const FTransform First = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, 0.375);
    AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        FTransform::Identity, FTransform::Identity, FVector::ZeroVector, 0.9);
    const FTransform Again = AInfinityStageCameraRig::BlendShadowCatCameraTransform(
        Route, Head, EyeOffset, 0.375);
    TestTrue(TEXT("Same Master pose and weight produce an identical POV transform"),
        First.Equals(Again, InfinityStageShadowCatActionTests::ShadowCatActionTolerance));
    TestTrue(TEXT("Default 12 cm eye offset clears 3 cm near clip plus 2 cm guard"),
        AInfinityStageCameraRig::IsShadowCatHeadPOVNearClipSafe(EyeOffset, 3.0, 2.0));
    TestFalse(TEXT("Near-plane intersection mutant is rejected"),
        AInfinityStageCameraRig::IsShadowCatHeadPOVNearClipSafe(FVector(4.0, 0.0, 0.0), 3.0, 2.0));
    return true;
}

#endif
