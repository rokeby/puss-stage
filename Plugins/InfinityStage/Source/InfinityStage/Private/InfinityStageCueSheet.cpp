#include "InfinityStageCueSheet.h"

#include "HAL/IConsoleManager.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageRehearsalBar.h"
#include "InfinityStageVideoFallback.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Widgets/SBoxPanel.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageCueSheet, Log, All);

namespace
{
TAutoConsoleVariable<FString> CVarCueSheetPath(
    TEXT("InfinityStage.CueSheet.Path"),
    TEXT(""),
    TEXT("CSV export of the master cue sheet. Empty: Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv"));

TAutoConsoleVariable<FString> CVarCueDirectorSettingsPath(
    TEXT("InfinityStage.CueDirector.SettingsPath"),
    TEXT(""),
    TEXT("Cue Director run settings. Empty: Content/InfinityStage/CueSheet/cue_director.txt"));

FString Clean(const FString& Cell)
{
    FString Out = Cell;
    Out.ReplaceInline(TEXT("\r"), TEXT(""));
    Out.TrimStartAndEndInline();
    return Out;
}

enum class ERole : uint8 { None, Number, Light, SoundTech, Action, SoundCue, VideoCue, Speaker, Beat, Notes };

ERole RoleOf(const FString& Header, const int32 Column)
{
    const FString H = Header.ToLower();
    if (H == TEXT("light")) { return ERole::Light; }
    if (H.StartsWith(TEXT("sound tech"))) { return ERole::SoundTech; }
    if (H == TEXT("action")) { return ERole::Action; }
    if (H.StartsWith(TEXT("sound cue"))) { return ERole::SoundCue; }
    if (H.StartsWith(TEXT("video"))) { return ERole::VideoCue; }
    if (H.StartsWith(TEXT("speaker"))) { return ERole::Speaker; }
    if (H.StartsWith(TEXT("beat"))) { return ERole::Beat; }
    if (H.StartsWith(TEXT("note"))) { return ERole::Notes; }
    return Column == 0 ? ERole::Number : ERole::None;
}
}

bool FInfinityCueSheetRow::IsBlank() const
{
    return Number.IsEmpty() && !HasContent() && VideoCue.IsEmpty();
}

bool FInfinityCueSheetRow::HasContent() const
{
    return !Light.IsEmpty() || !SoundTech.IsEmpty() || !Action.IsEmpty() || !SoundCue.IsEmpty()
        || !Beat.IsEmpty() || !Notes.IsEmpty() || !Lines.IsEmpty() || !VideoCue.IsEmpty();
}

void FInfinityCueSheet::ParseCsv(const FString& Text, TArray<TArray<FString>>& OutTable)
{
    OutTable.Reset();
    TArray<FString> Row;
    FString Cell;
    bool bQuoted = false;
    const int32 Length = Text.Len();
    for (int32 Index = 0; Index < Length; ++Index)
    {
        const TCHAR Char = Text[Index];
        if (bQuoted)
        {
            if (Char == TEXT('"'))
            {
                if (Index + 1 < Length && Text[Index + 1] == TEXT('"'))
                {
                    Cell.AppendChar(TEXT('"'));
                    ++Index;
                }
                else
                {
                    bQuoted = false;
                }
            }
            else
            {
                Cell.AppendChar(Char);
            }
            continue;
        }
        if (Char == TEXT('"'))
        {
            bQuoted = true;
        }
        else if (Char == TEXT(','))
        {
            Row.Add(Cell);
            Cell.Reset();
        }
        else if (Char == TEXT('\n'))
        {
            Row.Add(Cell);
            Cell.Reset();
            OutTable.Add(MoveTemp(Row));
            Row.Reset();
        }
        else if (Char != TEXT('\r'))
        {
            Cell.AppendChar(Char);
        }
    }
    if (!Cell.IsEmpty() || !Row.IsEmpty())
    {
        Row.Add(Cell);
        OutTable.Add(MoveTemp(Row));
    }
}

