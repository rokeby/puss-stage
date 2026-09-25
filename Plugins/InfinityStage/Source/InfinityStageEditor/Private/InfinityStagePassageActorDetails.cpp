#include "InfinityStagePassageActorDetails.h"

#include "Components/SplineComponent.h"
#include "DetailCategoryBuilder.h"
#include "DetailLayoutBuilder.h"
#include "DetailWidgetRow.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Framework/Notifications/NotificationManager.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageShowAsset.h"
#include "ScopedTransaction.h"
#include "Subsystems/EditorActorSubsystem.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Notifications/SNotificationList.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "InfinityStagePassageActorDetails"

namespace
{
void ShowNotification(const FText& Message, const bool bSuccess, const float ExpireSeconds = 6.0f)
{
    FNotificationInfo Info(Message);
    Info.ExpireDuration = ExpireSeconds;
    Info.bFireAndForget = true;
    const TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info);
    if (Item.IsValid())
    {
        Item->SetCompletionState(bSuccess ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
    }
}

/** Offers Scene handoff matching as an explicit action: it writes to the Scene
 * sequences, and silently dirtying them would blur the mutation boundary. */
void OfferSceneHandoffMatch(UInfinityStageShowAsset* Show)
{
    if (!Show || !GEditor)
    {
        return;
    }

    FNotificationInfo Info(LOCTEXT(
        "RouteHandoffPrompt",
        "Route materialized. Passage endpoint framing may have moved — re-match the Scene cameras?"));
    Info.ExpireDuration = 20.0f;
    Info.bFireAndForget = false;

    TWeakObjectPtr<UInfinityStageShowAsset> WeakShow(Show);
    TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info);
    if (!Item.IsValid())
    {
        return;
    }

    TWeakPtr<SNotificationItem> WeakItem(Item);
    Item->SetCompletionState(SNotificationItem::CS_Pending);
    Item->SetHyperlink(
        FSimpleDelegate::CreateLambda([WeakShow, WeakItem]()
        {
            UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
            if (!WeakShow.IsValid() || !World)
            {
                return;
            }
            const FScopedTransaction Transaction(
                LOCTEXT("RouteMatchHandoffTransaction", "Match Infinity Stage Scene Camera Handoffs"));
            FString Report;
            const bool bMatched = FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(
                *WeakShow.Get(), *World, TArray<FGuid>(), Report);
            UE_LOG(
                LogTemp,
                Display,
                TEXT("INFINITY_STAGE_ROUTE_HANDOFF_MATCH ok=%d report=%s"),
                bMatched ? 1 : 0,
                *Report);
            if (const TSharedPtr<SNotificationItem> Pinned = WeakItem.Pin())
            {
                Pinned->SetCompletionState(bMatched ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
                Pinned->SetText(bMatched
                    ? LOCTEXT("RouteHandoffDone", "Scene camera handoffs re-matched. Affected sequences are dirty — save them intentionally.")
                    : LOCTEXT("RouteHandoffFailed", "Scene camera handoff matching failed. See the Output Log."));
                Pinned->SetHyperlink(FSimpleDelegate());
                Pinned->ExpireAndFadeout();
            }
        }),
        LOCTEXT("RouteMatchHandoffLink", "Match All Scenes"));
}
}

TSharedRef<IDetailCustomization> FInfinityStagePassageActorDetails::MakeInstance()
{
    return MakeShared<FInfinityStagePassageActorDetails>();
}

AInfinityStagePassageActor* FInfinityStagePassageActorDetails::GetSelectedActor() const
{
    // Route editing is deliberately single-actor: each Passage has its own
    // compiled length, so a multi-selection has no single correct route.
    return SelectedActors.Num() == 1 ? SelectedActors[0].Get() : nullptr;
}

bool FInfinityStagePassageActorDetails::IsAutoFitEnabled() const
{
    const AInfinityStagePassageActor* Actor = GetSelectedActor();
    return Actor && Actor->bAutoFitStraightRoute;
}

