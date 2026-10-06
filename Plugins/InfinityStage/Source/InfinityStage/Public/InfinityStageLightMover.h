#pragma once

#include "CoreMinimal.h"
#include "InfinityStageLightMover.generated.h"

/**
 * Club "mover" spots (Gary, P05): spot lights that start focused on the ground
 * and then "go a bit haywire", with their own repetitive, quite rapid, jolting
 * rotation routine.
 *
 * A Light attachment option (FInfinityCueAttachment::Mover). The routine is a
 * deterministic sequence of seeded yaw/pitch targets, one per step: each step
 * moves to its target with a fast ease over EaseFraction of the step, then holds.
 * Amplitude starts at CalmScale at the onset and rises to full over ErraticRampCm
 * of camera travel, so it starts calm and becomes erratic. The pose is a function
 * of the Show's Master clock and the camera's route distance only, so scrubbing,
 * reversing and replaying show the same moves.
 *
 * Runs in game worlds only, in the Passage's per-frame attachment pass (after
 * Light Drama), so it survives every re-materialize (the data lives in the Show)
 * and never dirties the level at edit time. Station-anchored lamps only, like
 * Light Drama's slow move; it turns the lamp in its own frame from the authored aim.
 *
 * Python (scores tool): attachment["mover"] fields, snake_case:
 *   enabled, trigger ("ALWAYS_IN_PASSAGE" | "ON_APPROACH"), approach_distance_cm,
 *   yaw_amplitude_degrees, pitch_amplitude_degrees, steps_per_second, ease_fraction,
 *   calm_scale, erratic_ramp_cm, seed.
 */
UENUM(BlueprintType)
enum class EInfinityLightMoverTrigger : uint8
{
    /** Moving from the Passage's start (calm at route distance 0, erratic ErraticRampCm on). */
    AlwaysInPassage,
    /** Rests on its authored aim until the camera is ApproachDistanceCm from the lamp. */
    OnApproach
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityLightMoverSettings
{
    GENERATED_BODY()

    /** Off by default: existing lights are unchanged. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover")
    bool bEnabled = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover", meta = (EditCondition = "bEnabled"))
    EInfinityLightMoverTrigger Trigger = EInfinityLightMoverTrigger::OnApproach;

    /** OnApproach: how far ahead of the camera, along the route, the routine starts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.0", Units = "cm", EditCondition = "bEnabled"))
    double ApproachDistanceCm = 2500.0;

    /** Swing either side of the authored aim, at full erraticness. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.0", ClampMax = "180.0", Units = "deg", EditCondition = "bEnabled"))
    float YawAmplitudeDegrees = 35.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.0", ClampMax = "89.0", Units = "deg", EditCondition = "bEnabled"))
    float PitchAmplitudeDegrees = 20.0f;

    /** Moves per second of Master time ("quite rapid"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.1", UIMax = "12.0", EditCondition = "bEnabled"))
    float StepsPerSecond = 3.0f;

    /** Share of each step spent moving (a fast ease-out); the rest holds. Small = jolting. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.01", ClampMax = "1.0", EditCondition = "bEnabled"))
    float EaseFraction = 0.25f;

    /** Amplitude share at the onset (0 = starts still on its ground focus). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bEnabled"))
    float CalmScale = 0.15f;

    /** Camera travel after the onset over which it goes from calm to full haywire. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (ClampMin = "1.0", Units = "cm", EditCondition = "bEnabled"))
    double ErraticRampCm = 1500.0;

    /** Mixed with the attachment's identity: each mover runs its own routine. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover", meta = (EditCondition = "bEnabled"))
    int32 Seed = 0;
};

namespace InfinityStageLightMover
{
/** 0 before the onset; CalmScale at it; 1 after ErraticRampCm more travel. */
INFINITYSTAGE_API float ErraticScale(const FInfinityLightMoverSettings& Settings, double LampRouteDistanceCm, double CameraRouteDistanceCm);

/**
 * Pure and deterministic: the aim offset (pitch, yaw) in the lamp's own frame.
 * Zero when disabled or before the onset.
 */
INFINITYSTAGE_API FRotator Evaluate(
    const FInfinityLightMoverSettings& Settings,
    const FGuid& Identity,
    double LampRouteDistanceCm,
    double CameraRouteDistanceCm,
    double ShowSeconds);
}
