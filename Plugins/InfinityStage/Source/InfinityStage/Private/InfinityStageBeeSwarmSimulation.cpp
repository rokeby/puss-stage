#include "InfinityStageBeeSwarmSimulation.h"

namespace
{
constexpr float MinimumFixedStepSeconds = 1.0f / 1000.0f;

void ConstrainAxis(double& Position, double& Velocity, const double Minimum, const double Maximum)
{
    if (Position < Minimum)
    {
        Position = Minimum;
        Velocity = FMath::Abs(Velocity);
    }
    else if (Position > Maximum)
    {
        Position = Maximum;
        Velocity = -FMath::Abs(Velocity);
    }
}
}

void FInfinityStageBeeSwarmSimulation::Reset(
    const FInfinityStageBeeSwarmParameters& InParameters,
    const FVector& InSwarmOrigin,
    const FVector& InCameraPosition)
{
    Parameters = InParameters;
    Parameters.BeeCount = FMath::Max(1, Parameters.BeeCount);
    Parameters.FixedStepSeconds = FMath::Max(MinimumFixedStepSeconds, Parameters.FixedStepSeconds);
    Parameters.MaxSpeedCmPerSecond = FMath::Max(1.0f, Parameters.MaxSpeedCmPerSecond);
    Parameters.BoundsExtentCm.X = FMath::Max(1.0, FMath::Abs(Parameters.BoundsExtentCm.X));
    Parameters.BoundsExtentCm.Y = FMath::Max(1.0, FMath::Abs(Parameters.BoundsExtentCm.Y));
    Parameters.BoundsExtentCm.Z = FMath::Max(1.0, FMath::Abs(Parameters.BoundsExtentCm.Z));

    // A sphere no larger than the box half-diagonal always leaves at least one
    // feasible point in the box, even when its centre is inside the box.
    Parameters.CameraRepulsionRadiusCm = FMath::Clamp(
        Parameters.CameraRepulsionRadiusCm,
        0.0f,
        static_cast<float>(Parameters.BoundsExtentCm.Size()));
    Parameters.TargetDragPerSecond = FMath::Max(0.0f, Parameters.TargetDragPerSecond);
    Parameters.TargetJumpIntervalSeconds.X = FMath::Max(0.01, Parameters.TargetJumpIntervalSeconds.X);
    Parameters.TargetJumpIntervalSeconds.Y = FMath::Max(
        Parameters.TargetJumpIntervalSeconds.X,
        Parameters.TargetJumpIntervalSeconds.Y);
    Parameters.OrbitRadiusRangeCm.X = FMath::Max(
        Parameters.CameraRepulsionRadiusCm + 1.0f,
        Parameters.OrbitRadiusRangeCm.X);
    Parameters.OrbitRadiusRangeCm.Y = FMath::Max(
        Parameters.OrbitRadiusRangeCm.X,
        Parameters.OrbitRadiusRangeCm.Y);

    SwarmOrigin = InSwarmOrigin;
    TargetPosition = SwarmOrigin;
    TargetRandomStream.Initialize(Parameters.Seed);
    const FVector InitialTargetDirection = RandomUnitVector(TargetRandomStream);
    TargetVelocity = InitialTargetDirection * Parameters.TargetWanderSpeedCmPerSecond;
    SimulationSeconds = 0.0;
    AccumulatorSeconds = 0.0;
    NextTargetJumpSeconds = RandomRange(
        TargetRandomStream,
        Parameters.TargetJumpIntervalSeconds.X,
        Parameters.TargetJumpIntervalSeconds.Y);
    NextFlyBySeconds = SchedulePoisson(0.0, Parameters.FlyByRatePerSecond, TargetRandomStream);
    LastCameraPosition = InCameraPosition;
    bHasCameraPosition = true;

    Bees.SetNum(Parameters.BeeCount);
    BeeRuntime.SetNum(Parameters.BeeCount);
    for (int32 BeeIndex = 0; BeeIndex < Parameters.BeeCount; ++BeeIndex)
    {
        FBeeRuntime& Runtime = BeeRuntime[BeeIndex];
        const uint32 MixedSeed = static_cast<uint32>(Parameters.Seed)
            ^ (0x9E3779B9u * static_cast<uint32>(BeeIndex + 1));
        Runtime.RandomStream.Initialize(static_cast<int32>(MixedSeed));
        Runtime.OrbitAxis = RandomUnitVector(Runtime.RandomStream);
        Runtime.OrbitRadiusCm = RandomRange(
            Runtime.RandomStream,
            Parameters.OrbitRadiusRangeCm.X,
            Parameters.OrbitRadiusRangeCm.Y);
        Runtime.NextDartSeconds = SchedulePoisson(
            0.0,
            Parameters.DartRatePerSecond,
            Runtime.RandomStream);

        const float InitialRadius = RandomRange(
            Runtime.RandomStream,
            Parameters.CameraRepulsionRadiusCm + 5.0f,
            Parameters.OrbitRadiusRangeCm.Y);
        const FVector InitialDirection = RandomUnitVector(Runtime.RandomStream);
        const FVector InitialVelocityDirection = RandomUnitVector(Runtime.RandomStream);
        const float InitialSpeedFraction = RandomRange(Runtime.RandomStream, 0.1f, 0.35f);

        FInfinityStageBeeKinematics& Bee = Bees[BeeIndex];
        Bee.Position = SwarmOrigin + InitialDirection * InitialRadius;
        Bee.Velocity = InitialVelocityDirection
            * InitialSpeedFraction
            * Parameters.MaxSpeedCmPerSecond;
        ResolveConstraints(
            Bee.Position,
            Bee.Velocity,
            InCameraPosition,
            Runtime.OrbitAxis,
            1.0f);
    }
}

