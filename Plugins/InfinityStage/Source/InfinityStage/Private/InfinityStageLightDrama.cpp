#include "InfinityStageLightDrama.h"

#include "Components/LightComponent.h"
#include "GameFramework/Actor.h"
#include "Math/RandomStream.h"

namespace
{
/** Distinct salts, so a lamp's stutter and its sweep phase never share a stream. */
constexpr uint32 StutterSalt = 0x5717u;
constexpr uint32 PhaseSalt = 0x9A5Eu;

/** The strike ramp is cut into this many steps, each with its own dip. */
constexpr double StutterSteps = 11.0;

float Noise01(const FGuid& Identity, const uint32 Salt, const int32 Step)
{
    const uint32 Seed = HashCombineFast(
        HashCombineFast(GetTypeHash(Identity), ::GetTypeHash(Salt)),
        ::GetTypeHash(Step));
    return FRandomStream(static_cast<int32>(Seed)).GetFraction();
}

float EvaluateStrike(const FInfinityStageLightDrama& Drama, const FGuid& Identity, const double AheadCm)
{
    const float Unstruck = FMath::Clamp(Drama.UnstruckIntensityScale, 0.0f, 1.0f);
    const double StrikeStartCm = FMath::Max(0.0, Drama.StrikeDistanceCm);

    float Level = Unstruck;
    if (AheadCm <= StrikeStartCm)
    {
        const double Progress = FMath::Clamp((StrikeStartCm - AheadCm) / FMath::Max(1.0, Drama.StrikeRampCm), 0.0, 1.0);
        Level = FMath::Lerp(Unstruck, 1.0f, static_cast<float>(FMath::SmoothStep(0.0, 1.0, Progress)));
        if (Progress < 1.0)
        {
            // The lamp fights to catch: dips deepest as it first strikes, dying
            // away as it steadies. Keyed to distance, so it replays identically.
            const int32 Step = FMath::FloorToInt32(Progress * StutterSteps);
            const float Dip = FMath::Clamp(Drama.IgnitionStutter, 0.0f, 1.0f)
                * Noise01(Identity, StutterSalt, Step)
                * static_cast<float>(1.0 - Progress);
            Level *= 1.0f - Dip;
        }
    }

    const double PastCm = -AheadCm - FMath::Max(0.0, Drama.AfterPassDistanceCm);
    if (PastCm > 0.0)
    {
        if (Drama.AfterPass == EInfinityLightAfterPass::Extinguish)
        {
            Level = Unstruck;
        }
        else if (Drama.AfterPass == EInfinityLightAfterPass::Decay)
        {
            const double Faded = FMath::Clamp(PastCm / FMath::Max(1.0, Drama.DecayDistanceCm), 0.0, 1.0);
            Level = FMath::Lerp(Level, Unstruck, static_cast<float>(Faded));
        }
    }
    return Level;
}

FRotator EvaluateSlowMove(const FInfinityStageLightDrama& Drama, const FGuid& Identity, const double ShowSeconds)
{
    const double Phase = Drama.PhaseCycles + (Drama.bPhaseFromIdentity ? Noise01(Identity, PhaseSalt, 0) : 0.0);
    const double Angle = UE_TWO_PI * (ShowSeconds / FMath::Max(1.0f, Drama.PeriodSeconds) + Phase);
    // Tilt a quarter cycle behind pan: the pool drifts round an ellipse.
    return FRotator(
        FMath::Clamp(Drama.TiltAmplitudeDegrees, 0.0f, 45.0f) * FMath::Sin(Angle - UE_HALF_PI),
        FMath::Clamp(Drama.PanAmplitudeDegrees, 0.0f, 45.0f) * FMath::Sin(Angle),
        0.0);
}
}

namespace InfinityStageLightDrama
{
bool IsActive(const FInfinityStageLightDrama& Drama)
{
    return Drama.bStrikeOnApproach || Drama.bSlowMove;
}

FInfinityLightDramaPose Evaluate(
    const FInfinityStageLightDrama& Drama,
    const FGuid& Identity,
    const double LampRouteDistanceCm,
    const double CameraRouteDistanceCm,
    const double ShowSeconds)
{
    FInfinityLightDramaPose Pose;
    if (Drama.bStrikeOnApproach)
    {
        Pose.IntensityScale = EvaluateStrike(Drama, Identity, LampRouteDistanceCm - CameraRouteDistanceCm);
    }
    if (Drama.bSlowMove)
    {
        Pose.AimOffset = EvaluateSlowMove(Drama, Identity, ShowSeconds);
    }
    return Pose;
}

void ApplyToLamp(
    AActor& Lamp,
    const FInfinityStageLightDrama& Drama,
    const float AuthoredIntensity,
    const FTransform& AuthoredWorld,
    const FGuid& Identity,
    const double LampRouteDistanceCm,
    const double CameraRouteDistanceCm,
    const double ShowSeconds)
{
    const FInfinityLightDramaPose Pose =
        Evaluate(Drama, Identity, LampRouteDistanceCm, CameraRouteDistanceCm, ShowSeconds);
    if (Drama.bStrikeOnApproach)
    {
        if (ULightComponent* Light = Lamp.FindComponentByClass<ULightComponent>())
        {
            // Switched off rather than set to zero: an unlit lamp then costs no
            // shadow map, which is what lets a long corridor of them be affordable.
            const bool bLit = Pose.IntensityScale > UE_KINDA_SMALL_NUMBER;
            if (Light->IsVisible() != bLit)
            {
                Light->SetVisibility(bLit);
            }
            if (bLit)
            {
                Light->SetIntensity(AuthoredIntensity * Pose.IntensityScale);
            }
        }
    }
    if (Drama.bSlowMove)
    {
        // The offset turns the lamp in its own frame, so a pool sweeps across the
        // wing it was aimed at rather than swinging about world axes.
        Lamp.SetActorRotation(AuthoredWorld.GetRotation() * Pose.AimOffset.Quaternion(), ETeleportType::TeleportPhysics);
    }
}
}
