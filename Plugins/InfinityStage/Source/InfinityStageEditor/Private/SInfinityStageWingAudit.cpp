#include "SInfinityStageWingAudit.h"

#include "ContentBrowserModule.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "IContentBrowserSingleton.h"
#include "InfinityStageWingAuditProxy.h"
#include "InfinityStageWingLibraryAsset.h"
#include "Misc/MessageDialog.h"
#include "PropertyEditorModule.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Input/SSearchBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"

namespace
{
FText RoleText(const EInfinityWingAssetRole Role)
{
    return StaticEnum<EInfinityWingAssetRole>()->GetDisplayNameTextByValue(static_cast<int64>(Role));
}

FText StatusText(const EInfinityWingAuditStatus Status)
{
    return StaticEnum<EInfinityWingAuditStatus>()->GetDisplayNameTextByValue(static_cast<int64>(Status));
}

class SInfinityWingAuditRow final : public SMultiColumnTableRow<TSharedPtr<FInfinityWingAuditListItem>>
{
public:
    SLATE_BEGIN_ARGS(SInfinityWingAuditRow) {}
        SLATE_ARGUMENT(TSharedPtr<FInfinityWingAuditListItem>, Item)
        SLATE_ARGUMENT(TWeakObjectPtr<UInfinityStageWingLibraryAsset>, Library)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& Owner)
    {
        Item = InArgs._Item;
        Library = InArgs._Library;
        SMultiColumnTableRow::Construct(FSuperRowType::FArguments().Padding(FMargin(3.0f, 1.0f)), Owner);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        const FInfinityWingAssetEntry* Entry = Library.IsValid() && Item.IsValid()
            ? Library->Entries.FindByPredicate([this](const FInfinityWingAssetEntry& Candidate)
                { return Candidate.EntryGuid == Item->EntryGuid; })
            : nullptr;
        if (!Entry)
        {
            return SNew(STextBlock).Text(FText::GetEmpty());
        }
        if (ColumnName == TEXT("Status")) return SNew(STextBlock).Text(StatusText(Entry->Status));
        if (ColumnName == TEXT("Role")) return SNew(STextBlock).Text(RoleText(Entry->Role));
        if (ColumnName == TEXT("Asset")) return SNew(STextBlock).Text(FText::FromString(Entry->Mesh.GetAssetName()));
        if (ColumnName == TEXT("Bounds"))
        {
            const FVector Size = Entry->bGeometryCanonical ? Entry->CanonicalBoundsSizeCm : Entry->OriginalBoundsSizeCm;
            return SNew(STextBlock).Text(FText::FromString(FString::Printf(
                TEXT("%.2f × %.2f × %.2f m"), Size.X / 100.0, Size.Y / 100.0, Size.Z / 100.0)));
        }
        if (ColumnName == TEXT("Axis"))
        {
            return SNew(STextBlock).Text(StaticEnum<EInfinityWingThicknessAxis>()->GetDisplayNameTextByValue(
                static_cast<int64>(Entry->OriginalThicknessAxis)));
        }
        const FString Correction = Entry->bGeometryCanonical
            ? TEXT("Canonical")
            : Entry->bSafeToApplyAutomatically
                ? (Entry->bMirroredForOutsideTallEdge ? TEXT("Axis / pivot / scale / outside edge") : TEXT("Axis / pivot / scale"))
                : TEXT("Artist review");
        return SNew(STextBlock).Text(FText::FromString(Correction));
    }

private:
    TSharedPtr<FInfinityWingAuditListItem> Item;
    TWeakObjectPtr<UInfinityStageWingLibraryAsset> Library;
};
}