void FInfinityStageBeeSwarmSimulation::Advance(
    const float DeltaSeconds,
    const FVector& CameraPosition,
    const bool bCameraCut)
{
    if (!bHasCameraPosition)
    {
        LastCameraPosition = CameraPosition;
        bHasCameraPosition = true;
    }

    const float ClampedDeltaSeconds = FMath::Max(0.0f, DeltaSeconds);
    const double AccumulatorAtFrameStart = AccumulatorSeconds;
    AccumulatorSeconds += ClampedDeltaSeconds;
    double StepTimeFromFrameStart = Parameters.FixedStepSeconds - AccumulatorAtFrameStart;

    while (AccumulatorSeconds + UE_DOUBLE_SMALL_NUMBER >= Parameters.FixedStepSeconds)
    {
        const double Alpha = bCameraCut || ClampedDeltaSeconds <= UE_SMALL_NUMBER
            ? 1.0
            : FMath::Clamp(StepTimeFromFrameStart / ClampedDeltaSeconds, 0.0, 1.0);
        const FVector StepCameraPosition = FMath::Lerp(
            bCameraCut ? CameraPosition : LastCameraPosition,
            CameraPosition,
            Alpha);
        StepFixed(Parameters.FixedStepSeconds, StepCameraPosition);
        AccumulatorSeconds -= Parameters.FixedStepSeconds;
        StepTimeFromFrameStart += Parameters.FixedStepSeconds;
    }

    AccumulatorSeconds = FMath::Max(0.0, AccumulatorSeconds);
    LastCameraPosition = CameraPosition;

    // Deliberately outside the loop: cuts, pause ticks and short frames still
    // cannot put a bee inside the camera bubble.
    ResolveAllConstraints(CameraPosition);
}

