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
    const double ShowSeconds,
    const TConstArrayView<double> KickTimesSeconds)
{
    if (!Settings.bSwingOnCord)
    {
        return FRotator::ZeroRotator;
    }
    const double Period = FMath::Max(0.25, static_cast<double>(Settings.SwingPeriodSeconds));
    const double Phase = static_cast<double>(HashUnit(Identity, Settings.SwaySeed, 0, 4u)) * UE_TWO_PI;
    const double Angle = ShowSeconds * UE_TWO_PI / Period + Phase;
    const FRotator Idle(
        Settings.SwingPitchAmplitudeDegrees * FMath::Sin(Angle + UE_HALF_PI),
        Settings.SwingYawAmplitudeDegrees * FMath::Sin(Angle),
        0.0);
    // Keep the established sway's arithmetic path bit-identical when no kick is
    // authored. This is an explicit compatibility contract, not an optimisation.
    if (Settings.KickAmplitudeDegrees <= 0.0f || KickTimesSeconds.IsEmpty())
    {
        return Idle;
    }

    const double Decay = FMath::Max(0.05, static_cast<double>(Settings.KickDecaySeconds));
    double Kick = 0.0;
    for (const double KickTime : KickTimesSeconds)
    {
        const double Since = ShowSeconds - KickTime;
        if (Since >= 0.0)
        {
            // An impulse begins at zero displacement and maximum velocity, then
            // oscillates at the prop's idle frequency under exponential damping.
            Kick += static_cast<double>(Settings.KickAmplitudeDegrees)
                * FMath::Exp(-Since / Decay) * FMath::Sin(Since * UE_TWO_PI / Period);
        }
    }
    return FRotator(Idle.Pitch + Kick * 0.6, Idle.Yaw + Kick, 0.0);
}

bool ResolveCordSwingKickTimes(
    const FInfinityBulbBodySettings& Settings,
    const TConstArrayView<TPair<FGuid, double>> AvailableCueTimes,
    TArray<double>& OutKickTimesSeconds,
    FString& OutError)
{
    OutKickTimesSeconds.Reset();
    OutError.Reset();
    if (Settings.KickAmplitudeDegrees <= 0.0f)
    {
        return true;
    }
    if (Settings.KickCueIds.IsEmpty())
    {
        OutError = TEXT("KickAmplitudeDegrees requires at least one Show cue id; raw kick seconds are not supported");
        return false;
    }
    for (const FGuid& CueId : Settings.KickCueIds)
    {
        const TPair<FGuid, double>* Match = AvailableCueTimes.FindByPredicate(
            [&CueId](const TPair<FGuid, double>& Row) { return Row.Key == CueId; });
        if (!Match)
        {
            OutError = FString::Printf(TEXT("Cue kick id %s is not in this compiled Passage"), *CueId.ToString());
            OutKickTimesSeconds.Reset();
            return false;
        }
        OutKickTimesSeconds.AddUnique(Match->Value);
    }
    OutKickTimesSeconds.Sort();
    return true;
}
}
