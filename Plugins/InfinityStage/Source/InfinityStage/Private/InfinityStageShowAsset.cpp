#include "InfinityStageShowAsset.h"

#include "Curves/RichCurve.h"
#include "Math/RandomStream.h"
#include "InfinityStageCustomVersion.h"

namespace
{
void WriteSmoothUndulationCurve(FRuntimeFloatCurve& Curve)
{
    FRichCurve* RichCurve = Curve.GetRichCurve();
    RichCurve->Reset();

    // One closed cosine-shaped breath. User tangents keep both the position and
    // tangent continuous where phase wraps from 1 back to 0.
    struct FWaveKey
    {
        float Time;
        float Value;
        float Tangent;
    };
    static constexpr FWaveKey Keys[] =
    {
        { 0.00f, 0.00f, 0.0f },
        { 0.25f, 0.50f, PI },
        { 0.50f, 1.00f, 0.0f },
        { 0.75f, 0.50f, -PI },
        { 1.00f, 0.00f, 0.0f }
    };
    for (const FWaveKey& KeyDefinition : Keys)
    {
        const FKeyHandle Handle = RichCurve->AddKey(KeyDefinition.Time, KeyDefinition.Value);
        FRichCurveKey& Key = RichCurve->GetKey(Handle);
        Key.InterpMode = RCIM_Cubic;
        Key.TangentMode = RCTM_User;
        Key.ArriveTangent = KeyDefinition.Tangent;
        Key.LeaveTangent = KeyDefinition.Tangent;
    }
}

void WriteFanOpeningCurve(FRuntimeFloatCurve& Curve)
{
    FRichCurve* RichCurve = Curve.GetRichCurve();
    RichCurve->Reset();
    const FKeyHandle Closed = RichCurve->AddKey(0.0f, 1.0f);
    const FKeyHandle Open = RichCurve->AddKey(1.0f, 0.0f);
    for (const FKeyHandle Handle : { Closed, Open })
    {
        FRichCurveKey& Key = RichCurve->GetKey(Handle);
        Key.InterpMode = RCIM_Cubic;
        Key.TangentMode = RCTM_User;
        Key.ArriveTangent = 0.0f;
        Key.LeaveTangent = 0.0f;
    }
}

bool IsFanOpeningCurve(const FRuntimeFloatCurve& Curve)
{
    const FRichCurve* RichCurve = Curve.GetRichCurveConst();
    return RichCurve->GetNumKeys() == 2
        && FMath::IsNearlyEqual(RichCurve->Eval(0.0f), 1.0f)
        && FMath::IsNearlyZero(RichCurve->Eval(1.0f));
}

bool CameraGustSettingsEqual(
    const FInfinityCameraGustSettings& A,
    const FInfinityCameraGustSettings& B)
{
    return A.TimingMode == B.TimingMode
        && A.FanDepthPairs == B.FanDepthPairs
        && FMath::IsNearlyEqual(A.OpeningSpanPairs, B.OpeningSpanPairs)
        && FMath::IsNearlyEqual(A.CascadeDurationSeconds, B.CascadeDurationSeconds)
        && FMath::IsNearlyEqual(A.PairOpeningDurationSeconds, B.PairOpeningDurationSeconds)
        && FMath::IsNearlyEqual(A.PairStaggerSeconds, B.PairStaggerSeconds)
        && A.Direction == B.Direction
        && A.HoldOpenPolicy == B.HoldOpenPolicy
        && A.TriggerOffsetUnit == B.TriggerOffsetUnit
        && FMath::IsNearlyEqual(A.TriggerOffset, B.TriggerOffset)
        && A.GroupAnchorCueGuid == B.GroupAnchorCueGuid
        && A.GroupOrdinal == B.GroupOrdinal
        && A.GroupSize == B.GroupSize;
}
}

UInfinityStageShowAsset::UInfinityStageShowAsset()
    : DisplayRate(25, 1)
    , TickResolution(24000, 1)
{
}

