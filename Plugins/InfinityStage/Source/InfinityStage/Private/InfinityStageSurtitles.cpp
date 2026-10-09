#include "InfinityStageSurtitles.h"

#include <initializer_list>

#include "Brushes/SlateColorBrush.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Fonts/CompositeFont.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageSurtitles, Log, All);

namespace
{
TAutoConsoleVariable<int32> CVarSurtitles(
    TEXT("InfinityStage.Surtitles"),
    1,
    TEXT("1 show surtitles, 0 blackout (operator; key T in the show viewport)."));

TAutoConsoleVariable<FString> CVarSurtitlesPath(
    TEXT("InfinityStage.Surtitles.Path"),
    TEXT(""),
    TEXT("Surtitle sheet CSV. Empty: <Project>/Content/InfinityStage/CueSheet/Puss_Surtitles.csv"));

TAutoConsoleVariable<FString> CVarSurtitlesFont(
    TEXT("InfinityStage.Surtitles.Font"),
    TEXT(""),
    TEXT("TTF/OTF file. Empty: Content/InfinityStage/Surtitles/Fonts/Surtitle.ttf (or .otf), else Windows Georgia."));

TAutoConsoleVariable<float> CVarSurtitlesSize(
    TEXT("InfinityStage.Surtitles.Size"),
    54.0f,
    TEXT("Text size, in pixels of a 1920x1080 frame (scaled to the real viewport)."));

TAutoConsoleVariable<float> CVarSurtitlesTop(
    TEXT("InfinityStage.Surtitles.Top"),
    40.0f,
    TEXT("Gap above the bar, in pixels of a 1920x1080 frame (safe area for the real screen)."));

TAutoConsoleVariable<float> CVarSurtitlesBarOpacity(
    TEXT("InfinityStage.Surtitles.BarOpacity"),
    0.85f,
    TEXT("Black bar behind the text: 0 none, 1 solid."));

TAutoConsoleVariable<float> CVarSurtitlesFade(
    TEXT("InfinityStage.Surtitles.Fade"),
    0.3f,
    TEXT("Fade in/out, seconds. 0: hard cuts."));

TAutoConsoleVariable<int32> CVarSurtitlesSpeakers(
    TEXT("InfinityStage.Surtitles.Speakers"),
    0,
    TEXT("1: show the Speaker column, small, above the line."));

/** Over the show and the video fallback (5), under the rehearsal bar (20). */
constexpr int32 SurtitleZOrder = 10;
/** The show's frame rate, for hh:mm:ss:ff. */
constexpr double SurtitleSheetFps = 25.0;
/** The layout's reference frame; SScaleBox fits it to the viewport. */
constexpr float SurtitleFrameWidth = 1920.0f;
constexpr float SurtitleFrameHeight = 1080.0f;

TCHAR SurtitleKindLetter(const EInfinityCueType Type)
{
    switch (Type)
    {
    case EInfinityCueType::WingPair: return TEXT('P');
    case EInfinityCueType::Scene: return TEXT('S');
    case EInfinityCueType::Sequence: return TEXT('I');
    default: return TEXT('?');
    }
}

bool SurtitleKeyMatches(const FString& Key, const TArray<FInfinityTransportSegment>& Segments, const int32 SegmentIndex)
{
    const FString Trimmed = Key.TrimStartAndEnd();
    if (Trimmed.IsEmpty() || !Segments.IsValidIndex(SegmentIndex))
    {
        return false;
    }
    return Trimmed.Equals(InfinityStageSurtitles::SegmentCode(Segments, SegmentIndex), ESearchCase::IgnoreCase)
        || Trimmed.Equals(Segments[SegmentIndex].Label.ToString().TrimStartAndEnd(), ESearchCase::IgnoreCase);
}

int32 FindSurtitleColumn(const TArray<FString>& Header, std::initializer_list<const TCHAR*> Names)
{
    for (int32 Column = 0; Column < Header.Num(); ++Column)
    {
        const FString Cell = Header[Column].TrimStartAndEnd();
        for (const TCHAR* Name : Names)
        {
            if (Cell.Equals(Name, ESearchCase::IgnoreCase))
            {
                return Column;
            }
        }
    }
    return INDEX_NONE;
}

FString SurtitleCell(const TArray<FString>& Row, const int32 Column)
{
    return Row.IsValidIndex(Column) ? Row[Column].TrimStartAndEnd() : FString();
}

FString ResolveSurtitleFontPath()
{
    const FString Override = CVarSurtitlesFont.GetValueOnGameThread();
    if (!Override.IsEmpty())
    {
        return FPaths::FileExists(Override) ? Override : FString();
    }
    const FString Dir = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("InfinityStage/Surtitles/Fonts"));
    for (const TCHAR* Name : { TEXT("Surtitle.ttf"), TEXT("Surtitle.otf") })
    {
        const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(Dir, Name));
        if (FPaths::FileExists(Path))
        {
            return Path;
        }
    }
    const FString Georgia = TEXT("C:/Windows/Fonts/georgia.ttf");
    return FPaths::FileExists(Georgia) ? Georgia : FString();
}

void SurtitleDumpWorld(UWorld* World)
{
    if (UInfinityStageSurtitleSubsystem* Surtitles = World ? World->GetSubsystem<UInfinityStageSurtitleSubsystem>() : nullptr)
    {
        Surtitles->Dump();
    }
    else
    {
        UE_LOG(LogInfinityStageSurtitles, Warning, TEXT("INFINITY_SURTITLES_DUMP no game world (start PIE or the show first)"));
    }
}

