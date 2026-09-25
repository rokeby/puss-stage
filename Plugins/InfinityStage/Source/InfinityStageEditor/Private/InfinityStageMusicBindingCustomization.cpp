#include "InfinityStageMusicBindingCustomization.h"

#include "ContentBrowserModule.h"
#include "DetailWidgetRow.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "IContentBrowserSingleton.h"
#include "IDetailChildrenBuilder.h"
#include "InfinityStageCueProxy.h"
#include "InfinityStagePassageProxy.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTypes.h"
#include "Modules/ModuleManager.h"
#include "PropertyHandle.h"
#include "ScopedTransaction.h"
#include "Sound/SoundBase.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "InfinityStageMusicBinding"

namespace
{
const TCHAR* PrimaryGuidName = TEXT("PrimaryRailGuid");
const TCHAR* SecondaryGuidName = TEXT("SecondaryRailGuid");

/** Reads/writes an FGuid property through its handle's raw data. */
FGuid ReadGuid(const TSharedRef<IPropertyHandle>& Handle)
{
    TArray<void*> RawData;
    Handle->AccessRawData(RawData);
    return (RawData.Num() == 1 && RawData[0]) ? *static_cast<FGuid*>(RawData[0]) : FGuid();
}
}

TSharedRef<IPropertyTypeCustomization> FInfinityStageMusicBindingCustomization::MakeInstance()
{
    return MakeShared<FInfinityStageMusicBindingCustomization>();
}

UInfinityStageShowAsset* FInfinityStageMusicBindingCustomization::ResolveShow(
    const TSharedRef<IPropertyHandle>& Handle) const
{
    TArray<UObject*> Outers;
    Handle->GetOuterObjects(Outers);
    for (UObject* Outer : Outers)
    {
        if (const UInfinityStageCueProxy* CueProxy = Cast<UInfinityStageCueProxy>(Outer))
        {
            return CueProxy->GetShowAsset();
        }
        if (const UInfinityStagePassageProxy* PassageProxy = Cast<UInfinityStagePassageProxy>(Outer))
        {
            return PassageProxy->GetShowAsset();
        }
        // The Show Asset edited directly is also a valid context.
        if (UInfinityStageShowAsset* Show = Cast<UInfinityStageShowAsset>(Outer))
        {
            return Show;
        }
    }
    return nullptr;
}

FText FInfinityStageMusicBindingCustomization::GetRailLabel(TSharedRef<IPropertyHandle> GuidHandle) const
{
    const FGuid Current = ReadGuid(GuidHandle);
    if (!Current.IsValid())
    {
        return LOCTEXT("NoRail", "None");
    }
    const UInfinityStageShowAsset* Show = ResolveShow(GuidHandle);
    if (!Show)
    {
        return LOCTEXT("UnknownShow", "Rail set (Show not resolved)");
    }
    const FInfinityMusicRail* Rail = Show->MusicRails.FindByPredicate(
        [Current](const FInfinityMusicRail& Candidate) { return Candidate.RailGuid == Current; });
    if (!Rail)
    {
        // A dangling GUID plays nothing; saying so beats rendering silence.
        return LOCTEXT("MissingRail", "Missing rail — not in this Show");
    }
    return Rail->Label.IsEmpty()
        ? LOCTEXT("UnnamedRail", "(unnamed rail)")
        : Rail->Label;
}

void FInfinityStageMusicBindingCustomization::SetRail(
    TSharedRef<IPropertyHandle> GuidHandle,
    const FGuid RailGuid)
{
    TArray<UObject*> Outers;
    GuidHandle->GetOuterObjects(Outers);
    const FScopedTransaction Transaction(LOCTEXT("SetRailTransaction", "Set Infinity Stage Music Rail"));
    for (UObject* Outer : Outers)
    {
        if (Outer)
        {
            Outer->Modify();
        }
    }
    GuidHandle->NotifyPreChange();
    TArray<void*> RawData;
    GuidHandle->AccessRawData(RawData);
    for (void* Data : RawData)
    {
        if (Data)
        {
            *static_cast<FGuid*>(Data) = RailGuid;
        }
    }
    GuidHandle->NotifyPostChange(EPropertyChangeType::ValueSet);
    GuidHandle->NotifyFinishedChangingProperties();
}

void FInfinityStageMusicBindingCustomization::CreateRailFromSelectedSound(
    TSharedRef<IPropertyHandle> GuidHandle)
{
    UInfinityStageShowAsset* Show = ResolveShow(GuidHandle);
    if (!Show)
    {
        return;
    }
    FContentBrowserModule& ContentBrowser =
        FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
    TArray<FAssetData> Selection;
    ContentBrowser.Get().GetSelectedAssets(Selection);

    USoundBase* Sound = nullptr;
    for (const FAssetData& Asset : Selection)
    {
        if (USoundBase* Candidate = Cast<USoundBase>(Asset.GetAsset()))
        {
            Sound = Candidate;
            break;
        }
    }
    if (!Sound)
    {
        return;
    }

    const FScopedTransaction Transaction(LOCTEXT("NewRailTransaction", "Add Infinity Stage Music Rail"));
    Show->Modify();
    FInfinityMusicRail& Rail = Show->MusicRails.AddDefaulted_GetRef();
    Rail.RailGuid = FGuid::NewGuid();
    Rail.Label = FText::FromString(Sound->GetName());
    Rail.Sound = Sound;
    SetRail(GuidHandle, Rail.RailGuid);
}

