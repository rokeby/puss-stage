#include "InfinityStageEffectLibrary.h"

#include "InfinityStageShowAsset.h"
#include "Math/RandomStream.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageEffectAuthoring, Log, All);

namespace
{
bool IsReplicatedEffect(const FInfinityCueAttachment& Attachment)
{
    return Attachment.Kind == EInfinityAttachmentKind::Effect
        && Attachment.Effect.ReplicatedFromAttachmentGuid.IsValid();
}

TArray<FGuid> LightGuidsInOrder(const FInfinityShowCue& Cue)
{
    TArray<FGuid> Result;
    for (const FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Light)
        {
            Result.Add(Attachment.AttachmentGuid);
        }
    }
    return Result;
}
}

FInfinityStageEffectSettings UInfinityStageEffectLibrary::MakeDefaultEffectSettings(const EInfinityStageEffectType Type)
{
    FInfinityStageEffectSettings Settings;
    Settings.Type = Type;
    switch (Type)
    {
    case EInfinityStageEffectType::Haze:
        // The struct defaults are the haze pot.
        break;
    case EInfinityStageEffectType::Smoke:
        Settings.Tint = FLinearColor(0.35f, 0.33f, 0.30f);
        Settings.PulsePeriodSeconds = 4.0f;
        Settings.PulseDuty = 0.25f;
        Settings.MediumRadiusCm = 300.0f;
        Settings.MediumDensity = 0.25f;
        Settings.MediumHeightFalloff = 800.0f;
        break;
    case EInfinityStageEffectType::Steam:
        Settings.PulsePeriodSeconds = 3.0f;
        Settings.PulseDuty = 0.2f;
        Settings.MediumRadiusCm = 250.0f;
        Settings.MediumDensity = 0.08f;
        break;
    case EInfinityStageEffectType::Fire:
        Settings.Tint = FLinearColor(1.0f, 0.55f, 0.25f);
        Settings.PulsePeriodSeconds = 0.0f;
        Settings.bFeedsLocalMedium = false;
        Settings.FlickerAmount = 0.3f;
        break;
    case EInfinityStageEffectType::WingBurn:
        Settings.Tint = FLinearColor(1.0f, 0.5f, 0.2f);
        Settings.PulsePeriodSeconds = 0.0f;
        Settings.bFeedsLocalMedium = false;
        Settings.FlickerAmount = 0.35f;
        break;
    case EInfinityStageEffectType::Motes:
        Settings.Tint = FLinearColor(1.0f, 0.95f, 0.85f);
        Settings.Output = 0.3f;
        Settings.PulsePeriodSeconds = 0.0f;
        Settings.bFeedsLocalMedium = false;
        Settings.ActiveRadiusCm = 4000.0f;
        break;
    }
    return Settings;
}