void SurtitleReloadWorld(UWorld* World)
{
    if (UInfinityStageSurtitleSubsystem* Surtitles = World ? World->GetSubsystem<UInfinityStageSurtitleSubsystem>() : nullptr)
    {
        Surtitles->Reload();
    }
}

UInfinityStageSurtitleSubsystem* SurtitleSubsystemOf(UWorld* World)
{
    UInfinityStageSurtitleSubsystem* Surtitles = World ? World->GetSubsystem<UInfinityStageSurtitleSubsystem>() : nullptr;
    if (!Surtitles)
    {
        UE_LOG(LogInfinityStageSurtitles, Warning, TEXT("INFINITY_SURTITLES_CONTROL no game world (start PIE or the show first)"));
    }
    return Surtitles;
}

void LogSurtitleControl(UInfinityStageSurtitleSubsystem* Surtitles, const TCHAR* What, const bool bOk)
{
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_CONTROL %s ok=%d %s | %s"),
        What, bOk ? 1 : 0, *Surtitles->GetLastMessage(), *Surtitles->DescribeSelected());
}

void SurtitleStepWorld(const TArray<FString>& Args, UWorld* World)
{
    if (UInfinityStageSurtitleSubsystem* Surtitles = SurtitleSubsystemOf(World))
    {
        const int32 Delta = Args.Num() > 0 && FCString::Atoi(*Args[0]) < 0 ? -1 : 1;
        LogSurtitleControl(Surtitles, Delta > 0 ? TEXT("next") : TEXT("previous"), Surtitles->StepLine(Delta));
    }
}

void SurtitleStampWorld(const TArray<FString>& Args, UWorld* World)
{
    if (UInfinityStageSurtitleSubsystem* Surtitles = SurtitleSubsystemOf(World))
    {
        const bool bOut = Args.Num() > 0 && Args[0].Equals(TEXT("Out"), ESearchCase::IgnoreCase);
        LogSurtitleControl(Surtitles, bOut ? TEXT("stamp_out") : TEXT("stamp_in"), Surtitles->StampAtPlayhead(bOut));
    }
}

void SurtitleNudgeWorld(const TArray<FString>& Args, UWorld* World)
{
    if (UInfinityStageSurtitleSubsystem* Surtitles = SurtitleSubsystemOf(World))
    {
        const bool bOut = Args.Num() > 0 && Args[0].Equals(TEXT("Out"), ESearchCase::IgnoreCase);
        const double Delta = Args.Num() > 1 ? FCString::Atod(*Args[1]) : 0.0;
        LogSurtitleControl(Surtitles, bOut ? TEXT("nudge_out") : TEXT("nudge_in"), Surtitles->Nudge(bOut, Delta));
    }
}

FAutoConsoleCommandWithWorldAndArgs SurtitleStepCommand(
    TEXT("InfinityStage.Surtitles.Step"),
    TEXT("1 next / -1 previous surtitle: scrubs there (pauses) and selects it."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&SurtitleStepWorld));

FAutoConsoleCommandWithWorldAndArgs SurtitleStampCommand(
    TEXT("InfinityStage.Surtitles.Stamp"),
    TEXT("In | Out: sets the selected surtitle's In or Out to the playhead, in the sheet."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&SurtitleStampWorld));

FAutoConsoleCommandWithWorldAndArgs SurtitleNudgeCommand(
    TEXT("InfinityStage.Surtitles.Nudge"),
    TEXT("In | Out <seconds>: moves the selected surtitle's In or Out, in the sheet."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&SurtitleNudgeWorld));

FAutoConsoleCommandWithWorld SurtitleDumpCommand(
    TEXT("InfinityStage.Surtitles.Dump"),
    TEXT("Logs every surtitle line at its absolute Master time (INFINITY_SURTITLE rows)."),
    FConsoleCommandWithWorldDelegate::CreateStatic(&SurtitleDumpWorld));

FAutoConsoleCommandWithWorld SurtitleReloadCommand(
    TEXT("InfinityStage.Surtitles.Reload"),
    TEXT("Re-reads the surtitle sheet."),
    FConsoleCommandWithWorldDelegate::CreateStatic(&SurtitleReloadWorld));
}

// ---------------------------------------------------------------------------

