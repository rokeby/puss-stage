#include "InfinityStageDirectorHud.h"

#include "Algo/BinarySearch.h"
#include "CanvasItem.h"
#include "Debug/DebugDrawService.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "LevelSequence.h"
#include "LevelSequencePlayer.h"
#include "MovieScene.h"
#include "InfinityStageCueSheet.h"
#include "SceneInterface.h"
#include "SceneView.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieSceneSubTrack.h"

namespace
{
TAutoConsoleVariable<int32> CVarInfinityStageDirectorHud(
    TEXT("InfinityStage.DirectorHud"),
    -1,
    TEXT("Director's bottom-row HUD (cue, kind, bay, GO, Master/segment time, sub-sequence).\n")
    TEXT("-1: auto (default) - on in PIE, off in a packaged or standalone game.\n")
    TEXT("0: off. 1: on in any game world. Key H in the show viewport toggles it."));

TAutoConsoleVariable<int32> CVarInfinityStageDirectorHudScript(
    TEXT("InfinityStage.DirectorHudScript"),
    0,
    TEXT("1: show the script panel (current line, next lines, standby) above the Director HUD strip. H cycles it."));

/** No Show Root in the world: look again at most this often (never a per-frame actor walk). */
constexpr double RootSearchIntervalSeconds = 2.0;

void AddSpansFromSequence(
    const UMovieSceneSequence* Sequence,
    const FFrameNumber SegmentStart,
    const FFrameRate ShowTickResolution,
    TArray<FInfinityHudShotSpan>& OutSpans)
{
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid() || !ShowTickResolution.IsValid())
    {
        return;
    }
    // The cue's sub-section puts its playback start on the segment's first frame
    // (the same convention the transport's marker and camera-cut lookups use).
    const FFrameNumber PlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    const auto ToMaster = [&](const FFrameNumber Local)
    {
        return SegmentStart + FFrameRate::TransformTime(
            FFrameTime(Local - PlaybackStart), MovieScene->GetTickResolution(), ShowTickResolution).RoundToFrame();
    };
    for (const UMovieSceneTrack* Track : MovieScene->GetTracks())
    {
        const UMovieSceneSubTrack* SubTrack = Cast<UMovieSceneSubTrack>(Track);
        if (!SubTrack)
        {
            continue;
        }
        for (const UMovieSceneSection* Section : SubTrack->GetAllSections())
        {
            const UMovieSceneSubSection* Sub = Cast<UMovieSceneSubSection>(Section);
            if (!Sub || !Sub->IsActive() || !Sub->GetSequence()
                || !Sub->GetRange().HasLowerBound() || !Sub->GetRange().HasUpperBound())
            {
                continue;
            }
            FInfinityHudShotSpan& Span = OutSpans.AddDefaulted_GetRef();
            Span.StartFrame = ToMaster(Sub->GetInclusiveStartFrame());
            Span.EndFrame = ToMaster(Sub->GetExclusiveEndFrame());
            Span.Name = Sub->GetSequence()->GetName();
        }
    }
    OutSpans.StableSort([](const FInfinityHudShotSpan& A, const FInfinityHudShotSpan& B)
        { return A.StartFrame < B.StartFrame; });
}
}

