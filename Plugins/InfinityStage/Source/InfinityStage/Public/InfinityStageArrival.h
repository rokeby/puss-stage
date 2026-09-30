#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Misc/FrameRate.h"
#include "Misc/FrameTime.h"
#include "InfinityStageArrival.generated.h"

class ULevelSequence;
class UInfinityStageShowAsset;
class UMovieScene;
class UMovieSceneSubSection;
class USceneComponent;

/**
 * One float channel the Arrival reads before its Scene starts. The target is either a
 * light component (Intensity) or a post-process volume (BlendWeight).
 *
 * Patch P authoring contract (30 Sep 2026): LS_S4_HangarRise currently keys the
 * practicals/glow and exposure from 0 to W1, where W0 is approximately -5.874 s
 * (the P04 cloth release) and W1 is approximately +4.126 s (the cloth section end),
 * as recorded in Saved/CodexStructure/p04_backcloth_section_record.json. After this
 * patch is built, Rig & atmosphere re-keys those tracks from W0 to W1 and authors the
 * S4 Arrival's 14 practical, 24 glow and one exposure-volume drives. This struct does
 * not perform either authoring step.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityArrivalFloatDrive
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    TSoftObjectPtr<UObject> Target;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    FGuid BindingGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    FName PropertyName;
};

/**
 * Starts a Scene's opening motion before the Scene does: while the Master is still in
 * the Passage that arrives there (Scene 4's hangar rises as the camera walks through
 * the falling backcloth).
 *
 * One motion sequence, no handover. The motion is keyed on bindings in the sequence
 * the Scene plays as a sub-section, and its keys may sit at NEGATIVE time.
 * Sequencer evaluates it from the Scene's first frame on; before that, this actor maps
 * Master time through the same sub-section placement (play rate, offsets, tick
 * resolutions) to a negative motion time and evaluates the same channels there. Both
 * sides read one channel at continuous times, so position and velocity match at any
 * speed dial. Like the celestial rig it has no clock of its own: it is a pure function
 * of the Master frame, evaluated from the Passage track, so scrubbing, reversing and
 * jumping are safe, and every Passage frame before the window re-asserts the rest pose.
 */
UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageArrival : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageArrival();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Arrival")
    TObjectPtr<USceneComponent> SceneRoot;

    /** The Scene cue whose sequence continues the motion from its first frame. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    FGuid SceneCueGuid;

    /** The sequence the Scene plays as a sub-section (Scene 4: LS_S4_HangarRise). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    TSoftObjectPtr<ULevelSequence> MotionSequence;

    /** The possessable in MotionSequence whose 3D transform rotation drives DrivenActor. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    FGuid MotionBindingGuid;

    /** The actor whose relative rotation is set before the Scene starts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    TObjectPtr<AActor> DrivenActor;

    /** Sets DrivenActor's relative rotation for a Master time before the Scene starts.
     * Returns false, touching nothing, at or after the Scene's first frame (Sequencer
     * owns it there) or when any link is missing. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Arrival")
    bool EvaluateAtMasterFrame(const UInfinityStageShowAsset* Show, FFrameTime MasterTime);

    /** The rotation EvaluateAtMasterFrame would set, with no side effects. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Arrival")
    bool ResolveRotationAtMasterFrame(const UInfinityStageShowAsset* Show, FFrameTime MasterTime, FRotator& OutRotation) const;

    /** A cloth that falls as the motion begins (Scene 4: the Passage's backcloth), placed as its
     * own GeometryCache actor. Its timeline is a GeometryCache section in MotionSequence, which
     * may start at negative time: this actor plays it before the Scene, Sequencer after, so the
     * fall finishes inside the Scene instead of freezing at the boundary. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    TSoftObjectPtr<AActor> BackclothActor;

    /** The possessable in MotionSequence whose GeometryCache track holds the cloth's section. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    FGuid BackclothBindingGuid;

    /** Float channels shared with the Scene sequence for pre-cut light/exposure motion.
     * Resolution is side-effect-free in every world, but EvaluateAtMasterFrame writes
     * these targets only in game worlds: editor Sequencer evaluation must never persist
     * a previewed intensity or BlendWeight in a later level save. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Arrival")
    TArray<FInfinityArrivalFloatDrive> PreSceneFloatDrives;

    /** The cache time EvaluateAtMasterFrame would play on the backcloth, with no side effects:
     * the engine's own section mapping (MapTimeToAnimation) at the negative motion time, so
     * sample 0 before the section and the last sample after it. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Arrival")
    bool ResolveBackclothTimeAtMasterFrame(
        const UInfinityStageShowAsset* Show,
        FFrameTime MasterTime,
        float CacheDurationSeconds,
        float& OutCacheSeconds) const;

    /** A pre-Scene drive's float-channel value at the mapped motion time, with no side effects.
     * Returns false at or after the Scene's first frame or when the indexed drive cannot resolve. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Arrival")
    bool ResolveFloatDriveAtMasterFrame(
        const UInfinityStageShowAsset* Show,
        FFrameTime MasterTime,
        int32 DriveIndex,
        float& OutValue) const;

    /**
     * A time in the parent (Scene) sequence, in its tick resolution, mapped to the
     * sub-section's inner (motion) sequence exactly as the sub-section places it:
     * inner playback start + StartFrameOffset + (outer - section start) x play rate,
     * across the two tick resolutions. Linear, so it extends before the section start.
     * False if the section's time scale is not a fixed play rate.
     */
    static bool MapOuterToInnerTime(
        const UMovieSceneSubSection& Section,
        FFrameRate OuterTickResolution,
        FFrameTime OuterTime,
        FFrameTime& OutInnerTime);

protected:
    virtual void BeginPlay() override;

private:
    /** Master time -> the motion sequence's own time (negative before the Scene). False at or
     * after the Scene's first frame, or when any link is missing. */
    bool ResolveMotionTime(
        const UInfinityStageShowAsset* Show,
        FFrameTime MasterTime,
        FFrameTime& OutMotionTime,
        const UMovieScene*& OutMotionScene) const;

    /** Evaluate one configured float drive after the shared Master-to-motion mapping is known. */
    bool EvaluateFloatDriveAtMotionTime(
        const UMovieScene& MotionScene,
        FFrameTime MotionTime,
        int32 DriveIndex,
        float& OutValue) const;

    /** One warning per failure reason, not one per evaluated frame. */
    void WarnOnce(const TCHAR* Reason, const FString& Detail) const;

    mutable TSet<FString> WarnedReasons;
    bool bLoggedBackcloth = false;
};