void FInfinityStageBeeSwarmSimulation::StepFixed(
    const float StepSeconds,
    const FVector& CameraPosition)
{
    SimulationSeconds += StepSeconds;
    UpdateTarget(StepSeconds);

    if (SimulationSeconds >= NextFlyBySeconds)
    {
        InjectFlyBy(CameraPosition);
        NextFlyBySeconds = SchedulePoisson(
            SimulationSeconds,
            Parameters.FlyByRatePerSecond,
            TargetRandomStream);
    }

    const float DragMultiplier = FMath::Exp(-Parameters.DragPerSecond * StepSeconds);
    for (int32 BeeIndex = 0; BeeIndex < Bees.Num(); ++BeeIndex)
    {
        FInfinityStageBeeKinematics& Bee = Bees[BeeIndex];
        FBeeRuntime& Runtime = BeeRuntime[BeeIndex];

        const FVector ToTarget = TargetPosition - Bee.Position;
        const double TargetDistance = FMath::Max(1.0, ToTarget.Size());
        const FVector TargetDirection = ToTarget / TargetDistance;
        FVector Tangent = FVector::CrossProduct(Runtime.OrbitAxis, TargetDirection).GetSafeNormal();
        if (Tangent.IsNearlyZero())
        {
            Runtime.OrbitAxis = RandomUnitVector(Runtime.RandomStream);
            Tangent = FVector::CrossProduct(Runtime.OrbitAxis, TargetDirection).GetSafeNormal(
                UE_DOUBLE_SMALL_NUMBER,
                FVector::RightVector);
        }

        FVector Acceleration = TargetDirection
            * ((TargetDistance - Runtime.OrbitRadiusCm) * Parameters.OrbitSpringPerSecondSquared);
        Acceleration += Tangent * Parameters.OrbitTangentialAccelerationCmPerSecondSquared;
        Acceleration += CurlNoise(
            Bee.Position,
            SimulationSeconds,
            Parameters.LargeNoiseScalePerCm,
            0.37f) * Parameters.LargeNoiseAccelerationCmPerSecondSquared;
        Acceleration += CurlNoise(
            Bee.Position,
            SimulationSeconds,
            Parameters.SmallNoiseScalePerCm,
            1.31f) * Parameters.SmallNoiseAccelerationCmPerSecondSquared;

        const FVector ToCamera = CameraPosition - Bee.Position;
        const double CameraDistance = ToCamera.Size();
        if (CameraDistance > UE_DOUBLE_SMALL_NUMBER)
        {
            Acceleration += (ToCamera / CameraDistance)
                * (Parameters.CameraAttractWeight * 300.0f);
            const double RepulsionRange = Parameters.CameraRepulsionRadiusCm * 2.0;
            if (CameraDistance < RepulsionRange)
            {
                Acceleration -= (ToCamera / CameraDistance)
                    * ((1.0 - CameraDistance / FMath::Max(1.0, RepulsionRange))
                        * Parameters.DartStrengthCmPerSecond);
            }
        }

        if (SimulationSeconds >= Runtime.NextDartSeconds)
        {
            const FVector DartDirection = RandomUnitVector(Runtime.RandomStream);
            Bee.Velocity += DartDirection * Parameters.DartStrengthCmPerSecond;
            Runtime.NextDartSeconds = SchedulePoisson(
                SimulationSeconds,
                Parameters.DartRatePerSecond,
                Runtime.RandomStream);
        }

        Bee.Velocity = (Bee.Velocity + Acceleration * StepSeconds) * DragMultiplier;
        Bee.Velocity = Bee.Velocity.GetClampedToMaxSize(Parameters.MaxSpeedCmPerSecond);
        Bee.Position += Bee.Velocity * StepSeconds;
        ResolveConstraints(
            Bee.Position,
            Bee.Velocity,
            CameraPosition,
            Runtime.OrbitAxis,
            1.0f);
    }
}

void FInfinityStageBeeSwarmSimulation::UpdateTarget(const float StepSeconds)
{
    TargetVelocity += CurlNoise(
        TargetPosition,
        SimulationSeconds,
        Parameters.LargeNoiseScalePerCm * 0.35f,
        0.21f) * Parameters.TargetWanderSpeedCmPerSecond * StepSeconds;

    if (SimulationSeconds >= NextTargetJumpSeconds)
    {
        const FVector JumpDirection = RandomUnitVector(TargetRandomStream);
        TargetVelocity += JumpDirection * Parameters.TargetWanderSpeedCmPerSecond * 2.5f;
        const float JumpInterval = RandomRange(
            TargetRandomStream,
            Parameters.TargetJumpIntervalSeconds.X,
            Parameters.TargetJumpIntervalSeconds.Y);
        NextTargetJumpSeconds = SimulationSeconds + JumpInterval;
    }

    TargetVelocity *= FMath::Exp(-Parameters.TargetDragPerSecond * StepSeconds);

    TargetVelocity = TargetVelocity.GetClampedToMaxSize(
        Parameters.TargetWanderSpeedCmPerSecond * 3.0f);
    TargetPosition += TargetVelocity * StepSeconds;
    ConstrainToBounds(TargetPosition, TargetVelocity, 0.45f);
}