bool FInfinitySurtitleScript::LoadFromCsvText(const FString& Text)
{
    Lines.Reset();
    Warnings.Reset();

    TArray<TArray<FString>> Table;
    FInfinityCueSheet::ParseCsv(Text, Table);

    int32 HeaderRow = INDEX_NONE;
    for (int32 Row = 0; Row < Table.Num() && HeaderRow == INDEX_NONE; ++Row)
    {
        if (FindSurtitleColumn(Table[Row], { TEXT("Segment") }) != INDEX_NONE)
        {
            HeaderRow = Row;
        }
    }
    if (HeaderRow == INDEX_NONE)
    {
        Warnings.Add(TEXT("no header row (a cell \"Segment\")"));
        return false;
    }
    const TArray<FString>& Header = Table[HeaderRow];
    const int32 SegmentColumn = FindSurtitleColumn(Header, { TEXT("Segment") });
    const int32 InColumn = FindSurtitleColumn(Header, { TEXT("In"), TEXT("Start") });
    const int32 OutColumn = FindSurtitleColumn(Header, { TEXT("Out"), TEXT("End") });
    const int32 SpeakerColumn = FindSurtitleColumn(Header, { TEXT("Speaker") });
    const int32 TextColumn = FindSurtitleColumn(Header, { TEXT("Text"), TEXT("Surtitle"), TEXT("Line") });
    const int32 KeyColumn = FindSurtitleColumn(Header, { TEXT("Key") });
    if (InColumn == INDEX_NONE || TextColumn == INDEX_NONE)
    {
        Warnings.Add(TEXT("the header needs In and Text columns"));
        return false;
    }

    FString CarriedSegment;
    for (int32 Row = HeaderRow + 1; Row < Table.Num(); ++Row)
    {
        const TArray<FString>& Cells = Table[Row];
        const int32 SourceRow = Row + 1;
        const FString SegmentCell = SurtitleCell(Cells, SegmentColumn);
        if (!SegmentCell.IsEmpty())
        {
            CarriedSegment = SegmentCell;
        }
        const FString InCell = SurtitleCell(Cells, InColumn);
        const FString LineText = SurtitleCell(Cells, TextColumn);
        if (InCell.IsEmpty())
        {
            if (!LineText.IsEmpty())
            {
                Warnings.Add(FString::Printf(TEXT("row %d: text with no In time, skipped"), SourceRow));
            }
            continue;
        }

        FInfinitySurtitleLine Line;
        Line.SourceRow = SourceRow;
        Line.Segment = CarriedSegment;
        Line.Speaker = SurtitleCell(Cells, SpeakerColumn);
        Line.Key = SurtitleCell(Cells, KeyColumn);
        Line.Text = LineText;
        if (Line.Segment.IsEmpty())
        {
            Warnings.Add(FString::Printf(TEXT("row %d: no Segment yet, skipped"), SourceRow));
            continue;
        }
        if (!InfinityStageSurtitles::ParseTime(InCell, SurtitleSheetFps, Line.InSeconds))
        {
            Warnings.Add(FString::Printf(TEXT("row %d: In \"%s\" is not a time, skipped"), SourceRow, *InCell));
            continue;
        }
        const FString OutCell = SurtitleCell(Cells, OutColumn);
        if (!OutCell.IsEmpty())
        {
            double Out = 0.0;
            if (!InfinityStageSurtitles::ParseTime(OutCell, SurtitleSheetFps, Out))
            {
                Warnings.Add(FString::Printf(TEXT("row %d: Out \"%s\" is not a time; held to the next line"), SourceRow, *OutCell));
            }
            else if (Out <= Line.InSeconds)
            {
                Warnings.Add(FString::Printf(TEXT("row %d: Out is not after In, skipped"), SourceRow));
                continue;
            }
            else
            {
                Line.OutSeconds = Out;
            }
        }
        Lines.Add(MoveTemp(Line));
    }
    return true;
}

bool FInfinitySurtitleScript::LoadFromFile(const FString& Path)
{
    SourcePath = Path;
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path))
    {
        Lines.Reset();
        Warnings.Reset();
        Warnings.Add(FString::Printf(TEXT("cannot read %s"), *Path));
        return false;
    }
    return LoadFromCsvText(Text);
}

// ---------------------------------------------------------------------------

