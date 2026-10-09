#include "InfinityStageRehearsalBar.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageDirectorHud.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowGameMode.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageSurtitles.h"
#include "InfinityStageTransportController.h"
#include "InputCoreTypes.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SComboButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/Text/STextBlock.h"

#define LOCTEXT_NAMESPACE "InfinityStageRehearsalBar"

namespace InfinityStageRehearsal
{
FString Clock(const double Seconds)
{
    const int32 Tenths = FMath::Max(0, FMath::RoundToInt32(Seconds * 10.0));
    return FString::Printf(TEXT("%d:%02d.%d"), Tenths / 600, (Tenths / 10) % 60, Tenths % 10);
}

FInfinityNextStop NextStop(
    const TArray<FInfinityTransportSegment>& Segments,
    const TArray<FInfinityGoCue>& GoCues,
    const FFrameNumber Now,
    const bool bRunThrough,
    const TArray<FGuid>& StopAfter,
    const TArray<FString>& HoldGoNumbers)
{
    FInfinityNextStop Stop;
    if (Segments.IsEmpty())
    {
        return Stop;
    }
    int32 Current = 0;
    for (int32 Index = 0; Index < Segments.Num(); ++Index)
    {
        if (Segments[Index].StartFrame <= Now)
        {
            Current = Index;
        }
    }
    const int32 StopIndex = bRunThrough
        ? UInfinityStageTransportController::RunThroughStopIndex(Segments, Current, StopAfter)
        : Current;
    Stop.bValid = true;
    Stop.Frame = Segments[StopIndex].EndFrame;
    const bool bShowEnd = bRunThrough && StopIndex == Segments.Num() - 1 && !StopAfter.Contains(Segments[StopIndex].SegmentGuid);
    Stop.Label = bShowEnd ? FString(TEXT("show end")) : FString::Printf(TEXT("end of %s"), *Segments[StopIndex].Label.ToString());
    for (const FInfinityGoCue& Cue : GoCues)
    {
        const bool bHolds = Cue.bHold && (!bRunThrough || HoldGoNumbers.Contains(Cue.Number));
        if (bHolds && Cue.Frame > Now && Cue.Frame < Stop.Frame)
        {
            Stop.Frame = Cue.Frame;
            Stop.Label = FString::Printf(TEXT("GO %s %s"), *Cue.Number, *Cue.Label);
        }
    }
    return Stop;
}

FScriptStepPlan PlanScriptStep(
    FInfinityScriptCursor& Cursor,
    const FInfinityCueSheet& Sheet,
    const int32 Delta,
    const TArray<FInfinityTransportSegment>& Segments,
    const double TicksPerSecond)
{
    FScriptStepPlan Plan;
    for (int32 Step = 0; Step < FMath::Abs(Delta); ++Step)
    {
        if (!(Delta > 0 ? Cursor.Next(Sheet) : Cursor.Prev(Sheet)))
        {
            break;
        }
        Plan.bMoved = true;
    }
    if (!Plan.bMoved || !Sheet.Rows.IsValidIndex(Cursor.Row))
    {
        return Plan;
    }
    const FInfinityCueSheetRow& Row = Sheet.Rows[Cursor.Row];
    int32 SegmentIndex = InfinityStageSurtitles::ResolveSegment(Row.Segment, Segments);
    if (SegmentIndex == INDEX_NONE && Segments.IsValidIndex(Row.SegmentOrdinal))
    {
        SegmentIndex = Row.SegmentOrdinal;
    }
    if (!Row.bHasAtTime || !Segments.IsValidIndex(SegmentIndex) || TicksPerSecond <= 0.0)
    {
        return Plan;
    }
    const FInfinityTransportSegment& Segment = Segments[SegmentIndex];
    const int32 Length = FMath::Max(1, (Segment.EndFrame - Segment.StartFrame).Value);
    const int32 Offset = FMath::Clamp(FMath::RoundToInt32(Row.AtSeconds * TicksPerSecond), 0, Length - 1);
    Plan.ScrubFrame = Segment.StartFrame + FFrameNumber(Offset);
    return Plan;
}

TArray<FInfinityRehearsalMarker> LayoutMarkers(
    const FInfinityCueSheet& Sheet,
    const FInfinitySurtitleScript& Surtitles,
    const TArray<FInfinityTransportSegment>& Segments,
    const TArray<FInfinityGoCue>& GoCues,
    const int32 SegmentIndex,
    const double TicksPerSecond)
{
    TArray<FInfinityRehearsalMarker> Markers;
    if (!Segments.IsValidIndex(SegmentIndex) || TicksPerSecond <= 0.0)
    {
        return Markers;
    }
    const FInfinityTransportSegment& Segment = Segments[SegmentIndex];
    const int32 LengthFrames = FMath::Max(1, (Segment.EndFrame - Segment.StartFrame).Value);
    const double LengthSeconds = LengthFrames / TicksPerSecond;
    const auto FractionFromSeconds = [LengthSeconds](const double Seconds)
    {
        return static_cast<float>(FMath::Clamp(Seconds / LengthSeconds, 0.0, 1.0));
    };
    const auto FractionFromFrame = [&Segment, LengthFrames](const FFrameNumber Frame)
    {
        return FMath::Clamp(static_cast<float>((Frame - Segment.StartFrame).Value) / LengthFrames, 0.0f, 1.0f);
    };

    for (const FInfinityCueSheetRow& Row : Sheet.Rows)
    {
        int32 RowSegment = InfinityStageSurtitles::ResolveSegment(Row.Segment, Segments);
        if (RowSegment == INDEX_NONE && Segments.IsValidIndex(Row.SegmentOrdinal))
        {
            RowSegment = Row.SegmentOrdinal;
        }
        if (Row.bHasAtTime && RowSegment == SegmentIndex)
        {
            const float At = FractionFromSeconds(Row.AtSeconds);
            Markers.Add({EInfinityRehearsalMarkerKind::Script, At, At});
        }
    }
    for (int32 LineIndex = 0; LineIndex < Surtitles.Lines.Num(); ++LineIndex)
    {
        const FInfinitySurtitleLine& Line = Surtitles.Lines[LineIndex];
        if (!InfinityStageSurtitles::LineMatchesSegment(Line, Segments, SegmentIndex))
        {
            continue;
        }
        const float Start = FractionFromSeconds(Line.InSeconds);
        const float End = FractionFromSeconds(InfinityStageSurtitles::EffectiveOut(
            Surtitles, LineIndex, Segments, SegmentIndex, TicksPerSecond));
        Markers.Add({EInfinityRehearsalMarkerKind::Surtitle, Start, FMath::Max(Start, End)});
    }
    for (const FInfinityGoCue& Cue : GoCues)
    {
        if (Cue.Frame >= Segment.StartFrame && Cue.Frame < Segment.EndFrame)
        {
            const float At = FractionFromFrame(Cue.Frame);
            Markers.Add({EInfinityRehearsalMarkerKind::Go, At, At});
        }
    }
    Markers.Sort([](const FInfinityRehearsalMarker& A, const FInfinityRehearsalMarker& B)
    {
        return A.StartFraction == B.StartFraction
            ? static_cast<uint8>(A.Kind) < static_cast<uint8>(B.Kind)
            : A.StartFraction < B.StartFraction;
    });
    return Markers;
}

bool Gather(UWorld* World, FInfinityRehearsalState& Out)
{
    Out = FInfinityRehearsalState();
    if (!World)
    {
        return false;
    }
    UInfinityStageDirectorHudSubsystem* Hud = World->GetSubsystem<UInfinityStageDirectorHudSubsystem>();
    UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(World);
    if (!Hud || !Transport || Transport->Segments.IsEmpty())
    {
        return false;
    }
    const FInfinityDirectorHudState HudState = Hud->GatherState();
    if (!HudState.bHasShow)
    {
        return false;
    }
    Out.bHasShow = true;
    Out.CueSeconds = HudState.SegmentSeconds;
    Out.CueFraction = HudState.SegmentLengthSeconds > 0.0
        ? static_cast<float>(FMath::Clamp(HudState.SegmentSeconds / HudState.SegmentLengthSeconds, 0.0, 1.0))
        : 0.0f;
    Out.CueLengthSeconds = HudState.SegmentLengthSeconds;
    Out.ShowSeconds = HudState.MasterSeconds;
    Out.bPlaying = HudState.bPlaying;
    Out.bHold = HudState.bHold;
    Out.bRunThrough = Transport->bRunThrough;

    double TicksPerSecond = 0.0;
    for (TActorIterator<AInfinityStageShowRoot> It(World); It; ++It)
    {
        if (It->ShowAsset && It->ShowAsset->TickResolution.IsValid())
        {
            TicksPerSecond = It->ShowAsset->TickResolution.AsDecimal();
            break;
        }
    }
    if (TicksPerSecond > 0.0)
    {
        Out.ShowLengthSeconds = Transport->Segments.Last().EndFrame.Value / TicksPerSecond;
        const FFrameNumber Now = Transport->GetCurrentMasterFrame();
        const FInfinityNextStop Stop = NextStop(Transport->Segments, Transport->GoCues, Now, Transport->bRunThrough,
            Transport->RunThroughStopAfter, Transport->RunThroughHoldGoNumbers);
        if (Stop.bValid)
        {
            Out.NextStop = FString::Printf(TEXT("%s in %s"), *Stop.Label,
                *Clock(FMath::Max(0.0, (Stop.Frame - Now).Value / TicksPerSecond)));
        }
        const FInfinityCueSheet EmptySheet;
        const FInfinitySurtitleScript EmptySurtitles;
        const UInfinityStageCueDirectorSubsystem* CueDirector = World->GetSubsystem<UInfinityStageCueDirectorSubsystem>();
        const UInfinityStageSurtitleSubsystem* Surtitles = World->GetSubsystem<UInfinityStageSurtitleSubsystem>();
        Out.Markers = LayoutMarkers(
            CueDirector ? CueDirector->GetSheet() : EmptySheet,
            Surtitles ? Surtitles->GetScript() : EmptySurtitles,
            Transport->Segments,
            Transport->GoCues,
            HudState.SegmentIndex,
            TicksPerSecond);
    }

    FString SheetCue;
    if (UInfinityStageCueDirectorSubsystem* Director = World->GetSubsystem<UInfinityStageCueDirectorSubsystem>())
    {
        const FInfinityCueSheet& Sheet = Director->GetSheet();
        const int32 Row = Director->GetCursor().Row;
        if (Sheet.Rows.IsValidIndex(Row))
        {
            const FInfinityCueSheetRow& Current = Sheet.Rows[Row];
            // The last numbered row at or before the cursor is the cue we are in.
            for (int32 R = Row; R >= 0; --R)
            {
                if (!Sheet.Rows[R].Number.IsEmpty())
                {
                    SheetCue = Sheet.Rows[R].Number;
                    break;
                }
            }
            Out.Notes = InfinityStageCueSheet::DescribeActions(Current);
            const TArray<FString> Lines = InfinityStageCueSheet::DescribeLines(Current);
            Out.Script = Lines.IsEmpty() ? FString() : Lines[0];
            Out.Dog = InfinityStageCueSheet::DescribeDogDirection(Current);
            const int32 NextDogRow = InfinityStageCueSheet::NextDogDirectionRow(Sheet, Row);
            if (Sheet.Rows.IsValidIndex(NextDogRow))
            {
                Out.NextDog = InfinityStageCueSheet::DescribeDogDirection(Sheet.Rows[NextDogRow]);
            }
        }
    }
    Out.Cue = FString::Printf(TEXT("%d/%d  %s%s"), HudState.SegmentIndex + 1, HudState.SegmentCount, *HudState.SegmentLabel,
        SheetCue.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("   [sheet cue %s]"), *SheetCue));
    return true;
}

