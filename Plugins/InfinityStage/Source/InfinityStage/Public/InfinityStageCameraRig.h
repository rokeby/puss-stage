#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageCameraRig.generated.h"

class ACineCameraActor;
class AInfinityStagePassageActor;
class UChildActorComponent;
class UCineCameraComponent;
class USceneComponent;
class UInfinityStageShadowCatComponent;
struct FInfinityCompiledPassage;
struct FInfinityPassageCameraEvaluation;

UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageCameraRig : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageCameraRig();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<UCineCameraComponent> Camera;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> ShadowFigureRoot;

    /** Mesh-only AnimX cat carried by the camera-relative shadow root. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Shadow Cat")
    TObjectPtr<UInfinityStageShadowCatComponent> ShadowCat;

    /**
     * Travelling light behind the camera.
     *
     * Attached to the rig root, so it follows the route without any evaluation
     * of its own. Placed behind the shadow figure and pointing forward, it
     * throws the cat's shadow into the stage ahead of the camera.
     */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Follow Light")
    TObjectPtr<class USpotLightComponent> FollowLight;

    /** Off by default so existing levels light exactly as before. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light")
    bool bEnableFollowLight = false;

    /** Offset from the rig, in route space. Negative X sits behind the camera. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light", meta = (Units = "cm"))
    FVector FollowLightOffset = FVector(-600.0, 0.0, 250.0);

    /** Aim relative to the rig. Default looks slightly down the route ahead. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light")
    FRotator FollowLightRotation = FRotator(-8.0, 0.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<AInfinityStagePassageActor> PassageActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage", meta = (Units = "cm"))
    FVector CameraOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage", meta = (Units = "cm"))
    FVector ShadowFigureOffset = FVector(-200.0, 0.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    bool bKeepShadowFiguresWorldUpright = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat")
    bool bEnableShadowCat = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatCastShadow = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatRenderInMainPass = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatVisibleInReflections = true;

    /** Extra placement controls exposed on the parent passage camera instance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (Units = "cm"))
    FVector ShadowCatPositionOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement")
    FRotator ShadowCatRotationOffset = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (ClampMin = "0.01", UIMin = "0.1", UIMax = "5.0"))
    double ShadowCatUniformScale = 1.0;

    /** Retained for existing serialized instances; use the direct placement controls for routine adjustment. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (AdvancedDisplay, DisplayName = "Advanced Relative Transform"))
    FTransform ShadowCatRelativeTransform = FTransform::Identity;

    /** Keep AnimX in its walk gait even when the camera moves faster than a cat would walk. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation")
    bool bShadowCatForceWalk = true;

    /**
     * Play AnimX's authored forward-walk sequence directly. This bypasses the
     * vendor locomotion Blueprint, which can promote camera speeds to trot/run.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation")
    bool bShadowCatUseDirectWalkAnimation = true;

    /** Retained for compatibility with existing saved rig settings. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "1.0", Units = "cm/s"))
    double ShadowCatWalkBlendSpeedCmPerSecond = 120.0;

    /** Camera speed that plays the AnimX walk cycle at 1.0x. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "1.0", Units = "cm/s"))
    double ShadowCatReferenceWalkSpeedCmPerSecond = 250.0;

    /** Fine adjustment applied after converting camera speed to animation play rate. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0", UIMax = "2.0"))
    double ShadowCatAnimationSpeedMultiplier = 0.6;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0"))
    double ShadowCatMinPlayRate = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0"))
    double ShadowCatMaxPlayRate = 1.25;

    /**
     * Lift the camera with the cat's gait. The vertical travel of the reference
     * bone against its rest pose, in world centimetres after the cat's scale, is
     * added to the evaluated camera height. The cat itself is counter-offset so
     * its feet stay on the floor. Zero gain disables the effect without losing
     * the settings.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob")
    bool bShadowCatCameraBob = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (ClampMin = "0.0", UIMax = "3.0", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatCameraBobGain = 1.0;

    /** Small roll coupled to the lift so the bob reads as a body, not an elevator. Degrees per centimetre of lift. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (UIMin = "-1.0", UIMax = "1.0", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatCameraBobRollDegreesPerCm = 0.12;

    /** Bone whose height carries the gait. AnimX cats have no pelvis; Spine sits over the hips. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (EditCondition = "bShadowCatCameraBob"))
    FName ShadowCatBobReferenceBone = TEXT("Spine");

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat|Camera Bob", meta = (Units = "cm"))
    double CurrentShadowCatCameraBobCm = 0.0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat", meta = (Units = "cm/s"))
    double CurrentShadowCatCameraSpeedCmPerSecond = 0.0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat")
    double CurrentShadowCatPlayRate = 0.0;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool EvaluateAtMasterFrame(FFrameNumber MasterFrame);

    virtual void OnConstruction(const FTransform& Transform) override;

    /** Applies the follow-light properties to its component. */
    void ConfigureFollowLight();

    /** Samples the camera transform without changing the Actor or mechanism state. */
    bool GetCameraTransformAtMasterFrame(FFrameNumber MasterFrame, FTransform& OutWorldTransform) const;

    /** Pure endpoint sample used by Scene handoff generation, including managed lens channels. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Camera")
    bool GetCameraViewAtMasterFrame(
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        float& OutFocalLengthMm,
        float& OutFocusDistanceCm) const;

protected:
    virtual void BeginPlay() override;

private:
    FTransform BuildShadowCatRelativeTransform() const;
    void ConfigureShadowCat();
    void DestroyOrphanedShadowCats();
    void UpdateShadowCatAtMasterFrame(
        FFrameNumber MasterFrame,
        const FTransform& CameraTransform,
        const FInfinityCompiledPassage& Passage);
    double CalculateCameraSpeedAtMasterFrame(
        FFrameNumber MasterFrame,
        const FTransform& CameraTransform,
        const FInfinityCompiledPassage& Passage) const;

    /** Current gait lift of the reference bone over its rest pose, in world cm, scaled by the bob gain. */
    double SampleShadowCatGaitLiftCm() const;

    bool bShadowCatBobReported = false;

    bool GetCameraStateAtMasterFrame(
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        FInfinityPassageCameraEvaluation& OutEvaluation) const;

    /** As GetCameraStateAtMasterFrame, against a Passage the caller has already compiled. */
    bool GetCameraStateForCompiledPassage(
        const FInfinityCompiledPassage& Passage,
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        FInfinityPassageCameraEvaluation& OutEvaluation) const;
};
