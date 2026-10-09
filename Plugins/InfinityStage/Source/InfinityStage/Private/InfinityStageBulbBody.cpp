#include "InfinityStageBulbBody.h"

namespace
{
/** 0..1 from a hash of (identity, seed, step, channel). One combine per statement,
 * so the order is fixed (memory: puss-random-draw-order). */
float HashUnit(const FGuid& Identity, const int32 Seed, const int64 Step, const uint32 Channel)
{
    uint32 Hash = GetTypeHash(Identity);
    Hash = HashCombineFast(Hash, ::GetTypeHash(Seed));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Step));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Channel));
    // Finalise (murmur3 fmix32) so neighbouring steps are uncorrelated.
    Hash ^= Hash >> 16;
    Hash *= 0x85ebca6bu;
    Hash ^= Hash >> 13;
    Hash *= 0xc2b2ae35u;
    Hash ^= Hash >> 16;
    return static_cast<float>(Hash & 0xFFFFFFu) / static_cast<float>(0x1000000u);
}
}

namespace InfinityStageBulbBody
{
float FlickerScale(
    const FInfinityBulbBodySettings& Settings,
    const FGuid& Identity,
    const double ShowSeconds,
    const double CameraPastLampCm)
{
    if (Settings.Flicker == EInfinityBulbBodyFlicker::Stable)
    {
        return 1.0f;
    }
    const double Rate = FMath::Max(1.0, static_cast<double>(Settings.FlickerRateHz));
    const int64 Step = static_cast<int64>(FMath::FloorToDouble(ShowSeconds * Rate));

    if (Settings.Flicker == EInfinityBulbBodyFlicker::Slight)
    {
        const float Dip = HashUnit(Identity, Settings.Seed, Step, 1u);
        return 1.0f - FMath::Clamp(Settings.SlightDepth, 0.0f, 1.0f) * Dip * Dip;
    }

    // Fail: dead from the death point on; before it, worse the nearer it is.
    if (CameraPastLampCm >= Settings.FailAtCm)
    {
        return 0.0f;
    }
    const double Window = FMath::Max(1.0, Settings.FailWindowCm);
    const float Severity = static_cast<float>(FMath::Clamp(
        (CameraPastLampCm - (Settings.FailAtCm - Window)) / Window, 0.0, 1.0));
    const float DropRoll = HashUnit(Identity, Settings.Seed, Step, 2u);
    if (DropRoll < 0.65f * Severity)
    {
        return 0.0f;
    }
    const float Sag = HashUnit(Identity, Settings.Seed, Step, 3u);
    return 1.0f - 0.6f * Severity * Sag - 0.04f * Sag;
}

float BodyIntensity(const float FullIntensity, const float DramaScale, const float Flicker)
{
    return FMath::Max(0.0f, FullIntensity) * FMath::Max(0.0f, DramaScale) * FMath::Clamp(Flicker, 0.0f, 1.0f);
}

FRotator CordSwingRotation(
    const FInfinityBulbBodySettings& Settings,
    const FGuid& Identity,
    const double ShowSeconds)
{
    if (!Settings.bSwingOnCord)
    {
        return FRotator::ZeroRotator;
    }
    const double Period = FMath::Max(0.25, static_cast<double>(Settings.SwingPeriodSeconds));
    const double Phase = static_cast<double>(HashUnit(Identity, Settings.SwaySeed, 0, 4u)) * UE_TWO_PI;
    const double Angle = ShowSeconds * UE_TWO_PI / Period + Phase;
    return FRotator(
        Settings.SwingPitchAmplitudeDegrees * FMath::Sin(Angle + UE_HALF_PI),
        Settings.SwingYawAmplitudeDegrees * FMath::Sin(Angle),
        0.0);
}
}