namespace InfinityStageDirectorHud
{
bool IsEnabledFor(const int32 ConsoleValue, const EWorldType::Type WorldType)
{
    const bool bGameWorld = WorldType == EWorldType::PIE || WorldType == EWorldType::Game;
    if (!bGameWorld || ConsoleValue == 0)
    {
        return false;
    }
    if (ConsoleValue > 0)
    {
        return true;
    }
    return WorldType == EWorldType::PIE;
}

bool IsEnabledForWorld(const UWorld* World)
{
    return World && IsEnabledFor(CVarInfinityStageDirectorHud.GetValueOnGameThread(), World->WorldType);
}

void NextMode(const bool bStripOn, const bool bScriptOn, bool& bOutStripOn, bool& bOutScriptOn)
{
    if (!bStripOn)
    {
        bOutStripOn = true;
        bOutScriptOn = false;
    }
    else if (!bScriptOn)
    {
        bOutStripOn = true;
        bOutScriptOn = true;
    }
    else
    {
        bOutStripOn = false;
        bOutScriptOn = false;
    }
}

bool IsScriptPanelEnabledForWorld(const UWorld* World)
{
    return IsEnabledForWorld(World) && CVarInfinityStageDirectorHudScript.GetValueOnGameThread() > 0;
}

void Toggle(const UWorld* World)
{
    bool bStrip = false;
    bool bScript = false;
    NextMode(IsEnabledForWorld(World), IsScriptPanelEnabledForWorld(World), bStrip, bScript);
    CVarInfinityStageDirectorHud->Set(bStrip ? 1 : 0, ECVF_SetByConsole);
    CVarInfinityStageDirectorHudScript->Set(bScript ? 1 : 0, ECVF_SetByConsole);
}

TArray<FString> WrapText(const FString& Text, const int32 MaxChars)
{
    TArray<FString> Out;
    TArray<FString> Words;
    Text.Replace(TEXT("\n"), TEXT(" ")).ParseIntoArrayWS(Words);
    FString Line;
    for (const FString& Word : Words)
    {
        if (!Line.IsEmpty() && Line.Len() + 1 + Word.Len() > FMath::Max(8, MaxChars))
        {
            Out.Add(Line);
            Line.Reset();
        }
        Line += Line.IsEmpty() ? Word : TEXT(" ") + Word;
    }
    if (!Line.IsEmpty())
    {
        Out.Add(Line);
    }
    return Out;
}

int32 NearestBay(const TArray<double>& SortedStationDistancesCm, const double DistanceCm)
{
    const int32 Num = SortedStationDistancesCm.Num();
    if (Num == 0)
    {
        return 0;
    }
    // First station strictly beyond the camera; the nearest is it or the one before.
    const int32 Upper = Algo::UpperBound(SortedStationDistancesCm, DistanceCm);
    if (Upper <= 0)
    {
        return 1;
    }
    if (Upper >= Num)
    {
        return Num;
    }
    const double Before = DistanceCm - SortedStationDistancesCm[Upper - 1];
    const double After = SortedStationDistancesCm[Upper] - DistanceCm;
    return After <= Before ? Upper + 1 : Upper;
}

const TCHAR* KindLabel(const EInfinityCueType Type)
{
    switch (Type)
    {
    case EInfinityCueType::WingPair: return TEXT("Passage");
    case EInfinityCueType::Scene: return TEXT("Scene");
    case EInfinityCueType::Sequence: return TEXT("Interaction");
    default: return TEXT("?");
    }
}

FString FormatClock(const double Seconds)
{
    // Whole tenths first, then integer arithmetic. Subtracting the minutes in
    // floating point turned 62.3 s into 2.2999999 s, which truncated to "1:02.2"
    // (suite 6 Oct, DirectorHud.PureRules). The epsilon absorbs representation
    // error only; the clock still truncates, never shows a tenth not yet reached.
    const int64 Tenths = FMath::FloorToInt64(FMath::Max(0.0, Seconds) * 10.0 + 1.0e-6);
    const int64 Minutes = Tenths / 600;
    const int64 RestTenths = Tenths % 600;
    return FString::Printf(TEXT("%lld:%02lld.%lld"), Minutes, RestTenths / 10, RestTenths % 10);
}

FString ShotAtFrame(const TArray<FInfinityHudShotSpan>& Spans, const FFrameNumber Frame)
{
    FString Found;
    for (const FInfinityHudShotSpan& Span : Spans)
    {
        if (Frame >= Span.StartFrame && Frame < Span.EndFrame)
        {
            Found = Span.Name;
        }
    }
    return Found;
}

void FindGoAround(
    const TArray<FInfinityGoCue>& Cues,
    const int32 SegmentIndex,
    const FFrameNumber Frame,
    int32& OutLast,
    int32& OutNext)
{
    OutLast = INDEX_NONE;
    OutNext = INDEX_NONE;
    for (int32 Index = 0; Index < Cues.Num(); ++Index)
    {
        const FInfinityGoCue& Cue = Cues[Index];
        if (Cue.Frame <= Frame)
        {
            if (Cue.SegmentIndex == SegmentIndex)
            {
                OutLast = Index;
            }
        }
        else if (OutNext == INDEX_NONE)
        {
            OutNext = Index;
        }
    }
}

void FormatLines(const FInfinityDirectorHudState& State, FString& OutTop, FString& OutBottom)
{
    if (!State.bHasShow)
    {
        OutTop = TEXT("No Show Root driving this world");
        OutBottom.Reset();
        return;
    }
    if (State.SegmentIndex == INDEX_NONE)
    {
        OutTop = FString::Printf(TEXT("Outside every cue   Master %s"), *FormatClock(State.MasterSeconds));
        OutBottom.Reset();
        return;
    }

    OutTop = FString::Printf(TEXT("Cue %d/%d  %s  '%s'"),
        State.SegmentIndex + 1, State.SegmentCount, KindLabel(State.SegmentType), *State.SegmentLabel);
    if (State.SegmentType == EInfinityCueType::WingPair && State.BayCount > 0)
    {
        OutTop += FString::Printf(TEXT("   BAY %d/%d"), State.Bay, State.BayCount);
    }
    if (State.bHold && !State.LastGo.IsEmpty())
    {
        // A hold arms when the playhead crosses a HOLD GO, so the held GO is the last one crossed. Say so plainly:
        // "next GO 30" during a hold at GO 20 read as the wrong cue (Gary's I2 note, 9 Oct).
        OutTop += TEXT("   HOLDING at ") + State.LastGo + TEXT(" (press GO)");
    }
    else
    {
        if (!State.LastGo.IsEmpty())
        {
            OutTop += TEXT("   ") + State.LastGo;
        }
        if (!State.NextGo.IsEmpty())
        {
            OutTop += TEXT("   next ") + State.NextGo;
        }
    }

    const TCHAR* Status = State.bHold
        ? TEXT("HOLD")
        : (!State.bPlaying ? TEXT("PAUSED") : (State.bReversed ? TEXT("REV") : TEXT("PLAY")));
    OutBottom = FString::Printf(TEXT("%s"), Status);
    if (State.bPlaying && !FMath::IsNearlyEqual(State.PlayRate, 1.0f))
    {
        OutBottom += FString::Printf(TEXT(" x%.0f"), State.PlayRate);
    }
    OutBottom += FString::Printf(TEXT("   Master %s   in cue %s / %s"),
        *FormatClock(State.MasterSeconds), *FormatClock(State.SegmentSeconds), *FormatClock(State.SegmentLengthSeconds));
    if (!State.SequenceName.IsEmpty())
    {
        OutBottom += TEXT("   Seq ") + State.SequenceName;
        if (!State.ShotName.IsEmpty())
        {
            OutBottom += TEXT(" > ") + State.ShotName;
        }
    }
}
}

bool UInfinityStageDirectorHudSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UInfinityStageDirectorHudSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    // The "Game" debug-draw channel draws into game viewports (PIE included). The
    // delegate is global, so Draw filters on its own world.
    DrawHandle = UDebugDrawService::Register(
        TEXT("Game"), FDebugDrawDelegate::CreateUObject(this, &UInfinityStageDirectorHudSubsystem::Draw));
}

void UInfinityStageDirectorHudSubsystem::SetShowRootForTests(AInfinityStageShowRoot* Root)
{
    CachedShowRoot = Root;
}

void UInfinityStageDirectorHudSubsystem::Deinitialize()
{
    if (DrawHandle.IsValid())
    {
        UDebugDrawService::Unregister(DrawHandle);
        DrawHandle.Reset();
    }
    Super::Deinitialize();
}

AInfinityStageShowRoot* UInfinityStageDirectorHudSubsystem::FindShowRoot()
{
    if (AInfinityStageShowRoot* Root = CachedShowRoot.Get())
    {
        return Root;
    }
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    const double Now = World->GetRealTimeSeconds();
    if (Now - LastRootSearchRealSeconds < RootSearchIntervalSeconds && Now >= LastRootSearchRealSeconds)
    {
        return nullptr;
    }
    LastRootSearchRealSeconds = Now;
    for (TActorIterator<AInfinityStageShowRoot> It(World); It; ++It)
    {
        if (It->Transport && It->ShowAsset)
        {
            CachedShowRoot = *It;
            return *It;
        }
    }
    return nullptr;
}

