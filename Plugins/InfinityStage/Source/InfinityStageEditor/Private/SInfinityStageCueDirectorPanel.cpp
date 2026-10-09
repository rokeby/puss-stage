#include "SInfinityStageCueDirectorPanel.h"

#include "Editor.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageVideoFallback.h"
#include "LevelSequence.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Widgets/SNullWidget.h"
#include "MovieScene.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Views/STableRow.h"

#define LOCTEXT_NAMESPACE "InfinityStageCueDirector"

namespace
{
const TCHAR* ShowPath = TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show");

FString Clock(const double Seconds)
{
    const int32 Tenths = FMath::Max(0, FMath::RoundToInt32(Seconds * 10.0));
    return FString::Printf(TEXT("%d:%02d.%d"), Tenths / 600, (Tenths / 10) % 60, Tenths % 10);
}

const TCHAR* Kind(const EInfinityCueType Type)
{
    return Type == EInfinityCueType::WingPair ? TEXT("Passage") : Type == EInfinityCueType::Scene ? TEXT("Scene") : TEXT("Sequence");
}

/** GO markers of one sequence, as (offset seconds from its playback start, number, label). */
void GoMarkersOf(const UMovieSceneSequence* Sequence, TArray<TTuple<double, FString, FString>>& Out)
{
    const UMovieScene* Scene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!Scene)
    {
        return;
    }
    const FFrameRate Ticks = Scene->GetTickResolution();
    const FFrameNumber Start = Scene->GetPlaybackRange().GetLowerBoundValue();
    for (const FMovieSceneMarkedFrame& Marked : Scene->GetMarkedFrames())
    {
        FString Number;
        FString Label;
        int32 Mode = -1;
        if (InfinityStageGoCues::ParseMarkerLabel(Marked.Label, Number, Label, Mode))
        {
            Out.Emplace(Ticks.AsSeconds(FFrameTime(Marked.FrameNumber - Start)), Number, Label);
        }
    }
}
}

namespace
{
class SCueDirectorRow final : public SMultiColumnTableRow<TSharedPtr<SInfinityStageCueDirectorPanel::FRow>>
{
public:
    SLATE_BEGIN_ARGS(SCueDirectorRow) {}
    SLATE_END_ARGS()

    void Construct(const FArguments&, const TSharedRef<STableViewBase>& InOwner, TSharedPtr<SInfinityStageCueDirectorPanel::FRow> InRow,         FInfinityCueDirectorSettings* InSettings, bool* InDirty)
    {
        Row = InRow;
        Settings = InSettings;
        Dirty = InDirty;
        SMultiColumnTableRow<TSharedPtr<SInfinityStageCueDirectorPanel::FRow>>::Construct(FSuperRowType::FArguments(), InOwner);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& Column) override
    {
        const bool bGo = Row->bGo;
        if (Column == TEXT("Stop"))
        {
            return SNew(SCheckBox)
                .ToolTipText(bGo
                    ? LOCTEXT("HoldTip", "This GO marker still holds during run-through (Klara presses GO).")
                    : LOCTEXT("StopTip", "The show stops at the END of this segment (e.g. after lights out) until Klara's GO."))
                .IsChecked_Lambda([this, bGo]()
                {
                    const bool bOn = bGo ? Settings->HoldGoNumbers.Contains(Row->GoNumber) : Settings->StopAfterSegments.Contains(Row->SegmentGuid);
                    return bOn ? ECheckBoxState::Checked : ECheckBoxState::Unchecked;
                })
                .OnCheckStateChanged_Lambda([this, bGo](const ECheckBoxState State)
                {
                    const bool bOn = State == ECheckBoxState::Checked;
                    if (bGo)
                    {
                        bOn ? (void)Settings->HoldGoNumbers.AddUnique(Row->GoNumber) : (void)Settings->HoldGoNumbers.Remove(Row->GoNumber);
                    }
                    else
                    {
                        bOn ? (void)Settings->StopAfterSegments.AddUnique(Row->SegmentGuid) : (void)Settings->StopAfterSegments.Remove(Row->SegmentGuid);
                    }
                    *Dirty = true;
                });
        }
        if (Column == TEXT("Video"))
        {
            if (bGo || Row->SceneKey.IsEmpty())
            {
                return SNullWidget::NullWidget;
            }
            return SNew(SCheckBox)
                .IsEnabled(Row->bVideoAvailable)
                .ToolTipText(Row->bVideoAvailable
                    ? LOCTEXT("VideoTip", "Play this Scene's pre-rendered video instead of the live Scene (falls back to live if the file fails).")
                    : LOCTEXT("NoVideoTip", "No video for this Scene in Renders/Fallbacks/current.json yet."))
                .IsChecked_Lambda([this]()
                {
                    return Settings->UseVideoScenes.Contains(Row->SceneKey) ? ECheckBoxState::Checked : ECheckBoxState::Unchecked;
                })
                .OnCheckStateChanged_Lambda([this](const ECheckBoxState State)
                {
                    State == ECheckBoxState::Checked
                        ? (void)Settings->UseVideoScenes.AddUnique(Row->SceneKey)
                        : (void)Settings->UseVideoScenes.Remove(Row->SceneKey);
                    *Dirty = true;
                });
        }
        FString Text;
        if (Column == TEXT("Label"))
        {
            Text = bGo ? TEXT("      ") + Row->Label : FString::Printf(TEXT("%s  (%s)"), *Row->Label, Kind(Row->Type));
        }
        else if (Column == TEXT("Time"))
        {
            Text = Clock(Row->StartSeconds);
        }
        else if (Column == TEXT("Length"))
        {
            Text = bGo ? FString() : Clock(Row->LengthSeconds);
        }
        else if (Column == TEXT("Sheet"))
        {
            Text = bGo ? FString() : Row->SheetLabel;
        }
        return SNew(STextBlock).Text(FText::FromString(Text));
    }

private:
    TSharedPtr<SInfinityStageCueDirectorPanel::FRow> Row;
    FInfinityCueDirectorSettings* Settings = nullptr;
    bool* Dirty = nullptr;
};
}

