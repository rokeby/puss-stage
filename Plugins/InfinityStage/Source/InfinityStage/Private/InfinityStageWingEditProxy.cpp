#include "InfinityStageWingEditProxy.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"

AInfinityStageWingEditProxy::AInfinityStageWingEditProxy()
{
    PrimaryActorTick.bCanEverTick = false;
    SetFlags(RF_Transient | RF_Transactional);

    EditRoot = CreateDefaultSubobject<USceneComponent>(TEXT("EditRoot"));
    SetRootComponent(EditRoot);

    LeftPreview = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftPreview"));
    LeftPreview->SetupAttachment(EditRoot);
    RightPreview = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightPreview"));
    RightPreview->SetupAttachment(EditRoot);
    TopPreview = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TopPreview"));
    TopPreview->SetupAttachment(EditRoot);
    for (UStaticMeshComponent* Component : { LeftPreview.Get(), RightPreview.Get(), TopPreview.Get() })
    {
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->SetMobility(EComponentMobility::Movable);
        Component->SetIsVisualizationComponent(true);
    }
}

FInfinityShowCue* AInfinityStageWingEditProxy::FindMutableCue() const
{
    return ShowAsset
        ? ShowAsset->Cues.FindByPredicate([this](const FInfinityShowCue& Cue) { return Cue.CueGuid == CueGuid; })
        : nullptr;
}

bool AInfinityStageWingEditProxy::InitializeEdit(
    UInfinityStageShowAsset* InShow,
    AInfinityStagePassageActor* InPassageActor,
    const FGuid InCueGuid,
    const EInfinityWingEditTarget InTarget)
{
    ShowAsset = InShow;
    PassageActor = InPassageActor;
    CueGuid = InCueGuid;
    Target = InTarget;
    FInfinityShowCue* Cue = FindMutableCue();
    if (!Cue || Cue->Type != EInfinityCueType::WingPair || !PassageActor
        || !PassageActor->GetCuePlacementTransforms(CueGuid, StationWorld, PairWorldAtStart)
        || (Target == EInfinityWingEditTarget::Top && !Cue->WingPair.bHasTop))
    {
        return false;
    }

    OriginalOccurrenceOffset = Cue->WingPair.OccurrenceOffset;
    OriginalLeft = Cue->WingPair.Left.LocalTransform;
    OriginalRight = Cue->WingPair.Right.LocalTransform;
    OriginalTop = Cue->WingPair.Top.LocalTransform;

    LeftPreview->SetStaticMesh(Cue->WingPair.Left.Mesh.LoadSynchronous());
    RightPreview->SetStaticMesh(Cue->WingPair.Right.Mesh.LoadSynchronous());
    TopPreview->SetStaticMesh(Cue->WingPair.bHasTop ? Cue->WingPair.Top.Mesh.LoadSynchronous() : nullptr);
    LeftPreview->SetVisibility(Target == EInfinityWingEditTarget::Pair || Target == EInfinityWingEditTarget::Left);
    RightPreview->SetVisibility(Target == EInfinityWingEditTarget::Pair || Target == EInfinityWingEditTarget::Right);
    TopPreview->SetVisibility(Cue->WingPair.bHasTop && (Target == EInfinityWingEditTarget::Pair || Target == EInfinityWingEditTarget::Top));

    if (Target == EInfinityWingEditTarget::Pair)
    {
        SetActorTransform(PairWorldAtStart);
        LeftPreview->SetRelativeTransform(Cue->WingPair.Left.LocalTransform);
        RightPreview->SetRelativeTransform(Cue->WingPair.Right.LocalTransform);
        TopPreview->SetRelativeTransform(Cue->WingPair.Top.LocalTransform);
    }
    else
    {
        const FTransform& PanelLocal = Target == EInfinityWingEditTarget::Left
            ? Cue->WingPair.Left.LocalTransform
            : Target == EInfinityWingEditTarget::Right
                ? Cue->WingPair.Right.LocalTransform
                : Cue->WingPair.Top.LocalTransform;
        SetActorTransform(PanelLocal * PairWorldAtStart);
        LeftPreview->SetRelativeTransform(FTransform::Identity);
        RightPreview->SetRelativeTransform(FTransform::Identity);
        TopPreview->SetRelativeTransform(FTransform::Identity);
    }
    SetOriginalInstancesHidden(true);
    return true;
}

