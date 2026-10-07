#pragma once

#include "CoreMinimal.h"
#include "UObject/SoftObjectPtr.h"
#include "InfinityStageMechanismSound.generated.h"

class USoundAttenuation;
class USoundBase;

/**
 * Wing mechanism sound cues (Gary, 7 Oct): wings make sound as they move,
 * including a slam when a toppling wing hits the floor or a neighbour.
 *
 * A cue is placed on the mechanism's own PHASE (0..1 of the OneShot, or of each
 * cycle of a loop), never at an absolute Master time. The phase is already a
 * function of the pair's PhaseOrigin, rate and offset, so any re-time that moves
 * the motion moves its sounds with it, the same rule as attachments.
 *
 * Runtime (AInfinityStagePassageActor::EvaluateMechanismsInternal), game/PIE
 * worlds only: a cue fires when the phase crosses it going forward during real
 * playback. A scrub, a jump, a rewind or a fast-forward step crosses nothing; a
 * rewind re-arms the cue because the stored phase moves back with it. Empty
 * SoundCues (the default) leave every existing pair silent and unchanged.
 */
UENUM(BlueprintType)
enum class EInfinityMechanismSoundCueSide : uint8
{
    /** One sound for the pair, placed at its spline station. */
    Pair,
    Left,
    Right,
    Top
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMechanismSoundCue
{
    GENERATED_BODY()

    /** For authoring and logs only, e.g. "slam_floor" or "domino_hit". */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    FName Label;

    /** Where in the motion the sound starts: 0..1 of the OneShot, or of every
     * cycle of a loop. Fires when the phase passes it going forward, so a cue at
     * exactly 0 can never fire on a OneShot (the phase starts there). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double Phase = 0.5;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    EInfinityMechanismSoundCueSide Side = EInfinityMechanismSoundCueSide::Pair;

    /** Empty = this cue is a no-op. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    TSoftObjectPtr<USoundBase> Sound;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.0", ClampMax = "4.0"))
    float VolumeMultiplier = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.1", ClampMax = "4.0"))
    float PitchMultiplier = 1.0f;

    /** Offset of the sound from the panel's evaluated pose, in the panel's own
     * frame (e.g. its top edge, which is what hits the floor). For Side = Pair it
     * is in the station's frame. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound", meta = (Units = "cm"))
    FVector LocalOffsetCm = FVector::ZeroVector;

    /** Optional. Empty = a spherical falloff over the Passage set's Audible
     * Radius, so the sound is always spatialised at the panel. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    TSoftObjectPtr<USoundAttenuation> AttenuationOverride;
};

namespace InfinityStageMechanismSound
{
/**
 * True when the step from the last evaluation to this one is real forward
 * playback: Show time advanced, by no more than MaxRateRatio times the real
 * (world) time that passed plus one 60 Hz frame of slack, and by no more than
 * MaxStepSeconds. Paused (0), rewind (<0), a jump, a scrub or the 4x hold-right
 * fast-forward all return false, so they cross nothing.
 */
INFINITYSTAGE_API bool IsForwardPlaybackStep(
    double ShowDeltaSeconds,
    double RealElapsedSeconds,
    double MaxRateRatio,
    double MaxStepSeconds);

/**
 * True when the phase passed CuePhase going forward: Prev < CuePhase <= Curr.
 * With bLooping the phases are UNWRAPPED (cycles count up past 1) and the cue
 * repeats every cycle: true when some integer k has Prev < k + CuePhase <= Curr.
 * Curr <= Prev is never a crossing.
 */
INFINITYSTAGE_API bool CrossesForward(double PrevPhase, double CurrPhase, double CuePhase, bool bLooping);

/** Strictly upward through the threshold, by magnitude: |Prev| < T <= |Curr|. */
INFINITYSTAGE_API bool CrossesThresholdUpward(double PrevTravel, double CurrTravel, double Threshold);

/**
 * Indices of the cues for this side that this forward phase step fires, in
 * authored order. Nothing when the pair is muted, the Passage mutes its cues,
 * or the cue has no sound. The caller decides whether the step is forward
 * playback (IsForwardPlaybackStep) before calling.
 */
INFINITYSTAGE_API void CollectCrossedCues(
    const TArray<FInfinityMechanismSoundCue>& Cues,
    EInfinityMechanismSoundCueSide Side,
    double PrevPhase,
    double CurrPhase,
    bool bLooping,
    bool bMuted,
    TArray<int32>& OutIndices);
}
