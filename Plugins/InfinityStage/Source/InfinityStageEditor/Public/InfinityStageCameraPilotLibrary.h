#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "InfinityStageCameraPilotLibrary.generated.h"

class AInfinityStageCameraRig;
class UInfinityStageShowAsset;
class UMovieSceneInfinityPassageSection;
class USplineComponent;
class UWorld;

/**
 * What a Passage camera pose is measured from at one Master frame.
 *
 * The Passage camera's authority is the managed Passage section of the Master
 * Level Sequence, not the Show asset: the Show owns cue content and
 * attachments, the Master owns time and camera. The anchor is the route frame
 * at the section's evaluated (speed-warped) distance; the pose channels are
 * offsets from it.
 */
struct INFINITYSTAGEEDITOR_API FInfinityCameraPilotAnchor
{
    AInfinityStageCameraRig* Rig = nullptr;
    UMovieSceneInfinityPassageSection* Section = nullptr;
    FFrameNumber MasterFrame = 0;
    FFrameNumber PassageStartFrame = 0;
    FFrameNumber PassageEndFrame = 0;
    double RouteDistanceCm = 0.0;
    double LookAheadDistanceCm = 0.0;
    FVector CurrentLocalOffsetCm = FVector::ZeroVector;
    FRotator CurrentLocalRotation = FRotator::ZeroRotator;
    double CurrentFocalLengthMm = 35.0;
    double CurrentFocusDistanceCm = 100000.0;
};

/** Pose channel values that reproduce one camera view at one Master frame. */
struct INFINITYSTAGEEDITOR_API FInfinityCameraPilotSolution
{
    FVector LocalOffsetCm = FVector::ZeroVector;
    FRotator LocalRotation = FRotator::ZeroRotator;
    /** The rig-root pose solved for: the camera view with the Camera component's relative offset removed. */
    FTransform RigWorldTransform = FTransform::Identity;
};

/** Optional lens values keyed together with a pose. */
struct INFINITYSTAGEEDITOR_API FInfinityCameraPilotLens
{
    double FocalLengthMm = 35.0;
    double FocusDistanceCm = 100000.0;
};

/**
 * Camera piloting write-back (H.9): turns a camera view chosen by looking into
 * keys on the Passage camera channels, and proves the result by reading it back
 * through the rig's own evaluation.
 *
 * The Blueprint/Python functions act on the open editor world. The C++ entry
 * points take the world explicitly so tests can run in a preview world.
 */
