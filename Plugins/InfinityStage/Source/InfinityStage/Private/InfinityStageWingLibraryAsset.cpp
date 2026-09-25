#include "InfinityStageWingLibraryAsset.h"

UInfinityStageWingLibraryAsset::UInfinityStageWingLibraryAsset()
{
    EnsureStableIds();
}

void UInfinityStageWingLibraryAsset::EnsureStableIds()
{
    if (!LibraryGuid.IsValid())
    {
        LibraryGuid = FGuid::NewGuid();
    }
    for (FInfinityWingAssetEntry& Entry : Entries)
    {
        if (!Entry.EntryGuid.IsValid())
        {
            Entry.EntryGuid = FGuid::NewGuid();
        }
    }
}

FInfinityWingAssetEntry* UInfinityStageWingLibraryAsset::FindEntry(const FSoftObjectPath& MeshPath)
{
    return Entries.FindByPredicate([&MeshPath](const FInfinityWingAssetEntry& Entry)
    {
        return Entry.Mesh.ToSoftObjectPath() == MeshPath;
    });
}

const FInfinityWingAssetEntry* UInfinityStageWingLibraryAsset::FindEntry(const FSoftObjectPath& MeshPath) const
{
    return Entries.FindByPredicate([&MeshPath](const FInfinityWingAssetEntry& Entry)
    {
        return Entry.Mesh.ToSoftObjectPath() == MeshPath;
    });
}

FPrimaryAssetId UInfinityStageWingLibraryAsset::GetPrimaryAssetId() const
{
    return FPrimaryAssetId(TEXT("InfinityStageWingLibrary"), GetFName());
}

void UInfinityStageWingLibraryAsset::PostLoad()
{
    Super::PostLoad();
    EnsureStableIds();
}
