#pragma once

#include "CoreMinimal.h"
#include "InfinityStageWingAuditProxy.h"
#include "InfinityStageWingAssetAuditor.h"
#include "InfinityStageWingLibraryAsset.h"
#include "UObject/StrongObjectPtr.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Views/SListView.h"

class IDetailsView;
struct FInfinityWingAuditListItem
{
    FGuid EntryGuid;
};

class SInfinityStageWingAudit final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageWingAudit) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    using FItem = TSharedPtr<FInfinityWingAuditListItem>;

    TSharedRef<ITableRow> GenerateRow(FItem Item, const TSharedRef<STableViewBase>& OwnerTable);
    void HandleSelection(FItem Item, ESelectInfo::Type SelectInfo);
    TSharedRef<SWidget> BuildActionsMenu();
    void ScanAssets();
    void ApplySafeCorrections();
    void RevertSelected();
    void SyncSelectedAsset();
    void RefreshItems(bool bPreserveSelection = true);
    void HandleSearchChanged(const FText& Text);
    FText GetStatusText() const;
    const FInfinityWingAssetEntry* FindEntry(FGuid EntryGuid) const;

    TWeakObjectPtr<UInfinityStageWingLibraryAsset> Library;
    TArray<FItem> Items;
    TArray<FItem> FilteredItems;
    TSharedPtr<SListView<FItem>> ListView;
    TSharedPtr<IDetailsView> DetailsView;
    TStrongObjectPtr<UInfinityStageWingAuditProxy> Proxy;
    FString SearchText;
    FInfinityWingAuditSummary Summary;
    FString LastMessage;
};