bool FInfinityCueSheet::LoadFromCsvText(const FString& Text)
{
    Rows.Reset();
    SegmentLabels.Reset();
    SegmentStartRows.Reset();
    Speakers.Reset();
    Warnings.Reset();

    TArray<TArray<FString>> Table;
    ParseCsv(Text, Table);

    int32 HeaderRow = INDEX_NONE;
    for (int32 R = 0; R < Table.Num() && HeaderRow == INDEX_NONE; ++R)
    {
        for (const FString& Cell : Table[R])
        {
            if (Clean(Cell).Equals(TEXT("Light"), ESearchCase::IgnoreCase))
            {
                HeaderRow = R;
                break;
            }
        }
    }
    if (HeaderRow == INDEX_NONE)
    {
        Warnings.Add(TEXT("No header row (no cell reading 'Light'): is this the master cue sheet?"));
        return false;
    }

    const TArray<FString>& Header = Table[HeaderRow];
    TArray<ERole> Roles;
    TArray<FString> SpeakerOfColumn;
    for (int32 C = 0; C < Header.Num(); ++C)
    {
        Roles.Add(RoleOf(Clean(Header[C]), C));
        SpeakerOfColumn.Add(FString());
    }
    // The row under the header names the speakers ("Klara", "Gary", "Cameron").
    int32 FirstDataRow = HeaderRow + 1;
    if (Table.IsValidIndex(HeaderRow + 1))
    {
        bool bNamesRow = false;
        for (int32 C = 0; C < Roles.Num(); ++C)
        {
            if (Roles[C] == ERole::Speaker && Table[HeaderRow + 1].IsValidIndex(C) && !Clean(Table[HeaderRow + 1][C]).IsEmpty())
            {
                SpeakerOfColumn[C] = Clean(Table[HeaderRow + 1][C]);
                Speakers.AddUnique(SpeakerOfColumn[C]);
                bNamesRow = true;
            }
        }
        if (bNamesRow)
        {
            FirstDataRow = HeaderRow + 2;
        }
    }
    for (int32 C = 0; C < Roles.Num(); ++C)
    {
        if (Roles[C] == ERole::Speaker && SpeakerOfColumn[C].IsEmpty())
        {
            SpeakerOfColumn[C] = FString::Printf(TEXT("Speaker %d"), C + 1);
            Warnings.Add(FString::Printf(TEXT("Speaker column %d has no name under it"), C + 1));
        }
    }

    FString CurrentSegment;
    int32 CurrentOrdinal = INDEX_NONE;
    for (int32 R = FirstDataRow; R < Table.Num(); ++R)
    {
        FInfinityCueSheetRow Row;
        Row.SourceRow = R + 1;
        const TArray<FString>& Cells = Table[R];
        for (int32 C = 0; C < Cells.Num() && C < Roles.Num(); ++C)
        {
            const FString Value = Clean(Cells[C]);
            if (Value.IsEmpty())
            {
                continue;
            }
            switch (Roles[C])
            {
            case ERole::Number: Row.Number = Value; break;
            case ERole::Light: Row.Light = Value; break;
            case ERole::SoundTech: Row.SoundTech = Value; break;
            case ERole::Action: Row.Action = Value; break;
            case ERole::SoundCue: Row.SoundCue = Value; break;
            case ERole::VideoCue: Row.VideoCue = Value; break;
            case ERole::Beat: Row.Beat = Value; break;
            case ERole::Notes: Row.Notes = Value; break;
            case ERole::Speaker: Row.Lines.Add({SpeakerOfColumn[C], Value}); break;
            default: break;
            }
        }
        if (!Row.VideoCue.IsEmpty())
        {
            CurrentSegment = Row.VideoCue;
            CurrentOrdinal = SegmentLabels.Add(Row.VideoCue);
            SegmentStartRows.Add(Rows.Num());
        }
        Row.Segment = CurrentSegment;
        Row.SegmentOrdinal = CurrentOrdinal;
        if (!Row.IsBlank())
        {
            Rows.Add(MoveTemp(Row));
        }
    }
    UE_LOG(LogInfinityStageCueSheet, Log, TEXT("INFINITY_CUESHEET_LOADED rows=%d segments=%d speakers=%s warnings=%d source=%s"),
        Rows.Num(), SegmentLabels.Num(), *FString::Join(Speakers, TEXT(",")), Warnings.Num(), *SourcePath);
    return true;
}

bool FInfinityCueSheet::LoadFromFile(const FString& Path)
{
    SourcePath = Path;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path))
    {
        Rows.Reset();
        Warnings.Reset();
        Warnings.Add(FString::Printf(TEXT("Cue sheet not found: %s (File > Download > CSV from the Google Sheet)"), *Path));
        UE_LOG(LogInfinityStageCueSheet, Warning, TEXT("INFINITY_CUESHEET_MISSING path=%s"), *Path);
        return false;
    }
    return LoadFromCsvText(Text);
}