void UInfinityStageShowAsset::EnsureStableIds()
{
    if (!ShowGuid.IsValid())
    {
        ShowGuid = FGuid::NewGuid();
    }
    for (FInfinityShowCue& Cue : Cues)
    {
        if (!Cue.CueGuid.IsValid())
        {
            Cue.CueGuid = FGuid::NewGuid();
        }
        if (Cue.Type == EInfinityCueType::WingPair && !Cue.WingPair.OccurrenceGuid.IsValid())
        {
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        }
    }

    for (FInfinityPassageSettings& Passage : PassageSettings)
    {
        if (!Passage.PassageGuid.IsValid())
        {
            Passage.PassageGuid = FGuid::NewGuid();
        }
    }

    for (FInfinityMusicRail& Rail : MusicRails)
    {
        if (!Rail.RailGuid.IsValid())
        {
            Rail.RailGuid = FGuid::NewGuid();
        }
    }
}

void UInfinityStageShowAsset::ReconcilePassageSettings()
{
    EnsureStableIds();
    const TArray<FInfinityPassageSettings> PreviousSettings = PassageSettings;
    TArray<FInfinityPassageSettings> Reconciled;
    TSet<FGuid> UsedPassageIds;

    for (int32 Index = 0; Index < Cues.Num();)
    {
        if (!Cues[Index].bEnabled || Cues[Index].Type != EInfinityCueType::WingPair)
        {
            ++Index;
            continue;
        }

        const int32 FirstIndex = Index;
        int32 LastIndex = Index;
        while (LastIndex + 1 < Cues.Num()
            && Cues[LastIndex + 1].bEnabled
            && Cues[LastIndex + 1].Type == EInfinityCueType::WingPair)
        {
            ++LastIndex;
        }

        const FInfinityPassageSettings* Existing = PreviousSettings.FindByPredicate([this, FirstIndex, LastIndex, &UsedPassageIds](const FInfinityPassageSettings& Settings)
        {
            if (UsedPassageIds.Contains(Settings.PassageGuid))
            {
                return false;
            }
            const int32 PreviousFirst = FindCueIndex(Settings.FirstCueGuid);
            const int32 PreviousLast = FindCueIndex(Settings.LastCueGuid);
            return (PreviousFirst >= FirstIndex && PreviousFirst <= LastIndex)
                || (PreviousLast >= FirstIndex && PreviousLast <= LastIndex);
        });

        FInfinityPassageSettings& Settings = Reconciled.AddDefaulted_GetRef();
        if (Existing)
        {
            Settings = *Existing;
            UsedPassageIds.Add(Settings.PassageGuid);
        }
        if (!Settings.PassageGuid.IsValid())
        {
            Settings.PassageGuid = FGuid::NewGuid();
        }
        if (Settings.Label.IsEmpty())
        {
            Settings.Label = FText::Format(NSLOCTEXT("InfinityStage", "DefaultPassageLabel", "Passage {0}"), Reconciled.Num());
        }
        Settings.FirstCueGuid = Cues[FirstIndex].CueGuid;
        Settings.LastCueGuid = Cues[LastIndex].CueGuid;
        Index = LastIndex + 1;
    }

    PassageSettings = MoveTemp(Reconciled);
}

int32 UInfinityStageShowAsset::FindCueIndex(const FGuid CueGuid) const
{
    return Cues.IndexOfByPredicate([CueGuid](const FInfinityShowCue& Cue)
    {
        return Cue.CueGuid == CueGuid;
    });
}

int32 UInfinityStageShowAsset::ApplyImageFlipToAllUsesOfMesh(
    const FSoftObjectPath& MeshPath,
    const bool bFlipImageHorizontally)
{
    if (MeshPath.IsNull())
    {
        return 0;
    }

    int32 ChangedPanels = 0;
    const auto ApplyToPanel = [&MeshPath, bFlipImageHorizontally, &ChangedPanels](FInfinityPanelDesign& Panel)
    {
        if (Panel.Mesh.ToSoftObjectPath() == MeshPath
            && Panel.bFlipImageHorizontally != bFlipImageHorizontally)
        {
            Panel.bFlipImageHorizontally = bFlipImageHorizontally;
            ++ChangedPanels;
        }
    };
    for (FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        ApplyToPanel(Cue.WingPair.Left);
        ApplyToPanel(Cue.WingPair.Right);
        if (Cue.WingPair.bHasTop)
        {
            ApplyToPanel(Cue.WingPair.Top);
        }
    }
    return ChangedPanels;
}