void AInfinityStageWingEditProxy::SetOriginalInstancesHidden(const bool bShouldHide)
{
    if (!PassageActor)
    {
        return;
    }
    for (const FInfinityMaterializedPanelRef& Ref : PassageActor->MaterializedPanels)
    {
        const bool bTargetSide = Target == EInfinityWingEditTarget::Pair
            || (Target == EInfinityWingEditTarget::Left && Ref.Side == EInfinityPanelSide::Left)
            || (Target == EInfinityWingEditTarget::Right && Ref.Side == EInfinityPanelSide::Right)
            || (Target == EInfinityWingEditTarget::Top && Ref.Side == EInfinityPanelSide::Top);
        if (Ref.CueGuid != CueGuid || !bTargetSide || !Ref.Component
            || Ref.InstanceIndex < 0 || Ref.InstanceIndex >= Ref.Component->GetInstanceCount())
        {
            continue;
        }
        FTransform Transform = Ref.BaseWorldTransform;
        if (bShouldHide)
        {
            Transform.SetScale3D(FVector::ZeroVector);
        }
        Ref.Component->UpdateInstanceTransform(Ref.InstanceIndex, Transform, true, true, true);
    }
}

void AInfinityStageWingEditProxy::UpdateAssetFromActor()
{
    if (bUpdating || bFinished)
    {
        return;
    }
    FInfinityShowCue* Cue = FindMutableCue();
    if (!Cue)
    {
        return;
    }
    TGuardValue<bool> Guard(bUpdating, true);
    ShowAsset->Modify();
    if (Target == EInfinityWingEditTarget::Pair)
    {
        Cue->WingPair.OccurrenceOffset = GetActorTransform() * StationWorld.Inverse();
    }
    else
    {
        const FTransform NewLocal = GetActorTransform() * PairWorldAtStart.Inverse();
        if (Target == EInfinityWingEditTarget::Left)
        {
            Cue->WingPair.Left.LocalTransform = NewLocal;
        }
        else if (Target == EInfinityWingEditTarget::Right)
        {
            Cue->WingPair.Right.LocalTransform = NewLocal;
        }
        else
        {
            Cue->WingPair.Top.LocalTransform = NewLocal;
        }
    }
    ShowAsset->MarkPackageDirty();
}

void AInfinityStageWingEditProxy::FinishEditing()
{
    if (bFinished)
    {
        return;
    }
    UpdateAssetFromActor();
    bFinished = true;
    if (PassageActor)
    {
        PassageActor->MaterializePassage();
    }
    Destroy();
}

void AInfinityStageWingEditProxy::CancelEditing()
{
    if (bFinished)
    {
        return;
    }
    if (FInfinityShowCue* Cue = FindMutableCue())
    {
        ShowAsset->Modify();
        Cue->WingPair.OccurrenceOffset = OriginalOccurrenceOffset;
        Cue->WingPair.Left.LocalTransform = OriginalLeft;
        Cue->WingPair.Right.LocalTransform = OriginalRight;
        Cue->WingPair.Top.LocalTransform = OriginalTop;
        ShowAsset->MarkPackageDirty();
    }
    bFinished = true;
    if (PassageActor)
    {
        PassageActor->MaterializePassage();
    }
    Destroy();
}

#if WITH_EDITOR
void AInfinityStageWingEditProxy::PostEditMove(bool bInFinished)
{
    Super::PostEditMove(bInFinished);
    UpdateAssetFromActor();
}

void AInfinityStageWingEditProxy::PostEditUndo()
{
    Super::PostEditUndo();
    UpdateAssetFromActor();
}
#endif