void SInfinityStageCueDirectorPanel::Construct(const FArguments& InArgs)
{
    ChildSlot
    [
        SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(6.0f)
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.0f, 0.0f, 12.0f, 0.0f)
            [
                SNew(SCheckBox)
                .IsChecked_Lambda([this]() { return Settings.bRunThrough ? ECheckBoxState::Checked : ECheckBoxState::Unchecked; })
                .OnCheckStateChanged_Lambda([this](const ECheckBoxState State)
                {
                    Settings.bRunThrough = State == ECheckBoxState::Checked;
                    bDirty = true;
                })
                [
                    SNew(STextBlock).Text(LOCTEXT("RunThrough", "Run-through (the show runs on; stops only where ticked)"))
                ]
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton).Text(LOCTEXT("EveryScene", "Stop after every Scene"))
                .ToolTipText(LOCTEXT("EverySceneTip", "Tick 'stop after' on every Scene: the show waits in the dark after each Scene until Klara's GO."))
                .OnClicked_Lambda([this]() { StopAfterEveryScene(); return FReply::Handled(); })
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton).Text(LOCTEXT("Reload", "Reload"))
                .OnClicked_Lambda([this]() { Refresh(); return FReply::Handled(); })
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton).Text(LOCTEXT("Save", "Save"))
                .OnClicked_Lambda([this]() { Save(); return FReply::Handled(); })
            ]
            + SHorizontalBox::Slot().AutoWidth().Padding(2.0f)
            [
                SNew(SButton).Text(LOCTEXT("ApplyPie", "Save + apply to running PIE"))
                .OnClicked_Lambda([this]() { ApplyToPie(); return FReply::Handled(); })
            ]
        ]
        + SVerticalBox::Slot().AutoHeight().Padding(6.0f, 0.0f)
        [
            SNew(STextBlock).Text_Lambda([this]() { return bDirty ? FText::Format(LOCTEXT("Unsaved", "{0}   (unsaved changes)"), Status) : Status; })
        ]
        + SVerticalBox::Slot().FillHeight(1.0f).Padding(6.0f)
        [
            SAssignNew(List, SListView<TSharedPtr<FRow>>)
            .ListItemsSource(&Rows)
            .OnGenerateRow(this, &SInfinityStageCueDirectorPanel::GenerateRow)
            .HeaderRow
            (
                SNew(SHeaderRow)
                + SHeaderRow::Column(TEXT("Stop")).DefaultLabel(LOCTEXT("ColStop", "Klara GO")).FixedWidth(90.0f)
                + SHeaderRow::Column(TEXT("Video")).DefaultLabel(LOCTEXT("ColVideo", "Use video")).FixedWidth(80.0f)
                + SHeaderRow::Column(TEXT("Label")).DefaultLabel(LOCTEXT("ColLabel", "Segment / GO marker")).FillWidth(0.4f)
                + SHeaderRow::Column(TEXT("Time")).DefaultLabel(LOCTEXT("ColTime", "Starts")).FixedWidth(80.0f)
                + SHeaderRow::Column(TEXT("Length")).DefaultLabel(LOCTEXT("ColLength", "Length")).FixedWidth(80.0f)
                + SHeaderRow::Column(TEXT("Sheet")).DefaultLabel(LOCTEXT("ColSheet", "Cue sheet says")).FillWidth(0.35f)
            )
        ]
    ];
    Refresh();
}