FFrameNumber FrameAtFraction(const FFrameNumber Start, const FFrameNumber End, const float Fraction)
{
    const int32 Length = FMath::Max(1, (End - Start).Value);
    return Start + FFrameNumber(FMath::Clamp(FMath::RoundToInt32(FMath::Clamp(Fraction, 0.0f, 1.0f) * Length), 0, Length - 1));
}

void ScrubCurrentSegment(UWorld* World, const float Fraction)
{
    UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(World);
    if (!Transport || Transport->Segments.IsEmpty())
    {
        return;
    }
    const FFrameNumber Now = Transport->GetCurrentMasterFrame();
    int32 Current = 0;
    for (int32 Index = 0; Index < Transport->Segments.Num(); ++Index)
    {
        if (Transport->Segments[Index].StartFrame <= Now)
        {
            Current = Index;
        }
    }
    const FInfinityTransportSegment& Segment = Transport->Segments[Current];
    // Same path as the Cue Desk scrub: pauses and evaluates that frame (Scenes included,
    // since the Master evaluates the nested Scene sequence: one clock).
    Transport->ScrubToMasterFrame(FrameAtFraction(Segment.StartFrame, Segment.EndFrame, Fraction));
}

void JumpToSegmentStart(UWorld* World, const int32 Index)
{
    UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(World);
    if (Transport && Transport->Segments.IsValidIndex(Index))
    {
        Transport->ScrubToMasterFrame(Transport->Segments[Index].StartFrame);
    }
}

