#include "InfinityStageCameraRig.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGaitBobMasterTimedTest,
    "InfinityStage.ShadowCat.GaitBobMasterTimed",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageGaitBobMasterTimedTest::RunTest(const FString& Parameters)
{
    constexpr double FrameSeconds = 1.0 / 25.0;
    constexpr double ReferenceSpeed = 250.0;
    constexpr double RollMeanSeconds = 1.0;
    constexpr double FadeSeconds = 0.5;
    constexpr double RollDegPerCm = 0.12;

    // (a) A biased constant lift remains as height but converges to no roll.
    {
        FInfinityGaitBobState State;
        FInfinityGaitBob Bob = AInfinityStageCameraRig::StepGaitBob(
            State, 0.0, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        TestEqual(TEXT("The first sample returns zero height"), Bob.HeightCm, 0.0);
        TestEqual(TEXT("The first sample returns zero roll"), Bob.RollDeg, 0.0);
        for (int32 Frame = 1; Frame <= 250; ++Frame)
        {
            Bob = AInfinityStageCameraRig::StepGaitBob(
                State, Frame * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
                RollMeanSeconds, FadeSeconds, RollDegPerCm);
        }
        TestEqual(TEXT("Walking weight converges to the full -15 cm height"), Bob.HeightCm, -15.0, 0.001);
        TestTrue(TEXT("A constant biased raw lift converges to zero roll"), FMath::Abs(Bob.RollDeg) < 1.0e-9);
    }

    // (b) Wall time is absent from the state. After a pause with no evaluations,
    // the next contiguous master frame is identical to uninterrupted playback.
    {
        FInfinityGaitBobState BeforePause;
        AInfinityStageCameraRig::StepGaitBob(
            BeforePause, 0.0, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        for (int32 Frame = 1; Frame <= 20; ++Frame)
        {
            AInfinityStageCameraRig::StepGaitBob(
                BeforePause, Frame * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
                RollMeanSeconds, FadeSeconds, RollDegPerCm);
        }
        FInfinityGaitBobState Paused = BeforePause;
        FInfinityGaitBobState Uninterrupted = BeforePause;
        const double WeightBeforePause = Paused.WalkWeight;
        AInfinityStageCameraRig::StepGaitBob(
            Paused, 20.0 * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        TestEqual(TEXT("A held master frame does not change weight across a wall-time pause"),
            Paused.WalkWeight, WeightBeforePause);
        const FInfinityGaitBob AfterPause = AInfinityStageCameraRig::StepGaitBob(
            Paused, 21.0 * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        const FInfinityGaitBob WithoutPause = AInfinityStageCameraRig::StepGaitBob(
            Uninterrupted, 21.0 * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        TestEqual(TEXT("A pause does not re-prime the walk weight"), Paused.WalkWeight, Uninterrupted.WalkWeight);
        TestEqual(TEXT("A pause resumes with the uninterrupted height"), AfterPause.HeightCm, WithoutPause.HeightCm);
        TestTrue(TEXT("The resumed weight remains non-zero"), Paused.WalkWeight > 0.5);
    }

    // (c) Reverse master time re-primes both filters and suppresses this sample.
    {
        FInfinityGaitBobState State;
        AInfinityStageCameraRig::StepGaitBob(
            State, 1.0, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        AInfinityStageCameraRig::StepGaitBob(
            State, 1.0 + FrameSeconds, -10.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        const FInfinityGaitBob Reversed = AInfinityStageCameraRig::StepGaitBob(
            State, 0.5, -7.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        TestEqual(TEXT("Reverse re-primes the weight to zero"), State.WalkWeight, 0.0);
        TestEqual(TEXT("Reverse re-primes the mean on the raw lift"), State.LiftMeanCm, -7.0);
        TestEqual(TEXT("Reverse returns zero height"), Reversed.HeightCm, 0.0);
        TestEqual(TEXT("Reverse returns zero roll"), Reversed.RollDeg, 0.0);
    }

    // (d) The same master frame is a pure read: state and output repeat exactly.
    {
        FInfinityGaitBobState State;
        AInfinityStageCameraRig::StepGaitBob(
            State, 2.0, -15.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        const FInfinityGaitBob First = AInfinityStageCameraRig::StepGaitBob(
            State, 2.0 + FrameSeconds, -11.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        const FInfinityGaitBobState BeforeRepeat = State;
        const FInfinityGaitBob Repeated = AInfinityStageCameraRig::StepGaitBob(
            State, 2.0 + FrameSeconds, -11.0, ReferenceSpeed, ReferenceSpeed,
            RollMeanSeconds, FadeSeconds, RollDegPerCm);
        TestEqual(TEXT("Repeat leaves last master seconds unchanged"), State.LastMasterSeconds, BeforeRepeat.LastMasterSeconds);
        TestEqual(TEXT("Repeat leaves the lift mean unchanged"), State.LiftMeanCm, BeforeRepeat.LiftMeanCm);
        TestEqual(TEXT("Repeat leaves the walk weight unchanged"), State.WalkWeight, BeforeRepeat.WalkWeight);
        TestEqual(TEXT("Repeat returns identical height"), Repeated.HeightCm, First.HeightCm);
        TestEqual(TEXT("Repeat returns identical roll"), Repeated.RollDeg, First.RollDeg);
    }

    // (e) The raw mean is independent of the fade. Under the old weighted-lift
    // formula, at the W=0.5 fade midpoint the lagging mean produced about -0.75
    // degrees of roll for this -15 cm input; the raw-centred formula stays at 0.
    {
        FInfinityGaitBobState State;
        double MaxAbsRoll = 0.0;
        for (int32 Frame = 0; Frame <= 100; ++Frame)
        {
            const FInfinityGaitBob Bob = AInfinityStageCameraRig::StepGaitBob(
                State, Frame * FrameSeconds, -15.0, ReferenceSpeed, ReferenceSpeed,
                RollMeanSeconds, FadeSeconds, RollDegPerCm);
            MaxAbsRoll = FMath::Max(MaxAbsRoll, FMath::Abs(Bob.RollDeg));
        }
        TestTrue(TEXT("Fade contention never invents roll from a constant raw lift"), MaxAbsRoll < 0.05);
    }

    // (f) At full weight, a -15 +/- 8 cm gait rolls both ways and averages near zero.
    {
        FInfinityGaitBobState State;
        State.bPrimed = true;
        State.LastMasterSeconds = 0.0;
        State.LiftMeanCm = -15.0;
        State.WalkWeight = 1.0;
        double MinRoll = 0.0;
        double MaxRoll = 0.0;
        double RollSum = 0.0;
        int32 Samples = 0;
        for (int32 Frame = 1; Frame <= 500; ++Frame)
        {
            const double Seconds = Frame * FrameSeconds;
            const double RawLiftCm = -15.0 + 8.0 * FMath::Sin(2.0 * UE_DOUBLE_PI * Seconds / 0.8);
            const FInfinityGaitBob Bob = AInfinityStageCameraRig::StepGaitBob(
                State, Seconds, RawLiftCm, ReferenceSpeed, ReferenceSpeed,
                RollMeanSeconds, FadeSeconds, RollDegPerCm);
            if (Frame > 300)
            {
                MinRoll = FMath::Min(MinRoll, Bob.RollDeg);
                MaxRoll = FMath::Max(MaxRoll, Bob.RollDeg);
                RollSum += Bob.RollDeg;
                ++Samples;
            }
        }
        TestTrue(TEXT("A biased oscillating gait rolls to both sides"), MinRoll < -0.5 && MaxRoll > 0.5);
        TestTrue(TEXT("A biased oscillating gait averages near zero roll"), FMath::Abs(RollSum / Samples) < 0.02);
    }

    return true;
}

#endif