void SInfinityStageCueDirectorPanel::Refresh()
{
    Rows.Reset();
    Show = LoadObject<UInfinityStageShowAsset>(nullptr, ShowPath);
    {
        FString Text;
        TArray<FString> Warnings;
        Settings = FInfinityCueDirectorSettings();
        if (FFileHelper::LoadFileToString(Text, *InfinityStageCueSheet::ResolveSettingsPath()))
        {
            Settings.Parse(Text, Warnings);
        }
    }
    Sheet.LoadFromFile(InfinityStageCueSheet::ResolvePath());
    bDirty = false;
    if (!Show.IsValid())
    {
        Status = FText::Format(LOCTEXT("NoShow", "Show not found: {0}"), FText::FromString(ShowPath));
        if (List.IsValid()) { List->RequestListRefresh(); }
        return;
    }
    const UInfinityStageShowAsset& ShowRef = *Show.Get();
    TMap<int32, FInfinityFallbackClip> Clips;
    {
        FString Json;
        TArray<FString> VideoWarnings;
        const FString Root = InfinityStageVideoFallback::ResolveRoot();
        if (FFileHelper::LoadFileToString(Json, *FPaths::Combine(Root, TEXT("current.json"))))
        {
            Clips = InfinityStageVideoFallback::ParseRegistry(Json, Root, VideoWarnings);
        }
    }
    int32 SceneOrdinal = 0;
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(ShowRef);
    const double TickRate = ShowRef.TickResolution.AsDecimal();
    for (int32 Index = 0; Index < Compiled.Segments.Num(); ++Index)
    {
        const FInfinityCompiledSegment& Segment = Compiled.Segments[Index];
        TSharedPtr<FRow> Row = MakeShared<FRow>();
        Row->SegmentGuid = Segment.SegmentGuid;
        Row->Type = Segment.Type;
        Row->StartSeconds = Segment.StartFrame.Value / TickRate;
        Row->LengthSeconds = (Segment.EndFrame - Segment.StartFrame).Value / TickRate;
        Row->SheetLabel = Sheet.SegmentLabels.IsValidIndex(Index) ? Sheet.SegmentLabels[Index] : FString(TEXT("(not in the sheet)"));
        if (Segment.Type == EInfinityCueType::Scene)
        {
            ++SceneOrdinal;
            Row->SceneKey = FString::Printf(TEXT("S%d"), SceneOrdinal);
            Row->bVideoAvailable = Clips.Contains(SceneOrdinal);
        }
        const UMovieSceneSequence* Sequence = nullptr;
        if (Segment.Type == EInfinityCueType::WingPair)
        {
            const FInfinityPassageSettings* Passage = ShowRef.PassageSettings.FindByPredicate(
                [&Segment](const FInfinityPassageSettings& Candidate) { return Candidate.PassageGuid == Segment.SegmentGuid; });
            Row->Label = Passage ? Passage->Label.ToString() : FString(TEXT("Passage"));
            Sequence = Passage ? Passage->Choreography.LoadSynchronous() : nullptr;
        }
        else if (ShowRef.Cues.IsValidIndex(Segment.FirstCueIndex))
        {
            Row->Label = ShowRef.Cues[Segment.FirstCueIndex].Label.ToString();
            Sequence = ShowRef.Cues[Segment.FirstCueIndex].Scene.Sequence.LoadSynchronous();
        }
        Rows.Add(Row);

        TArray<TTuple<double, FString, FString>> Gos;
        GoMarkersOf(Sequence, Gos);
        for (const TTuple<double, FString, FString>& Go : Gos)
        {
            TSharedPtr<FRow> GoRow = MakeShared<FRow>();
            GoRow->bGo = true;
            GoRow->SegmentGuid = Segment.SegmentGuid;
            GoRow->GoNumber = Go.Get<1>();
            GoRow->Label = FString::Printf(TEXT("GO %s  %s"), *Go.Get<1>(), *Go.Get<2>());
            GoRow->StartSeconds = Row->StartSeconds + Go.Get<0>();
            Rows.Add(GoRow);
        }
    }
    Status = FText::Format(
        LOCTEXT("Loaded", "{0} segments, {1} stop(s), {2} held GO marker(s). Sheet: {3} segments. File: {4}"),
        FText::AsNumber(Compiled.Segments.Num()), FText::AsNumber(Settings.StopAfterSegments.Num()),
        FText::AsNumber(Settings.HoldGoNumbers.Num()), FText::AsNumber(Sheet.SegmentLabels.Num()),
        FText::FromString(InfinityStageCueSheet::ResolveSettingsPath()));
    if (List.IsValid())
    {
        List->RequestListRefresh();
    }
}

