#include "InfinityStageLightMover.h"

namespace
{
/** -1..1 from a hash of (identity, seed, step, channel). One combine per statement,
 * so the order is fixed (memory: puss-random-draw-order). */
double HashSigned(const FGuid& Identity, const int32 Seed, const int64 Step, const uint32 Channel)
{
    uint32 Hash = GetTypeHash(Identity);
    Hash = HashCombineFast(Hash, ::GetTypeHash(Seed));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Step));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Channel));
    Hash ^= Hash >> 16;
    Hash *= 0x85ebca6bu;
    Hash ^= Hash >> 13;
    Hash *= 0xc2b2ae35u;
    Hash ^= Hash >> 16;
    return static_cast<double>(Hash & 0xFFFFFFu) / static_cast<double>(0x800000u) - 1.0;
}
}

namespace InfinityStageLightMover
{
float ErraticScale(const FInfinityLightMoverSettings& Settings, const double LampRouteDistanceCm, const double CameraRouteDistanceCm)
{
    if (!Settings.bEnabled)
    {
        return 0.0f;
    }
    const double OnsetCm = Settings.Trigger == EInfinityLightMoverTrigger::OnApproach
        ? LampRouteDistanceCm - FMath::Max(0.0, Settings.ApproachDistanceCm)
        : 0.0;
    if (CameraRouteDistanceCm < OnsetCm)
    {
        return 0.0f;
    }
    const double Ramp = FMath::Clamp((CameraRouteDistanceCm - OnsetCm) / FMath::Max(1.0, Settings.ErraticRampCm), 0.0, 1.0);
    const float Calm = FMath::Clamp(Settings.CalmScale, 0.0f, 1.0f);
    return Calm + (1.0f - Calm) * static_cast<float>(Ramp);
}

FRotator Evaluate(
    const FInfinityLightMoverSettings& Settings,
    const FGuid& Identity,
    const double LampRouteDistanceCm,
    const double CameraRouteDistanceCm,
    const double ShowSeconds)
{
    const float Scale = ErraticScale(Settings, LampRouteDistanceCm, CameraRouteDistanceCm);
    if (Scale <= 0.0f)
    {
        return FRotator::ZeroRotator;
    }
    const double Rate = FMath::Max(0.1, static_cast<double>(Settings.StepsPerSecond));
    const double StepTime = ShowSeconds * Rate;
    const int64 Step = static_cast<int64>(FMath::FloorToDouble(StepTime));
    const double InStep = StepTime - static_cast<double>(Step);
    // Move fast, then hold: an ease-out cubic over the first EaseFraction of the step.
    const double Move = FMath::Clamp(InStep / FMath::Clamp(static_cast<double>(Settings.EaseFraction), 0.01, 1.0), 0.0, 1.0);
    const double Eased = 1.0 - FMath::Pow(1.0 - Move, 3.0);

    const double FromYaw = HashSigned(Identity, Settings.Seed, Step - 1, 1u);
    const double ToYaw = HashSigned(Identity, Settings.Seed, Step, 1u);
    const double FromPitch = HashSigned(Identity, Settings.Seed, Step - 1, 2u);
    const double ToPitch = HashSigned(Identity, Settings.Seed, Step, 2u);
    const double Yaw = FMath::Lerp(FromYaw, ToYaw, Eased) * Settings.YawAmplitudeDegrees * Scale;
    const double Pitch = FMath::Lerp(FromPitch, ToPitch, Eased) * Settings.PitchAmplitudeDegrees * Scale;
    return FRotator(Pitch, Yaw, 0.0);
}
}