int32 UInfinityStageShowAsset::ApplyRelativeTransformToAllUsesOfMesh(
    const FSoftObjectPath& MeshPath,
    const FTransform& RelativeTransform)
{
    if (MeshPath.IsNull())
    {
        return 0;
    }

    int32 ChangedPanels = 0;
    const auto ApplyToPanel = [&MeshPath, &RelativeTransform, &ChangedPanels](FInfinityPanelDesign& Panel)
    {
        if (Panel.Mesh.ToSoftObjectPath() == MeshPath
            && !Panel.LocalTransform.Equals(RelativeTransform))
        {
            Panel.LocalTransform = RelativeTransform;
            ++ChangedPanels;
        }
    };
    for (FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        ApplyToPanel(Cue.WingPair.Left);
        ApplyToPanel(Cue.WingPair.Right);
        if (Cue.WingPair.bHasTop)
        {
            ApplyToPanel(Cue.WingPair.Top);
        }
    }
    return ChangedPanels;
}

int32 UInfinityStageShowAsset::ApplyTravelingUndulation(
    const TArray<FGuid>& CueGuids,
    const double CycleRateHz,
    const double InwardTravelCm,
    const double PhaseStepCycles,
    const bool bUseLivePassagePattern)
{
    TSet<FGuid> TargetGuids;
    for (const FGuid& CueGuid : CueGuids)
    {
        TargetGuids.Add(CueGuid);
    }
    if (TargetGuids.IsEmpty())
    {
        return 0;
    }

    TSet<FGuid> LivePassageGuids;
    if (bUseLivePassagePattern)
    {
        for (FInfinityPassageSettings& Passage : PassageSettings)
        {
            const int32 FirstIndex = FindCueIndex(Passage.FirstCueGuid);
            const int32 LastIndex = FindCueIndex(Passage.LastCueGuid);
            if (FirstIndex == INDEX_NONE || LastIndex < FirstIndex)
            {
                continue;
            }
            bool bEveryWingIsTargeted = true;
            for (int32 Index = FirstIndex; Index <= LastIndex; ++Index)
            {
                const FInfinityShowCue& Candidate = Cues[Index];
                if (Candidate.bEnabled && Candidate.Type == EInfinityCueType::WingPair
                    && !TargetGuids.Contains(Candidate.CueGuid))
                {
                    bEveryWingIsTargeted = false;
                    break;
                }
            }
            if (bEveryWingIsTargeted)
            {
                Passage.bUseLiveMechanismPhasePattern = true;
                Passage.MechanismPhaseStepCycles = PhaseStepCycles;
                Passage.MechanismPhaseOffsetCycles = 0.0;
                LivePassageGuids.Add(Passage.PassageGuid);
            }
        }
    }

    int32 ChangedCues = 0;
    int32 PassageOrdinal = 0;
    const FInfinityPassageSettings* ActivePassage = nullptr;
    for (FInfinityShowCue& Cue : Cues)
    {
        if (!Cue.bEnabled || Cue.Type != EInfinityCueType::WingPair)
        {
            PassageOrdinal = 0;
            ActivePassage = nullptr;
            continue;
        }

        if (!ActivePassage)
        {
            ActivePassage = PassageSettings.FindByPredicate([this, &Cue](const FInfinityPassageSettings& Passage)
            {
                return FindCueIndex(Passage.FirstCueGuid) == FindCueIndex(Cue.CueGuid);
            });
        }

        if (TargetGuids.Contains(Cue.CueGuid))
        {
            FInfinityMechanismMotion& Motion = Cue.WingPair.Mechanism;
            Motion.PlaybackMode = EInfinityMotionPlaybackMode::ContinuousLoop;
            Motion.CycleRateHz = FMath::Max(0.0, CycleRateHz);
            Motion.PhaseOrigin = EInfinityMotionPhaseOrigin::PassageStart;
            const bool bLivePattern = ActivePassage
                && LivePassageGuids.Contains(ActivePassage->PassageGuid);
            if (bLivePattern)
            {
                Cue.WingPair.LocalOverrideMask &= ~static_cast<int32>(EInfinityLocalOverride::MechanismPhase);
                Motion.PhaseOffsetCycles = 0.0;
            }
            else
            {
                Cue.WingPair.LocalOverrideMask |= static_cast<int32>(EInfinityLocalOverride::MechanismPhase);
                Motion.PhaseOffsetCycles = PassageOrdinal * PhaseStepCycles;
            }
            Motion.InwardTravelCm = FMath::Max(0.0, InwardTravelCm);
            WriteSmoothUndulationCurve(Motion.LeftNormalizedCurve);
            WriteSmoothUndulationCurve(Motion.RightNormalizedCurve);
            WriteSmoothUndulationCurve(Motion.TopNormalizedCurve);
            ++ChangedCues;
        }
        ++PassageOrdinal;
    }
    return ChangedCues;
}