TArray<FString> SegmentLabels(UWorld* World)
{
    TArray<FString> Labels;
    if (UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(World))
    {
        for (int32 Index = 0; Index < Transport->Segments.Num(); ++Index)
        {
            Labels.Add(FString::Printf(TEXT("%d  %s"), Index + 1, *Transport->Segments[Index].Label.ToString()));
        }
    }
    return Labels;
}

void Command(UWorld* World, const ECommand Which)
{
    if (!World)
    {
        return;
    }
    AInfinityStageShowPlayerController* Controller = nullptr;
    for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
    {
        Controller = Cast<AInfinityStageShowPlayerController>(It->Get());
        if (Controller)
        {
            break;
        }
    }
    UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(World);
    switch (Which)
    {
    case ECommand::Back:
        if (Controller) { Controller->PreviousShowSegment(); }
        break;
    case ECommand::PlayPause:
        if (Controller) { Controller->ToggleShowPlayback(); }
        break;
    case ECommand::Go:
        // RIGHT's tap: GO at a hold, release a vamp, otherwise advance.
        if (Transport && (Transport->ReleaseActiveHold() || Transport->ReleaseActiveVamp()))
        {
            break;
        }
        if (Controller) { Controller->AdvanceShowSegment(); }
        break;
    case ECommand::PreviousLine:
        if (Controller) { Controller->PreviousScriptLine(); }
        break;
    case ECommand::NextLine:
        if (Controller) { Controller->NextScriptLine(); }
        break;
    }
}
}