UCLASS()
class INFINITYSTAGEEDITOR_API UInfinityStageCameraPilotLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /**
     * Keys the six pose channels (and optionally focal length and focus) at one
     * Master frame so the Passage camera sees exactly CameraWorldTransform there.
     * The keys are verified through the rig's evaluation and restored if the
     * read-back misses by more than 0.01 cm or 0.01 degrees. Writes the Master
     * sequence only; never the Show.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Camera Pilot")
    static bool KeyPassageCameraPose(
        UInfinityStageShowAsset* Show,
        FGuid PassageGuid,
        int32 MasterFrame,
        FTransform CameraWorldTransform,
        bool bKeyLens,
        float FocalLengthMm,
        float FocusDistanceCm,
        FString& OutReport);

    /**
     * Dry run of KeyPassageCameraPose: the channel values it would key, beside
     * the values the channels hold now. Solving the authored view must return
     * the current values, which checks the solve against a real route without
     * writing anything.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Camera Pilot")
    static bool SolvePassageCameraPose(
        UInfinityStageShowAsset* Show,
        FGuid PassageGuid,
        int32 MasterFrame,
        FTransform CameraWorldTransform,
        FVector& OutLocalOffsetCm,
        FRotator& OutLocalRotation,
        FVector& OutCurrentLocalOffsetCm,
        FRotator& OutCurrentLocalRotation,
        FString& OutReport);

    /**
     * Re-takes the handoff cameras of exactly the named Scenes from the current
     * Passage endpoints (the Cue Desk's Match, made scriptable). Writes the level
     * and those Scenes' sequences, undoably, and saves nothing.
     *
     * Deliberately narrow: the engine-side Match treats an empty list as "every
     * Scene", so this refuses an empty list, requires ExpectedSceneCount to equal
     * the number of GUIDs passed, and requires each to be an enabled Scene cue.
     * Nothing can be matched wide by passing nothing. The report gives the named
     * Scenes' staleness before and after.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Camera Pilot")
    static bool MatchNamedSceneHandoffs(
        UInfinityStageShowAsset* Show,
        const TArray<FGuid>& SceneCueGuids,
        int32 ExpectedSceneCount,
        FString& OutReport);

    /**
     * The Cue Desk's "Link / Reimport Music Analysis", made scriptable. Imports
     * every Passage analysis in Saved/InfinityStage/MusicAnalysis into its
     * MM_Pxx_Analysis map, relinks the Show's music rails, and saves those maps
     * and the Show (the importer saves them itself). Cue timing is not changed,
     * and marker and tempo Confirmed/Suggested states are kept. Refuses during
     * PIE.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Music")
    static bool ImportMusicAnalysis(UInfinityStageShowAsset* Show, FString& OutReport);

    /** The compiled Master-frame range of one Passage, lead-in and tail included. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Camera Pilot")
    static bool GetPassageFrameRange(
        UInfinityStageShowAsset* Show,
        FGuid PassageGuid,
        int32& OutStartFrame,
        int32& OutEndFrame);

    /** Read-back: the authored camera view at one Master frame, as the rig evaluates it (no gait bob). */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Camera Pilot")
    static bool GetPassageCameraPose(
        UInfinityStageShowAsset* Show,
        FGuid PassageGuid,
        int32 MasterFrame,
        FTransform& OutCameraWorldTransform,
        float& OutFocalLengthMm,
        float& OutFocusDistanceCm);

    static AInfinityStageCameraRig* FindCameraRig(
        UWorld& World,
        const UInfinityStageShowAsset& Show,
        const FGuid& PassageGuid);

    static UMovieSceneInfinityPassageSection* FindPassageSection(
        const UInfinityStageShowAsset& Show,
        const FGuid& PassageGuid);

    static bool ResolveAnchor(
        UWorld& World,
        const UInfinityStageShowAsset& Show,
        const FGuid& PassageGuid,
        FFrameNumber MasterFrame,
        FInfinityCameraPilotAnchor& OutAnchor,
        FString& OutError);

    /**
     * Exact inverse of the rig's route placement: position first, because with
     * Route Look Ahead the base rotation depends on where the camera stands.
     * Euler angles are unwound to the nearest equivalent of ReferenceRotation so
     * a new key never introduces a 360-degree spin between neighbouring keys.
     */
    static void SolveRigPose(
        const USplineComponent& Route,
        double RouteDistanceCm,
        const FVector& CameraOffset,
        double LookAheadDistanceCm,
        const FTransform& DesiredRigWorld,
        const FRotator& ReferenceRotation,
        FVector& OutLocalOffsetCm,
        FRotator& OutLocalRotation);

    static bool Solve(
        const FInfinityCameraPilotAnchor& Anchor,
        const FTransform& CameraWorldTransform,
        FInfinityCameraPilotSolution& OutSolution,
        FString& OutError);

    static bool KeyPose(
        UWorld& World,
        UInfinityStageShowAsset& Show,
        const FGuid& PassageGuid,
        FFrameNumber MasterFrame,
        const FTransform& CameraWorldTransform,
        const FInfinityCameraPilotLens* Lens,
        FString& OutReport);

    /** The rig's authored camera view (Camera component, not rig root) at one Master frame. */
    static bool GetCameraView(
        const AInfinityStageCameraRig& Rig,
        FFrameNumber MasterFrame,
        FTransform& OutCameraWorldTransform,
        float& OutFocalLengthMm,
        float& OutFocusDistanceCm);
};