FGuid UInfinityStageEffectLibrary::AddEffectAttachment(
    UInfinityStageShowAsset* Show,
    const FGuid CueGuid,
    const EInfinityStageEffectType Type,
    const EInfinityAttachmentAnchor Anchor,
    const FTransform RelativeTransform,
    const FText Label)
{
    if (!Show)
    {
        return FGuid();
    }
    FInfinityShowCue* Cue = Show->Cues.FindByPredicate(
        [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
    if (!Cue || Cue->Type != EInfinityCueType::WingPair)
    {
        return FGuid();
    }
    Show->Modify();
    FInfinityCueAttachment& Attachment = Cue->WingPair.Attachments.AddDefaulted_GetRef();
    Attachment.AttachmentGuid = FGuid::NewGuid();
    Attachment.Kind = EInfinityAttachmentKind::Effect;
    Attachment.Anchor = Anchor;
    Attachment.RelativeTransform = RelativeTransform;
    Attachment.Label = Label;
    Attachment.Effect = MakeDefaultEffectSettings(Type);
    UE_LOG(
        LogInfinityStageEffectAuthoring,
        Display,
        TEXT("INFINITY_STAGE_EFFECT_ADDED cue='%s' attachment=%s type=%s; written to the Show, save it intentionally."),
        *Cue->Label.ToString(),
        *Attachment.AttachmentGuid.ToString(EGuidFormats::DigitsWithHyphens),
        *StaticEnum<EInfinityStageEffectType>()->GetNameStringByValue(static_cast<int64>(Type)));
    return Attachment.AttachmentGuid;
}

TArray<FGuid> UInfinityStageEffectLibrary::SelectBeamBays(
    const UInfinityStageShowAsset* Show,
    const TArray<FGuid>& CueGuids,
    const float MinVolumetricScattering)
{
    TArray<FGuid> Result;
    if (!Show)
    {
        return Result;
    }
    for (const FGuid& CueGuid : CueGuids)
    {
        const FInfinityShowCue* Cue = Show->Cues.FindByPredicate(
            [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
        if (!Cue || Cue->Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        const bool bHasBeam = Cue->WingPair.Attachments.ContainsByPredicate(
            [MinVolumetricScattering](const FInfinityCueAttachment& Attachment)
            {
                return Attachment.bEnabled
                    && Attachment.Kind == EInfinityAttachmentKind::Light
                    && Attachment.Lighting.bCastVolumetricShadow
                    && Attachment.Lighting.VolumetricScatteringIntensity >= MinVolumetricScattering;
            });
        if (bHasBeam)
        {
            Result.Add(CueGuid);
        }
    }
    return Result;
}

TArray<FGuid> UInfinityStageEffectLibrary::SelectEveryNthPerPassage(
    const UInfinityStageShowAsset* Show,
    const TArray<FGuid>& CueGuids,
    const int32 Stride,
    const int32 Phase)
{
    TArray<FGuid> Result;
    if (!Show || Stride < 1)
    {
        return Result;
    }
    // Count in Show order whatever order the caller passed, so the same set
    // always selects the same bays.
    TSet<FGuid> Wanted(CueGuids);
    TMap<FGuid, int32> OrdinalByPassage;
    for (const FInfinityShowCue& Cue : Show->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || !Wanted.Contains(Cue.CueGuid))
        {
            continue;
        }
        // Cues outside any Passage count together under the invalid guid.
        int32& Ordinal = OrdinalByPassage.FindOrAdd(Show->FindPassageGuidForCue(Cue.CueGuid), 0);
        const int32 Offset = Ordinal - Phase;
        if (Offset >= 0 && Offset % Stride == 0)
        {
            Result.Add(Cue.CueGuid);
        }
        ++Ordinal;
    }
    return Result;
}

int32 UInfinityStageEffectLibrary::ClearReplicatedEffects(
    UInfinityStageShowAsset* Show,
    const FGuid SourceCueGuid,
    const TArray<FGuid>& ScopeCueGuids)
{
    if (!Show)
    {
        return 0;
    }
    TSet<FGuid> SourceAttachmentGuids;
    if (SourceCueGuid.IsValid())
    {
        const FInfinityShowCue* SourceCue = Show->Cues.FindByPredicate(
            [SourceCueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == SourceCueGuid; });
        if (!SourceCue)
        {
            return 0;
        }
        for (const FInfinityCueAttachment& Attachment : SourceCue->WingPair.Attachments)
        {
            if (Attachment.Kind == EInfinityAttachmentKind::Effect)
            {
                SourceAttachmentGuids.Add(Attachment.AttachmentGuid);
            }
        }
    }

    const TSet<FGuid> Scope(ScopeCueGuids);
    int32 Removed = 0;
    bool bModified = false;
    for (FInfinityShowCue& Cue : Show->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || Cue.CueGuid == SourceCueGuid || !Scope.Contains(Cue.CueGuid))
        {
            continue;
        }
        const auto IsOwnCopy = [&SourceCueGuid, &SourceAttachmentGuids](const FInfinityCueAttachment& Attachment)
        {
            return IsReplicatedEffect(Attachment)
                && (!SourceCueGuid.IsValid()
                    || SourceAttachmentGuids.Contains(Attachment.Effect.ReplicatedFromAttachmentGuid));
        };
        if (!Cue.WingPair.Attachments.ContainsByPredicate(IsOwnCopy))
        {
            continue;
        }
        if (!bModified)
        {
            Show->Modify();
            bModified = true;
        }
        Removed += Cue.WingPair.Attachments.RemoveAll(IsOwnCopy);
    }
    return Removed;
}

int32 UInfinityStageEffectLibrary::ReplicateEffectAttachments(
    UInfinityStageShowAsset* Show,
    const FGuid SourceCueGuid,
    const TArray<FGuid>& ScopeCueGuids,
    const TArray<FGuid>& TargetCueGuids,
    const FInfinityEffectReplicationVariation& Variation)
{
    if (!Show)
    {
        return 0;
    }
    const FInfinityShowCue* SourceCue = Show->Cues.FindByPredicate(
        [SourceCueGuid](const FInfinityShowCue& Candidate)
        { return Candidate.CueGuid == SourceCueGuid && Candidate.Type == EInfinityCueType::WingPair; });
    if (!SourceCue)
    {
        return 0;
    }

    // Only hand-placed effects are sources. A copy sitting on the source cue
    // belongs to some other source and is not re-copied.
    TArray<FInfinityCueAttachment> Sources;
    for (const FInfinityCueAttachment& Attachment : SourceCue->WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Effect && !IsReplicatedEffect(Attachment))
        {
            Sources.Add(Attachment);
        }
    }
    const TArray<FGuid> SourceLightGuids = LightGuidsInOrder(*SourceCue);
    const FString SourceCueLabel = SourceCue->Label.ToString();

    Show->Modify();
    TArray<FGuid> ClearScope = ScopeCueGuids;
    ClearScope.Append(TargetCueGuids);
    const int32 Removed = ClearReplicatedEffects(Show, SourceCueGuid, ClearScope);

    TSet<FGuid> Targets(TargetCueGuids);
    Targets.Remove(SourceCueGuid);
    const float OutputJitter = FMath::Clamp(Variation.OutputJitterFraction, 0.0f, 0.9f);
    const float PositionJitter = FMath::Max(0.0f, Variation.PositionJitterCm);
    const float RotationJitter = FMath::Max(0.0f, Variation.RotationJitterDegrees);

    int32 Placed = 0;
    for (FInfinityShowCue& Cue : Show->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair || !Targets.Contains(Cue.CueGuid))
        {
            continue;
        }
        // One stream per target pair: the same seed always yields the same corridor.
        FRandomStream Stream(static_cast<int32>(GetTypeHash(Cue.CueGuid)) ^ Variation.Seed);
        const TArray<FGuid> TargetLightGuids = LightGuidsInOrder(Cue);
        for (const FInfinityCueAttachment& Source : Sources)
        {
            FInfinityCueAttachment Copy = Source;
            // Deterministic, so re-replicating gives the same identities and the
            // level's placed actors keep their tags.
            Copy.AttachmentGuid = FGuid::NewDeterministicGuid(FString::Printf(
                TEXT("InfinityStage.EffectCopy/%s/%s"),
                *Source.AttachmentGuid.ToString(EGuidFormats::Digits),
                *Cue.CueGuid.ToString(EGuidFormats::Digits)));
            Copy.Effect.ReplicatedFromAttachmentGuid = Source.AttachmentGuid;

            // A fire's light is the pair's own: take the target's light in the
            // same ordinal slot, as light replication lays them out.
            if (Source.Effect.LinkedLightAttachmentGuid.IsValid())
            {
                const int32 LightOrdinal = SourceLightGuids.IndexOfByKey(Source.Effect.LinkedLightAttachmentGuid);
                Copy.Effect.LinkedLightAttachmentGuid = TargetLightGuids.IsValidIndex(LightOrdinal)
                    ? TargetLightGuids[LightOrdinal]
                    : FGuid();
            }

            // Always draw the same count, so one setting at zero cannot shift the
            // stream under the others.
            const float OutputScale = Stream.FRandRange(1.0f - OutputJitter, 1.0f + OutputJitter);
            const FVector Nudge(
                Stream.FRandRange(-PositionJitter, PositionJitter),
                Stream.FRandRange(-PositionJitter, PositionJitter),
                Stream.FRandRange(-PositionJitter, PositionJitter));
            const FRotator Aim(
                Stream.FRandRange(-RotationJitter, RotationJitter),
                Stream.FRandRange(-RotationJitter, RotationJitter),
                Stream.FRandRange(-RotationJitter, RotationJitter) * 0.5f);
            Copy.Effect.Output = FMath::Clamp(Copy.Effect.Output * OutputScale, 0.0f, 1.0f);
            Copy.RelativeTransform.AddToTranslation(Nudge);
            Copy.RelativeTransform.SetRotation((Aim.Quaternion() * Copy.RelativeTransform.GetRotation()).GetNormalized());

            const FString SourceLabel = Copy.Label.ToString();
            if (!SourceCueLabel.IsEmpty() && SourceLabel.StartsWith(SourceCueLabel))
            {
                Copy.Label = FText::FromString(Cue.Label.ToString() + SourceLabel.RightChop(SourceCueLabel.Len()));
            }
            else if (!SourceLabel.IsEmpty())
            {
                Copy.Label = FText::Format(
                    NSLOCTEXT("InfinityStage", "ReplicatedEffectLabel", "{0} — {1}"),
                    Cue.Label,
                    Copy.Label);
            }
            Cue.WingPair.Attachments.Add(MoveTemp(Copy));
            ++Placed;
        }
    }

    UE_LOG(
        LogInfinityStageEffectAuthoring,
        Display,
        TEXT("INFINITY_STAGE_EFFECTS_REPLICATED source=%s sources=%d removed=%d placed=%d seed=%d; written to the Show, save it intentionally."),
        *SourceCueGuid.ToString(EGuidFormats::DigitsWithHyphens),
        Sources.Num(),
        Removed,
        Placed,
        Variation.Seed);
    return Placed;
}