int32 FInfinityCueSheet::SegmentStartRow(const int32 SegmentOrdinal) const
{
    return SegmentStartRows.IsValidIndex(SegmentOrdinal) ? SegmentStartRows[SegmentOrdinal] : INDEX_NONE;
}

bool FInfinityScriptCursor::Next(const FInfinityCueSheet& Sheet)
{
    for (int32 R = Row + 1; R < Sheet.Rows.Num(); ++R)
    {
        if (Sheet.Rows[R].HasContent())
        {
            Row = R;
            return true;
        }
    }
    return false;
}

bool FInfinityScriptCursor::Prev(const FInfinityCueSheet& Sheet)
{
    for (int32 R = FMath::Min(Row, Sheet.Rows.Num()) - 1; R >= 0; --R)
    {
        if (Sheet.Rows[R].HasContent())
        {
            Row = R;
            return true;
        }
    }
    return false;
}

void FInfinityScriptCursor::SyncToSegment(const FInfinityCueSheet& Sheet, const int32 SegmentOrdinal)
{
    if (SegmentOrdinal == LastSyncedSegment)
    {
        return;
    }
    LastSyncedSegment = SegmentOrdinal;
    const int32 Start = Sheet.SegmentStartRow(SegmentOrdinal);
    if (Start != INDEX_NONE && Start > Row)
    {
        Row = Start;
    }
}

void FInfinityCueDirectorSettings::Parse(const FString& Text, TArray<FString>& OutWarnings)
{
    bRunThrough = false;
    StopAfterSegments.Reset();
    HoldGoNumbers.Reset();
    UseVideoScenes.Reset();
    VideoAudio = TEXT("ue");
    TArray<FString> Lines;
    Text.ParseIntoArrayLines(Lines);
    for (int32 LineIndex = 0; LineIndex < Lines.Num(); ++LineIndex)
    {
        FString Line = Lines[LineIndex];
        int32 Hash = INDEX_NONE;
        if (Line.FindChar(TEXT('#'), Hash))
        {
            Line.LeftInline(Hash);
        }
        Line.TrimStartAndEndInline();
        if (Line.IsEmpty())
        {
            continue;
        }
        FString Key;
        FString Value;
        if (!Line.Split(TEXT("="), &Key, &Value))
        {
            OutWarnings.Add(FString::Printf(TEXT("line %d: no '=' in '%s'"), LineIndex + 1, *Line));
            continue;
        }
        Key.TrimStartAndEndInline();
        Value.TrimStartAndEndInline();
        if (Key.Equals(TEXT("run_through"), ESearchCase::IgnoreCase))
        {
            bRunThrough = Value.ToBool();
        }
        else if (Key.Equals(TEXT("stop_after"), ESearchCase::IgnoreCase))
        {
            FGuid Guid;
            if (FGuid::Parse(Value, Guid))
            {
                StopAfterSegments.AddUnique(Guid);
            }
            else
            {
                OutWarnings.Add(FString::Printf(TEXT("line %d: stop_after needs a segment GUID, got '%s'"), LineIndex + 1, *Value));
            }
        }
        else if (Key.Equals(TEXT("hold_go"), ESearchCase::IgnoreCase))
        {
            HoldGoNumbers.AddUnique(Value);
        }
        else if (Key.Equals(TEXT("use_video"), ESearchCase::IgnoreCase))
        {
            UseVideoScenes.AddUnique(Value.ToUpper());
        }
        else if (Key.Equals(TEXT("video_audio"), ESearchCase::IgnoreCase))
        {
            if (Value.Equals(TEXT("ue"), ESearchCase::IgnoreCase) || Value.Equals(TEXT("desk"), ESearchCase::IgnoreCase))
            {
                VideoAudio = Value.ToLower();
            }
            else
            {
                OutWarnings.Add(FString::Printf(TEXT("line %d: video_audio must be 'ue' or 'desk', got '%s'"), LineIndex + 1, *Value));
            }
        }
        else
        {
            OutWarnings.Add(FString::Printf(TEXT("line %d: unknown key '%s'"), LineIndex + 1, *Key));
        }
    }
}