namespace InfinityStageSurtitles
{
bool ParseTime(const FString& Text, const double Fps, double& OutSeconds)
{
    TArray<FString> Fields;
    Text.TrimStartAndEnd().ParseIntoArray(Fields, TEXT(":"), false);
    if (Fields.Num() < 1 || Fields.Num() > 4)
    {
        return false;
    }
    TArray<double> Values;
    for (const FString& Field : Fields)
    {
        const FString Trimmed = Field.TrimStartAndEnd();
        double Value = 0.0;
        if (Trimmed.IsEmpty() || Trimmed.StartsWith(TEXT("-")) || !LexTryParseString(Value, *Trimmed))
        {
            return false;
        }
        Values.Add(Value);
    }
    double Seconds = 0.0;
    switch (Values.Num())
    {
    case 1: Seconds = Values[0]; break;
    case 2: Seconds = Values[0] * 60.0 + Values[1]; break;
    case 3: Seconds = Values[0] * 3600.0 + Values[1] * 60.0 + Values[2]; break;
    default:
        if (Fps <= 0.0 || Values[3] >= Fps)
        {
            return false;
        }
        Seconds = Values[0] * 3600.0 + Values[1] * 60.0 + Values[2] + Values[3] / Fps;
        break;
    }
    OutSeconds = Seconds;
    return true;
}

FString FormatTime(const double Seconds)
{
    const double Clamped = FMath::Max(0.0, Seconds);
    const int32 Minutes = FMath::FloorToInt32(Clamped / 60.0);
    return FString::Printf(TEXT("%d:%05.2f"), Minutes, Clamped - Minutes * 60.0);
}

FString SegmentCode(const TArray<FInfinityTransportSegment>& Segments, const int32 SegmentIndex)
{
    if (!Segments.IsValidIndex(SegmentIndex))
    {
        return FString();
    }
    const EInfinityCueType Type = Segments[SegmentIndex].Type;
    int32 Ordinal = 0;
    for (int32 Index = 0; Index <= SegmentIndex; ++Index)
    {
        Ordinal += Segments[Index].Type == Type ? 1 : 0;
    }
    return FString::Printf(TEXT("%c%d"), SurtitleKindLetter(Type), Ordinal);
}

bool LineMatchesSegment(const FInfinitySurtitleLine& Line, const TArray<FInfinityTransportSegment>& Segments, const int32 SegmentIndex)
{
    return SurtitleKeyMatches(Line.Segment, Segments, SegmentIndex);
}

int32 ResolveSegment(const FString& Key, const TArray<FInfinityTransportSegment>& Segments)
{
    for (int32 Index = 0; Index < Segments.Num(); ++Index)
    {
        if (SurtitleKeyMatches(Key, Segments, Index))
        {
            return Index;
        }
    }
    return INDEX_NONE;
}

double SegmentSeconds(const FInfinityTransportSegment& Segment, const double TicksPerSecond)
{
    return TicksPerSecond > 0.0 ? double(Segment.EndFrame.Value - Segment.StartFrame.Value) / TicksPerSecond : 0.0;
}

double EffectiveOut(
    const FInfinitySurtitleScript& Script,
    const int32 LineIndex,
    const TArray<FInfinityTransportSegment>& Segments,
    const int32 SegmentIndex,
    const double TicksPerSecond)
{
    const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
    if (Line.OutSeconds >= 0.0)
    {
        return Line.OutSeconds;
    }
    double Out = Segments.IsValidIndex(SegmentIndex) ? SegmentSeconds(Segments[SegmentIndex], TicksPerSecond) : TNumericLimits<double>::Max();
    for (int32 Other = 0; Other < Script.Lines.Num(); ++Other)
    {
        const FInfinitySurtitleLine& Next = Script.Lines[Other];
        if (Other != LineIndex && Next.InSeconds > Line.InSeconds && Next.InSeconds < Out
            && LineMatchesSegment(Next, Segments, SegmentIndex))
        {
            Out = Next.InSeconds;
        }
    }
    return Out;
}

FInfinitySurtitleShown Evaluate(
    const FInfinitySurtitleScript& Script,
    const TArray<FInfinityTransportSegment>& Segments,
    const int64 MasterFrame,
    const double TicksPerSecond,
    const double FadeSeconds)
{
    FInfinitySurtitleShown Shown;
    if (TicksPerSecond <= 0.0)
    {
        return Shown;
    }
    for (int32 Index = 0; Index < Segments.Num(); ++Index)
    {
        if (MasterFrame >= Segments[Index].StartFrame.Value && MasterFrame < Segments[Index].EndFrame.Value)
        {
            Shown.SegmentIndex = Index;
            break;
        }
    }
    if (Shown.SegmentIndex == INDEX_NONE)
    {
        return Shown;
    }
    const double Local = double(MasterFrame - Segments[Shown.SegmentIndex].StartFrame.Value) / TicksPerSecond;

    double BestIn = -1.0;
    double BestOut = 0.0;
    for (int32 LineIndex = 0; LineIndex < Script.Lines.Num(); ++LineIndex)
    {
        const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
        // >= : of two lines with the same In, the later sheet row wins.
        if (Line.InSeconds > Local || Line.InSeconds < BestIn || !LineMatchesSegment(Line, Segments, Shown.SegmentIndex))
        {
            continue;
        }
        const double Out = EffectiveOut(Script, LineIndex, Segments, Shown.SegmentIndex, TicksPerSecond);
        if (Local < Out)
        {
            Shown.LineIndex = LineIndex;
            BestIn = Line.InSeconds;
            BestOut = Out;
        }
    }
    if (Shown.LineIndex != INDEX_NONE)
    {
        const double Edge = FMath::Min(Local - BestIn, BestOut - Local);
        Shown.Opacity = FadeSeconds > 0.0 ? float(FMath::Clamp(Edge / FadeSeconds, 0.0, 1.0)) : 1.0f;
    }
    return Shown;
}

FString SerializeCsv(const TArray<TArray<FString>>& Table, const TCHAR* LineEnd)
{
    FString Out;
    for (const TArray<FString>& Row : Table)
    {
        for (int32 Column = 0; Column < Row.Num(); ++Column)
        {
            const FString& Value = Row[Column];
            if (Column > 0)
            {
                Out.AppendChar(TEXT(','));
            }
            int32 Unused = 0;
            if (Value.FindChar(TEXT(','), Unused) || Value.FindChar(TEXT('"'), Unused)
                || Value.FindChar(TEXT('\n'), Unused) || Value.FindChar(TEXT('\r'), Unused))
            {
                Out += TEXT("\"") + Value.Replace(TEXT("\""), TEXT("\"\"")) + TEXT("\"");
            }
            else
            {
                Out += Value;
            }
        }
        Out += LineEnd;
    }
    return Out;
}

bool SetLineTime(FString& InOutCsvText, const FInfinitySurtitleLine& Line, const bool bOut, const double Seconds, FString& OutError)
{
    TArray<TArray<FString>> Table;
    FInfinityCueSheet::ParseCsv(InOutCsvText, Table);
    int32 HeaderRow = INDEX_NONE;
    for (int32 Row = 0; Row < Table.Num() && HeaderRow == INDEX_NONE; ++Row)
    {
        if (FindSurtitleColumn(Table[Row], { TEXT("Segment") }) != INDEX_NONE)
        {
            HeaderRow = Row;
        }
    }
    const int32 RowIndex = Line.SourceRow - 1;
    if (HeaderRow == INDEX_NONE || RowIndex <= HeaderRow || !Table.IsValidIndex(RowIndex))
    {
        OutError = FString::Printf(TEXT("row %d is not in the sheet any more"), Line.SourceRow);
        return false;
    }
    const TArray<FString>& Header = Table[HeaderRow];
    const int32 InColumn = FindSurtitleColumn(Header, { TEXT("In"), TEXT("Start") });
    const int32 OutColumn = FindSurtitleColumn(Header, { TEXT("Out"), TEXT("End") });
    const int32 KeyColumn = FindSurtitleColumn(Header, { TEXT("Key") });
    TArray<FString>& Cells = Table[RowIndex];

    // Stale guard: the row on disk must still be the line we loaded.
    double DiskIn = -1.0;
    if (SurtitleCell(Cells, KeyColumn) != Line.Key
        || !ParseTime(SurtitleCell(Cells, InColumn), SurtitleSheetFps, DiskIn) || !FMath::IsNearlyEqual(DiskIn, Line.InSeconds, 1e-6))
    {
        OutError = FString::Printf(TEXT("row %d changed on disk; reloaded, try again"), Line.SourceRow);
        return false;
    }
    const int32 Column = bOut ? OutColumn : InColumn;
    if (Column == INDEX_NONE)
    {
        OutError = TEXT("the sheet has no Out column");
        return false;
    }
    if (Seconds < 0.0)
    {
        OutError = TEXT("a time cannot be before the segment start");
        return false;
    }
    double OtherOut = -1.0;
    const bool bHasOut = ParseTime(SurtitleCell(Cells, OutColumn), SurtitleSheetFps, OtherOut);
    if ((bOut && Seconds <= Line.InSeconds) || (!bOut && bHasOut && OtherOut <= Seconds))
    {
        OutError = TEXT("Out must stay after In");
        return false;
    }
    while (Cells.Num() <= Column)
    {
        Cells.Add(FString());
    }
    Cells[Column] = FormatTime(Seconds);
    InOutCsvText = SerializeCsv(Table, InOutCsvText.Contains(TEXT("\r\n")) ? TEXT("\r\n") : TEXT("\n"));
    return true;
}

double LandingSeconds(const FInfinitySurtitleLine& Line, const double OutSeconds, const double FadeSeconds)
{
    return Line.InSeconds + FMath::Min(FMath::Max(0.0, FadeSeconds), FMath::Max(0.0, (OutSeconds - Line.InSeconds) * 0.5));
}

int32 FindStepTarget(
    const FInfinitySurtitleScript& Script,
    const TArray<FInfinityTransportSegment>& Segments,
    const int64 MasterFrame,
    const double TicksPerSecond,
    const double FadeSeconds,
    const int32 Delta,
    int64& OutLandingFrame)
{
    int32 Best = INDEX_NONE;
    int64 BestFrame = 0;
    for (int32 LineIndex = 0; LineIndex < Script.Lines.Num(); ++LineIndex)
    {
        const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
        const int32 SegmentIndex = ResolveSegment(Line.Segment, Segments);
        if (Line.Text.IsEmpty() || SegmentIndex == INDEX_NONE)
        {
            continue;
        }
        const double Out = EffectiveOut(Script, LineIndex, Segments, SegmentIndex, TicksPerSecond);
        const int64 Land = Segments[SegmentIndex].StartFrame.Value
            + int64(FMath::RoundToDouble(LandingSeconds(Line, Out, FadeSeconds) * TicksPerSecond));
        const bool bAhead = Delta > 0 ? Land > MasterFrame : Land < MasterFrame;
        const bool bCloser = Best == INDEX_NONE || (Delta > 0 ? Land < BestFrame : Land > BestFrame);
        if (bAhead && bCloser)
        {
            Best = LineIndex;
            BestFrame = Land;
        }
    }
    OutLandingFrame = BestFrame;
    return Best;
}

FString ResolvePath()
{
    const FString Override = CVarSurtitlesPath.GetValueOnGameThread();
    return Override.IsEmpty()
        ? FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("InfinityStage/CueSheet/Puss_Surtitles.csv")))
        : Override;
}