bool FInfinityStagePassageActorDetails::IsRouteShort() const
{
    const AInfinityStagePassageActor* Actor = GetSelectedActor();
    double RequiredCm = 0.0;
    double CurrentCm = 0.0;
    return Actor
        && Actor->GetRouteLengthStatus(RequiredCm, CurrentCm)
        && CurrentCm + UE_KINDA_SMALL_NUMBER < RequiredCm;
}

FText FInfinityStagePassageActorDetails::GetRouteStatusText() const
{
    const AInfinityStagePassageActor* Actor = GetSelectedActor();
    if (!Actor)
    {
        return LOCTEXT("RouteStatusMultiple", "Select a single Passage Actor to edit its route.");
    }

    double RequiredCm = 0.0;
    double CurrentCm = 0.0;
    if (!Actor->GetRouteLengthStatus(RequiredCm, CurrentCm))
    {
        return LOCTEXT("RouteStatusNoCompile", "No compiled Passage. Assign a Show Asset and a valid Passage GUID.");
    }

    const FText Lengths = FText::Format(
        LOCTEXT("RouteStatusLengths", "Route {0} cm  ·  required {1} cm"),
        FText::AsNumber(FMath::RoundToInt(CurrentCm)),
        FText::AsNumber(FMath::RoundToInt(RequiredCm)));

    if (Actor->bAutoFitStraightRoute)
    {
        return FText::Format(
            LOCTEXT("RouteStatusAutoFit", "{0}\nAuto Fit is ON — materializing will replace the route with a straight line."),
            Lengths);
    }
    if (CurrentCm + UE_KINDA_SMALL_NUMBER < RequiredCm)
    {
        return FText::Format(
            LOCTEXT("RouteStatusShort", "{0}\nRoute is {1} cm short — materialization will refuse and keep the previous geometry."),
            Lengths,
            FText::AsNumber(FMath::RoundToInt(RequiredCm - CurrentCm)));
    }
    return FText::Format(
        LOCTEXT("RouteStatusReady", "{0}\nRoute is long enough. Shape it, then use Finish Route Edit."),
        Lengths);
}

FSlateColor FInfinityStagePassageActorDetails::GetRouteStatusColor() const
{
    if (!GetSelectedActor())
    {
        return FSlateColor::UseSubduedForeground();
    }
    if (IsAutoFitEnabled() || IsRouteShort())
    {
        return FSlateColor(FLinearColor(0.95f, 0.65f, 0.20f));
    }
    return FSlateColor(FLinearColor(0.45f, 0.90f, 0.55f));
}

FReply FInfinityStagePassageActorDetails::BeginRouteEdit()
{
    AInfinityStagePassageActor* Actor = GetSelectedActor();
    if (!Actor)
    {
        return FReply::Handled();
    }

    const FScopedTransaction Transaction(LOCTEXT("BeginRouteEditTransaction", "Begin Infinity Stage Route Edit"));
    Actor->Modify();
    const bool bWasAutoFit = Actor->bAutoFitStraightRoute;
    Actor->bAutoFitStraightRoute = false;

    if (GEditor && Actor->Route)
    {
        GEditor->SelectNone(false, true, false);
        GEditor->SelectActor(Actor, true, true, true);
        GEditor->SelectComponent(Actor->Route, true, true, true);
    }

    ShowNotification(
        bWasAutoFit
            ? LOCTEXT("BeginRouteEditDisabled", "Auto Fit disabled and the Route spline selected. Shape it in the viewport, then press Finish Route Edit.")
            : LOCTEXT("BeginRouteEditAlready", "Route spline selected. Shape it in the viewport, then press Finish Route Edit."),
        true);
    return FReply::Handled();
}