FString FInfinityCueDirectorSettings::Serialize(TFunctionRef<FString(const FGuid&)> LabelOf) const
{
    FString Out = TEXT("# Puss Cue Director: how the show runs in performance. Written by the Cue Desk panel;\n")
        TEXT("# safe to edit by hand. Applied in PIE at start and on F5.\n");
    Out += FString::Printf(TEXT("run_through = %s\n"), bRunThrough ? TEXT("true") : TEXT("false"));
    for (const FGuid& Guid : StopAfterSegments)
    {
        Out += FString::Printf(TEXT("stop_after = %s   # %s\n"), *Guid.ToString(EGuidFormats::Digits), *LabelOf(Guid));
    }
    for (const FString& Number : HoldGoNumbers)
    {
        Out += FString::Printf(TEXT("hold_go = %s\n"), *Number);
    }
    for (const FString& Scene : UseVideoScenes)
    {
        Out += FString::Printf(TEXT("use_video = %s\n"), *Scene);
    }
    Out += FString::Printf(TEXT("video_audio = %s\n"), *VideoAudio);
    return Out;
}

namespace InfinityStageCueSheet
{
FString ResolveSettingsPath()
{
    const FString Override = CVarCueDirectorSettingsPath.GetValueOnGameThread();
    return Override.IsEmpty()
        ? FPaths::Combine(FPaths::ProjectContentDir(), TEXT("InfinityStage/CueSheet/cue_director.txt"))
        : Override;
}

FString ResolvePath()
{
    const FString Override = CVarCueSheetPath.GetValueOnGameThread();
    if (!Override.IsEmpty())
    {
        return Override;
    }
    return FPaths::Combine(FPaths::ProjectContentDir(), TEXT("InfinityStage/CueSheet/Puss_Master_cue_sheet.csv"));
}

TArray<FString> DescribeLines(const FInfinityCueSheetRow& Row)
{
    TArray<FString> Out;
    for (const FInfinityCueSheetLine& Line : Row.Lines)
    {
        Out.Add(FString::Printf(TEXT("%s: %s"), *Line.Speaker.ToUpper(), *Line.Text));
    }
    return Out;
}

FString DescribeActions(const FInfinityCueSheetRow& Row)
{
    TArray<FString> Parts;
    const auto Add = [&Parts](const TCHAR* Tag, const FString& Value)
    {
        if (!Value.IsEmpty())
        {
            Parts.Add(FString::Printf(TEXT("%s: %s"), Tag, *Value.Replace(TEXT("\n"), TEXT(" / "))));
        }
    };
    Add(TEXT("LX"), Row.Light);
    Add(TEXT("SND"), Row.SoundTech);
    Add(TEXT("DO"), Row.Action);
    Add(TEXT("UE SOUND"), Row.SoundCue);
    Add(TEXT("STAGE"), Row.VideoCue);
    Add(TEXT("BEAT"), Row.Beat);
    Add(TEXT("NOTE"), Row.Notes);
    return FString::Join(Parts, TEXT("  |  "));
}

int32 NextStandbyRow(const FInfinityCueSheet& Sheet, const int32 From)
{
    for (int32 R = From + 1; R < Sheet.Rows.Num(); ++R)
    {
        const FInfinityCueSheetRow& Row = Sheet.Rows[R];
        if (!Row.Number.IsEmpty() || !Row.VideoCue.IsEmpty() || !Row.Beat.IsEmpty() || !Row.Light.IsEmpty())
        {
            return R;
        }
    }
    return INDEX_NONE;
}
}

bool UInfinityStageCueDirectorSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UInfinityStageCueDirectorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Reload();
}

