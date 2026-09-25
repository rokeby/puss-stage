#include "InfinityStageWingAuditProxy.h"

void UInfinityStageWingAuditProxy::Initialize(UInfinityStageWingLibraryAsset* InLibrary, const FGuid InEntryGuid)
{
    Library = InLibrary;
    EntryGuid = InEntryGuid;
    if (InLibrary)
    {
        if (const FInfinityWingAssetEntry* Found = InLibrary->Entries.FindByPredicate(
            [InEntryGuid](const FInfinityWingAssetEntry& Candidate) { return Candidate.EntryGuid == InEntryGuid; }))
        {
            Entry = *Found;
        }
    }
}

void UInfinityStageWingAuditProxy::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    if (UInfinityStageWingLibraryAsset* Asset = Library.Get())
    {
        if (FInfinityWingAssetEntry* Found = Asset->Entries.FindByPredicate(
            [this](const FInfinityWingAssetEntry& Candidate) { return Candidate.EntryGuid == EntryGuid; }))
        {
            Asset->Modify();
            *Found = Entry;
            Found->EntryGuid = EntryGuid;
            Asset->MarkPackageDirty();
            OnChanged.ExecuteIfBound();
        }
    }
}

void UInfinityStageWingAuditProxy::PostEditUndo()
{
    Super::PostEditUndo();
    OnChanged.ExecuteIfBound();
}