FString SInfinityStageCueDirectorPanel::LabelOf(const FGuid& Guid) const
{
    for (const TSharedPtr<FRow>& Row : Rows)
    {
        if (!Row->bGo && Row->SegmentGuid == Guid)
        {
            return Row->Label;
        }
    }
    return TEXT("(segment not in the Show)");
}

void SInfinityStageCueDirectorPanel::Save()
{
    const FString Path = InfinityStageCueSheet::ResolveSettingsPath();
    const FString Text = Settings.Serialize([this](const FGuid& Guid) { return LabelOf(Guid); });
    const bool bOk = FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    bDirty = !bOk;
    Status = bOk
        ? FText::Format(LOCTEXT("Saved", "Saved {0} stop(s), {1} held GO marker(s), run-through {2} -> {3}"),
            FText::AsNumber(Settings.StopAfterSegments.Num()), FText::AsNumber(Settings.HoldGoNumbers.Num()),
            Settings.bRunThrough ? LOCTEXT("On", "ON") : LOCTEXT("Off", "off"), FText::FromString(Path))
        : FText::Format(LOCTEXT("SaveFailed", "Could not write {0}"), FText::FromString(Path));
    UE_LOG(LogTemp, Display, TEXT("INFINITY_CUE_DIRECTOR_SAVED ok=%d stops=%d hold_go=%d run_through=%d path=%s"),
        bOk ? 1 : 0, Settings.StopAfterSegments.Num(), Settings.HoldGoNumbers.Num(), Settings.bRunThrough ? 1 : 0, *Path);
}

void SInfinityStageCueDirectorPanel::ApplyToPie()
{
    Save();
    UWorld* PlayWorld = GEditor ? GEditor->PlayWorld.Get() : nullptr;
    UInfinityStageCueDirectorSubsystem* Director = PlayWorld ? PlayWorld->GetSubsystem<UInfinityStageCueDirectorSubsystem>() : nullptr;
    if (!Director)
    {
        Status = FText::Format(LOCTEXT("NoPie", "{0}  (no PIE running: it applies when PIE starts)"), Status);
        return;
    }
    Director->Reload();
    Status = FText::Format(LOCTEXT("Applied", "{0}  (applied to PIE)"), Status);
}

void SInfinityStageCueDirectorPanel::StopAfterEveryScene()
{
    for (const TSharedPtr<FRow>& Row : Rows)
    {
        if (!Row->bGo && Row->Type == EInfinityCueType::Scene)
        {
            Settings.StopAfterSegments.AddUnique(Row->SegmentGuid);
        }
    }
    Settings.bRunThrough = true;
    bDirty = true;
}

TSharedRef<ITableRow> SInfinityStageCueDirectorPanel::GenerateRow(TSharedPtr<FRow> Row, const TSharedRef<STableViewBase>& Owner)
{
    return SNew(SCueDirectorRow, Owner, Row, &Settings, &bDirty);
}

#undef LOCTEXT_NAMESPACE
