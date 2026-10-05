#include "InfinityStageBeeSwarmSimulation.h"

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
constexpr int32 TestBeeCount = 24;
constexpr double PositionToleranceCm = 1.0e-4;
constexpr double VelocityToleranceCmPerSecond = 1.0e-4;

FInfinityStageBeeSwarmParameters MakeTestParameters()
{
    FInfinityStageBeeSwarmParameters Parameters;
    Parameters.BeeCount = TestBeeCount;
    Parameters.Seed = static_cast<int32>(0xBEE62026u);
    Parameters.BoundsExtentCm = FVector(600.0, 450.0, 300.0);
    return Parameters;
}

bool StatesMatch(
    const FInfinityStageBeeSwarmSimulation& A,
    const FInfinityStageBeeSwarmSimulation& B,
    const double PositionTolerance = PositionToleranceCm,
    const double VelocityTolerance = VelocityToleranceCmPerSecond)
{
    const TConstArrayView<FInfinityStageBeeKinematics> ABees = A.GetBees();
    const TConstArrayView<FInfinityStageBeeKinematics> BBees = B.GetBees();
    if (ABees.Num() != BBees.Num())
    {
        return false;
    }
    for (int32 BeeIndex = 0; BeeIndex < ABees.Num(); ++BeeIndex)
    {
        if (!ABees[BeeIndex].Position.Equals(BBees[BeeIndex].Position, PositionTolerance)
            || !ABees[BeeIndex].Velocity.Equals(BBees[BeeIndex].Velocity, VelocityTolerance))
        {
            return false;
        }
    }
    return A.GetTargetPosition().Equals(B.GetTargetPosition(), PositionTolerance)
        && FMath::IsNearlyEqual(A.GetSimulationSeconds(), B.GetSimulationSeconds(), UE_DOUBLE_SMALL_NUMBER);
}

bool SatisfiesBoundsAndBubble(
    const FInfinityStageBeeSwarmSimulation& Simulation,
    const FInfinityStageBeeSwarmParameters& Parameters,
    const FVector& Origin,
    const FVector& CameraPosition)
{
    for (const FInfinityStageBeeKinematics& Bee : Simulation.GetBees())
    {
        const FVector Relative = Bee.Position - Origin;
        if (FMath::Abs(Relative.X) > Parameters.BoundsExtentCm.X + 0.01
            || FMath::Abs(Relative.Y) > Parameters.BoundsExtentCm.Y + 0.01
            || FMath::Abs(Relative.Z) > Parameters.BoundsExtentCm.Z + 0.01
            || FVector::Distance(Bee.Position, CameraPosition) + 0.01
                < Parameters.CameraRepulsionRadiusCm)
        {
            return false;
        }
    }
    return true;
}