void SInfinityStageWingAudit::Construct(const FArguments& InArgs)
{
    Library = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
    FPropertyEditorModule& PropertyEditor = FModuleManager::LoadModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
    FDetailsViewArgs DetailsArgs;
    DetailsArgs.bAllowSearch = true;
    DetailsArgs.bHideSelectionTip = true;
    DetailsArgs.NameAreaSettings = FDetailsViewArgs::HideNameArea;
    DetailsView = PropertyEditor.CreateDetailView(DetailsArgs);
    DetailsView->SetObject(nullptr);

    ChildSlot
    [
        SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(4.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1.0f)
            [
                SNew(SSearchBox).HintText(NSLOCTEXT("InfinityStage", "WingAuditSearch", "Search assets or roles"))
                .OnTextChanged(this, &SInfinityStageWingAudit::HandleSearchChanged)
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(4.0f, 0.0f)
            [
                SNew(SComboButton)
                .ButtonContent()[SNew(STextBlock).Text(NSLOCTEXT("InfinityStage", "WingAuditActions", "Actions"))]
                .MenuContent()[BuildActionsMenu()]
            ]
        ]
        + SVerticalBox::Slot().FillHeight(1.0f)
        [
            SNew(SSplitter)
            .PhysicalSplitterHandleSize(6.0f)
            + SSplitter::Slot().Value(0.74f)
            [
                SAssignNew(ListView, SListView<FItem>)
                .ListItemsSource(&FilteredItems)
                .SelectionMode(ESelectionMode::Multi)
                .OnGenerateRow(this, &SInfinityStageWingAudit::GenerateRow)
                .OnSelectionChanged(this, &SInfinityStageWingAudit::HandleSelection)
                .HeaderRow
                (
                    SNew(SHeaderRow)
                    + SHeaderRow::Column(TEXT("Status")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditStatus", "Status")).FixedWidth(92.0f)
                    + SHeaderRow::Column(TEXT("Role")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditRole", "Role")).FixedWidth(140.0f)
                    + SHeaderRow::Column(TEXT("Asset")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditAsset", "Wing Asset")).FillWidth(1.0f)
                    + SHeaderRow::Column(TEXT("Bounds")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditBounds", "Bounds")).FixedWidth(155.0f)
                    + SHeaderRow::Column(TEXT("Axis")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditAxis", "Depth Axis")).FixedWidth(76.0f)
                    + SHeaderRow::Column(TEXT("Correction")).DefaultLabel(NSLOCTEXT("InfinityStage", "AuditCorrection", "Correction")).FixedWidth(210.0f)
                )
            ]
            + SSplitter::Slot().Value(0.26f).MinSize(220.0f)[DetailsView.ToSharedRef()]
        ]
        + SVerticalBox::Slot().AutoHeight()
        [
            SNew(SBorder).Padding(FMargin(8.0f, 4.0f))[SNew(STextBlock).Text(this, &SInfinityStageWingAudit::GetStatusText)]
        ]
    ];
    RefreshItems(false);
}

TSharedRef<ITableRow> SInfinityStageWingAudit::GenerateRow(FItem Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SInfinityWingAuditRow, OwnerTable).Item(Item).Library(Library);
}

void SInfinityStageWingAudit::HandleSelection(FItem Item, ESelectInfo::Type)
{
    Proxy.Reset();
    if (!Item.IsValid() || !Library.IsValid())
    {
        DetailsView->SetObject(nullptr, true);
        return;
    }
    Proxy = TStrongObjectPtr<UInfinityStageWingAuditProxy>(
        NewObject<UInfinityStageWingAuditProxy>(GetTransientPackage(), NAME_None, RF_Transactional));
    Proxy->Initialize(Library.Get(), Item->EntryGuid);
    Proxy->OnChanged.BindLambda([this]()
    {
        if (ListView.IsValid()) ListView->RequestListRefresh();
    });
    DetailsView->SetObject(Proxy.Get(), true);
}

TSharedRef<SWidget> SInfinityStageWingAudit::BuildActionsMenu()
{
    FMenuBuilder Menu(true, nullptr);
    Menu.AddMenuEntry(NSLOCTEXT("InfinityStage", "ScanWingAssets", "Scan / Refresh Audit"), FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageWingAudit::ScanAssets)));
    Menu.AddMenuEntry(NSLOCTEXT("InfinityStage", "ApplySafeWingCorrections", "Apply All Safe Corrections"),
        NSLOCTEXT("InfinityStage", "ApplySafeWingCorrectionsTip", "Modify original Static Mesh source geometry only where axis, scale, pivot and outside-edge correction are deterministic."),
        FSlateIcon(), FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageWingAudit::ApplySafeCorrections)));
    Menu.AddSeparator();
    Menu.AddMenuEntry(NSLOCTEXT("InfinityStage", "RevertWingCorrections", "Revert Selected Corrections"), FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageWingAudit::RevertSelected)));
    Menu.AddMenuEntry(NSLOCTEXT("InfinityStage", "SyncWingAsset", "Show Selected in Content Browser"), FText::GetEmpty(), FSlateIcon(),
        FUIAction(FExecuteAction::CreateSP(this, &SInfinityStageWingAudit::SyncSelectedAsset)));
    return Menu.MakeWidget();
}

void SInfinityStageWingAudit::ScanAssets()
{
    FString Error;
    if (!Library.IsValid() || !FInfinityStageWingAssetAuditor::Scan(*Library, Summary, Error))
    {
        LastMessage = Error.IsEmpty() ? TEXT("Audit completed with errors.") : Error;
    }
    else
    {
        LastMessage = FString::Printf(TEXT("Audit complete · report: %s"), *Summary.ReportPath);
    }
    RefreshItems(false);
}

