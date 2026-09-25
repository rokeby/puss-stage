#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageCurtainRig.generated.h"

class USceneComponent;
class UStaticMeshComponent;

/**
 * Camera-relative curtain anchor intended to be spawned by Level Sequence.
 *
 * Blueprint subclasses can attach arbitrary geometry, cloth, materials,
 * lights, VFX and audio beneath CurtainMotionRoot. The supplied static mesh
 * remains as a backwards-compatible starting point, but is not the rig
 * contract. Sequencer can key CurtainProgress while the actor follows the
 * evaluated player camera in PIE/runtime.
 */
UCLASS(BlueprintType, Blueprintable)
class INFINITYSTAGE_API AInfinityStageCurtainRig : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageCurtainRig();

    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Curtain")
    TObjectPtr<USceneComponent> CurtainRoot;

    /** Attach all authored show-system components beneath this moving root. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Curtain")
    TObjectPtr<USceneComponent> CurtainMotionRoot;

    /** Correct production fire-safety curtain supplied as an editable static-mesh component. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Curtain|Geometry")
    TObjectPtr<UStaticMeshComponent> CurtainMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement")
    bool bFollowPlayerCamera = true;

    /** Distance from the evaluated player camera to the curtain plane. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement", meta = (ClampMin = "10.0", Units = "cm"))
    float CurtainDistanceCm = 500.0f;

    /** Additional camera-local translation after CurtainDistanceCm. X is
     * forward/back, Y is lateral, and Z is vertical. Editable per spawnable. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Curtain|Placement", meta = (Units = "cm"))
    FVector CurtainViewLocalOffsetCm = FVector::ZeroVector;

    /** Camera-relative pitch/yaw/roll used to tune the curtain plane without
     * giving up camera following. Editable per Level Sequence spawnable. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Curtain|Placement")
    FRotator CurtainViewRotationOffset = FRotator::ZeroRotator;

    /** Camera-local height of the curtain centre when fully open. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (Units = "cm"))
    float CurtainOpenCenterOffsetCm = 700.0f;

    /** Camera-local height of the curtain centre when fully closed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (Units = "cm"))
    float CurtainClosedCenterOffsetCm = 0.0f;

    /** Optional asset-pivot compensation applied below CurtainMotionRoot. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement", meta = (Units = "cm"))
    float CurtainMeshCenterZCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (ClampMin = "0.01"))
    float CurtainUniformScale = 1.1f;

    /** Use full Blueprint-authored relative transforms instead of the legacy scalar placement. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement")
    bool bUseAuthoredOpenClosedTransforms = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement",
        meta = (EditCondition = "bUseAuthoredOpenClosedTransforms", MakeEditWidget))
    FTransform CurtainOpenRelativeTransform = FTransform(
        FRotator::ZeroRotator,
        FVector(0.0, 0.0, 700.0),
        FVector(1.1));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain|Placement",
        meta = (EditCondition = "bUseAuthoredOpenClosedTransforms", MakeEditWidget))
    FTransform CurtainClosedRelativeTransform = FTransform(
        FRotator::ZeroRotator,
        FVector::ZeroVector,
        FVector(1.1));

    /** Zero is open/above frame; one is fully lowered. Key this in Sequencer. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Curtain")
    float CurtainProgress = 0.0f;

    /** Legacy global evaluation toggles this; sequence spawnables normally leave it enabled. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Curtain")
    bool bCurtainActive = false;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Curtain")
    void SetCurtainState(float InProgress, bool bInActive);

protected:
    virtual void BeginPlay() override;
    virtual void OnConstruction(const FTransform& Transform) override;
    virtual bool ShouldTickIfViewportsOnly() const override;

private:
    void ApplyCurtainPresentation();
    void RefreshFromPlayerView();
};