void ToggleBlackout()
{
    const int32 Next = CVarSurtitles.GetValueOnGameThread() != 0 ? 0 : 1;
    CVarSurtitles->Set(Next, ECVF_SetByConsole);
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_%s"), Next ? TEXT("ON") : TEXT("BLACKOUT"));
}
}

// ---------------------------------------------------------------------------

bool UInfinityStageSurtitleSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UInfinityStageSurtitleSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Reload();
}

void UInfinityStageSurtitleSubsystem::Deinitialize()
{
    if (bOverlayAdded && Overlay.IsValid() && GetWorld() && GetWorld()->GetGameViewport())
    {
        GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(Overlay.ToSharedRef());
    }
    bOverlayAdded = false;
    Super::Deinitialize();
}

bool UInfinityStageSurtitleSubsystem::Reload()
{
    const FString Path = InfinityStageSurtitles::ResolvePath();
    LoadedStamp = IFileManager::Get().GetTimeStamp(*Path);
    // Keep the selection across a reload (a Cue Book export lands while rehearsing): by Key, else by row.
    const FInfinitySurtitleLine Selected = Script.Lines.IsValidIndex(SelectedLine) ? Script.Lines[SelectedLine] : FInfinitySurtitleLine();
    const bool bOk = Script.LoadFromFile(Path);
    ShownLine = INDEX_NONE;
    SelectedLine = Selected.SourceRow == 0 ? INDEX_NONE : Script.Lines.IndexOfByPredicate([&Selected](const FInfinitySurtitleLine& Each)
    {
        return Selected.Key.IsEmpty() ? Each.SourceRow == Selected.SourceRow : Each.Key == Selected.Key;
    });
    for (const FString& Warning : Script.Warnings)
    {
        UE_LOG(LogInfinityStageSurtitles, Warning, TEXT("INFINITY_SURTITLES_WARNING %s"), *Warning);
    }
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_LOADED ok=%d lines=%d warnings=%d path=%s"),
        bOk ? 1 : 0, Script.Lines.Num(), Script.Warnings.Num(), *Path);
    return bOk;
}