void UInfinityStageDirectorHudSubsystem::RebuildSegmentCache(const AInfinityStageShowRoot& Root, const int32 SegmentIndex)
{
    ++SegmentCacheBuilds;
    CachedSegmentIndex = SegmentIndex;
    CachedSegmentCount = Root.Transport ? Root.Transport->Segments.Num() : -1;
    CachedSegmentGuid.Invalidate();
    CachedStationDistancesCm.Reset();
    CachedShotSpans.Reset();
    CachedSequenceName.Reset();

    const UInfinityStageTransportController* Transport = Root.Transport;
    const UInfinityStageShowAsset* Show = Root.ShowAsset;
    if (!Transport || !Show || !Transport->Segments.IsValidIndex(SegmentIndex))
    {
        return;
    }
    const FInfinityTransportSegment& Segment = Transport->Segments[SegmentIndex];
    CachedSegmentGuid = Segment.SegmentGuid;

    if (Segment.Type == EInfinityCueType::WingPair)
    {
        // Once per segment change, never per frame (compile ~0.05 ms; memory note).
        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
        if (const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
            [&Segment](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == Segment.SegmentGuid; }))
        {
            for (const FInfinityCompiledWing& Wing : Passage->Wings)
            {
                CachedStationDistancesCm.Add(Wing.DistanceCm);
            }
            CachedStationDistancesCm.Sort();
        }
        const FInfinityPassageSettings* Settings = Show->PassageSettings.FindByPredicate(
            [&Segment](const FInfinityPassageSettings& Candidate) { return Candidate.PassageGuid == Segment.SegmentGuid; });
        if (Settings && !Settings->Choreography.IsNull())
        {
            const ULevelSequence* Choreo = Settings->Choreography.Get();
            CachedSequenceName = Choreo ? Choreo->GetName() : Settings->Choreography.GetAssetName();
            AddSpansFromSequence(Choreo, Segment.StartFrame, Show->TickResolution, CachedShotSpans);
        }
        return;
    }

    if (Show->Cues.IsValidIndex(Segment.CueIndex))
    {
        const FInfinityShowCue& Cue = Show->Cues[Segment.CueIndex];
        if (!Cue.Scene.Sequence.IsNull())
        {
            // The transport already loaded it while compiling segments; Get() never hitches.
            const ULevelSequence* Sequence = Cue.Scene.Sequence.Get();
            CachedSequenceName = Sequence ? Sequence->GetName() : Cue.Scene.Sequence.GetAssetName();
            AddSpansFromSequence(Sequence, Segment.StartFrame, Show->TickResolution, CachedShotSpans);
        }
    }
}

FInfinityDirectorHudState UInfinityStageDirectorHudSubsystem::GatherState()
{
    FInfinityDirectorHudState State;
    AInfinityStageShowRoot* Root = FindShowRoot();
    UInfinityStageTransportController* Transport = Root ? Root->Transport.Get() : nullptr;
    const UInfinityStageShowAsset* Show = Root ? Root->ShowAsset.Get() : nullptr;
    if (!Transport || !Show || !Show->TickResolution.IsValid())
    {
        return State;
    }
    State.bHasShow = true;
    const double TickRate = Show->TickResolution.AsDecimal();
    const FFrameNumber Frame = Transport->GetCurrentMasterFrame();
    State.MasterSeconds = Frame.Value / TickRate;
    State.SegmentCount = Transport->Segments.Num();
    State.bPlaying = Transport->IsTransportPlaying();
    State.bHold = Transport->IsHoldActive();
    if (Root->SequencePlayer)
    {
        State.bReversed = Root->SequencePlayer->IsReversed();
        State.PlayRate = Root->SequencePlayer->GetPlayRate();
    }

    const int32 SegmentIndex = Transport->FindSegmentAtFrame(Frame);
    State.SegmentIndex = SegmentIndex;
    if (!Transport->Segments.IsValidIndex(SegmentIndex))
    {
        return State;
    }
    const FInfinityTransportSegment& Segment = Transport->Segments[SegmentIndex];
    if (SegmentIndex != CachedSegmentIndex
        || CachedSegmentCount != Transport->Segments.Num()
        || CachedSegmentGuid != Segment.SegmentGuid)
    {
        RebuildSegmentCache(*Root, SegmentIndex);
    }

    State.SegmentLabel = Segment.Label.ToString();
    State.SegmentType = Segment.Type;
    State.SegmentSeconds = (Frame - Segment.StartFrame).Value / TickRate;
    State.SegmentLengthSeconds = (Segment.EndFrame - Segment.StartFrame).Value / TickRate;

    if (Segment.Type == EInfinityCueType::WingPair)
    {
        State.BayCount = CachedStationDistancesCm.Num();
        // The rig's own last evaluated station distance (camera offsets included),
        // the same number its Passage mechanisms are driven by.
        if (const AInfinityStageCameraRig* Rig = Transport->FindCameraRigForPassage(Segment.SegmentGuid))
        {
            State.Bay = InfinityStageDirectorHud::NearestBay(CachedStationDistancesCm, Rig->CurrentCameraDistanceCm);
        }
    }

    int32 LastGo = INDEX_NONE;
    int32 NextGo = INDEX_NONE;
    InfinityStageDirectorHud::FindGoAround(Transport->GoCues, SegmentIndex, Frame, LastGo, NextGo);
    const auto DescribeGo = [&Transport](const int32 Index)
    {
        const FInfinityGoCue& Cue = Transport->GoCues[Index];
        return FString::Printf(TEXT("GO %s%s%s"), *Cue.Number, Cue.bHold ? TEXT(" HOLD") : TEXT(""),
            Cue.Label.IsEmpty() ? TEXT("") : *(TEXT(" '") + Cue.Label + TEXT("'")));
    };
    if (Transport->GoCues.IsValidIndex(LastGo))
    {
        State.LastGo = DescribeGo(LastGo);
    }
    if (Transport->GoCues.IsValidIndex(NextGo))
    {
        State.NextGo = DescribeGo(NextGo) + TEXT(" @ ")
            + InfinityStageDirectorHud::FormatClock(Transport->GoCues[NextGo].Frame.Value / TickRate);
    }

    State.SequenceName = CachedSequenceName;
    State.ShotName = InfinityStageDirectorHud::ShotAtFrame(CachedShotSpans, Frame);
    return State;
}

