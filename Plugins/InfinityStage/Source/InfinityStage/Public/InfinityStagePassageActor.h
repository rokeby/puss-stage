#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStagePassageActor.generated.h"

class UInfinityStageShowAsset;
struct FInfinityStageLightSettings;
class UInstancedStaticMeshComponent;
class USceneComponent;
class USplineComponent;

UENUM(BlueprintType)
enum class EInfinityPanelSide : uint8
{
    Left,
    Right,
    Top
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMaterializedPanelRef
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    FGuid CueGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    EInfinityPanelSide Side = EInfinityPanelSide::Left;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    TObjectPtr<UInstancedStaticMeshComponent> Component = nullptr;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 InstanceIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    FTransform BaseWorldTransform = FTransform::Identity;

    /**
     * World-space direction in which this panel travels toward the centre of its
     * Wing Pair. This is deliberately derived from the pair/station frame rather
     * than the mesh-facing transform, so asset orientation corrections cannot
     * reverse the mechanism motion.
     */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    FVector InwardWorldDirection = FVector::ZeroVector;

    /** Mesh-local pivot location and +X rotation axis cached at materialization.
     * Topple uses Hinge (or the bounds bottom centre); Turn uses Pivot (or the
     * bounds centre and local +Z). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    FTransform MechanismPivotLocal = FTransform::Identity;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStagePassageActor : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStagePassageActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USplineComponent> Route;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<UInfinityStageShowAsset> ShowAsset;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FGuid PassageGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    bool bAutoFitStraightRoute = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage", meta = (ClampMin = "1", ClampMax = "1024"))
    int32 ComponentBudget = 256;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Materialization")
    TArray<TObjectPtr<UInstancedStaticMeshComponent>> ManagedComponents;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    TArray<FInfinityMaterializedPanelRef> MaterializedPanels;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 MaterializedWingPairCount = 0;

    /**
     * Actors spawned for cue attachments, owned by this Passage.
     *
     * Kept as one ownership story with the wings: whatever materialization
     * creates, materialization destroys. Otherwise a re-fit would leave orphaned
     * lights and props in the level for the artist to find and tidy by hand.
     */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    TArray<TObjectPtr<AActor>> ManagedAttachmentActors;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool MaterializePassage();

    /** Details-panel button wrapper. Unreal editor buttons require a void,
     * parameterless CallInEditor function; MaterializePassage retains its bool
     * result for C++, Blueprint and automated callers. */
    UFUNCTION(CallInEditor, Category = "Infinity Stage", meta = (DisplayName = "Materialize Passage"))
    void MaterializePassageInEditor();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Infinity Stage")
    void ClearMaterializedPassage();

    /**
     * Compiled distance this Passage needs from its route, and the route's
     * current length. Materialization refuses a route shorter than the compiled
     * distance, so this is the check that turns that late failure into a warning.
     */
    /**
     * World transform for a cue-anchored attachment at the current evaluated state.
     *
     * Station-anchored attachments sit at the pair's spline station; panel-anchored
     * ones ride that panel, including its inward travel, so a light bolted to a
     * moving wing moves with it. Because the anchor is a cue identity and the
     * offset is relative, re-spacing or re-timing the Show re-places the
     * attachment instead of orphaning it.
     */
    /**
     * Which sound in the Passage's set voices a given Wing Pair.
     *
     * Deterministic by design: the same wing must make the same sound on every
     * replay, or reverse and scrub would fight the audio. Returns INDEX_NONE
     * when the set is empty, disabled, or this pair is muted.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Content")
    int32 GetMechanismSoundIndexForCue(FGuid CueGuid) const;

    /** Spawns or re-places every enabled attachment on this Passage's cues.
     * Returns how many were placed; broken references warn and are skipped. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Content")
    int32 MaterializeAttachments();

    /** The anchor an attachment is measured from, without its relative offset.
     * Editing writes back against this, so a dragged light keeps its offset. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Content")
    bool GetAttachmentAnchorWorldTransform(
        FGuid CueGuid,
        FGuid AttachmentGuid,
        FTransform& OutAnchorWorld) const;

    /** Which cue/attachment a spawned actor belongs to, if any. */
    bool FindAttachmentByActor(const AActor* Actor, FGuid& OutCueGuid, FGuid& OutAttachmentGuid) const;

    /** The inverse of materialization's light setup: reads a placed light actor's
     * component back into Show settings so Details-panel edits become authored
     * values. Returns false when the actor carries no Light Component. */
    static bool CaptureAttachmentLightSettings(const AActor& Actor, FInfinityStageLightSettings& OutSettings);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Content")
    bool GetAttachmentWorldTransform(
        FGuid CueGuid,
        FGuid AttachmentGuid,
        FTransform& OutWorldTransform) const;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool GetRouteLengthStatus(double& OutRequiredCm, double& OutCurrentCm) const;

    /**
     * Extends the tail of the route along its final tangent until it covers the
     * compiled distance. Wings occupy the route from zero forward, so only the
     * unpopulated tail changes. Returns false when no extension was needed or
     * possible.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool ExtendRouteToCompiledLength();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool EvaluateMechanismsAtMasterFrame(FFrameNumber MasterFrame);

    /** Camera-rig path: the same absolute frame plus the fully evaluated rail/spline distance. */
    bool EvaluateMechanismsAtCameraDistance(FFrameNumber MasterFrame, double CameraDistanceCm);

    /** Resolves the stable Cue to its spline station and occurrence-root world transforms. */
    bool GetCuePlacementTransforms(FGuid CueGuid, FTransform& OutStationWorld, FTransform& OutPairWorld) const;

private:
    bool EvaluateMechanismsInternal(FFrameNumber MasterFrame, TOptional<double> CameraDistanceCm);

    bool AddPanelInstance(
        const FGuid& CueGuid,
        EInfinityPanelSide Side,
        const struct FInfinityPanelDesign& Panel,
        const FTransform& OccurrenceOffset,
        const FTransform& StationTransform,
        TMap<FString, UInstancedStaticMeshComponent*>& ComponentsByKey,
        FString& OutError);
};