AInfinityStageShowRoot* UInfinityStageSurtitleSubsystem::FindRoot()
{
    if (!Root.IsValid() && GetWorld())
    {
        for (TActorIterator<AInfinityStageShowRoot> It(GetWorld()); It; ++It)
        {
            if (It->Transport && It->ShowAsset)
            {
                Root = *It;
                break;
            }
        }
    }
    return Root.Get();
}

void UInfinityStageSurtitleSubsystem::Dump()
{
    AInfinityStageShowRoot* ShowRoot = FindRoot();
    if (!ShowRoot)
    {
        UE_LOG(LogInfinityStageSurtitles, Warning, TEXT("INFINITY_SURTITLES_DUMP no Show Root in this world"));
        return;
    }
    const TArray<FInfinityTransportSegment>& Segments = ShowRoot->Transport->Segments;
    const double Ticks = ShowRoot->ShowAsset->TickResolution.AsDecimal();
    int32 Unresolved = 0;
    for (int32 LineIndex = 0; LineIndex < Script.Lines.Num(); ++LineIndex)
    {
        const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
        const int32 SegmentIndex = InfinityStageSurtitles::ResolveSegment(Line.Segment, Segments);
        const FString OneLine = Line.Text.Replace(TEXT("\r"), TEXT("")).Replace(TEXT("\n"), TEXT(" / "));
        if (SegmentIndex == INDEX_NONE)
        {
            ++Unresolved;
            UE_LOG(LogInfinityStageSurtitles, Warning, TEXT("INFINITY_SURTITLE_UNRESOLVED row=%d segment=\"%s\" text=\"%s\""),
                Line.SourceRow, *Line.Segment, *OneLine);
            continue;
        }
        const double Out = InfinityStageSurtitles::EffectiveOut(Script, LineIndex, Segments, SegmentIndex, Ticks);
        const double Length = InfinityStageSurtitles::SegmentSeconds(Segments[SegmentIndex], Ticks);
        const double MasterIn = Segments[SegmentIndex].StartFrame.Value / Ticks + Line.InSeconds;
        UE_LOG(LogInfinityStageSurtitles, Display,
            TEXT("INFINITY_SURTITLE row=%d seg=%s (%s) in=%s out=%s hold=%.1fs master=%s%s speaker=\"%s\" text=\"%s\""),
            Line.SourceRow, *InfinityStageSurtitles::SegmentCode(Segments, SegmentIndex),
            *Segments[SegmentIndex].Label.ToString(),
            *InfinityStageSurtitles::FormatTime(Line.InSeconds), *InfinityStageSurtitles::FormatTime(Out),
            Out - Line.InSeconds, *InfinityStageSurtitles::FormatTime(MasterIn),
            Line.InSeconds >= Length ? TEXT(" PAST_SEGMENT_END") : TEXT(""),
            *Line.Speaker, *OneLine);
    }
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_DUMP lines=%d unresolved=%d path=%s"),
        Script.Lines.Num(), Unresolved, *Script.SourcePath);
}

void UInfinityStageSurtitleSubsystem::ApplyStyle()
{
    UGameViewportClient* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;
    if (!Viewport)
    {
        return;
    }
    const FString FontPath = ResolveSurtitleFontPath();
    const float Size = FMath::Max(8.0f, CVarSurtitlesSize.GetValueOnGameThread());
    const float Top = FMath::Max(0.0f, CVarSurtitlesTop.GetValueOnGameThread());
    const float BarOpacity = FMath::Clamp(CVarSurtitlesBarOpacity.GetValueOnGameThread(), 0.0f, 1.0f);
    const bool bSpeakers = CVarSurtitlesSpeakers.GetValueOnGameThread() != 0;
    const FString Key = FString::Printf(TEXT("%s|%.1f|%.1f|%.3f|%d"), *FontPath, Size, Top, BarOpacity, bSpeakers ? 1 : 0);
    if (bOverlayAdded && Key == StyleKey)
    {
        return;
    }
    StyleKey = Key;

    if (bOverlayAdded && Overlay.IsValid())
    {
        Viewport->RemoveViewportWidgetContent(Overlay.ToSharedRef());
        bOverlayAdded = false;
    }

    FSlateFontInfo TextFont = FCoreStyle::GetDefaultFontStyle("Regular", Size);
    FSlateFontInfo SpeakerFont = FCoreStyle::GetDefaultFontStyle("Regular", Size * 0.55f);
    if (!FontPath.IsEmpty())
    {
        Font = MakeShared<FStandaloneCompositeFont>(NAME_None, FontPath, EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
        TextFont = FSlateFontInfo(Font, Size);
        SpeakerFont = FSlateFontInfo(Font, Size * 0.55f);
    }
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_STYLE font=%s size=%.1f top=%.1f bar=%.2f speakers=%d"),
        FontPath.IsEmpty() ? TEXT("<engine default>") : *FontPath, Size, Top, BarOpacity, bSpeakers ? 1 : 0);

    BarBrush = MakeShared<FSlateColorBrush>(FLinearColor::White);
    Overlay = SNew(SScaleBox)
        .Stretch(EStretch::ScaleToFit)
        .Visibility(EVisibility::Collapsed)
        [
            SNew(SBox)
            .WidthOverride(SurtitleFrameWidth)
            .HeightOverride(SurtitleFrameHeight)
            [
                SNew(SVerticalBox)
                + SVerticalBox::Slot()
                .AutoHeight()
                .HAlign(HAlign_Center)
                .Padding(0.0f, Top, 0.0f, 0.0f)
                [
                    SAssignNew(Bar, SBorder)
                    .BorderImage(BarBrush.Get())
                    .BorderBackgroundColor(FLinearColor(0.0f, 0.0f, 0.0f, BarOpacity))
                    .Padding(FMargin(Size * 0.7f, Size * 0.22f))
                    [
                        SNew(SBox)
                        .MaxDesiredWidth(SurtitleFrameWidth * 0.8f)
                        [
                            SNew(SVerticalBox)
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            .HAlign(HAlign_Center)
                            [
                                SAssignNew(SpeakerBlock, STextBlock)
                                .Font(SpeakerFont)
                                .ColorAndOpacity(FLinearColor(0.75f, 0.75f, 0.75f))
                                .Justification(ETextJustify::Center)
                                .Visibility(EVisibility::Collapsed)
                            ]
                            + SVerticalBox::Slot()
                            .AutoHeight()
                            .HAlign(HAlign_Center)
                            [
                                SAssignNew(TextBlock, STextBlock)
                                .Font(TextFont)
                                .ColorAndOpacity(FLinearColor::White)
                                .Justification(ETextJustify::Center)
                                .AutoWrapText(true)
                            ]
                        ]
                    ]
                ]
            ]
        ];
    Viewport->AddViewportWidgetContent(Overlay.ToSharedRef(), SurtitleZOrder);
    bOverlayAdded = true;
    ShownLine = INDEX_NONE;
}

