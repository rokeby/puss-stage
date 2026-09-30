#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Misc/FrameRate.h"
#include "Misc/FrameTime.h"
#include "InfinityStageArrival.generated.h"

class ULevelSequence;
class UInfinityStageShowAsset;
class UMovieSceneSubSection;
class USceneComponent;

/**
 * Starts a Scene's opening motion before the Scene does: while the Master is still in
 * the Passage that arrives there (Scene 4's hangar rises as the camera walks through
 * the falling backcloth).
 *
 * One curve, two evaluators, no handover. The motion is keyed on a binding in the
 * sequence the Scene plays as a sub-section, and its keys may sit at NEGATIVE time.
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

private:
    /** One warning per failure reason, not one per evaluated frame. */
    void WarnOnce(const TCHAR* Reason, const FString& Detail) const;

    mutable TSet<FString> WarnedReasons;
};