namespace InfinityStageRehearsal
{
FInfinitySurtitleCall PlanSurtitleAction(const ESurtitleAction Action)
{
    FInfinitySurtitleCall Call;
    using EKind = FInfinitySurtitleCall::EKind;
    switch (Action)
    {
    case ESurtitleAction::Previous:   Call.Kind = EKind::Step;  Call.Delta = -1; break;
    case ESurtitleAction::Next:       Call.Kind = EKind::Step;  Call.Delta = 1; break;
    case ESurtitleAction::StampIn:    Call.Kind = EKind::Stamp; Call.bOut = false; break;
    case ESurtitleAction::StampOut:   Call.Kind = EKind::Stamp; Call.bOut = true; break;
    case ESurtitleAction::InEarlier:  Call.Kind = EKind::Nudge; Call.bOut = false; Call.Seconds = -SurtitleNudgeSeconds; break;
    case ESurtitleAction::InLater:    Call.Kind = EKind::Nudge; Call.bOut = false; Call.Seconds = SurtitleNudgeSeconds; break;
    case ESurtitleAction::OutEarlier: Call.Kind = EKind::Nudge; Call.bOut = true;  Call.Seconds = -SurtitleNudgeSeconds; break;
    case ESurtitleAction::OutLater:   Call.Kind = EKind::Nudge; Call.bOut = true;  Call.Seconds = SurtitleNudgeSeconds; break;
    }
    return Call;
}

FString SurtitleAction(UWorld* World, const ESurtitleAction Action)
{
    UInfinityStageSurtitleSubsystem* Surtitles = World ? World->GetSubsystem<UInfinityStageSurtitleSubsystem>() : nullptr;
    if (!Surtitles)
    {
        return TEXT("Not done: no surtitles here (start PIE; the sheet lives in the game world).");
    }
    const FInfinitySurtitleCall Call = PlanSurtitleAction(Action);
    bool bOk = false;
    switch (Call.Kind)
    {
    case FInfinitySurtitleCall::EKind::Step:  bOk = Surtitles->StepLine(Call.Delta); break;
    case FInfinitySurtitleCall::EKind::Stamp: bOk = Surtitles->StampAtPlayhead(Call.bOut); break;
    case FInfinitySurtitleCall::EKind::Nudge: bOk = Surtitles->Nudge(Call.bOut, Call.Seconds); break;
    }
    // A refusal (outside the line's segment, Out <= In, changed on disk, interlock) is shown, never forced.
    return bOk ? Surtitles->DescribeSelected() : TEXT("Not done: ") + Surtitles->GetLastMessage();
}

FString DescribeSurtitle(UWorld* World)
{
    const UInfinityStageSurtitleSubsystem* Surtitles = World ? World->GetSubsystem<UInfinityStageSurtitleSubsystem>() : nullptr;
    return Surtitles ? Surtitles->DescribeSelected() : FString();
}
}