void FInfinityStageBeeSwarmSimulation::InjectFlyBy(const FVector& CameraPosition)
{
    if (Bees.IsEmpty())
    {
        return;
    }

    const int32 BeeIndex = TargetRandomStream.RandRange(0, Bees.Num() - 1);
    FInfinityStageBeeKinematics& Bee = Bees[BeeIndex];
    FBeeRuntime& Runtime = BeeRuntime[BeeIndex];
    const FVector Radial = RandomUnitVector(Runtime.RandomStream);
    const FVector TangentSeed = RandomUnitVector(Runtime.RandomStream);
    FVector Tangent = FVector::CrossProduct(Radial, TangentSeed).GetSafeNormal();
    if (Tangent.IsNearlyZero())
    {
        Tangent = FVector::CrossProduct(Radial, FVector::UpVector).GetSafeNormal(
            UE_DOUBLE_SMALL_NUMBER,
            FVector::RightVector);
    }
    Bee.Position = CameraPosition + Radial * (Parameters.CameraRepulsionRadiusCm + 20.0f);
    Bee.Velocity = (Tangent * 0.9f + Radial * 0.1f).GetSafeNormal()
        * (Parameters.MaxSpeedCmPerSecond * 0.9f);
    ResolveConstraints(
        Bee.Position,
        Bee.Velocity,
        CameraPosition,
        Runtime.OrbitAxis,
        1.0f);
}

void FInfinityStageBeeSwarmSimulation::ResolveAllConstraints(const FVector& CameraPosition)
{
    for (int32 BeeIndex = 0; BeeIndex < Bees.Num(); ++BeeIndex)
    {
        ResolveConstraints(
            Bees[BeeIndex].Position,
            Bees[BeeIndex].Velocity,
            CameraPosition,
            BeeRuntime[BeeIndex].OrbitAxis,
            1.0f);
    }
}

void FInfinityStageBeeSwarmSimulation::ResolveConstraints(
    FVector& Position,
    FVector& Velocity,
    const FVector& CameraPosition,
    const FVector& FallbackDirection,
    const float ExtentScale) const
{
    // One order everywhere: box first, then camera sphere. If the radial
    // projection clips back into the sphere, use the farthest box corner,
    // guaranteed feasible by Reset's radius clamp.
    ConstrainToBounds(Position, Velocity, ExtentScale);

    const double Radius = Parameters.CameraRepulsionRadiusCm;
    if (Radius <= 0.0)
    {
        return;
    }

    const FVector FromCamera = Position - CameraPosition;
    if (FromCamera.SizeSquared() + UE_DOUBLE_SMALL_NUMBER >= FMath::Square(Radius))
    {
        return;
    }

    const FVector Extent = Parameters.BoundsExtentCm * ExtentScale;
    const FVector Minimum = SwarmOrigin - Extent;
    const FVector Maximum = SwarmOrigin + Extent;
    const FVector Outward = FromCamera.GetSafeNormal(
        UE_DOUBLE_SMALL_NUMBER,
        FallbackDirection.GetSafeNormal(UE_DOUBLE_SMALL_NUMBER, FVector::UpVector));
    FVector Candidate = CameraPosition + Outward * Radius;
    Candidate.X = FMath::Clamp(Candidate.X, Minimum.X, Maximum.X);
    Candidate.Y = FMath::Clamp(Candidate.Y, Minimum.Y, Maximum.Y);
    Candidate.Z = FMath::Clamp(Candidate.Z, Minimum.Z, Maximum.Z);

    if (FVector::DistSquared(Candidate, CameraPosition) + UE_DOUBLE_SMALL_NUMBER
        < FMath::Square(Radius))
    {
        Candidate.X = FMath::Abs(Minimum.X - CameraPosition.X)
                > FMath::Abs(Maximum.X - CameraPosition.X)
            ? Minimum.X
            : Maximum.X;
        Candidate.Y = FMath::Abs(Minimum.Y - CameraPosition.Y)
                > FMath::Abs(Maximum.Y - CameraPosition.Y)
            ? Minimum.Y
            : Maximum.Y;
        Candidate.Z = FMath::Abs(Minimum.Z - CameraPosition.Z)
                > FMath::Abs(Maximum.Z - CameraPosition.Z)
            ? Minimum.Z
            : Maximum.Z;
    }

    Position = Candidate;
    const FVector FinalOutward = (Position - CameraPosition).GetSafeNormal(
        UE_DOUBLE_SMALL_NUMBER,
        Outward);
    const double InwardSpeed = FVector::DotProduct(Velocity, FinalOutward);
    if (InwardSpeed < 0.0)
    {
        Velocity -= FinalOutward * InwardSpeed;
    }
}

