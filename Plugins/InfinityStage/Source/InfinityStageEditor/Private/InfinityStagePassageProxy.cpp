#include "InfinityStagePassageProxy.h"

#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"

void UInfinityStagePassageProxy::Initialize(UInfinityStageShowAsset* InAsset, const FGuid InPassageGuid)
{
    Asset = InAsset;
    PassageGuid = InPassageGuid;
    RailGuid.Invalidate();
    bApplying = true;
    Passage = FInfinityPassageSettings();
    MusicRail = FInfinityMusicRail();

    if (InAsset)
    {
        if (const FInfinityPassageSettings* SourcePassage = InAsset->PassageSettings.FindByPredicate(
            [InPassageGuid](const FInfinityPassageSettings& Candidate)
            {
                return Candidate.PassageGuid == InPassageGuid;
            }))
        {
            Passage = *SourcePassage;
            RailGuid = Passage.Music.PrimaryRailGuid;
            if (const FInfinityMusicRail* SourceRail = InAsset->MusicRails.FindByPredicate(
                [this](const FInfinityMusicRail& Candidate)
                {
                    return Candidate.RailGuid == RailGuid;
                }))
            {
                MusicRail = *SourceRail;
            }
        }
    }
    RefreshDerived();
    bApplying = false;
}

void UInfinityStagePassageProxy::RefreshDerived()
{
    UsedMusicSeconds = 0.0;
    CurrentWingPairCount = 0;
    CurrentRouteDistanceCm = 0.0;
    ApparentCelestialCycles = 0.0;
    if (!Asset.IsValid())
    {
        return;
    }

    const double TickRate = Asset->TickResolution.AsDecimal();
    if (TickRate > 0.0 && MusicRail.SourceOutFrame > MusicRail.SourceInFrame)
    {
        UsedMusicSeconds = (MusicRail.SourceOutFrame - MusicRail.SourceInFrame).Value / TickRate;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Asset);
    if (const FInfinityCompiledPassage* CompiledPassage = Compiled.Passages.FindByPredicate(
        [this](const FInfinityCompiledPassage& Candidate)
        {
            return Candidate.PassageGuid == PassageGuid;
        }))
    {
        CurrentWingPairCount = CompiledPassage->Wings.Num();
        CurrentRouteDistanceCm = CompiledPassage->TotalDistanceCm;
        const double PassageSeconds = TickRate > 0.0
            ? (CompiledPassage->SegmentEndFrame.Value - CompiledPassage->SegmentStartFrame.Value) / TickRate
            : 0.0;
        if (Passage.CelestialCycle.bAnimate && Passage.CelestialCycle.CycleDurationSeconds > 0.0)
        {
            ApparentCelestialCycles = PassageSeconds
                * FMath::Max(0.0, Passage.CelestialCycle.CycleRateMultiplier)
                / Passage.CelestialCycle.CycleDurationSeconds;
        }
    }
}

void UInfinityStagePassageProxy::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    if (bApplying || !Asset.IsValid())
    {
        return;
    }

    Asset->Modify();
    if (FInfinityPassageSettings* TargetPassage = Asset->PassageSettings.FindByPredicate(
        [this](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == PassageGuid;
        }))
    {
        const FGuid StableGuid = TargetPassage->PassageGuid;
        const FGuid StableFirst = TargetPassage->FirstCueGuid;
        const FGuid StableLast = TargetPassage->LastCueGuid;
        *TargetPassage = Passage;
        TargetPassage->PassageGuid = StableGuid;
        TargetPassage->FirstCueGuid = StableFirst;
        TargetPassage->LastCueGuid = StableLast;
        Passage = *TargetPassage;
        RailGuid = TargetPassage->Music.PrimaryRailGuid;
    }
    if (FInfinityMusicRail* TargetRail = Asset->MusicRails.FindByPredicate(
        [this](const FInfinityMusicRail& Candidate)
        {
            return Candidate.RailGuid == RailGuid;
        }))
    {
        const FGuid StableRailGuid = TargetRail->RailGuid;
        *TargetRail = MusicRail;
        TargetRail->RailGuid = StableRailGuid;
        MusicRail = *TargetRail;
    }
    Asset->EnsureStableIds();
    Asset->ReconcilePassageSettings();
    Asset->MarkPackageDirty();
    RefreshDerived();
    OnChanged.ExecuteIfBound();
}

void UInfinityStagePassageProxy::PostEditUndo()
{
    Super::PostEditUndo();
    RefreshDerived();
    OnChanged.ExecuteIfBound();
}
