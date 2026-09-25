#include "InfinityStageCueProxy.h"

#include "InfinityStageShowAsset.h"

void UInfinityStageCueProxy::RefreshOpeningLayoutFromCue()
{
    bIsWingPair = Cue.Type == EInfinityCueType::WingPair;
    if (!bIsWingPair)
    {
        RestOpeningWidthCm = 0.0;
        OpeningCentreOffsetCm = 0.0;
        return;
    }

    const double LeftY = Cue.WingPair.Left.LocalTransform.GetTranslation().Y;
    const double RightY = Cue.WingPair.Right.LocalTransform.GetTranslation().Y;
    RestOpeningWidthCm = FMath::Abs(RightY - LeftY);
    OpeningCentreOffsetCm = (LeftY + RightY) * 0.5;
}

void UInfinityStageCueProxy::ApplyOpeningLayoutToCue()
{
    if (Cue.Type != EInfinityCueType::WingPair)
    {
        return;
    }

    RestOpeningWidthCm = FMath::Max(0.0, RestOpeningWidthCm);
    FVector LeftLocation = Cue.WingPair.Left.LocalTransform.GetTranslation();
    FVector RightLocation = Cue.WingPair.Right.LocalTransform.GetTranslation();
    LeftLocation.Y = OpeningCentreOffsetCm - RestOpeningWidthCm * 0.5;
    RightLocation.Y = OpeningCentreOffsetCm + RestOpeningWidthCm * 0.5;
    Cue.WingPair.Left.LocalTransform.SetTranslation(LeftLocation);
    Cue.WingPair.Right.LocalTransform.SetTranslation(RightLocation);
}

void UInfinityStageCueProxy::Initialize(UInfinityStageShowAsset* InAsset, const int32 InCueIndex)
{
    Asset = InAsset;
    CueIndex = InCueIndex;
    if (InAsset && InAsset->Cues.IsValidIndex(InCueIndex))
    {
        bApplying = true;
        Cue = InAsset->Cues[InCueIndex];
        RefreshOpeningLayoutFromCue();
        bApplying = false;
    }
}

void UInfinityStageCueProxy::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    if (bApplying || !Asset.IsValid() || !Asset->Cues.IsValidIndex(CueIndex))
    {
        return;
    }

    const FName ChangedProperty = PropertyChangedEvent.GetPropertyName();
    const bool bOpeningLayoutChanged = ChangedProperty == GET_MEMBER_NAME_CHECKED(
        UInfinityStageCueProxy, RestOpeningWidthCm)
        || ChangedProperty == GET_MEMBER_NAME_CHECKED(
            UInfinityStageCueProxy, OpeningCentreOffsetCm);
    if (bOpeningLayoutChanged)
    {
        ApplyOpeningLayoutToCue();
    }
    else
    {
        RefreshOpeningLayoutFromCue();
    }

    Asset->Modify();
    Asset->Cues[CueIndex] = Cue;
    Asset->EnsureStableIds();
    Asset->ReconcilePassageSettings();
    Asset->MarkPackageDirty();
    OnChanged.ExecuteIfBound();
}

void UInfinityStageCueProxy::PostEditUndo()
{
    Super::PostEditUndo();
    RefreshOpeningLayoutFromCue();
    OnChanged.ExecuteIfBound();
}
