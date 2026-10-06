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

void Toggle(const UWorld* World)
{
    const bool bNow = IsEnabledForWorld(World);
    CVarInfinityStageDirectorHud->Set(bNow ? 0 : 1, ECVF_SetByConsole);
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
    const double Clamped = FMath::Max(0.0, Seconds);
    const int32 Minutes = FMath::FloorToInt32(Clamped / 60.0);
    const double Rest = Clamped - Minutes * 60.0;
    return FString::Printf(TEXT("%d:%04.1f"), Minutes, FMath::FloorToDouble(Rest * 10.0) / 10.0);
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
    if (!State.LastGo.IsEmpty())
    {
        OutTop += TEXT("   ") + State.LastGo;
    }
    if (!State.NextGo.IsEmpty())
    {
        OutTop += TEXT("   next ") + State.NextGo;
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