int32 UInfinityStageShowAsset::ApplyCameraGust(
    const TArray<FGuid>& OrderedCueGuids,
    const FInfinityCameraGustSettings& Settings,
    const bool bPartitionIntoFanDepthGroups)
{
    TArray<FGuid> ApplicableCueGuids;
    TSet<FGuid> SeenCueGuids;
    for (const FGuid& CueGuid : OrderedCueGuids)
    {
        const FInfinityShowCue* Cue = Cues.FindByPredicate([CueGuid](const FInfinityShowCue& Candidate)
        {
            return Candidate.CueGuid == CueGuid;
        });
        if (Cue && Cue->bEnabled && Cue->Type == EInfinityCueType::WingPair
            && !SeenCueGuids.Contains(CueGuid))
        {
            ApplicableCueGuids.Add(CueGuid);
            SeenCueGuids.Add(CueGuid);
        }
    }
    if (ApplicableCueGuids.IsEmpty())
    {
        return 0;
    }

    FInfinityCameraGustSettings Sanitized = Settings;
    Sanitized.FanDepthPairs = FMath::Max(1, Sanitized.FanDepthPairs);
    Sanitized.OpeningSpanPairs = FMath::Max(0.01, Sanitized.OpeningSpanPairs);
    Sanitized.CascadeDurationSeconds = FMath::Max(0.01, Sanitized.CascadeDurationSeconds);
    Sanitized.PairOpeningDurationSeconds = FMath::Max(0.01, Sanitized.PairOpeningDurationSeconds);
    Sanitized.PairStaggerSeconds = FMath::Max(0.0, Sanitized.PairStaggerSeconds);
    Sanitized.TriggerOffset = FMath::Max(0.0, Sanitized.TriggerOffset);

    const bool bUseTimedGroups = Sanitized.TimingMode == EInfinityCameraGustTimingMode::TimedCascade;
    const int32 GroupDepth = bPartitionIntoFanDepthGroups && bUseTimedGroups
        ? Sanitized.FanDepthPairs
        : ApplicableCueGuids.Num();
    int32 ChangedCues = 0;
    for (int32 GroupStart = 0; GroupStart < ApplicableCueGuids.Num(); GroupStart += GroupDepth)
    {
        const int32 GroupSize = FMath::Min(GroupDepth, ApplicableCueGuids.Num() - GroupStart);
        const FGuid GroupAnchorGuid = ApplicableCueGuids[GroupStart];
        for (int32 GroupOrdinal = 0; GroupOrdinal < GroupSize; ++GroupOrdinal)
        {
            const FGuid CueGuid = ApplicableCueGuids[GroupStart + GroupOrdinal];
            FInfinityShowCue* Cue = Cues.FindByPredicate([CueGuid](const FInfinityShowCue& Candidate)
            {
                return Candidate.CueGuid == CueGuid;
            });
            if (!Cue)
            {
                continue;
            }

            FInfinityCameraGustSettings Desired = Sanitized;
            Desired.GroupAnchorCueGuid = GroupAnchorGuid;
            Desired.GroupOrdinal = GroupOrdinal;
            Desired.GroupSize = GroupSize;
            FInfinityMechanismMotion& Motion = Cue->WingPair.Mechanism;
            const bool bAlreadyMatches = Motion.PlaybackMode == EInfinityMotionPlaybackMode::CameraGust
                && CameraGustSettingsEqual(Motion.CameraGust, Desired)
                && IsFanOpeningCurve(Motion.LeftNormalizedCurve)
                && IsFanOpeningCurve(Motion.RightNormalizedCurve)
                && IsFanOpeningCurve(Motion.TopNormalizedCurve);
            if (bAlreadyMatches)
            {
                continue;
            }

            // InwardTravelCm and the authored panel/rest transforms are deliberately
            // untouched. At phase zero the pair is fully inward/closed; at phase one
            // it returns to its own authored rest/open transform.
            Motion.PlaybackMode = EInfinityMotionPlaybackMode::CameraGust;
            Motion.CameraGust = Desired;
            WriteFanOpeningCurve(Motion.LeftNormalizedCurve);
            WriteFanOpeningCurve(Motion.RightNormalizedCurve);
            WriteFanOpeningCurve(Motion.TopNormalizedCurve);
            ++ChangedCues;
        }
    }
    return ChangedCues;
}

