#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageWingEditProxy.generated.h"

class AInfinityStagePassageActor;
class UInfinityStageShowAsset;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EInfinityWingEditTarget : uint8
{
    Pair,
    Left,
    Right,
    Top
};

/** Transient editor-only gizmo proxy. It writes back to the Cue asset and never
 * becomes authoritative fixed stage content. */
UCLASS(NotPlaceable, Transient)
class INFINITYSTAGE_API AInfinityStageWingEditProxy : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageWingEditProxy();

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage Edit")
    TObjectPtr<USceneComponent> EditRoot;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage Edit")
    TObjectPtr<UStaticMeshComponent> LeftPreview;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage Edit")
    TObjectPtr<UStaticMeshComponent> RightPreview;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage Edit")
    TObjectPtr<UStaticMeshComponent> TopPreview;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage Edit")
    EInfinityWingEditTarget Target = EInfinityWingEditTarget::Pair;

    bool InitializeEdit(
        UInfinityStageShowAsset* InShow,
        AInfinityStagePassageActor* InPassageActor,
        FGuid InCueGuid,
        EInfinityWingEditTarget InTarget);

    void FinishEditing();
    void CancelEditing();

    virtual bool IsEditorOnly() const override { return true; }

#if WITH_EDITOR
    virtual void PostEditMove(bool bFinished) override;
    virtual void PostEditUndo() override;
#endif

private:
    UPROPERTY(Transient)
    TObjectPtr<UInfinityStageShowAsset> ShowAsset;

    UPROPERTY(Transient)
    TObjectPtr<AInfinityStagePassageActor> PassageActor;

    FGuid CueGuid;
    FTransform StationWorld = FTransform::Identity;
    FTransform PairWorldAtStart = FTransform::Identity;
    FTransform OriginalOccurrenceOffset = FTransform::Identity;
    FTransform OriginalLeft = FTransform::Identity;
    FTransform OriginalRight = FTransform::Identity;
    FTransform OriginalTop = FTransform::Identity;
    bool bUpdating = false;
    bool bFinished = false;

    void UpdateAssetFromActor();
    void SetOriginalInstancesHidden(bool bShouldHide);
    struct FInfinityShowCue* FindMutableCue() const;
};