void UInfinityStageDirectorHudSubsystem::Draw(UCanvas* Canvas, APlayerController* PlayerController)
{
    UWorld* World = GetWorld();
    if (!Canvas || !World || !InfinityStageDirectorHud::IsEnabledForWorld(World))
    {
        return;
    }
    // The draw delegate is global: only draw this world's HUD into this world's viewport.
    const UWorld* ViewWorld = PlayerController ? PlayerController->GetWorld() : nullptr;
    if (!ViewWorld && Canvas->SceneView && Canvas->SceneView->Family && Canvas->SceneView->Family->Scene)
    {
        ViewWorld = Canvas->SceneView->Family->Scene->GetWorld();
    }
    if (ViewWorld != World)
    {
        return;
    }

    const FInfinityDirectorHudState State = GatherState();
    FString Top;
    FString Bottom;
    InfinityStageDirectorHud::FormatLines(State, Top, Bottom);

    UFont* Font = GEngine ? GEngine->GetMediumFont() : nullptr;
    if (!Font)
    {
        return;
    }
    const float LineHeight = Font->GetMaxCharHeight() + 4.0f;
    const float Left = 16.0f;
    const float BottomY = Canvas->ClipY - 12.0f - LineHeight;
    const float TopY = Bottom.IsEmpty() ? BottomY : BottomY - LineHeight;

    // A dark band behind the text so it reads over a lit stage.
    FCanvasTileItem Band(
        FVector2D(0.0f, TopY - 4.0f),
        FVector2D(Canvas->ClipX, (BottomY - TopY) + LineHeight + 8.0f),
        FLinearColor(0.0f, 0.0f, 0.0f, 0.55f));
    Band.BlendMode = SE_BLEND_Translucent;
    Canvas->DrawItem(Band);

    if (InfinityStageDirectorHud::IsScriptPanelEnabledForWorld(World))
    {
        DrawScriptPanel(Canvas, Font, TopY - 8.0f, State);
    }

    FCanvasTextItem TopItem(FVector2D(Left, TopY), FText::FromString(Top), Font, FLinearColor(1.0f, 0.86f, 0.35f));
    TopItem.EnableShadow(FLinearColor::Black);
    Canvas->DrawItem(TopItem);
    if (!Bottom.IsEmpty())
    {
        FCanvasTextItem BottomItem(FVector2D(Left, BottomY), FText::FromString(Bottom), Font, FLinearColor(0.85f, 0.92f, 1.0f));
        BottomItem.EnableShadow(FLinearColor::Black);
        Canvas->DrawItem(BottomItem);
    }
}