FReply FInfinityStagePassageActorDetails::ExtendRoute()
{
    AInfinityStagePassageActor* Actor = GetSelectedActor();
    if (!Actor)
    {
        return FReply::Handled();
    }

    const FScopedTransaction Transaction(LOCTEXT("ExtendRouteTransaction", "Extend Infinity Stage Route"));
    if (Actor->ExtendRouteToCompiledLength())
    {
        ShowNotification(LOCTEXT("ExtendRouteOk", "Route extended along its final tangent to the compiled length."), true);
    }
    else
    {
        ShowNotification(LOCTEXT("ExtendRouteNoop", "Route already covers the compiled length; nothing to extend."), true);
    }
    return FReply::Handled();
}

FReply FInfinityStagePassageActorDetails::FinishRouteEdit()
{
    AInfinityStagePassageActor* Actor = GetSelectedActor();
    if (!Actor)
    {
        return FReply::Handled();
    }

    if (Actor->bAutoFitStraightRoute)
    {
        ShowNotification(
            LOCTEXT("FinishRouteAutoFit", "Auto Fit is still enabled, so materializing would discard your curve. Press Edit Route first."),
            false);
        return FReply::Handled();
    }

    // Extend before materializing rather than letting the length guard refuse.
    if (IsRouteShort())
    {
        const FScopedTransaction Transaction(LOCTEXT("FinishRouteExtendTransaction", "Extend Infinity Stage Route"));
        Actor->ExtendRouteToCompiledLength();
    }
    if (IsRouteShort())
    {
        ShowNotification(
            LOCTEXT("FinishRouteStillShort", "Route could not be extended to the compiled length. Add a spline point at the end and retry."),
            false);
        return FReply::Handled();
    }

    const FScopedTransaction Transaction(LOCTEXT("FinishRouteEditTransaction", "Materialize Infinity Stage Passage"));
    if (!Actor->MaterializePassage())
    {
        ShowNotification(
            LOCTEXT("FinishRouteMaterializeFailed", "Materialization failed; the previous valid geometry was kept. See the Output Log."),
            false);
        return FReply::Handled();
    }

    UE_LOG(
        LogTemp,
        Display,
        TEXT("INFINITY_STAGE_ROUTE_EDIT_OK actor='%s' passage=%s wing_pairs=%d route_cm=%.1f"),
        *Actor->GetActorLabel(),
        *Actor->PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
        Actor->MaterializedWingPairCount,
        Actor->Route ? Actor->Route->GetSplineLength() : 0.0);

    OfferSceneHandoffMatch(Actor->ShowAsset);
    return FReply::Handled();
}