void UInfinityStageCueDirectorSubsystem::ToggleRehearsalBar()
{
    UWorld* World = GetWorld();
    UGameViewportClient* Viewport = World ? World->GetGameViewport() : nullptr;
    APlayerController* Controller = World ? World->GetFirstPlayerController() : nullptr;
    if (!Viewport)
    {
        return;
    }
    if (RehearsalBarWidget.IsValid())
    {
        Viewport->RemoveViewportWidgetContent(RehearsalBarWidget.ToSharedRef());
        RehearsalBarWidget.Reset();
        if (Controller)
        {
            Controller->SetShowMouseCursor(false);
            Controller->SetInputMode(FInputModeGameOnly());
        }
        UE_LOG(LogInfinityStageCueSheet, Display, TEXT("INFINITY_REHEARSAL_BAR on=0"));
        return;
    }
    const TWeakObjectPtr<UWorld> WeakWorld(World);
    RehearsalBarWidget = SNew(SVerticalBox)
        .Visibility(EVisibility::SelfHitTestInvisible)   // the show stays clickable-through above the bar
        + SVerticalBox::Slot().FillHeight(1.0f)[SNullWidget::NullWidget]
        + SVerticalBox::Slot().AutoHeight()
        [
            SNew(SInfinityStageRehearsalBar).World([WeakWorld]() { return WeakWorld.Get(); })
        ];
    Viewport->AddViewportWidgetContent(RehearsalBarWidget.ToSharedRef(), 20);
    if (Controller)
    {
        // A cursor for the buttons; keys keep working because the buttons never take focus.
        Controller->SetShowMouseCursor(true);
        FInputModeGameAndUI Mode;
        Mode.SetHideCursorDuringCapture(false);
        Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        Controller->SetInputMode(Mode);
    }
    UE_LOG(LogInfinityStageCueSheet, Display, TEXT("INFINITY_REHEARSAL_BAR on=1"));
}

void UInfinityStageCueDirectorSubsystem::Deinitialize()
{
    if (RehearsalBarWidget.IsValid())
    {
        if (UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr)
        {
            Viewport->RemoveViewportWidgetContent(RehearsalBarWidget.ToSharedRef());
        }
        RehearsalBarWidget.Reset();
    }
    Super::Deinitialize();
}

void UInfinityStageCueDirectorSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    bSettingsApplied = ApplyToTransport();
}

void UInfinityStageCueDirectorSubsystem::Tick(const float DeltaTime)
{
    Super::Tick(DeltaTime);
    if (!bSettingsApplied)
    {
        bSettingsApplied = ApplyToTransport();
    }
}

bool UInfinityStageCueDirectorSubsystem::ApplyToTransport()
{
    UInfinityStageTransportController* Transport = UInfinityStageTransportController::FindForWorld(GetWorld());
    if (!Transport || Transport->Segments.IsEmpty())
    {
        return false;   // retried every tick until the Show transport exists
    }
    Transport->ApplyCueDirector(Settings.bRunThrough, Settings.StopAfterSegments, Settings.HoldGoNumbers);
    return true;
}

bool UInfinityStageCueDirectorSubsystem::Reload()
{
    const int32 KeepRow = Cursor.Row;
    {
        FString SettingsText;
        TArray<FString> SettingsWarnings;
        const FString SettingsPath = InfinityStageCueSheet::ResolveSettingsPath();
        if (FFileHelper::LoadFileToString(SettingsText, *SettingsPath))
        {
            Settings.Parse(SettingsText, SettingsWarnings);
        }
        else
        {
            Settings = FInfinityCueDirectorSettings();
        }
        for (const FString& Warning : SettingsWarnings)
        {
            UE_LOG(LogInfinityStageCueSheet, Warning, TEXT("INFINITY_CUE_DIRECTOR_SETTINGS_WARNING %s: %s"), *SettingsPath, *Warning);
        }
        bSettingsApplied = ApplyToTransport();
        if (UInfinityStageVideoFallbackSubsystem* Video = GetWorld() ? GetWorld()->GetSubsystem<UInfinityStageVideoFallbackSubsystem>() : nullptr)
        {
            Video->ReloadRegistry();
        }
    }
    const bool bOk = Sheet.LoadFromFile(InfinityStageCueSheet::ResolvePath());
    Cursor.Row = Sheet.Rows.IsEmpty() ? 0 : FMath::Clamp(KeepRow, 0, Sheet.Rows.Num() - 1);
    for (const FString& Warning : Sheet.Warnings)
    {
        UE_LOG(LogInfinityStageCueSheet, Warning, TEXT("INFINITY_CUESHEET_WARNING %s"), *Warning);
    }
    return bOk;
}

void UInfinityStageCueDirectorSubsystem::StepLine(const int32 Delta)
{
    for (int32 Step = 0; Step < FMath::Abs(Delta); ++Step)
    {
        if (!(Delta > 0 ? Cursor.Next(Sheet) : Cursor.Prev(Sheet)))
        {
            break;
        }
    }
    UE_LOG(LogInfinityStageCueSheet, Log, TEXT("INFINITY_CUESHEET_CURSOR row=%d sheet_row=%d"),
        Cursor.Row, Sheet.Rows.IsValidIndex(Cursor.Row) ? Sheet.Rows[Cursor.Row].SourceRow : -1);
}