namespace
{
DECLARE_DELEGATE_OneParam(FP86OnTimelineScrub, float);

/** P86's compact sequencer-like strip. It owns no clock; every drag calls the existing Master scrub path. */
class SP86InfinityStageTimelineStrip final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SP86InfinityStageTimelineStrip) {}
        SLATE_ATTRIBUTE(float, Fraction)
        SLATE_ATTRIBUTE(TArray<FInfinityRehearsalMarker>, Markers)
        SLATE_EVENT(FP86OnTimelineScrub, OnScrub)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs)
    {
        Fraction = InArgs._Fraction;
        Markers = InArgs._Markers;
        OnScrub = InArgs._OnScrub;
    }

    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(640.0f, 54.0f); }

    virtual int32 OnPaint(
        const FPaintArgs& Args,
        const FGeometry& AllottedGeometry,
        const FSlateRect& CullingRect,
        FSlateWindowElementList& OutDrawElements,
        int32 LayerId,
        const FWidgetStyle& WidgetStyle,
        bool bParentEnabled) const override
    {
        const FVector2D Size = AllottedGeometry.GetLocalSize();
        const FSlateBrush* White = FCoreStyle::Get().GetBrush("GenericWhiteBox");
        const ESlateDrawEffect Effects = ESlateDrawEffect::None;
        FSlateDrawElement::MakeBox(OutDrawElements, LayerId,
            AllottedGeometry.ToPaintGeometry(Size, FSlateLayoutTransform()), White, Effects,
            FLinearColor(0.055f, 0.065f, 0.085f, 1.0f));

        const TArray<FInfinityRehearsalMarker> CurrentMarkers = Markers.Get();
        for (const FInfinityRehearsalMarker& Marker : CurrentMarkers)
        {
            const float X = FMath::Clamp(Marker.StartFraction, 0.0f, 1.0f) * Size.X;
            FVector2D MarkSize(2.0f, 15.0f);
            FVector2D MarkPos(X - 1.0f, 3.0f);
            FLinearColor Colour(1.0f, 0.72f, 0.20f, 0.95f); // script At
            if (Marker.Kind == EInfinityRehearsalMarkerKind::Surtitle)
            {
                MarkPos = FVector2D(X, Size.Y - 13.0f);
                MarkSize = FVector2D(FMath::Max(2.0f,
                    (FMath::Clamp(Marker.EndFraction, Marker.StartFraction, 1.0f) - Marker.StartFraction) * Size.X), 8.0f);
                Colour = FLinearColor(0.25f, 0.72f, 1.0f, 0.80f);
            }
            else if (Marker.Kind == EInfinityRehearsalMarkerKind::Go)
            {
                MarkPos = FVector2D(X - 1.5f, 20.0f);
                MarkSize = FVector2D(3.0f, 18.0f);
                Colour = FLinearColor(0.35f, 1.0f, 0.48f, 0.95f);
            }
            FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 1,
                AllottedGeometry.ToPaintGeometry(MarkSize, FSlateLayoutTransform(MarkPos)), White, Effects, Colour);
        }

        const float PlayheadX = FMath::Clamp(Fraction.Get(0.0f), 0.0f, 1.0f) * Size.X;
        FSlateDrawElement::MakeBox(OutDrawElements, LayerId + 2,
            AllottedGeometry.ToPaintGeometry(FVector2D(6.0f, Size.Y),
                FSlateLayoutTransform(FVector2D(PlayheadX - 3.0f, 0.0f))),
            White, Effects, FLinearColor(1.0f, 0.25f, 0.18f, 1.0f));
        return LayerId + 2;
    }

    virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton() != EKeys::LeftMouseButton)
        {
            return FReply::Unhandled();
        }
        Scrub(Geometry, Event);
        return FReply::Handled().CaptureMouse(SharedThis(this));
    }

    virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (!HasMouseCapture())
        {
            return FReply::Unhandled();
        }
        Scrub(Geometry, Event);
        return FReply::Handled();
    }

    virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (!HasMouseCapture() || Event.GetEffectingButton() != EKeys::LeftMouseButton)
        {
            return FReply::Unhandled();
        }
        Scrub(Geometry, Event);
        return FReply::Handled().ReleaseMouseCapture();
    }