void UInfinityStageSurtitleSubsystem::Tick(const float DeltaTime)
{
    Super::Tick(DeltaTime);

    // Pick up edits to the sheet without a key press.
    const double Now = FPlatformTime::Seconds();
    if (Now >= NextStampCheck)
    {
        NextStampCheck = Now + 1.0;
        if (IFileManager::Get().GetTimeStamp(*InfinityStageSurtitles::ResolvePath()) != LoadedStamp)
        {
            Reload();
        }
    }

    AInfinityStageShowRoot* ShowRoot = FindRoot();
    if (!ShowRoot || Script.Lines.IsEmpty())
    {
        if (bOverlayAdded)
        {
            Overlay->SetVisibility(EVisibility::Collapsed);
        }
        return;
    }
    ApplyStyle();
    if (!bOverlayAdded)
    {
        return;
    }

    FInfinitySurtitleShown Shown;
    if (CVarSurtitles.GetValueOnGameThread() != 0)
    {
        Shown = InfinityStageSurtitles::Evaluate(
            Script,
            ShowRoot->Transport->Segments,
            ShowRoot->Transport->GetCurrentMasterFrame().Value,
            ShowRoot->ShowAsset->TickResolution.AsDecimal(),
            FMath::Max(0.0f, CVarSurtitlesFade.GetValueOnGameThread()));
    }
    const FInfinitySurtitleLine* Line = Script.Lines.IsValidIndex(Shown.LineIndex) ? &Script.Lines[Shown.LineIndex] : nullptr;
    if (!Line || Line->Text.IsEmpty())
    {
        // A row with a time and no text clears the line before it.
        Overlay->SetVisibility(EVisibility::Collapsed);
        ShownLine = INDEX_NONE;
        return;
    }
    if (Shown.LineIndex != ShownLine)
    {
        ShownLine = Shown.LineIndex;
        TextBlock->SetText(FText::FromString(Line->Text.Replace(TEXT("\r"), TEXT(""))));
        const bool bSpeaker = CVarSurtitlesSpeakers.GetValueOnGameThread() != 0 && !Line->Speaker.IsEmpty();
        SpeakerBlock->SetText(FText::FromString(Line->Speaker.ToUpper()));
        SpeakerBlock->SetVisibility(bSpeaker ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
    }
    Bar->SetRenderOpacity(Shown.Opacity);
    Overlay->SetVisibility(EVisibility::HitTestInvisible);
}

// --- Rehearsal controls ----------------------------------------------------

bool UInfinityStageSurtitleSubsystem::Fail(const FString& Message)
{
    LastMessage = Message;
    return false;
}

int32 UInfinityStageSurtitleSubsystem::GetSelectedLine() const
{
    return Script.Lines.IsValidIndex(SelectedLine) ? SelectedLine
        : (Script.Lines.IsValidIndex(ShownLine) ? ShownLine : INDEX_NONE);
}

FString UInfinityStageSurtitleSubsystem::DescribeSelected() const
{
    const int32 LineIndex = GetSelectedLine();
    if (LineIndex == INDEX_NONE)
    {
        return TEXT("no surtitle selected");
    }
    const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
    const FString Out = Line.OutSeconds >= 0.0 ? InfinityStageSurtitles::FormatTime(Line.OutSeconds) : FString(TEXT("next"));
    FString Text = Line.Text.Replace(TEXT("\r"), TEXT("")).Replace(TEXT("\n"), TEXT(" / "));
    if (Text.Len() > 60)
    {
        Text = Text.Left(57) + TEXT("...");
    }
    const FString KeyPart = Line.Key.IsEmpty() ? FString() : FString::Printf(TEXT(" [%s]"), *Line.Key);
    return FString::Printf(TEXT("%s row %d%s %s-%s %s%s%s"),
        *Line.Segment, Line.SourceRow, *KeyPart,
        *InfinityStageSurtitles::FormatTime(Line.InSeconds), *Out,
        *Line.Speaker, Line.Speaker.IsEmpty() ? TEXT("") : TEXT(": "), *Text);
}

bool UInfinityStageSurtitleSubsystem::StepLine(const int32 Delta)
{
    AInfinityStageShowRoot* ShowRoot = FindRoot();
    if (!ShowRoot)
    {
        return Fail(TEXT("no Show Root"));
    }
    UInfinityStageTransportController& Transport = *ShowRoot->Transport;
    int64 Landing = 0;
    const int32 Target = InfinityStageSurtitles::FindStepTarget(
        Script, Transport.Segments, Transport.GetCurrentMasterFrame().Value,
        ShowRoot->ShowAsset->TickResolution.AsDecimal(),
        FMath::Max(0.0f, CVarSurtitlesFade.GetValueOnGameThread()), Delta, Landing);
    if (Target == INDEX_NONE)
    {
        return Fail(Delta > 0 ? TEXT("no later surtitle") : TEXT("no earlier surtitle"));
    }
    const EInfinityTransportResult Result = Transport.ScrubToMasterFrame(FFrameNumber(int32(Landing)));
    if (Result != EInfinityTransportResult::Succeeded)
    {
        // Never forced: a refusal is the transport's rule (e.g. a Scene in Performance mode).
        return Fail(FString::Printf(TEXT("transport refused the jump (result=%d)"), int32(Result)));
    }
    SelectedLine = Target;
    LastMessage = TEXT("jumped");
    return true;
}

bool UInfinityStageSurtitleSubsystem::StampAtPlayhead(const bool bOut)
{
    AInfinityStageShowRoot* ShowRoot = FindRoot();
    const int32 LineIndex = GetSelectedLine();
    if (!ShowRoot || LineIndex == INDEX_NONE)
    {
        return Fail(ShowRoot ? TEXT("no surtitle selected (step to one first)") : TEXT("no Show Root"));
    }
    const TArray<FInfinityTransportSegment>& Segments = ShowRoot->Transport->Segments;
    const int64 Frame = ShowRoot->Transport->GetCurrentMasterFrame().Value;
    const int32 SegmentIndex = InfinityStageSurtitles::ResolveSegment(Script.Lines[LineIndex].Segment, Segments);
    if (SegmentIndex == INDEX_NONE || Frame < Segments[SegmentIndex].StartFrame.Value || Frame >= Segments[SegmentIndex].EndFrame.Value)
    {
        return Fail(FString::Printf(TEXT("the playhead is not in %s"), *Script.Lines[LineIndex].Segment));
    }
    const double Local = double(Frame - Segments[SegmentIndex].StartFrame.Value) / ShowRoot->ShowAsset->TickResolution.AsDecimal();
    return WriteLineTime(LineIndex, bOut, Local);
}

bool UInfinityStageSurtitleSubsystem::Nudge(const bool bOut, const double DeltaSeconds)
{
    AInfinityStageShowRoot* ShowRoot = FindRoot();
    const int32 LineIndex = GetSelectedLine();
    if (!ShowRoot || LineIndex == INDEX_NONE)
    {
        return Fail(ShowRoot ? TEXT("no surtitle selected (step to one first)") : TEXT("no Show Root"));
    }
    const FInfinitySurtitleLine& Line = Script.Lines[LineIndex];
    double Base = Line.InSeconds;
    if (bOut)
    {
        const TArray<FInfinityTransportSegment>& Segments = ShowRoot->Transport->Segments;
        const int32 SegmentIndex = InfinityStageSurtitles::ResolveSegment(Line.Segment, Segments);
        Base = InfinityStageSurtitles::EffectiveOut(Script, LineIndex, Segments, SegmentIndex, ShowRoot->ShowAsset->TickResolution.AsDecimal());
    }
    return WriteLineTime(LineIndex, bOut, FMath::Max(0.0, Base + DeltaSeconds));
}

bool UInfinityStageSurtitleSubsystem::WriteLineTime(const int32 LineIndex, const bool bOut, const double Seconds)
{
    const FString Path = InfinityStageSurtitles::ResolvePath();
    const FInfinitySurtitleLine Line = Script.Lines[LineIndex];
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *Path))
    {
        return Fail(FString::Printf(TEXT("cannot read %s"), *Path));
    }
    FString Error;
    if (!InfinityStageSurtitles::SetLineTime(Text, Line, bOut, Seconds, Error))
    {
        Reload();
        return Fail(Error);
    }
    // Rename-over, so neither the Cue Book nor this runtime's own reload reads half a file.
    const FString Temp = Path + TEXT(".tmp");
    if (!FFileHelper::SaveStringToFile(Text, *Temp, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)
        || !IFileManager::Get().Move(*Path, *Temp, true, true))
    {
        IFileManager::Get().Delete(*Temp);
        return Fail(FString::Printf(TEXT("cannot write %s"), *Path));
    }
    Reload();
    SelectedLine = Script.Lines.IndexOfByPredicate([&Line](const FInfinitySurtitleLine& Each) { return Each.SourceRow == Line.SourceRow; });
    LastMessage = FString::Printf(TEXT("row %d %s = %s"), Line.SourceRow, bOut ? TEXT("Out") : TEXT("In"), *InfinityStageSurtitles::FormatTime(Seconds));
    UE_LOG(LogInfinityStageSurtitles, Display, TEXT("INFINITY_SURTITLES_WRITE %s path=%s"), *LastMessage, *Path);
    return true;
}