void FInfinityStagePassageActorDetails::CustomizeDetails(IDetailLayoutBuilder& DetailBuilder)
{
    TArray<TWeakObjectPtr<UObject>> Objects;
    DetailBuilder.GetObjectsBeingCustomized(Objects);
    SelectedActors.Reset();
    for (const TWeakObjectPtr<UObject>& Object : Objects)
    {
        if (AInfinityStagePassageActor* Actor = Cast<AInfinityStagePassageActor>(Object.Get()))
        {
            SelectedActors.Add(Actor);
        }
    }
    if (SelectedActors.IsEmpty())
    {
        return;
    }

    // Materialization output is diagnostic, not authoring data, and it is large:
    // a 93-pair Passage carries 279 panel records and 837 attachment actors, so
    // the default details view builds thousands of rows — including an asset
    // picker per attachment — and selecting the actor stalls for many seconds.
    // Summarise instead; the Show Asset remains the place to inspect authoring.
    {
        int32 PairCount = 0;
        int32 PanelCount = 0;
        int32 AttachmentCount = 0;
        int32 ComponentCount = 0;
        for (const TWeakObjectPtr<AInfinityStagePassageActor>& Actor : SelectedActors)
        {
            if (const AInfinityStagePassageActor* Passage = Actor.Get())
            {
                PairCount += Passage->MaterializedWingPairCount;
                PanelCount += Passage->MaterializedPanels.Num();
                AttachmentCount += Passage->ManagedAttachmentActors.Num();
                ComponentCount += Passage->ManagedComponents.Num();
            }
        }
        for (const TCHAR* PropertyName : {TEXT("MaterializedPanels"), TEXT("ManagedAttachmentActors"), TEXT("ManagedComponents")})
        {
            DetailBuilder.HideProperty(DetailBuilder.GetProperty(
                FName(PropertyName), AInfinityStagePassageActor::StaticClass()));
        }
        IDetailCategoryBuilder& MaterializationCategory = DetailBuilder.EditCategory(
            TEXT("Materialization"),
            LOCTEXT("MaterializationCategory", "Materialization"),
            ECategoryPriority::Uncommon);
        const FText Summary = FText::Format(
            LOCTEXT(
                "MaterializationSummary",
                "{0} wing pair(s) · {1} panel(s) · {2} attachment actor(s) · {3} instanced component(s)"),
            FText::AsNumber(PairCount),
            FText::AsNumber(PanelCount),
            FText::AsNumber(AttachmentCount),
            FText::AsNumber(ComponentCount));
        MaterializationCategory.AddCustomRow(LOCTEXT("MaterializationSummaryRow", "Materialization Summary"))
            .WholeRowContent()
            [
                SNew(SBox)
                .Padding(4.0f)
                [
                    SNew(STextBlock)
                    .AutoWrapText(true)
                    .Text(Summary)
                ]
            ];
    }

    IDetailCategoryBuilder& Category = DetailBuilder.EditCategory(
        TEXT("Route"),
        LOCTEXT("RouteCategory", "Route"),
        ECategoryPriority::Important);

    Category.AddCustomRow(LOCTEXT("RouteStatusRow", "Route Status"))
        .WholeRowContent()
        [
            SNew(SBox)
            .Padding(4.0f)
            [
                SNew(STextBlock)
                .AutoWrapText(true)
                .Text(this, &FInfinityStagePassageActorDetails::GetRouteStatusText)
                .ColorAndOpacity(this, &FInfinityStagePassageActorDetails::GetRouteStatusColor)
            ]
        ];

    Category.AddCustomRow(LOCTEXT("RouteActionsRow", "Route Actions"))
        .WholeRowContent()
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton)
                .Text(LOCTEXT("EditRouteButton", "Edit Route"))
                .ToolTipText(LOCTEXT(
                    "EditRouteButtonTip",
                    "Disable Auto Fit Straight Route and select the Route spline so it can be shaped in the viewport. Without this, the next materialization replaces the curve with a straight line."))
                .IsEnabled_Lambda([this]() { return GetSelectedActor() != nullptr; })
                .OnClicked(this, &FInfinityStagePassageActorDetails::BeginRouteEdit)
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton)
                .Text(LOCTEXT("ExtendRouteButton", "Extend to Compiled Length"))
                .ToolTipText(LOCTEXT(
                    "ExtendRouteButtonTip",
                    "Extend the tail of the route along its final tangent until it covers the compiled Passage distance. Wings are placed from distance zero forward, so only the unused tail changes."))
                .IsEnabled(this, &FInfinityStagePassageActorDetails::IsRouteShort)
                .OnClicked(this, &FInfinityStagePassageActorDetails::ExtendRoute)
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton)
                .Text(LOCTEXT("FinishRouteButton", "Finish Route Edit"))
                .ToolTipText(LOCTEXT(
                    "FinishRouteButtonTip",
                    "Validate the route length, materialize this Passage onto the new curve, then offer to re-match the Scene camera handoffs. Nothing is saved automatically."))
                .IsEnabled_Lambda([this]() { return GetSelectedActor() != nullptr; })
                .OnClicked(this, &FInfinityStagePassageActorDetails::FinishRouteEdit)
            ]
        ];
}

#undef LOCTEXT_NAMESPACE