private:
    void Scrub(const FGeometry& Geometry, const FPointerEvent& Event) const
    {
        const float Width = FMath::Max(1.0f, Geometry.GetLocalSize().X);
        OnScrub.ExecuteIfBound(FMath::Clamp(Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition()).X / Width, 0.0f, 1.0f));
    }

    TAttribute<float> Fraction;
    TAttribute<TArray<FInfinityRehearsalMarker>> Markers;
    FP86OnTimelineScrub OnScrub;
};
}

const FInfinityRehearsalState& SInfinityStageRehearsalBar::State() const
{
    // Gathered once per engine frame however many text bindings ask.
    if (CachedFrame != GFrameCounter)
    {
        CachedFrame = GFrameCounter;
        InfinityStageRehearsal::Gather(GetWorldFn ? GetWorldFn() : nullptr, Cached);
    }
    return Cached;
}

void SInfinityStageRehearsalBar::Construct(const FArguments& InArgs)
{
    using namespace InfinityStageRehearsal;
    GetWorldFn = InArgs._World;
    const FSlateFontInfo Big = FCoreStyle::GetDefaultFontStyle("Bold", 16);
    const FSlateFontInfo Mid = FCoreStyle::GetDefaultFontStyle("Regular", 13);
    const auto SurtitleButton = [this](const FText& Label, const FText& Tip, const ESurtitleAction Which)
    {
        return SNew(SButton)
            .IsFocusable(false)   // Space / RIGHT stay the show keys
            .Text(Label)
            .ToolTipText(Tip)
            .OnClicked_Lambda([this, Which]()
            {
                SurtitleMessage = SurtitleAction(GetWorldFn ? GetWorldFn() : nullptr, Which);
                return FReply::Handled();
            });
    };
    const auto Button = [this](const FText& Label, const FText& Tip, const ECommand Which)
    {
        return SNew(SButton)
            .IsFocusable(false)   // never keep focus: Space / RIGHT must stay the show keys
            .Text(Label)
            .ToolTipText(Tip)
            .IsEnabled_Lambda([this]() { return State().bHasShow; })
            .OnClicked_Lambda([this, Which]()
            {
                Command(GetWorldFn ? GetWorldFn() : nullptr, Which);
                return FReply::Handled();
            });
    };

    ChildSlot
    [
        SNew(SBorder)
        .BorderImage(FCoreStyle::Get().GetBrush("GenericWhiteBox"))
        .BorderBackgroundColor(FLinearColor(0.02f, 0.02f, 0.03f, 0.92f))
        .Padding(FMargin(8.0f, 4.0f))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("Back", "< Back"), LOCTEXT("BackTip", "Previous segment / shot (LEFT)"), ECommand::Back) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("Go", "GO >"), LOCTEXT("GoTip", "GO: release a hold, else advance (RIGHT)"), ECommand::Go) ]
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(12.0f, 0.0f)
                [
                    SNew(STextBlock).Font(Big).ColorAndOpacity(FLinearColor(1.0f, 0.86f, 0.35f))
                    .Text_Lambda([this]()
                    {
                        const FInfinityRehearsalState& S = State();
                        if (!S.bHasShow)
                        {
                            return LOCTEXT("NoShow", "Rehearsal bar: no show running (press Play in the editor)");
                        }
                        return FText::FromString(FString::Printf(TEXT("%s%s"), *S.Cue, S.bHold ? TEXT("   HOLD: waiting for GO") : TEXT("")));
                    })
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(12.0f, 0.0f)
                [
                    SNew(STextBlock).Font(Big)
                    .Text_Lambda([this]()
                    {
                        const FInfinityRehearsalState& S = State();
                        return S.bHasShow
                            ? FText::FromString(FString::Printf(TEXT("cue %s / %s    show %s / %s"),
                                *Clock(S.CueSeconds), *Clock(S.CueLengthSeconds), *Clock(S.ShowSeconds), *Clock(S.ShowLengthSeconds)))
                            : FText::GetEmpty();
                    })
                ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("PrevLine", "< line"), LOCTEXT("PrevLineTip", "Script cursor back (comma key)"), ECommand::PreviousLine) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("NextLine", "line >"), LOCTEXT("NextLineTip", "Script cursor on (full-stop key)"), ECommand::NextLine) ]
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 3.0f, 0.0f, 0.0f)
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
                [
                    SNew(SComboButton)
                    .IsFocusable(false)
                    .ToolTipText(LOCTEXT("JumpTip", "Jump to the start of any Passage, Scene or Interaction (pauses there)"))
                    .ButtonContent()[ SNew(STextBlock).Text(LOCTEXT("Jump", "Jump to...")) ]
                    .OnGetMenuContent_Lambda([this]()
                    {
                        FMenuBuilder Menu(true, nullptr);
                        const TArray<FString> Labels = SegmentLabels(GetWorldFn ? GetWorldFn() : nullptr);
                        for (int32 Index = 0; Index < Labels.Num(); ++Index)
                        {
                            Menu.AddMenuEntry(FText::FromString(Labels[Index]), FText::GetEmpty(), FSlateIcon(),
                                FUIAction(FExecuteAction::CreateLambda([this, Index]()
                                {
                                    JumpToSegmentStart(GetWorldFn ? GetWorldFn() : nullptr, Index);
                                })));
                        }
                        return Menu.MakeWidget();
                    })
                ]
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(8.0f, 0.0f)
                [
                    // One clock: this strip drags the Master, which evaluates nested Scenes. Scene 3's lock still applies.
                    SNew(SP86InfinityStageTimelineStrip)
                    .ToolTipText(LOCTEXT("ScrubTip", "Drag the playhead through this Passage / Scene (pauses). Hold the Scene 3 lock off with Rehearsal Transport."))
                    .IsEnabled_Lambda([this]() { return State().bHasShow; })
                    .Fraction_Lambda([this]() { return State().CueFraction; })
                    .Markers_Lambda([this]() { return State().Markers; })
                    .OnScrub(FP86OnTimelineScrub::CreateLambda([this](const float Value)
                    {
                        ScrubCurrentSegment(GetWorldFn ? GetWorldFn() : nullptr, Value);
                    }))
                ]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Fill).Padding(4.0f, 0.0f)
                [
                    SNew(SBox).WidthOverride(130.0f).MinDesiredHeight(54.0f)
                    [
                        SNew(SButton)
                        .IsFocusable(false)
                        .Text_Lambda([this]() { return State().bPlaying ? LOCTEXT("Pause", "||  PAUSE") : LOCTEXT("Play", ">  PLAY"); })
                        .ToolTipText(LOCTEXT("PlayTip", "Play / pause (Space)"))
                        .IsEnabled_Lambda([this]() { return State().bHasShow; })
                        .OnClicked_Lambda([this]() { Command(GetWorldFn ? GetWorldFn() : nullptr, ECommand::PlayPause); return FReply::Handled(); })
                    ]
                ]
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 3.0f, 0.0f, 0.0f)
            [
                SNew(STextBlock).Font(Mid).ColorAndOpacity(FLinearColor(0.45f, 0.9f, 1.0f)).AutoWrapText(true)
                .Text_Lambda([this]()
                {
                    const FInfinityRehearsalState& S = State();
                    if (!S.bHasShow)
                    {
                        return FText::GetEmpty();
                    }
                    FString Line = FString::Printf(TEXT("NEXT STOP: %s%s"), *S.NextStop, S.bRunThrough ? TEXT("  (run-through)") : TEXT(""));
                    if (!S.Dog.IsEmpty())
                    {
                        Line += TEXT("      ") + S.Dog;
                    }
                    if (!S.NextDog.IsEmpty())
                    {
                        Line += TEXT("      NEXT ") + S.NextDog;
                    }
                    if (!S.Notes.IsEmpty())
                    {
                        Line += TEXT("      CUE: ") + S.Notes;
                    }
                    return FText::FromString(Line);
                })
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(STextBlock).Font(Mid).AutoWrapText(true)
                .Text_Lambda([this]() { return FText::FromString(State().Script); })
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 3.0f, 0.0f, 0.0f)
            [
                // Surtitles: step between lines, stamp In/Out at the playhead, nudge by 0.25 s. Hidden without them.
                SNew(SHorizontalBox)
                .Visibility_Lambda([this]()
                {
                    UWorld* World = GetWorldFn ? GetWorldFn() : nullptr;
                    return World && World->GetSubsystem<UInfinityStageSurtitleSubsystem>() ? EVisibility::Visible : EVisibility::Collapsed;
                })
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2.0f, 0.0f, 6.0f, 0.0f)
                [ SNew(STextBlock).Font(Mid).Text(LOCTEXT("SurtitlesLabel", "SURTITLE")) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurPrev", "< prev"), LOCTEXT("SurPrevTip", "Jump to the previous surtitle line (pauses there)"), ESurtitleAction::Previous) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurNext", "next >"), LOCTEXT("SurNextTip", "Jump to the next surtitle line (pauses there)"), ESurtitleAction::Next) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(8.0f, 2.0f, 2.0f, 2.0f)[ SurtitleButton(LOCTEXT("SurStampIn", "Stamp In"), LOCTEXT("SurStampInTip", "Set the selected line's In to the playhead"), ESurtitleAction::StampIn) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurStampOut", "Stamp Out"), LOCTEXT("SurStampOutTip", "Set the selected line's Out to the playhead"), ESurtitleAction::StampOut) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(8.0f, 2.0f, 2.0f, 2.0f)[ SurtitleButton(LOCTEXT("SurInEarlier", "In -"), LOCTEXT("SurInEarlierTip", "In 0.25 s earlier"), ESurtitleAction::InEarlier) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurInLater", "In +"), LOCTEXT("SurInLaterTip", "In 0.25 s later"), ESurtitleAction::InLater) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurOutEarlier", "Out -"), LOCTEXT("SurOutEarlierTip", "Out 0.25 s earlier"), ESurtitleAction::OutEarlier) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ SurtitleButton(LOCTEXT("SurOutLater", "Out +"), LOCTEXT("SurOutLaterTip", "Out 0.25 s later"), ESurtitleAction::OutLater) ]
                + SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center).Padding(10.0f, 0.0f)
                [
                    SNew(STextBlock).Font(Mid).AutoWrapText(true)
                    .Text_Lambda([this]()
                    {
                        // A refusal stays up until the next action; otherwise the selected line.
                        return FText::FromString(SurtitleMessage.StartsWith(TEXT("Not done"))
                            ? SurtitleMessage
                            : DescribeSurtitle(GetWorldFn ? GetWorldFn() : nullptr));
                    })
                ]
            ]
        ]
    ];
}

#undef LOCTEXT_NAMESPACE
