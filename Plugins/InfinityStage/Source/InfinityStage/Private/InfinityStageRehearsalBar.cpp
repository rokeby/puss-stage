#include "InfinityStageRehearsalBar.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageDirectorHud.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowGameMode.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
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
        }
    }
    Out.Cue = FString::Printf(TEXT("%d/%d  %s%s"), HudState.SegmentIndex + 1, HudState.SegmentCount, *HudState.SegmentLabel,
        SheetCue.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("   [sheet cue %s]"), *SheetCue));
    return true;
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
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
                [
                    SNew(SButton)
                    .IsFocusable(false)
                    .Text_Lambda([this]() { return State().bPlaying ? LOCTEXT("Pause", "|| Pause") : LOCTEXT("Play", "> Play"); })
                    .ToolTipText(LOCTEXT("PlayTip", "Play / pause (Space)"))
                    .IsEnabled_Lambda([this]() { return State().bHasShow; })
                    .OnClicked_Lambda([this]() { Command(GetWorldFn ? GetWorldFn() : nullptr, ECommand::PlayPause); return FReply::Handled(); })
                ]
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
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("PrevLine", "< line"), LOCTEXT("PrevLineTip", "Script cursor back (PageUp)"), ECommand::PreviousLine) ]
                + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)[ Button(LOCTEXT("NextLine", "line >"), LOCTEXT("NextLineTip", "Script cursor on (PageDown)"), ECommand::NextLine) ]
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
        ]
    ];
}

#undef LOCTEXT_NAMESPACE