void SInfinityStageWingAudit::ApplySafeCorrections()
{
    int32 CorrectionCount = 0;
    if (Library.IsValid())
    {
        for (const FInfinityWingAssetEntry& Entry : Library->Entries)
        {
            CorrectionCount += Entry.bSafeToApplyAutomatically && !Entry.bGeometryCanonical ? 1 : 0;
        }
    }
    if (CorrectionCount == 0)
    {
        LastMessage = TEXT("No safe corrections are pending.");
        return;
    }
    const FText Confirmation = FText::Format(
        NSLOCTEXT("InfinityStage", "ConfirmWingCorrections", "Back up and rewrite {0} original Static Mesh assets? Close other Unreal Editor instances for this project first."),
        FText::AsNumber(CorrectionCount));
    if (FMessageDialog::Open(EAppMsgType::YesNo, Confirmation) != EAppReturnType::Yes)
    {
        LastMessage = TEXT("Correction pass cancelled.");
        return;
    }
    FString Error;
    if (!Library.IsValid() || !FInfinityStageWingAssetAuditor::ApplySafeCorrections(*Library, Summary, Error))
    {
        LastMessage = Error.IsEmpty() ? TEXT("Correction pass completed with errors.") : Error;
    }
    else
    {
        LastMessage = TEXT("Safe canonical corrections applied and saved.");
    }
    RefreshItems(false);
}

void SInfinityStageWingAudit::RevertSelected()
{
    TSet<FGuid> Guids;
    for (const FItem& Item : ListView->GetSelectedItems()) if (Item.IsValid()) Guids.Add(Item->EntryGuid);
    FString Error;
    if (!Library.IsValid() || !FInfinityStageWingAssetAuditor::RevertCorrections(*Library, Guids, Error))
    {
        LastMessage = Error;
    }
    else
    {
        LastMessage = TEXT("Selected canonical corrections reverted.");
    }
    RefreshItems(false);
}

void SInfinityStageWingAudit::SyncSelectedAsset()
{
    if (!ListView.IsValid() || ListView->GetSelectedItems().IsEmpty()) return;
    const FInfinityWingAssetEntry* Entry = FindEntry(ListView->GetSelectedItems()[0]->EntryGuid);
    UObject* Asset = Entry ? Entry->Mesh.LoadSynchronous() : nullptr;
    if (Asset)
    {
        TArray<UObject*> AssetsToSync;
        AssetsToSync.Add(Asset);
        FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"))
            .Get().SyncBrowserToAssets(AssetsToSync);
    }
}

void SInfinityStageWingAudit::RefreshItems(const bool bPreserveSelection)
{
    const FGuid Selected = bPreserveSelection && ListView.IsValid() && !ListView->GetSelectedItems().IsEmpty()
        ? ListView->GetSelectedItems()[0]->EntryGuid : FGuid();
    Items.Reset();
    FilteredItems.Reset();
    if (Library.IsValid())
    {
        for (const FInfinityWingAssetEntry& Entry : Library->Entries)
        {
            FItem Item = MakeShared<FInfinityWingAuditListItem>();
            Item->EntryGuid = Entry.EntryGuid;
            Items.Add(Item);
            const FString Haystack = Entry.Mesh.GetAssetName() + TEXT(" ") + RoleText(Entry.Role).ToString();
            if (SearchText.IsEmpty() || Haystack.Contains(SearchText, ESearchCase::IgnoreCase))
            {
                FilteredItems.Add(Item);
            }
        }
    }
    if (ListView.IsValid())
    {
        ListView->RequestListRefresh();
        if (Selected.IsValid())
        {
            if (const FItem* Found = FilteredItems.FindByPredicate([Selected](const FItem& Item) { return Item->EntryGuid == Selected; }))
            {
                ListView->SetSelection(*Found);
            }
        }
    }
}

void SInfinityStageWingAudit::HandleSearchChanged(const FText& Text)
{
    SearchText = Text.ToString();
    RefreshItems(true);
}

FText SInfinityStageWingAudit::GetStatusText() const
{
    const FString Base = Summary.Total > 0 ? Summary.ToString() : FString::Printf(TEXT("%d assets in library"), Items.Num());
    return FText::FromString(LastMessage.IsEmpty() ? Base : Base + TEXT("  |  ") + LastMessage);
}

const FInfinityWingAssetEntry* SInfinityStageWingAudit::FindEntry(const FGuid EntryGuid) const
{
    return Library.IsValid()
        ? Library->Entries.FindByPredicate([EntryGuid](const FInfinityWingAssetEntry& Entry) { return Entry.EntryGuid == EntryGuid; })
        : nullptr;
}