int32 UInfinityStageShowAsset::SetMechanismsStatic(const TArray<FGuid>& CueGuids)
{
    TSet<FGuid> TargetGuids;
    for (const FGuid& CueGuid : CueGuids)
    {
        TargetGuids.Add(CueGuid);
    }
    int32 ChangedCues = 0;
    for (FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type == EInfinityCueType::WingPair
            && TargetGuids.Contains(Cue.CueGuid)
            && Cue.WingPair.Mechanism.PlaybackMode != EInfinityMotionPlaybackMode::Static)
        {
            Cue.WingPair.Mechanism.PlaybackMode = EInfinityMotionPlaybackMode::Static;
            ++ChangedCues;
        }
    }
    return ChangedCues;
}

TArray<FGuid> UInfinityStageShowAsset::GetAllWingPairCueGuids() const
{
    TArray<FGuid> Result;
    for (const FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type == EInfinityCueType::WingPair)
        {
            Result.Add(Cue.CueGuid);
        }
    }
    return Result;
}

FGuid UInfinityStageShowAsset::FindPassageGuidForCue(const FGuid CueGuid) const
{
    const int32 CueIndex = FindCueIndex(CueGuid);
    if (CueIndex == INDEX_NONE)
    {
        return FGuid();
    }
    for (const FInfinityPassageSettings& Passage : PassageSettings)
    {
        const int32 First = FindCueIndex(Passage.FirstCueGuid);
        const int32 Last = FindCueIndex(Passage.LastCueGuid);
        if (First != INDEX_NONE && Last != INDEX_NONE && CueIndex >= First && CueIndex <= Last)
        {
            return Passage.PassageGuid;
        }
    }
    return FGuid();
}

TArray<FGuid> UInfinityStageShowAsset::GetWingPairCueGuidsInPassage(const FGuid PassageGuid) const
{
    TArray<FGuid> Result;
    const FInfinityPassageSettings* Passage = PassageSettings.FindByPredicate([PassageGuid](const FInfinityPassageSettings& Candidate)
    {
        return Candidate.PassageGuid == PassageGuid;
    });
    if (!Passage)
    {
        return Result;
    }
    const int32 First = FindCueIndex(Passage->FirstCueGuid);
    const int32 Last = FindCueIndex(Passage->LastCueGuid);
    if (First == INDEX_NONE || Last == INDEX_NONE)
    {
        return Result;
    }
    for (int32 CueIndex = First; CueIndex <= Last && Cues.IsValidIndex(CueIndex); ++CueIndex)
    {
        if (Cues[CueIndex].Type == EInfinityCueType::WingPair)
        {
            Result.Add(Cues[CueIndex].CueGuid);
        }
    }
    return Result;
}