TSharedRef<SWidget> FInfinityStageMusicBindingCustomization::BuildRailMenu(
    TSharedRef<IPropertyHandle> GuidHandle)
{
    FMenuBuilder MenuBuilder(true, nullptr);
    const UInfinityStageShowAsset* Show = ResolveShow(GuidHandle);

    MenuBuilder.AddMenuEntry(
        LOCTEXT("ClearRail", "None"),
        LOCTEXT("ClearRailTip", "Play no music for this binding."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateLambda(
            [this, GuidHandle]() { SetRail(GuidHandle, FGuid()); })));

    if (Show && !Show->MusicRails.IsEmpty())
    {
        MenuBuilder.BeginSection(TEXT("Rails"), LOCTEXT("RailsSection", "Show Music Rails"));
        for (const FInfinityMusicRail& Rail : Show->MusicRails)
        {
            const FGuid RailGuid = Rail.RailGuid;
            const FText Label = Rail.Label.IsEmpty()
                ? LOCTEXT("UnnamedRailEntry", "(unnamed rail)")
                : Rail.Label;
            MenuBuilder.AddMenuEntry(
                Label,
                FText::FromString(Rail.Sound.ToSoftObjectPath().GetAssetName()),
                FSlateIcon(),
                FUIAction(
                    FExecuteAction::CreateLambda(
                        [this, GuidHandle, RailGuid]() { SetRail(GuidHandle, RailGuid); }),
                    FCanExecuteAction(),
                    FIsActionChecked::CreateLambda(
                        [GuidHandle, RailGuid]() { return ReadGuid(GuidHandle) == RailGuid; })),
                NAME_None,
                EUserInterfaceActionType::RadioButton);
        }
        MenuBuilder.EndSection();
    }

    MenuBuilder.AddSeparator();
    MenuBuilder.AddMenuEntry(
        LOCTEXT("NewRailFromSelection", "New Rail from Content Browser Selection"),
        LOCTEXT(
            "NewRailFromSelectionTip",
            "Add a Music Rail to this Show from the Sound currently selected in the Content Browser, and bind it here."),
        FSlateIcon(),
        FUIAction(FExecuteAction::CreateLambda(
            [this, GuidHandle]() { CreateRailFromSelectedSound(GuidHandle); })));

    return MenuBuilder.MakeWidget();
}

TSharedRef<SWidget> FInfinityStageMusicBindingCustomization::BuildRailRow(
    TSharedRef<IPropertyHandle> GuidHandle)
{
    return SNew(SComboButton)
        .OnGetMenuContent(this, &FInfinityStageMusicBindingCustomization::BuildRailMenu, GuidHandle)
        .ContentPadding(2.0f)
        .ButtonContent()
        [
            SNew(STextBlock)
            .Text(this, &FInfinityStageMusicBindingCustomization::GetRailLabel, GuidHandle)
        ];
}

void FInfinityStageMusicBindingCustomization::CustomizeHeader(
    TSharedRef<IPropertyHandle> PropertyHandle,
    FDetailWidgetRow& HeaderRow,
    IPropertyTypeCustomizationUtils& CustomizationUtils)
{
    HeaderRow
        .NameContent()[PropertyHandle->CreatePropertyNameWidget()]
        .ValueContent()
        .MinDesiredWidth(220.0f)
        [
            SNew(STextBlock).Text(LOCTEXT("BindingSummary", "Music rail binding"))
        ];
}

void FInfinityStageMusicBindingCustomization::CustomizeChildren(
    TSharedRef<IPropertyHandle> PropertyHandle,
    IDetailChildrenBuilder& ChildBuilder,
    IPropertyTypeCustomizationUtils& CustomizationUtils)
{
    uint32 ChildCount = 0;
    PropertyHandle->GetNumChildren(ChildCount);
    for (uint32 Index = 0; Index < ChildCount; ++Index)
    {
        const TSharedPtr<IPropertyHandle> Child = PropertyHandle->GetChildHandle(Index);
        if (!Child.IsValid())
        {
            continue;
        }
        const FName ChildName = Child->GetProperty() ? Child->GetProperty()->GetFName() : NAME_None;
        if (ChildName == PrimaryGuidName || ChildName == SecondaryGuidName)
        {
            // Swap the raw GUID entry for a rail picker.
            ChildBuilder.AddCustomRow(Child->GetPropertyDisplayName())
                .NameContent()[Child->CreatePropertyNameWidget()]
                .ValueContent()
                .MinDesiredWidth(220.0f)
                [
                    BuildRailRow(Child.ToSharedRef())
                ];
            continue;
        }
        ChildBuilder.AddProperty(Child.ToSharedRef());
    }
}

#undef LOCTEXT_NAMESPACE
