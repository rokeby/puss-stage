#pragma once

#include "CoreMinimal.h"
#include "InfinityStageLightDrama.generated.h"

class AActor;

/** What a struck lamp does once the camera has gone past it. */
UENUM(BlueprintType)
enum class EInfinityLightAfterPass : uint8
{
    /** Stays lit behind the camera. */
    Hold,
    /** Fades back down over Decay Distance once the camera is past. */
    Decay,
    /** Drops back at once, like a lamp snuffed behind the audience. */
    Extinguish
};

/**
 * Light that behaves like apparatus: lamps that strike as the camera approaches,
 * and lamps that slowly sweep their pool across a wing.
 *
 * Strike is driven by camera distance along the route, never by elapsed time, so
 * scrubbing, reversing and re-running a pass always light the same lamps the same
 * way; it is the rule AnimationTrigger's TriggerDistanceCm already follows. Slow
 * moves follow the Show's master clock, so a scrubbed frame always shows the same
 * aim. Both default off, which leaves every existing light unchanged.
 *
 * Unstruck lamps are switched off rather than dimmed to zero, so a corridor of
 * strike-on-approach lamps only pays shadow cost for the lamps near the camera.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageLightDrama
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike")
    bool bStrikeOnApproach = false;

    /** How far ahead of the camera, along the route, the lamp begins to strike. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "0.0", Units = "cm", EditCondition = "bStrikeOnApproach"))
    double StrikeDistanceCm = 2500.0;

    /** Travel over which it comes up to full. Short reads as a strike, long as a fade-up. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "1.0", Units = "cm", EditCondition = "bStrikeOnApproach"))
    double StrikeRampCm = 250.0;

    /** How hard the lamp sputters while it catches: 0 is a clean fade, 1 violent.
     * The stutter is keyed to distance too, so it replays identically. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bStrikeOnApproach"))
    float IgnitionStutter = 0.6f;

    /** Brightness before the strike, as a fraction of authored. Above zero reads
     * as a pilot flame; zero switches the lamp off entirely. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bStrikeOnApproach"))
    float UnstruckIntensityScale = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (EditCondition = "bStrikeOnApproach"))
    EInfinityLightAfterPass AfterPass = EInfinityLightAfterPass::Hold;

    /** How far past the lamp the camera travels before After Pass applies. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "0.0", Units = "cm",
            EditCondition = "bStrikeOnApproach && AfterPass != EInfinityLightAfterPass::Hold"))
    double AfterPassDistanceCm = 600.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Strike",
        meta = (ClampMin = "1.0", Units = "cm",
            EditCondition = "bStrikeOnApproach && AfterPass == EInfinityLightAfterPass::Decay"))
    double DecayDistanceCm = 1500.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move")
    bool bSlowMove = false;

    /** Side-to-side sweep either way of the authored aim. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move",
        meta = (ClampMin = "0.0", ClampMax = "45.0", Units = "deg", EditCondition = "bSlowMove"))
    float PanAmplitudeDegrees = 6.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move",
        meta = (ClampMin = "0.0", ClampMax = "45.0", Units = "deg", EditCondition = "bSlowMove"))
    float TiltAmplitudeDegrees = 3.0f;

    /** One full sweep. Tilt runs a quarter cycle behind pan, so the pool drifts
     * round an ellipse instead of wiping back and forth. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move",
        meta = (ClampMin = "1.0", Units = "s", EditCondition = "bSlowMove"))
    float PeriodSeconds = 14.0f;

    /** Each lamp takes its own starting phase from its identity, so a row of
     * lamps never sweeps in unison. Off, every lamp starts at Phase Cycles. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move",
        meta = (EditCondition = "bSlowMove"))
    bool bPhaseFromIdentity = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Slow Move",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bSlowMove"))
    float PhaseCycles = 0.0f;

    /** Brief bursts keyed to camera distance, like a strike, so a scrub replays them
     * exactly. Each entry fires once; between them the lamp rests at Flash Rest Scale
     * (zero switches it off, costing no shadow map). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Flash")
    bool bFlash = false;

    /** Where the camera is, relative to this lamp along the route, at each flash's
     * peak. Negative fires while the camera is still approaching, so a lamp deep in
     * a bay can flash for a camera two bays away, and one lamp can blink many times. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Flash",
        meta = (EditCondition = "bFlash"))
    TArray<float> FlashCameraOffsetsCm;

    /** Camera travel from dark to peak. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Flash",
        meta = (ClampMin = "0.1", Units = "cm", EditCondition = "bFlash"))
    float FlashAttackCm = 3.0f;

    /** Camera travel from peak to dark. The fall is cubic, so most of the light is
     * gone in the first fifth of it, as a flash tube's is. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Flash",
        meta = (ClampMin = "0.1", Units = "cm", EditCondition = "bFlash"))
    float FlashDecayCm = 18.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama|Flash",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bFlash"))
    float FlashRestScale = 0.0f;
};

/** What drama does to a lamp at one moment: a brightness scale on the authored
 * intensity and an aim offset in the lamp's own frame. */
struct INFINITYSTAGE_API FInfinityLightDramaPose
{
    float IntensityScale = 1.0f;
    FRotator AimOffset = FRotator::ZeroRotator;
};

namespace InfinityStageLightDrama
{
/** False for the default: no strike, no move. Callers skip such lamps entirely. */
INFINITYSTAGE_API bool IsActive(const FInfinityStageLightDrama& Drama);

/**
 * Pure and deterministic: the same inputs give the same pose on every pass,
 * forwards, backwards or scrubbed.
 *
 * @param Identity            Stable per lamp (the attachment GUID); seeds stutter and phase.
 * @param LampRouteDistanceCm The lamp's position along the route.
 * @param CameraRouteDistanceCm The evaluated camera's position along the same route.
 * @param ShowSeconds         The Show's master clock, for slow moves.
 */
INFINITYSTAGE_API FInfinityLightDramaPose Evaluate(
    const FInfinityStageLightDrama& Drama,
    const FGuid& Identity,
    double LampRouteDistanceCm,
    double CameraRouteDistanceCm,
    double ShowSeconds);

/**
 * Applies a pose to a placed lamp: authored intensity times the scale, switched
 * off when the scale reaches zero, and the authored aim turned by the offset.
 *
 * Callers must only do this in game worlds. In the editor the lamp must keep
 * showing authored values, because editing a lamp captures its live settings and
 * aim back into the Show, and a modulated value would be written as authored.
 */
INFINITYSTAGE_API void ApplyToLamp(
    AActor& Lamp,
    const FInfinityStageLightDrama& Drama,
    float AuthoredIntensity,
    const FTransform& AuthoredWorld,
    const FGuid& Identity,
    double LampRouteDistanceCm,
    double CameraRouteDistanceCm,
    double ShowSeconds);
}