int32 UInfinityStageShowAsset::ReplicateLightAttachmentsWithVariation(
    const FGuid SourceCueGuid,
    const TArray<FGuid>& TargetCueGuids,
    const FInfinityLightReplicationVariation& Variation)
{
    const int32 ChangedCues = ReplicateLightAttachments(SourceCueGuid, TargetCueGuids);
    if (ChangedCues == 0)
    {
        return 0;
    }
    for (FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || Cue.CueGuid == SourceCueGuid || !TargetCueGuids.Contains(Cue.CueGuid))
        {
            continue;
        }
        // One stream per target pair: the same seed always yields the same corridor.
        FRandomStream Stream(static_cast<int32>(GetTypeHash(Cue.CueGuid)) ^ Variation.Seed);
        for (FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
        {
            if (Attachment.Kind != EInfinityAttachmentKind::Light)
            {
                continue;
            }
            const float P = FMath::Max(0.0f, Variation.PositionJitterCm);
            const float R = FMath::Max(0.0f, Variation.RotationJitterDegrees);
            const float I = FMath::Clamp(Variation.IntensityJitterFraction, 0.0f, 0.9f);
            Attachment.RelativeTransform.AddToTranslation(FVector(
                Stream.FRandRange(-P, P), Stream.FRandRange(-P, P), Stream.FRandRange(-P, P)));
            const FQuat Aim = FRotator(
                Stream.FRandRange(-R, R), Stream.FRandRange(-R, R), Stream.FRandRange(-R, R) * 0.5f).Quaternion();
            Attachment.RelativeTransform.SetRotation((Aim * Attachment.RelativeTransform.GetRotation()).GetNormalized());
            Attachment.Lighting.Intensity *= Stream.FRandRange(1.0f - I, 1.0f + I);
        }
    }
    return ChangedCues;
}

int32 UInfinityStageShowAsset::ReplicateLightAttachments(
    const FGuid SourceCueGuid,
    const TArray<FGuid>& TargetCueGuids)
{
    const FInfinityShowCue* SourceCue = Cues.FindByPredicate([SourceCueGuid](const FInfinityShowCue& Cue)
    {
        return Cue.CueGuid == SourceCueGuid && Cue.Type == EInfinityCueType::WingPair;
    });
    if (!SourceCue)
    {
        return 0;
    }

    TArray<FInfinityCueAttachment> SourceLights;
    for (const FInfinityCueAttachment& Attachment : SourceCue->WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Light)
        {
            SourceLights.Add(Attachment);
        }
    }
    TSet<FGuid> Targets;
    for (const FGuid& CueGuid : TargetCueGuids)
    {
        if (CueGuid != SourceCueGuid)
        {
            Targets.Add(CueGuid);
        }
    }

    const FString SourceCueLabel = SourceCue->Label.ToString();
    int32 ChangedCues = 0;
    for (FInfinityShowCue& Cue : Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || !Targets.Contains(Cue.CueGuid))
        {
            continue;
        }

        TArray<FGuid> ExistingLightGuids;
        for (const FInfinityCueAttachment& Existing : Cue.WingPair.Attachments)
        {
            if (Existing.Kind == EInfinityAttachmentKind::Light)
            {
                ExistingLightGuids.Add(Existing.AttachmentGuid);
            }
        }
        Cue.WingPair.Attachments.RemoveAll([](const FInfinityCueAttachment& Existing)
        {
            return Existing.Kind == EInfinityAttachmentKind::Light;
        });

        for (int32 LightIndex = 0; LightIndex < SourceLights.Num(); ++LightIndex)
        {
            FInfinityCueAttachment Copy = SourceLights[LightIndex];
            Copy.AttachmentGuid = ExistingLightGuids.IsValidIndex(LightIndex)
                && ExistingLightGuids[LightIndex].IsValid()
                ? ExistingLightGuids[LightIndex]
                : FGuid::NewGuid();

            const FString SourceLabel = Copy.Label.ToString();
            if (!SourceCueLabel.IsEmpty() && SourceLabel.StartsWith(SourceCueLabel))
            {
                Copy.Label = FText::FromString(Cue.Label.ToString() + SourceLabel.RightChop(SourceCueLabel.Len()));
            }
            else if (!SourceLabel.IsEmpty())
            {
                Copy.Label = FText::Format(
                    NSLOCTEXT("InfinityStage", "ReplicatedLightLabel", "{0} — {1}"),
                    Cue.Label,
                    Copy.Label);
            }
            Cue.WingPair.Attachments.Add(MoveTemp(Copy));
        }
        ++ChangedCues;
    }
    return ChangedCues;
}

FPrimaryAssetId UInfinityStageShowAsset::GetPrimaryAssetId() const
{
    return FPrimaryAssetId(TEXT("InfinityStageShow"), GetFName());
}

void UInfinityStageShowAsset::Serialize(FArchive& Ar)
{
    Ar.UsingCustomVersion(FInfinityStageCustomVersion::GUID);
    Super::Serialize(Ar);
}

void UInfinityStageShowAsset::PostLoad()
{
    Super::PostLoad();
    EnsureStableIds();
}