double MinimumReturnMapRecurrence(
    const TArray<TArray<FVector>>& Frames,
    const int32 MinimumLag,
    const int32 MaximumLag,
    const double NormalizationDistance)
{
    double MinimumNormalizedRms = TNumericLimits<double>::Max();
    for (int32 Lag = MinimumLag; Lag <= MaximumLag; ++Lag)
    {
        double SquaredDistance = 0.0;
        int64 ValueCount = 0;
        for (int32 Frame = 0; Frame + Lag + 1 < Frames.Num(); ++Frame)
        {
            const int32 BeeCount = FMath::Min(Frames[Frame].Num(), Frames[Frame + Lag].Num());
            for (int32 BeeIndex = 0; BeeIndex < BeeCount; ++BeeIndex)
            {
                const FVector PositionReturn = Frames[Frame][BeeIndex]
                    - Frames[Frame + Lag][BeeIndex];
                const FVector FirstStep = Frames[Frame + 1][BeeIndex]
                    - Frames[Frame][BeeIndex];
                const FVector ReturnedStep = Frames[Frame + Lag + 1][BeeIndex]
                    - Frames[Frame + Lag][BeeIndex];
                const FVector StepReturn = FirstStep - ReturnedStep;
                SquaredDistance += PositionReturn.SizeSquared() + StepReturn.SizeSquared();
                ValueCount += 2;
            }
        }
        if (ValueCount > 0)
        {
            const double NormalizedRms = FMath::Sqrt(SquaredDistance / ValueCount)
                / FMath::Max(1.0, NormalizationDistance);
            MinimumNormalizedRms = FMath::Min(MinimumNormalizedRms, NormalizedRms);
        }
    }
    return MinimumNormalizedRms;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmSeedRepeatTest,
    "InfinityStage.Effects.BeeSwarm.SeedRepeat",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmSeedRepeatTest::RunTest(const FString& Parameters)
{
    const FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    const FVector Camera(0.0, 0.0, 0.0);
    FInfinityStageBeeSwarmSimulation First;
    FInfinityStageBeeSwarmSimulation Second;
    First.Reset(SwarmParameters, FVector::ZeroVector, Camera);
    Second.Reset(SwarmParameters, FVector::ZeroVector, Camera);

    for (int32 Frame = 0; Frame < 600; ++Frame)
    {
        First.Advance(1.0f / 60.0f, Camera);
        Second.Advance(1.0f / 60.0f, Camera);
    }
    TestTrue(TEXT("Identical seeds and inputs produce identical states"), StatesMatch(First, Second, 0.0, 0.0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmVariableFrameRateTest,
    "InfinityStage.Effects.BeeSwarm.VariableFrameRate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmVariableFrameRateTest::RunTest(const FString& Parameters)
{
    const FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    const FVector Camera(0.0, 0.0, 0.0);
    FInfinityStageBeeSwarmSimulation AtThirtyFps;
    FInfinityStageBeeSwarmSimulation AtSixtyFps;
    FInfinityStageBeeSwarmSimulation Jittered;
    AtThirtyFps.Reset(SwarmParameters, FVector::ZeroVector, Camera);
    AtSixtyFps.Reset(SwarmParameters, FVector::ZeroVector, Camera);
    Jittered.Reset(SwarmParameters, FVector::ZeroVector, Camera);

    constexpr int32 FixedSteps = 1200;
    for (int32 Frame = 0; Frame < FixedSteps / 4; ++Frame)
    {
        AtThirtyFps.Advance(SwarmParameters.FixedStepSeconds * 4.0f, Camera);
    }
    for (int32 Frame = 0; Frame < FixedSteps / 2; ++Frame)
    {
        AtSixtyFps.Advance(SwarmParameters.FixedStepSeconds * 2.0f, Camera);
    }
    constexpr int32 JitterPattern[] = {1, 7, 2, 5, 3, 6};
    int32 StepsSubmitted = 0;
    int32 PatternIndex = 0;
    while (StepsSubmitted < FixedSteps)
    {
        const int32 StepCount = FMath::Min(
            JitterPattern[PatternIndex % UE_ARRAY_COUNT(JitterPattern)],
            FixedSteps - StepsSubmitted);
        Jittered.Advance(SwarmParameters.FixedStepSeconds * StepCount, Camera);
        StepsSubmitted += StepCount;
        ++PatternIndex;
    }

    TestTrue(TEXT("30 and 60 fps schedules converge to the same fixed-step state"), StatesMatch(AtThirtyFps, AtSixtyFps));
    TestTrue(TEXT("A jittered schedule converges to the same fixed-step state"), StatesMatch(AtThirtyFps, Jittered));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmMovingCameraInterpolationTest,
    "InfinityStage.Effects.BeeSwarm.MovingCameraInterpolation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmMovingCameraInterpolationTest::RunTest(const FString& Parameters)
{
    FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    SwarmParameters.CameraRepulsionRadiusCm = 0.0f;
    SwarmParameters.FlyByRatePerSecond = 0.0f;
    const FVector StartCamera(-1000.0, -200.0, 100.0);
    const FVector EndCamera(1000.0, 200.0, 100.0);
    FInfinityStageBeeSwarmSimulation AtThirtyFps;
    FInfinityStageBeeSwarmSimulation AtSixtyFps;
    AtThirtyFps.Reset(SwarmParameters, FVector::ZeroVector, StartCamera);
    AtSixtyFps.Reset(SwarmParameters, FVector::ZeroVector, StartCamera);

    constexpr int32 DurationSeconds = 4;
    for (int32 Frame = 1; Frame <= DurationSeconds * 30; ++Frame)
    {
        const double Alpha = static_cast<double>(Frame) / (DurationSeconds * 30);
        AtThirtyFps.Advance(1.0f / 30.0f, FMath::Lerp(StartCamera, EndCamera, Alpha));
    }
    for (int32 Frame = 1; Frame <= DurationSeconds * 60; ++Frame)
    {
        const double Alpha = static_cast<double>(Frame) / (DurationSeconds * 60);
        AtSixtyFps.Advance(1.0f / 60.0f, FMath::Lerp(StartCamera, EndCamera, Alpha));
    }

    TestTrue(
        TEXT("Moving-camera substeps are frame-rate independent"),
        StatesMatch(AtThirtyFps, AtSixtyFps, 0.01, 0.01));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmCameraCutTest,
    "InfinityStage.Effects.BeeSwarm.CameraCutBubble",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmCameraCutTest::RunTest(const FString& Parameters)
{
    const FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    FInfinityStageBeeSwarmSimulation Simulation;
    Simulation.Reset(SwarmParameters, FVector::ZeroVector, FVector(1000.0, 0.0, 0.0));
    const FVector CutCamera = Simulation.GetBees()[0].Position;
    const double TimeBeforeCut = Simulation.GetSimulationSeconds();
    Simulation.Advance(0.0f, CutCamera, true);

    TestEqual(TEXT("A zero-delta camera cut does not advance simulation time"), Simulation.GetSimulationSeconds(), TimeBeforeCut);
    TestTrue(TEXT("A cut enforces both box and bubble immediately"), SatisfiesBoundsAndBubble(Simulation, SwarmParameters, FVector::ZeroVector, CutCamera));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmPauseTest,
    "InfinityStage.Effects.BeeSwarm.PauseBubble",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmPauseTest::RunTest(const FString& Parameters)
{
    const FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    FInfinityStageBeeSwarmSimulation Simulation;
    Simulation.Reset(SwarmParameters, FVector::ZeroVector, FVector(1000.0, 0.0, 0.0));
    Simulation.Advance(1.0f / 60.0f, FVector(1000.0, 0.0, 0.0));
    const FVector PausedCamera = Simulation.GetBees()[1].Position;
    const double TimeBeforePauseTick = Simulation.GetSimulationSeconds();
    Simulation.Advance(0.0f, PausedCamera);

    TestEqual(TEXT("A pause tick does not advance simulation time"), Simulation.GetSimulationSeconds(), TimeBeforePauseTick);
    TestTrue(TEXT("A pause tick enforces the moved camera bubble"), SatisfiesBoundsAndBubble(Simulation, SwarmParameters, FVector::ZeroVector, PausedCamera));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmBoundaryConstraintTest,
    "InfinityStage.Effects.BeeSwarm.BoundaryConstraints",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmBoundaryConstraintTest::RunTest(const FString& Parameters)
{
    FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    SwarmParameters.BoundsExtentCm = FVector(40.0, 30.0, 20.0);
    SwarmParameters.CameraRepulsionRadiusCm = 25.0f;
    const FVector Origin(50.0, -25.0, 10.0);
    const FVector Cameras[] =
    {
        Origin + FVector(40.0, 0.0, 0.0),
        Origin + FVector(-40.0, -30.0, -20.0),
        Origin + FVector(40.0, 30.0, 20.0)
    };

    FInfinityStageBeeSwarmSimulation Simulation;
    Simulation.Reset(SwarmParameters, Origin, Cameras[0]);
    TestTrue(TEXT("Reset resolves a camera sphere intersecting a box face"), SatisfiesBoundsAndBubble(Simulation, SwarmParameters, Origin, Cameras[0]));
    for (const FVector& Camera : Cameras)
    {
        Simulation.Advance(0.0f, Camera, true);
        TestTrue(TEXT("Corner and face cuts preserve both constraints"), SatisfiesBoundsAndBubble(Simulation, SwarmParameters, Origin, Camera));
        for (int32 Step = 0; Step < 120; ++Step)
        {
            Simulation.Advance(SwarmParameters.FixedStepSeconds, Camera);
        }
        TestTrue(TEXT("Every integrated boundary step preserves both constraints"), SatisfiesBoundsAndBubble(Simulation, SwarmParameters, Origin, Camera));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmNonRepetitionTest,
    "InfinityStage.Effects.BeeSwarm.NonRepetitionReturnMap",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBeeSwarmNonRepetitionTest::RunTest(const FString& Parameters)
{
    constexpr int32 SamplesPerSecond = 10;
    constexpr int32 DurationSeconds = 60;
    constexpr int32 TwelveSecondPeriodSamples = 12 * SamplesPerSecond;
    constexpr double MinimumAcceptedRecurrence = 0.01;

    TArray<TArray<FVector>> PerfectLoop;
    PerfectLoop.SetNum(DurationSeconds * SamplesPerSecond);
    for (int32 Sample = 0; Sample < PerfectLoop.Num(); ++Sample)
    {
        const double Phase = 2.0 * PI
            * static_cast<double>(Sample % TwelveSecondPeriodSamples)
            / TwelveSecondPeriodSamples;
        PerfectLoop[Sample].Add(FVector(100.0 * FMath::Cos(Phase), 100.0 * FMath::Sin(Phase), 0.0));
        PerfectLoop[Sample].Add(FVector(50.0 * FMath::Cos(Phase + 0.7), 50.0 * FMath::Sin(Phase + 0.7), 20.0));
    }
    const double LoopRecurrence = MinimumReturnMapRecurrence(
        PerfectLoop,
        2 * SamplesPerSecond,
        30 * SamplesPerSecond,
        100.0);
    const bool bPerfectLoopPassesGate = LoopRecurrence >= MinimumAcceptedRecurrence;
    TestFalse(
        *FString::Printf(TEXT("A perfect 12 s loop fails the return-map gate (%.9f < %.3f)"), LoopRecurrence, MinimumAcceptedRecurrence),
        bPerfectLoopPassesGate);

    const FInfinityStageBeeSwarmParameters SwarmParameters = MakeTestParameters();
    FInfinityStageBeeSwarmSimulation Simulation;
    Simulation.Reset(SwarmParameters, FVector::ZeroVector, FVector::ZeroVector);
    TArray<TArray<FVector>> SwarmFrames;
    SwarmFrames.Reserve(DurationSeconds * SamplesPerSecond);
    for (int32 Sample = 0; Sample < DurationSeconds * SamplesPerSecond; ++Sample)
    {
        Simulation.Advance(1.0f / SamplesPerSecond, FVector::ZeroVector);
        TArray<FVector>& Frame = SwarmFrames.Emplace_GetRef();
        constexpr int32 BeesInReturnMap = 4;
        Frame.Reserve(BeesInReturnMap);
        for (int32 BeeIndex = 0; BeeIndex < BeesInReturnMap; ++BeeIndex)
        {
            Frame.Add(Simulation.GetBees()[BeeIndex].Position);
        }
    }
    const double SwarmRecurrence = MinimumReturnMapRecurrence(
        SwarmFrames,
        2 * SamplesPerSecond,
        30 * SamplesPerSecond,
        SwarmParameters.BoundsExtentCm.Size());
    TestTrue(
        *FString::Printf(TEXT("Four-bee return map remains above %.3f (actual %.6f)"), MinimumAcceptedRecurrence, SwarmRecurrence),
        SwarmRecurrence >= MinimumAcceptedRecurrence);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBeeSwarmPythonMirrorGoldenTest,
    "InfinityStage.Effects.BeeSwarm.PythonMirrorGolden",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

/**
 * v3: the offline tuning harness (Tools/BeeSwarm/bee_swarm_mirror.py) must predict
 * this simulation, or the tuned defaults mean nothing. Values are the mirror's
 * output (python Tools/BeeSwarm/bee_swarm_harness.py --golden) for the header
 * defaults with 24 bees. 1 s: strict (no jump or fly-by has fired yet). 3 s: one
 * jump and one fly-by have fired; chaos amplifies CRT-level exp/cos differences,
 * so the tolerance is loose and a miss there alone is diagnostic. If the 1 s check
 * fails, re-tune only after fixing the mirror. Re-generate if any default changes.
 */
bool FInfinityStageBeeSwarmPythonMirrorGoldenTest::RunTest(const FString& Parameters)
{
    struct FGolden
    {
        int32 Frames;
        FVector Target;
        FVector Bees[4];
        int32 Jumps;
        int32 FlyBys;
    };
    const FGolden Goldens[] =
    {
        {60, FVector(-95.542060, -65.115590, -27.170772), {FVector(31.880307, -65.775054, -103.292955), FVector(-274.788225, -121.600288, -23.981981), FVector(-106.100343, -88.405933, 93.608277), FVector(-181.766003, -15.201736, -66.731934)}, 0, 0},
        {180, FVector(-223.533736, -34.821448, 0.077398), {FVector(-366.547897, 2.146363, -4.904196), FVector(-337.728099, -104.397014, 65.737197), FVector(-353.603326, -41.587562, 41.480011), FVector(-209.347499, -169.055507, 116.622096)}, 1, 1},
    };
    const double Tolerances[] = {0.01, 1.0};

    FInfinityStageBeeSwarmParameters SwarmParameters;
    SwarmParameters.BeeCount = 24;
    const FVector StartCamera(-300.0, 40.0, -60.0);
    const FVector EndCamera(-240.0, 10.0, -50.0);
    FInfinityStageBeeSwarmSimulation Simulation;
    Simulation.Reset(SwarmParameters, FVector::ZeroVector, StartCamera);

    int32 Frame = 0;
    for (int32 GoldenIndex = 0; GoldenIndex < static_cast<int32>(UE_ARRAY_COUNT(Goldens)); ++GoldenIndex)
    {
        const FGolden& Golden = Goldens[GoldenIndex];
        while (Frame < Golden.Frames)
        {
            ++Frame;
            const double Alpha = FMath::Min(1.0, static_cast<double>(Frame) / 60.0);
            Simulation.Advance(1.0f / 60.0f, FMath::Lerp(StartCamera, EndCamera, Alpha));
        }
        const double Tolerance = Tolerances[GoldenIndex];
        double WorstCm = FVector::Distance(Simulation.GetTargetPosition(), Golden.Target);
        for (int32 BeeIndex = 0; BeeIndex < 4; ++BeeIndex)
        {
            WorstCm = FMath::Max(WorstCm, FVector::Distance(Simulation.GetBees()[BeeIndex].Position, Golden.Bees[BeeIndex]));
        }
        TestTrue(
            *FString::Printf(TEXT("Mirror golden at frame %d within %.3f cm (worst %.6f cm)"), Golden.Frames, Tolerance, WorstCm),
            WorstCm <= Tolerance);
    }
    return true;
}

#endif