void FInfinityStageBeeSwarmSimulation::ConstrainToBounds(
    FVector& Position,
    FVector& Velocity,
    const float ExtentScale) const
{
    const FVector Extent = Parameters.BoundsExtentCm * ExtentScale;
    ConstrainAxis(Position.X, Velocity.X, SwarmOrigin.X - Extent.X, SwarmOrigin.X + Extent.X);
    ConstrainAxis(Position.Y, Velocity.Y, SwarmOrigin.Y - Extent.Y, SwarmOrigin.Y + Extent.Y);
    ConstrainAxis(Position.Z, Velocity.Z, SwarmOrigin.Z - Extent.Z, SwarmOrigin.Z + Extent.Z);
}

float FInfinityStageBeeSwarmSimulation::RandomRange(
    FRandomStream& Stream,
    const float Minimum,
    const float Maximum)
{
    return Stream.FRandRange(Minimum, Maximum);
}

FVector FInfinityStageBeeSwarmSimulation::RandomUnitVector(FRandomStream& Stream)
{
    const double Z = RandomRange(Stream, -1.0f, 1.0f);
    const double Angle = RandomRange(Stream, 0.0f, 2.0f * PI);
    const double Radius = FMath::Sqrt(FMath::Max(0.0, 1.0 - Z * Z));
    return FVector(Radius * FMath::Cos(Angle), Radius * FMath::Sin(Angle), Z);
}

FVector FInfinityStageBeeSwarmSimulation::CurlNoise(
    const FVector& Position,
    const double TimeSeconds,
    const float Scale,
    const float TimeScale)
{
    const FVector P = Position * Scale;
    const double T = TimeSeconds * TimeScale;
    // Analytic curl of A=(sin(y+mz+t0), sin(z+mx+t1), sin(x+my+t2)).
    constexpr double Mix = 0.73;
    const double C0 = FMath::Cos(P.Y + Mix * P.Z + T * 1.11);
    const double C1 = FMath::Cos(P.Z + Mix * P.X + T * 0.89);
    const double C2 = FMath::Cos(P.X + Mix * P.Y + T * 1.23);
    return FVector(Mix * C2 - C1, Mix * C0 - C2, Mix * C1 - C0).GetSafeNormal();
}

double FInfinityStageBeeSwarmSimulation::SchedulePoisson(
    const double NowSeconds,
    const float RatePerSecond,
    FRandomStream& Stream)
{
    if (RatePerSecond <= UE_SMALL_NUMBER)
    {
        return TNumericLimits<double>::Max();
    }
    const double Draw = Stream.FRand();
    const double U = FMath::Clamp(Draw, 0.0, 1.0 - UE_DOUBLE_SMALL_NUMBER);
    return NowSeconds - FMath::Loge(1.0 - U) / RatePerSecond;
}