void UInfinityStageDirectorHudSubsystem::DrawScriptPanel(
    UCanvas* Canvas,
    UFont* Font,
    const float BottomOfPanel,
    const FInfinityDirectorHudState& State)
{
    UInfinityStageCueDirectorSubsystem* Director = GetWorld() ? GetWorld()->GetSubsystem<UInfinityStageCueDirectorSubsystem>() : nullptr;
    if (!Director)
    {
        return;
    }
    // Sheet segment k is the stage's segment k (Opening, P1, S1, I1, P2 ...): the stage moving on
    // pulls the script cursor forward; it never pulls it back.
    if (State.SegmentIndex != INDEX_NONE)
    {
        Director->SyncToSegment(State.SegmentIndex);
    }
    const FInfinityCueSheet& Sheet = Director->GetSheet();
    struct FPanelLine
    {
        FString Text;
        FLinearColor Color;
    };
    TArray<FPanelLine> Lines;
    float CharWidth = 0.0f;
    float CharHeight = 0.0f;
    Canvas->StrLen(Font, TEXT("M"), CharWidth, CharHeight);
    const int32 MaxChars = FMath::Max(40, FMath::FloorToInt32((Canvas->ClipX - 40.0f) / FMath::Max(1.0f, CharWidth * 0.62f)));
    const FLinearColor Amber(1.0f, 0.62f, 0.2f);
    const FLinearColor White(1.0f, 1.0f, 1.0f);
    const FLinearColor Dim(0.62f, 0.66f, 0.72f);
    const FLinearColor Cyan(0.45f, 0.9f, 1.0f);
    const auto Add = [&Lines, MaxChars](const FString& Text, const FLinearColor& Color)
    {
        for (const FString& Wrapped : InfinityStageDirectorHud::WrapText(Text, MaxChars))
        {
            Lines.Add({Wrapped, Color});
        }
    };

    if (Sheet.Rows.IsEmpty())
    {
        Add(Sheet.Warnings.IsEmpty() ? FString(TEXT("Cue sheet: no rows")) : Sheet.Warnings[0], Amber);
    }
    else
    {
        const int32 Current = FMath::Clamp(Director->GetCursor().Row, 0, Sheet.Rows.Num() - 1);
        const FInfinityCueSheetRow& Row = Sheet.Rows[Current];
        const FString StageLabel = State.SegmentLabel;
        const FString SheetLabel = Row.Segment.IsEmpty() ? FString(TEXT("(pre-show)")) : Row.Segment;
        const bool bAgree = Row.SegmentOrdinal == State.SegmentIndex;
        Add(FString::Printf(TEXT("SCRIPT  sheet row %d%s   sheet: %s   stage: %s%s"),
            Row.SourceRow, Row.Number.IsEmpty() ? TEXT("") : *FString::Printf(TEXT("  [cue %s]"), *Row.Number),
            *SheetLabel, *StageLabel, bAgree ? TEXT("") : TEXT("   (script and stage differ)")),
            bAgree ? Dim : Amber);
        const FString Actions = InfinityStageCueSheet::DescribeActions(Row);
        if (!Actions.IsEmpty())
        {
            Add(TEXT("> ") + Actions, Cyan);
        }
        for (const FString& Spoken : InfinityStageCueSheet::DescribeLines(Row))
        {
            Add(TEXT("> ") + Spoken, White);
        }
        int32 Shown = 0;
        for (int32 R = Current + 1; R < Sheet.Rows.Num() && Shown < 2; ++R)
        {
            if (!Sheet.Rows[R].HasContent())
            {
                continue;
            }
            ++Shown;
            const TArray<FString> Spoken = InfinityStageCueSheet::DescribeLines(Sheet.Rows[R]);
            Add(TEXT("  next: ") + (Spoken.IsEmpty() ? InfinityStageCueSheet::DescribeActions(Sheet.Rows[R]) : Spoken[0]), Dim);
        }
        const int32 Standby = InfinityStageCueSheet::NextStandbyRow(Sheet, Current);
        if (Standby != INDEX_NONE)
        {
            const FInfinityCueSheetRow& Next = Sheet.Rows[Standby];
            Add(FString::Printf(TEXT("STANDBY%s  %s"),
                Next.Number.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" [cue %s]"), *Next.Number),
                *InfinityStageCueSheet::DescribeActions(Next)), Amber);
        }
    }

    const float LineHeight = Font->GetMaxCharHeight() + 3.0f;
    const float Height = Lines.Num() * LineHeight + 10.0f;
    const float Top = BottomOfPanel - Height;
    FCanvasTileItem Band(FVector2D(0.0f, Top), FVector2D(Canvas->ClipX, Height), FLinearColor(0.0f, 0.0f, 0.0f, 0.7f));
    Band.BlendMode = SE_BLEND_Translucent;
    Canvas->DrawItem(Band);
    float Y = Top + 5.0f;
    for (const FPanelLine& Line : Lines)
    {
        FCanvasTextItem Item(FVector2D(16.0f, Y), FText::FromString(Line.Text), Font, Line.Color);
        Item.EnableShadow(FLinearColor::Black);
        Canvas->DrawItem(Item);
        Y += LineHeight;
    }
}

