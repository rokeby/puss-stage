#include "InfinityStageTransportController.h"

#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "LevelSequencePlayer.h"
#include "MovieScene.h"
#include "MovieSceneInfinityAudioTrack.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MovieSceneInfinitySceneTrack.h"
#include "HAL/IConsoleManager.h"
#include "MovieSceneSequencePlayer.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneAudioTrack.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "Sections/MovieSceneSubSection.h"
#include "UObject/ObjectKey.h"
#include "UniversalObjectLocatorResolveParams.h"

DEFINE_LOG_CATEGORY(LogInfinityStageTransport);

namespace
{
constexpr TCHAR HiddenChangeoverMarker[] = TEXT("InfinityStage.HiddenChangeover");
constexpr TCHAR VampStartMarker[] = TEXT("InfinityStage.VampStart");
constexpr TCHAR VampEndMarker[] = TEXT("InfinityStage.VampEnd");
constexpr int32 JumpResettleMinTicks = 2;

TAutoConsoleVariable<int32> CVarInfinityStageSeamDiag(
    TEXT("InfinityStage.SeamDiag"),
    0,
    TEXT("Seam diagnostic: 1 logs INFINITY_SEAM_DIAG lines (both clocks, segment by compiled table and by Master\n")
    TEXT("sections, view target/blend, POV step, look offset, rig settle/bob, expected music position) at every\n")
    TEXT("pause/resume/play/jump/scrub/claim and every tick near a boundary, on a hitch or a view step. 0: off."));

TAutoConsoleVariable<float> CVarInfinityStageSeamDiagWindow(
    TEXT("InfinityStage.SeamDiag.WindowSeconds"), 1.0f,
    TEXT("Seam diagnostic: log every tick within this many Master seconds of a segment boundary."));

TAutoConsoleVariable<float> CVarInfinityStageSeamDiagStepCm(
    TEXT("InfinityStage.SeamDiag.StepCm"), 5.0f,
    TEXT("Seam diagnostic: also log any tick whose rendered POV moved more than this (cm) since the last tick."));

TAutoConsoleVariable<float> CVarInfinityStageSeamDiagStepDeg(
    TEXT("InfinityStage.SeamDiag.StepDeg"), 2.0f,
    TEXT("Seam diagnostic: also log any tick whose rendered POV turned more than this (degrees) since the last tick."));

bool SeamDiagOn()
{
    return CVarInfinityStageSeamDiag.GetValueOnGameThread() > 0;
}

/**
 * One transport per world, so sequence evaluation can find the single camera
 * authority without walking the actor list on every evaluated frame.
 */
TMap<FObjectKey, TWeakObjectPtr<UInfinityStageTransportController>>& GetTransportRegistry()
{
    static TMap<FObjectKey, TWeakObjectPtr<UInfinityStageTransportController>> Registry;
    return Registry;
}

EViewTargetBlendFunction ToEngineBlendFunction(const EInfinityHandoverBlendFunction Function)
{
    switch (Function)
    {
    case EInfinityHandoverBlendFunction::Linear: return VTBlend_Linear;
    case EInfinityHandoverBlendFunction::Cubic: return VTBlend_Cubic;
    case EInfinityHandoverBlendFunction::EaseIn: return VTBlend_EaseIn;
    case EInfinityHandoverBlendFunction::EaseOut: return VTBlend_EaseOut;
    case EInfinityHandoverBlendFunction::EaseInOut: return VTBlend_EaseInOut;
    default: return VTBlend_Linear;
    }
}

const TCHAR* LexHandoverSource(const EInfinityHandoverSource Value)
{
    switch (Value)
    {
    case EInfinityHandoverSource::SceneCameraCut: return TEXT("SceneCameraCut");
    case EInfinityHandoverSource::PassageRig: return TEXT("PassageRig");
    default: return TEXT("None");
    }
}

const TCHAR* LexHandoverResolution(const EInfinityHandoverResolution Value)
{
    switch (Value)
    {
    case EInfinityHandoverResolution::Resolved: return TEXT("Resolved");
    case EInfinityHandoverResolution::NoSuchSegment: return TEXT("NoSuchSegment");
    case EInfinityHandoverResolution::RetainWithoutPrevious: return TEXT("RetainWithoutPrevious");
    case EInfinityHandoverResolution::NoFollowingPassage: return TEXT("NoFollowingPassage");
    case EInfinityHandoverResolution::NoRuleForSegment: return TEXT("NoRuleForSegment");
    case EInfinityHandoverResolution::ChainTooLong: return TEXT("ChainTooLong");
    default: return TEXT("Unknown");
    }
}

const TCHAR* LexCoveredHandoffSource(const EInfinityCoveredHandoffSource Value)
{
    switch (Value)
    {
    case EInfinityCoveredHandoffSource::SequenceMarker: return TEXT("SequenceMarker");
    case EInfinityCoveredHandoffSource::FallbackNoSequenceAssigned: return TEXT("FallbackNoSequenceAssigned");
    case EInfinityCoveredHandoffSource::FallbackSequenceFailedToLoad: return TEXT("FallbackSequenceFailedToLoad");
    case EInfinityCoveredHandoffSource::FallbackInvalidTickResolution: return TEXT("FallbackInvalidTickResolution");
    case EInfinityCoveredHandoffSource::FallbackNoMarker: return TEXT("FallbackNoMarker");
    default: return TEXT("NotApplicable");
    }
}

/**
 * When a covered changeover happens, relative to the cue's first frame.
 *
 * A sequence-authored InfinityStage.HiddenChangeover marker is the authored
 * answer; entry + hold is the fallback. Those are both legitimate, but a
 * sequence that fails to load used to be indistinguishable from a sequence with
 * no marker, so the handoff moved with load state and nothing said so. The
 * caller gets the reason back and records it on the segment.
 */
FFrameNumber ResolveCoveredHandoffOffset(
    const UInfinityStageShowAsset& Show,
    const FInfinityShowCue& Cue,
    EInfinityCoveredHandoffSource& OutSource)
{
    const FFrameNumber Fallback(
        FMath::Max(0, Cue.Scene.CurtainEntryTransitionFrames.Value)
        + FMath::Max(0, Cue.Scene.CurtainHoldFrames.Value));

    if (Cue.Scene.Sequence.IsNull())
    {
        OutSource = EInfinityCoveredHandoffSource::FallbackNoSequenceAssigned;
        return Fallback;
    }
    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    if (!Sequence)
    {
        OutSource = EInfinityCoveredHandoffSource::FallbackSequenceFailedToLoad;
        return Fallback;
    }
    const UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid() || !Show.TickResolution.IsValid())
    {
        OutSource = EInfinityCoveredHandoffSource::FallbackInvalidTickResolution;
        return Fallback;
    }

    // A Scene sub-section places the sequence's playback start on the segment's
    // first frame, exactly as the Camera Cut lookup assumes. The marker's offset
    // is therefore measured from the playback range, not from the sequence's own
    // frame zero: any sequence not starting at zero handed off late by that much.
    const FFrameNumber PlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    for (const FMovieSceneMarkedFrame& MarkedFrame : MovieScene->GetMarkedFrames())
    {
        if (MarkedFrame.Label.Equals(HiddenChangeoverMarker, ESearchCase::IgnoreCase))
        {
            OutSource = EInfinityCoveredHandoffSource::SequenceMarker;
            return FFrameRate::TransformTime(
                FFrameTime(MarkedFrame.FrameNumber - PlaybackStart),
                MovieScene->GetTickResolution(),
                Show.TickResolution).RoundToFrame();
        }
    }
    OutSource = EInfinityCoveredHandoffSource::FallbackNoMarker;
    return Fallback;
}

struct FVampMarker
{
    FFrameNumber Offset = 0;
    bool bStart = false;
};

void CollectVampRanges(
    const UInfinityStageShowAsset& Show,
    const FInfinityShowCue& Cue,
    const int32 SegmentIndex,
    const FFrameNumber SegmentStart,
    const FFrameNumber SegmentEnd,
    TArray<FInfinityVampRange>& OutRanges)
{
    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid() || !Show.TickResolution.IsValid())
    {
        return;
    }

    const FFrameNumber PlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    TArray<FVampMarker> Markers;
    for (const FMovieSceneMarkedFrame& MarkedFrame : MovieScene->GetMarkedFrames())
    {
        const bool bStart = MarkedFrame.Label.Equals(VampStartMarker, ESearchCase::IgnoreCase);
        const bool bEnd = MarkedFrame.Label.Equals(VampEndMarker, ESearchCase::IgnoreCase);
        if (!bStart && !bEnd)
        {
            continue;
        }
        FVampMarker& Marker = Markers.AddDefaulted_GetRef();
        Marker.Offset = FFrameRate::TransformTime(
            FFrameTime(MarkedFrame.FrameNumber - PlaybackStart),
            MovieScene->GetTickResolution(),
            Show.TickResolution).RoundToFrame();
        Marker.bStart = bStart;
    }
    Markers.Sort([](const FVampMarker& A, const FVampMarker& B)
    {
        if (A.Offset == B.Offset)
        {
            return A.bStart && !B.bStart;
        }
        return A.Offset < B.Offset;
    });

    TOptional<FFrameNumber> PendingStart;
    const int32 SegmentLength = FMath::Max(0, (SegmentEnd - SegmentStart).Value);
    for (const FVampMarker& Marker : Markers)
    {
        const FFrameNumber ClampedOffset(FMath::Clamp(Marker.Offset.Value, 0, SegmentLength));
        if (Marker.bStart)
        {
            if (PendingStart.IsSet())
            {
                UE_LOG(LogInfinityStageTransport, Warning,
                    TEXT("INFINITY_VAMP_UNPAIRED cue='%s' marker=%s offset=%d"),
                    *Cue.Label.ToString(), VampStartMarker, PendingStart.GetValue().Value);
            }
            PendingStart = ClampedOffset;
            continue;
        }
        if (!PendingStart.IsSet() || ClampedOffset <= PendingStart.GetValue())
        {
            UE_LOG(LogInfinityStageTransport, Warning,
                TEXT("INFINITY_VAMP_UNPAIRED cue='%s' marker=%s offset=%d"),
                *Cue.Label.ToString(), VampEndMarker, ClampedOffset.Value);
            continue;
        }

        FInfinityVampRange& Range = OutRanges.AddDefaulted_GetRef();
        Range.StartFrame = SegmentStart + PendingStart.GetValue();
        Range.EndFrame = SegmentStart + ClampedOffset;
        Range.SegmentIndex = SegmentIndex;
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_VAMP_RANGE segment=%d cue='%s' start=%d end=%d"),
            SegmentIndex, *Cue.Label.ToString(), Range.StartFrame.Value, Range.EndFrame.Value);
        PendingStart.Reset();
    }
    if (PendingStart.IsSet())
    {
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_VAMP_UNPAIRED cue='%s' marker=%s offset=%d"),
            *Cue.Label.ToString(), VampStartMarker, PendingStart.GetValue().Value);
    }
}

void CollectGoCues(
    const UMovieSceneSequence* Sequence,
    const FFrameRate ShowTickResolution,
    const int32 SegmentIndex,
    const FFrameNumber SegmentStart,
    const FFrameNumber SegmentEnd,
    const bool bDefaultHold,
    TArray<FInfinityGoCue>& OutCues)
{
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid() || !ShowTickResolution.IsValid())
    {
        return;
    }
    // Measured from the playback start, as the vamp and handoff markers are: the
    // sub-section puts the playback start on the segment's first frame.
    const FFrameNumber PlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    const int32 SegmentLength = FMath::Max(0, (SegmentEnd - SegmentStart).Value);
    for (const FMovieSceneMarkedFrame& MarkedFrame : MovieScene->GetMarkedFrames())
    {
        FString Number;
        FString Label;
        int32 Mode = -1;
        if (!InfinityStageGoCues::ParseMarkerLabel(MarkedFrame.Label, Number, Label, Mode))
        {
            continue;
        }
        const FFrameNumber Offset = FFrameRate::TransformTime(
            FFrameTime(MarkedFrame.FrameNumber - PlaybackStart),
            MovieScene->GetTickResolution(),
            ShowTickResolution).RoundToFrame();
        if (Offset.Value < 0 || Offset.Value > SegmentLength)
        {
            UE_LOG(LogInfinityStageTransport, Warning,
                TEXT("INFINITY_GO_OUTSIDE_SEGMENT sequence=%s go=%s offset=%d length=%d: never reached, ignored."),
                *Sequence->GetName(), *Number, Offset.Value, SegmentLength);
            continue;
        }
        FInfinityGoCue& Cue = OutCues.AddDefaulted_GetRef();
        Cue.Frame = SegmentStart + Offset;
        Cue.Number = Number;
        Cue.Label = Label;
        Cue.bHold = Mode < 0 ? bDefaultHold : Mode == 1;
        Cue.SegmentIndex = SegmentIndex;
        Cue.SegmentStartFrame = SegmentStart;
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_GO_CUE number=%s mode=%s frame=%d segment=%d label='%s'"),
            *Cue.Number, Cue.bHold ? TEXT("HOLD") : TEXT("PASS"), Cue.Frame.Value, SegmentIndex, *Cue.Label);
    }
}

void CollectAudioTracks(
    UMovieSceneSequence* Sequence,
    TSet<const UMovieSceneSequence*>& Visited,
    TArray<UMovieSceneTrack*>& OutTracks,
    const int32 Depth)
{
    if (!Sequence || Depth > 8 || Visited.Contains(Sequence))
    {
        return;
    }
    Visited.Add(Sequence);
    UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (!MovieScene)
    {
        return;
    }
    for (UMovieSceneTrack* Track : MovieScene->GetTracks())
    {
        if (Track && Track->IsA<UMovieSceneAudioTrack>())
        {
            OutTracks.Add(Track);
            continue;
        }
        if (UMovieSceneSubTrack* SubTrack = Cast<UMovieSceneSubTrack>(Track))
        {
            for (UMovieSceneSection* Section : SubTrack->GetAllSections())
            {
                if (UMovieSceneSubSection* Sub = Cast<UMovieSceneSubSection>(Section))
                {
                    CollectAudioTracks(Sub->GetSequence(), Visited, OutTracks, Depth + 1);
                }
            }
        }
    }
}

void CollectSceneShotStarts(
    const UInfinityStageShowAsset& Show,
    const FInfinityShowCue& Cue,
    FInfinityTransportSegment& Segment)
{
    Segment.ShotStartFrames.Reset();
    if (Segment.Type != EInfinityCueType::Scene)
    {
        return;
    }

    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    const UMovieSceneCameraCutTrack* CutTrack = MovieScene
        ? Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack())
        : nullptr;
    if (!CutTrack || !MovieScene->GetTickResolution().IsValid() || !Show.TickResolution.IsValid())
    {
        return;
    }

    const FFrameNumber PlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    const FFrameNumber PlaybackEnd = MovieScene->GetPlaybackRange().GetUpperBoundValue();
    TArray<FFrameNumber> Starts;
    for (const UMovieSceneSection* BaseSection : CutTrack->GetAllSections())
    {
        const UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(BaseSection);
        if (!Cut || !Cut->IsActive() || !Cut->GetRange().HasLowerBound())
        {
            continue;
        }
        const FFrameNumber LocalStart = Cut->GetInclusiveStartFrame();
        if (LocalStart < PlaybackStart || LocalStart >= PlaybackEnd)
        {
            continue;
        }
        const FFrameNumber MasterStart = Segment.StartFrame + FFrameRate::TransformTime(
            FFrameTime(LocalStart - PlaybackStart),
            MovieScene->GetTickResolution(),
            Show.TickResolution).RoundToFrame();
        if (MasterStart >= Segment.StartFrame && MasterStart < Segment.EndFrame)
        {
            Starts.Add(MasterStart);
        }
    }

    Starts.Sort();
    for (const FFrameNumber Start : Starts)
    {
        if (Segment.ShotStartFrames.IsEmpty() || Segment.ShotStartFrames.Last() != Start)
        {
            Segment.ShotStartFrames.Add(Start);
        }
    }
}
}

void FInfinityVampPlaybackState::Reset()
{
    ActiveVampIndex = INDEX_NONE;
    LoopCount = 0;
    ReleasedVamps.Reset();
    PreviousFrame = 0;
    bHasPreviousFrame = false;
}

void FInfinityVampPlaybackState::OnNavigation(const FFrameNumber TargetFrame)
{
    // A seek establishes a new observation point but cannot arm a vamp.
    ActiveVampIndex = INDEX_NONE;
    PreviousFrame = TargetFrame;
    bHasPreviousFrame = true;
}

EInfinityVampPlaybackAction FInfinityVampPlaybackState::Tick(
    const FFrameNumber CurrentFrame,
    const bool bPlaying,
    const bool bReversed,
    const float PlayRate,
    const TArray<FInfinityVampRange>& Ranges,
    FFrameNumber& OutLoopFrame)
{
    OutLoopFrame = CurrentFrame;
    if (!bHasPreviousFrame)
    {
        PreviousFrame = CurrentFrame;
        bHasPreviousFrame = true;
        return EInfinityVampPlaybackAction::None;
    }

    // PlayTo pauses when it reaches its target. Handle an already-armed vamp's
    // end before the generic paused-player path, otherwise the seam can lose to
    // the segment-end PlayTo that started the Scene (C3, Gary 8 Oct).
    if (!bPlaying
        && !bReversed
        && !bPlayOnce
        && Ranges.IsValidIndex(ActiveVampIndex)
        && CurrentFrame >= Ranges[ActiveVampIndex].EndFrame)
    {
        const FInfinityVampRange& Range = Ranges[ActiveVampIndex];
        const int32 Duration = (Range.EndFrame - Range.StartFrame).Value;
        const int32 Overshoot = FMath::Max(0, (CurrentFrame - Range.EndFrame).Value);
        OutLoopFrame = Range.StartFrame + FFrameNumber(Overshoot % Duration);
        PreviousFrame = OutLoopFrame;
        ++LoopCount;
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_VAMP_PAUSED_END_LOOP index=%d count=%d from=%d to=%d"),
            ActiveVampIndex, LoopCount, CurrentFrame.Value, OutLoopFrame.Value);
        return EInfinityVampPlaybackAction::LoopToStart;
    }

    if (!bPlaying)
    {
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    if (bReversed)
    {
        if (CurrentFrame < PreviousFrame)
        {
            for (int32 Index = 0; Index < Ranges.Num(); ++Index)
            {
                const FInfinityVampRange& Range = Ranges[Index];
                if (Range.IsValid() && ReleasedVamps.Contains(Index) && CurrentFrame < Range.EndFrame)
                {
                    ReleasedVamps.Remove(Index);
                    ActiveVampIndex = CurrentFrame >= Range.StartFrame ? Index : INDEX_NONE;
                }
            }
        }
        if (Ranges.IsValidIndex(ActiveVampIndex)
            && CurrentFrame < Ranges[ActiveVampIndex].StartFrame)
        {
            ActiveVampIndex = INDEX_NONE;
        }
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    if (CurrentFrame < PreviousFrame)
    {
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    if (bPlayOnce)
    {
        // Run-Through: release a vamp already looping, arm none; play on through.
        if (ActiveVampIndex != INDEX_NONE)
        {
            ReleasedVamps.Add(ActiveVampIndex);
            ActiveVampIndex = INDEX_NONE;
        }
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    if (ActiveVampIndex == INDEX_NONE)
    {
        for (int32 Index = 0; Index < Ranges.Num(); ++Index)
        {
            const FInfinityVampRange& Range = Ranges[Index];
            if (Range.IsValid()
                && !ReleasedVamps.Contains(Index)
                && PreviousFrame <= Range.StartFrame
                && CurrentFrame >= Range.StartFrame)
            {
                ActiveVampIndex = Index;
                break;
            }
        }
    }

    if (!FMath::IsNearlyEqual(PlayRate, 1.0f))
    {
        if (Ranges.IsValidIndex(ActiveVampIndex))
        {
            const FInfinityVampRange& Range = Ranges[ActiveVampIndex];
            if (CurrentFrame >= Range.EndFrame)
            {
                const int32 Duration = (Range.EndFrame - Range.StartFrame).Value;
                const int32 Overshoot = FMath::Max(0, (CurrentFrame - Range.EndFrame).Value);
                OutLoopFrame = Range.StartFrame + FFrameNumber(Overshoot % Duration);
                PreviousFrame = OutLoopFrame;
                ++LoopCount;
                return EInfinityVampPlaybackAction::LoopToStart;
            }
            PreviousFrame = CurrentFrame;
            return EInfinityVampPlaybackAction::NormalizeToOne;
        }
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    if (!Ranges.IsValidIndex(ActiveVampIndex)
        || CurrentFrame < Ranges[ActiveVampIndex].EndFrame)
    {
        PreviousFrame = CurrentFrame;
        return EInfinityVampPlaybackAction::None;
    }

    const FInfinityVampRange& Range = Ranges[ActiveVampIndex];
    const int32 Duration = (Range.EndFrame - Range.StartFrame).Value;
    const int32 Overshoot = FMath::Max(0, (CurrentFrame - Range.EndFrame).Value);
    OutLoopFrame = Range.StartFrame + FFrameNumber(Overshoot % Duration);
    PreviousFrame = OutLoopFrame;
    ++LoopCount;
    return EInfinityVampPlaybackAction::LoopToStart;
}

bool FInfinityVampPlaybackState::Release(
    const FFrameNumber CurrentFrame,
    const TArray<FInfinityVampRange>& Ranges)
{
    if (!Ranges.IsValidIndex(ActiveVampIndex))
    {
        return false;
    }
    const FInfinityVampRange& Range = Ranges[ActiveVampIndex];
    if (CurrentFrame < Range.StartFrame || CurrentFrame > Range.EndFrame)
    {
        return false;
    }
    ReleasedVamps.Add(ActiveVampIndex);
    ActiveVampIndex = INDEX_NONE;
    PreviousFrame = CurrentFrame;
    bHasPreviousFrame = true;
    return true;
}

void FInfinityHoldRightState::Press(const bool bInWasPlaying)
{
    if (bPressed)
    {
        return;
    }
    Reset();
    bPressed = true;
    bWasPlaying = bInWasPlaying;
}

EInfinityHoldRightAction FInfinityHoldRightState::Tick(
    const float DeltaSeconds,
    const float HoldThresholdSeconds)
{
    if (!bPressed || bThresholdReached)
    {
        return EInfinityHoldRightAction::None;
    }
    HeldSeconds += FMath::Max(0.0f, DeltaSeconds);
    if (HeldSeconds < FMath::Max(0.0f, HoldThresholdSeconds))
    {
        return EInfinityHoldRightAction::None;
    }
    bThresholdReached = true;
    return EInfinityHoldRightAction::BeginFastForward;
}

void FInfinityHoldRightState::ResolveFastForwardStart(const EInfinityTransportResult Result)
{
    bFastForwardActive = bPressed
        && bThresholdReached
        && Result == EInfinityTransportResult::Succeeded;
}

EInfinityHoldRightAction FInfinityHoldRightState::Release()
{
    if (!bPressed)
    {
        return EInfinityHoldRightAction::None;
    }

    EInfinityHoldRightAction Action = EInfinityHoldRightAction::None;
    if (bFastForwardActive)
    {
        Action = bWasPlaying
            ? EInfinityHoldRightAction::EndFastForwardPlaying
            : EInfinityHoldRightAction::EndFastForwardHeld;
    }
    else if (!bThresholdReached)
    {
        Action = EInfinityHoldRightAction::Advance;
    }

    Reset();
    return Action;
}

void FInfinityHoldRightState::Reset()
{
    bPressed = false;
    bThresholdReached = false;
    bFastForwardActive = false;
    bWasPlaying = false;
    HeldSeconds = 0.0f;
}

UInfinityStageTransportController::UInfinityStageTransportController()
{
    // The camera claim used to happen only on init, scrub and jump, so playing
    // across a Passage/Scene boundary never handed the view over: the previous
    // segment's camera stayed live for the whole next segment. One component
    // tick watches for that crossing, after Sequencer has evaluated the frame.
    // Wings remain tick-free.
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}

namespace InfinityStageGoCues
{
bool ParseMarkerLabel(const FString& Text, FString& OutNumber, FString& OutLabel, int32& OutMode)
{
    OutNumber.Reset();
    OutLabel.Reset();
    OutMode = -1;
    TArray<FString> Words;
    Text.TrimStartAndEnd().ParseIntoArrayWS(Words);
    // Upper-case GO and a numeric cue number only, so a Scene note such as "go on"
    // can never become a HOLD.
    if (Words.Num() < 2 || !Words[0].Equals(TEXT("GO"), ESearchCase::CaseSensitive))
    {
        return false;
    }
    const FString& Candidate = Words[1];
    bool bDigit = false;
    for (const TCHAR Character : Candidate)
    {
        if (FChar::IsDigit(Character))
        {
            bDigit = true;
        }
        else if (Character != TEXT('.'))
        {
            return false;
        }
    }
    if (!bDigit)
    {
        return false;
    }
    OutNumber = Candidate;
    int32 LabelStart = 2;
    if (Words.IsValidIndex(2) && Words[2].Equals(TEXT("HOLD"), ESearchCase::CaseSensitive))
    {
        OutMode = 1;
        LabelStart = 3;
    }
    else if (Words.IsValidIndex(2) && Words[2].Equals(TEXT("PASS"), ESearchCase::CaseSensitive))
    {
        OutMode = 0;
        LabelStart = 3;
    }
    for (int32 Index = LabelStart; Index < Words.Num(); ++Index)
    {
        OutLabel += (OutLabel.IsEmpty() ? TEXT("") : TEXT(" ")) + Words[Index];
    }
    return true;
}
}

void FInfinityGoHoldState::Reset()
{
    ActiveIndex = INDEX_NONE;
    Released.Reset();
    bHasPreviousFrame = false;
}

void FInfinityGoHoldState::OnNavigation(const FFrameNumber TargetFrame)
{
    ActiveIndex = INDEX_NONE;
    PreviousFrame = TargetFrame;
    bHasPreviousFrame = true;
}

int32 FInfinityGoHoldState::Tick(
    const FFrameNumber CurrentFrame,
    const bool bPlayingForward,
    const TArray<FInfinityGoCue>& Cues)
{
    // Back before a released hold's settle frame: it stops the show again next time through.
    for (auto It = Released.CreateIterator(); It; ++It)
    {
        if (!Cues.IsValidIndex(*It) || CurrentFrame < SettleFrame(Cues[*It]))
        {
            It.RemoveCurrent();
        }
    }
    if (ActiveIndex != INDEX_NONE)
    {
        if (bPlayingForward && Cues.IsValidIndex(ActiveIndex) && CurrentFrame != SettleFrame(Cues[ActiveIndex]))
        {
            // Resumed by something other than GO (Cue Desk, Blueprint): the hold is
            // spent, and must neither disarm later holds nor eat the next RIGHT.
            Released.Add(ActiveIndex);
            ActiveIndex = INDEX_NONE;
        }
        else
        {
            PreviousFrame = CurrentFrame;
            bHasPreviousFrame = true;
            return INDEX_NONE;
        }
    }
    if (!bHasPreviousFrame)
    {
        PreviousFrame = CurrentFrame;
        bHasPreviousFrame = true;
        return INDEX_NONE;
    }
    int32 Hit = INDEX_NONE;
    // Run-Through crosses every HOLD as a PASS; PreviousFrame still advances, so
    // switching it off mid-show arms only the holds still ahead.
    if (bPlayingForward && CurrentFrame > PreviousFrame && (!bPassAll || !KeepNumbers.IsEmpty()))
    {
        for (int32 Index = 0; Index < Cues.Num(); ++Index)
        {
            const FInfinityGoCue& Cue = Cues[Index];
            if (Cue.bHold && (!bPassAll || KeepNumbers.Contains(Cue.Number))
                && Cue.Frame > PreviousFrame && Cue.Frame <= CurrentFrame && !Released.Contains(Index))
            {
                Hit = Index;
                break;
            }
        }
    }
    PreviousFrame = CurrentFrame;
    ActiveIndex = Hit;
    return Hit;
}

bool FInfinityGoHoldState::Release()
{
    if (ActiveIndex == INDEX_NONE)
    {
        return false;
    }
    Released.Add(ActiveIndex);
    ActiveIndex = INDEX_NONE;
    return true;
}

void FInfinityGoHoldState::Consume(const int32 Index)
{
    Released.Add(Index);
    if (ActiveIndex == Index)
    {
        ActiveIndex = INDEX_NONE;
    }
}

bool UInfinityStageTransportController::StepJumpResettle(
    FInfinityJumpResettle& State,
    const FFrameNumber CurrentFrame,
    const bool bPlaying,
    const float DeltaSeconds,
    const float SettleSeconds,
    const int32 MinTicks)
{
    if (!State.bPending)
    {
        return false;
    }
    if (SettleSeconds <= 0.0f || bPlaying || CurrentFrame != State.Frame)
    {
        State.bPending = false;
        return false;
    }

    State.Elapsed += FMath::Max(0.0f, DeltaSeconds);
    ++State.Ticks;
    if (State.Elapsed < SettleSeconds || State.Ticks < MinTicks)
    {
        return false;
    }

    State.bPending = false;
    return true;
}

void UInfinityStageTransportController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bVideoAudioMuted = false;
    SetManagedMasterAudioMuted(false);
    UnregisterForWorld();
    CameraRigCache.Reset();
    ClaimedViewTarget.Reset();
    ClaimedAtWorldSeconds = -1.0;
    ClaimedBlendSeconds = 0.0f;
    Super::EndPlay(EndPlayReason);
}

void UInfinityStageTransportController::BeginDestroy()
{
    bVideoAudioMuted = false;
    SetManagedMasterAudioMuted(false);
    UnregisterForWorld();
    Super::BeginDestroy();
}

void UInfinityStageTransportController::TickComponent(
    const float DeltaTime,
    const ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    if (!Player || Segments.IsEmpty())
    {
        return;
    }
    const FFrameNumber CurrentFrame = GetCurrentMasterFrame();
    const int32 FrameSegment = FindSegmentAtFrame(CurrentFrame);
    if (SeamDiagOn())
    {
        TickSeamDiag(CurrentFrame, DeltaTime);
    }
    if (bFastForwardActive
        && Segments.IsValidIndex(FrameSegment)
        && Segments[FrameSegment].ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable)
    {
        // A hold begun in an earlier segment must not carry a rate change into
        // a live-performer clock. Continue through the segment, but at 1x.
        StopFastForwardPlayback();
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_FAST_FORWARD_INTERLOCK frame=%d segment=%d"),
            CurrentFrame.Value, FrameSegment);
    }
    if (bRewindActive
        && bPerformanceMode
        && Segments.IsValidIndex(FrameSegment)
        && Segments[FrameSegment].ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable)
    {
        // BeginRewind's target never enters a live-performer segment; if one is
        // reached anyway, drop the rate change at once (as fast-forward does).
        StopFastForwardPlayback();
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_REWIND_INTERLOCK frame=%d segment=%d"),
            CurrentFrame.Value, FrameSegment);
    }
    if (HandleGoHold(CurrentFrame))
    {
        return;
    }
    if (HandleVampPlayback(CurrentFrame))
    {
        return;
    }
    const bool bCoveredHandoff = IsCoveredHandoffActive(FrameSegment, CurrentFrame);
    if (FrameSegment != INDEX_NONE
        && (FrameSegment != SelectedSegmentIndex || bCoveredHandoff != bCoveredHandoffActive))
    {
        // A claim happens at segment boundaries and at the deterministic covered
        // threshold inside an interstitial. Reverse playback crosses it as well.
        SelectedSegmentIndex = FrameSegment;
        bCoveredHandoffActive = bCoveredHandoff;
        ClaimSegmentCamera(FrameSegment, CurrentFrame);
        return;
    }
    RunTickTail(CurrentFrame, DeltaTime);
}

void UInfinityStageTransportController::RunTickTail(
    const FFrameNumber CurrentFrame,
    const float DeltaTime)
{
    if (StepJumpResettle(
        JumpResettleState,
        CurrentFrame,
        Player && Player->IsPlaying(),
        DeltaTime,
        JumpResettleSeconds,
        JumpResettleMinTicks))
    {
        // StepJumpResettle fires only while the playhead is still on this exact
        // frame. Keep the external-clock safety gate explicit even though that
        // makes this a same-frame evaluation rather than a move.
        const FFrameNumber TargetFrame = JumpResettleState.Frame;
        if (Player && !IsUnsafeExternalMove(TargetFrame))
        {
            const FFrameTime DisplayFrame = ShowAsset
                ? FFrameRate::TransformTime(FFrameTime(TargetFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
                : FFrameTime(TargetFrame);
            Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Jump));
            ++JumpResettleCount;
            UE_LOG(LogInfinityStageTransport, Verbose,
                TEXT("INFINITY_JUMP_RESETTLE frame=%d"), TargetFrame.Value);

            // TEST SEAM: Sequencer may restore the pre-animated view target as
            // part of the evaluation above. The test performs that steal here.
            if (JumpResettlePostEvaluationTestSeam)
            {
                JumpResettlePostEvaluationTestSeam();
            }
        }
    }

    // This must remain after the same-frame evaluation. A Passage's Camera Cut
    // can restore its pre-animated target during SetPlaybackPosition, and the
    // transport must reclaim the Passage before this tick's camera update.
    ReassertPassageClaimIfLost();
}

bool UInfinityStageTransportController::BuildSegments(UInfinityStageShowAsset* InShowAsset)
{
    ShowAsset = InShowAsset;
    Segments.Reset();
    VampRanges.Reset();
    VampPlaybackState.Reset();
    GoCues.Reset();
    GoHoldState.Reset();
    ClearTransportRests();
    if (InShowAsset && InShowAsset->DisplayRate.IsValid() && InShowAsset->TickResolution.IsValid())
    {
        GoHoldState.SettleOffset = FMath::Max(1, FMath::CeilToInt32(
            InShowAsset->TickResolution.AsDecimal() / InShowAsset->DisplayRate.AsDecimal()));
    }
    CameraRigCache.Reset();
    SelectedSegmentIndex = INDEX_NONE;
    bCoveredHandoffActive = false;
    LastHandover = FInfinityCameraHandover();

    if (!ShowAsset)
    {
        return false;
    }

    ShowAsset->EnsureStableIds();
    ShowAsset->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    if (Compiled.HasErrors())
    {
        for (const FInfinityCompileIssue& Issue : Compiled.Issues)
        {
            if (Issue.Severity == EInfinityCompileIssueSeverity::Error)
            {
                UE_LOG(LogInfinityStageTransport, Warning,
                    TEXT("INFINITY_TRANSPORT_COMPILE_ERROR subject=%s message=%s"),
                    *Issue.SubjectGuid.ToString(EGuidFormats::DigitsWithHyphens),
                    *Issue.Message);
            }
        }
        return false;
    }

    for (const FInfinityCompiledSegment& CompiledSegment : Compiled.Segments)
    {
        const int32 SegmentIndex = Segments.Num();
        FInfinityTransportSegment& Segment = Segments.AddDefaulted_GetRef();
        Segment.SegmentGuid = CompiledSegment.SegmentGuid;
        Segment.Type = CompiledSegment.Type;
        Segment.CueIndex = CompiledSegment.FirstCueIndex;
        Segment.StartFrame = CompiledSegment.StartFrame;
        Segment.EndFrame = CompiledSegment.EndFrame;
        Segment.ExternalSound = CompiledSegment.ExternalSound;
        if (CompiledSegment.Type == EInfinityCueType::WingPair)
        {
            const FInfinityPassageSettings* Settings = ShowAsset->PassageSettings.FindByPredicate([&CompiledSegment](const FInfinityPassageSettings& Candidate)
            {
                return Candidate.PassageGuid == CompiledSegment.SegmentGuid;
            });
            Segment.Label = Settings ? Settings->Label : NSLOCTEXT("InfinityStage", "PassageTransportLabel", "Passage");
            const ULevelSequence* Choreo = Settings && !Settings->Choreography.IsNull()
                ? Settings->Choreography.LoadSynchronous()
                : nullptr;
            // The rebuild refuses to nest a Choreo with a Camera Cut track, so its
            // GO markers would hold over content that is not playing: skip them too.
            if (Choreo && !(Choreo->GetMovieScene() && Choreo->GetMovieScene()->GetCameraCutTrack()))
            {
                CollectGoCues(Choreo, ShowAsset->TickResolution, SegmentIndex,
                    Segment.StartFrame, Segment.EndFrame, false, GoCues);
            }
            continue;
        }
        if (!ShowAsset->Cues.IsValidIndex(CompiledSegment.FirstCueIndex))
        {
            continue;
        }

        const FInfinityShowCue& Cue = ShowAsset->Cues[CompiledSegment.FirstCueIndex];
        Segment.Label = Cue.Label;
        Segment.CurtainMode = Cue.Scene.CurtainMode;
        Segment.bRetainPreviousCamera = Cue.Scene.bRetainPreviousCamera;
        Segment.bRevealNextPassageWhenCovered =
            Cue.Scene.CurtainMode == EInfinityCurtainCueMode::PostSceneInterstitial
            && Cue.Scene.bRevealNextPassageWhenCovered;

        CollectSceneShotStarts(*ShowAsset, Cue, Segment);

        CollectVampRanges(
            *ShowAsset,
            Cue,
            SegmentIndex,
            Segment.StartFrame,
            Segment.EndFrame,
            VampRanges);

        const int32 FirstNewGo = GoCues.Num();
        CollectGoCues(Cue.Scene.Sequence.LoadSynchronous(), ShowAsset->TickResolution, SegmentIndex,
            Segment.StartFrame, Segment.EndFrame, true, GoCues);
        if (Cue.Scene.ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable)
        {
            // A live performer owns this clock (the result=4 interlock): it can never hold.
            for (int32 Index = FirstNewGo; Index < GoCues.Num(); ++Index)
            {
                if (GoCues[Index].bHold)
                {
                    GoCues[Index].bHold = false;
                    UE_LOG(LogInfinityStageTransport, Warning,
                        TEXT("INFINITY_GO_HOLD_DEMOTED number=%s segment=%d: DeclaredUnpausable, listed as PASS."),
                        *GoCues[Index].Number, SegmentIndex);
                }
            }
        }

        EInfinityCoveredHandoffSource HandoffSource = EInfinityCoveredHandoffSource::NotApplicable;
        const FFrameNumber HandoffOffset = ResolveCoveredHandoffOffset(*ShowAsset, Cue, HandoffSource);
        const int32 SegmentLength =
            FMath::Max(0, (Segment.EndFrame - Segment.StartFrame).Value);
        const int32 ClampedOffset = FMath::Clamp(HandoffOffset.Value, 0, SegmentLength);
        Segment.CoveredHandoffFrame = Segment.StartFrame + FFrameNumber(ClampedOffset);

        if (!Segment.bRevealNextPassageWhenCovered)
        {
            // The frame is still computed so a cue can be switched on without a
            // recompile, but no timing decision rests on it.
            Segment.CoveredHandoffSource = EInfinityCoveredHandoffSource::NotApplicable;
            continue;
        }
        Segment.CoveredHandoffSource = HandoffSource;

        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_HANDOFF_OFFSET segment=%d cue='%s' source=%s offset=%d frame=%d"),
            SegmentIndex,
            *Segment.Label.ToString(),
            LexCoveredHandoffSource(HandoffSource),
            ClampedOffset,
            Segment.CoveredHandoffFrame.Value);
        if (HandoffSource == EInfinityCoveredHandoffSource::FallbackSequenceFailedToLoad)
        {
            UE_LOG(LogInfinityStageTransport, Warning,
                TEXT("INFINITY_HANDOFF_OFFSET cue='%s' has a Sequence that failed to load; the covered ")
                TEXT("changeover fell back to entry + hold and will move if the asset later loads."),
                *Segment.Label.ToString());
        }
        if (ClampedOffset != HandoffOffset.Value)
        {
            UE_LOG(LogInfinityStageTransport, Warning,
                TEXT("INFINITY_HANDOFF_OFFSET cue='%s' asked for offset %d but the cue is only %d ")
                TEXT("frames long; the covered changeover was clamped to %d."),
                *Segment.Label.ToString(), HandoffOffset.Value, SegmentLength, ClampedOffset);
        }
    }

    GoCues.StableSort([](const FInfinityGoCue& A, const FInfinityGoCue& B) { return A.Frame < B.Frame; });
    // A HOLD inside a vamp would re-hold every loop and take every RIGHT as GO,
    // so the vamp could hardly be released (review N2): list it as PASS.
    for (FInfinityGoCue& Cue : GoCues)
    {
        if (!Cue.bHold)
        {
            continue;
        }
        for (const FInfinityVampRange& Range : VampRanges)
        {
            if (Cue.Frame >= Range.StartFrame && Cue.Frame <= Range.EndFrame)
            {
                Cue.bHold = false;
                UE_LOG(LogInfinityStageTransport, Warning,
                    TEXT("INFINITY_GO_HOLD_IN_VAMP number=%s frame=%d vamp=%d-%d: listed as PASS."),
                    *Cue.Number, Cue.Frame.Value, Range.StartFrame.Value, Range.EndFrame.Value);
                break;
            }
        }
    }
    return !Segments.IsEmpty();
}

bool UInfinityStageTransportController::InitializeTransport(ULevelSequencePlayer* InPlayer, UInfinityStageShowAsset* InShowAsset)
{
    SetManagedMasterAudioMuted(false);
    Player = InPlayer;
    bFastForwardActive = false;
    bRewindActive = false;
    bMasterAudioMutedForFastForward = false;
    JumpResettleState.bPending = false;
    ClearTransportRests();
    LastPlayToTargetForTests.Reset();
    LastResult = EInfinityTransportResult::NoPlayer;
    if (!InPlayer || !InShowAsset)
    {
        ShowAsset = InShowAsset;
        Segments.Reset();
        CameraRigCache.Reset();
        SelectedSegmentIndex = INDEX_NONE;
        bCoveredHandoffActive = false;
        UnregisterForWorld();
        return false;
    }

    if (!BuildSegments(InShowAsset))
    {
        LastResult = EInfinityTransportResult::NoSegment;
        UnregisterForWorld();
        return false;
    }

    // Registered only once the table is good, so sequence evaluation falls back
    // to its own claim while the show is not actually driveable.
    RegisterForWorld();
    RefreshSelectedSegment();
    LastResult = EInfinityTransportResult::Succeeded;
    if (Segments.IsValidIndex(SelectedSegmentIndex))
    {
        // Claim the correct view target during PIE initialization even before
        // the first evaluated Sequencer frame. This makes both auto-play and a
        // held-at-frame-zero rehearsal begin through the Passage camera.
        ClaimSegmentCamera(SelectedSegmentIndex, GetCurrentMasterFrame());
    }
    VampPlaybackState.OnNavigation(GetCurrentMasterFrame());
    GoHoldState.OnNavigation(GetCurrentMasterFrame());
    return true;
}

EInfinityTransportResult UInfinityStageTransportController::PlayForwardToBoundary()
{
    RefreshSelectedSegment();
    if (!Segments.IsValidIndex(SelectedSegmentIndex))
    {
        return LastResult = Player ? EInfinityTransportResult::NoSegment : EInfinityTransportResult::NoPlayer;
    }
    const int32 StopIndex = GetForwardStopSegmentIndex(SelectedSegmentIndex);
    if (!Segments[SelectedSegmentIndex].bReady || !Segments[StopIndex].bReady)
    {
        return LastResult = EInfinityTransportResult::NotReady;
    }
    // Use one uninterrupted PlayTo operation so the nested Scene evaluates on
    // the boundary frame without a pause/restart or a second sequence player.
    const EInfinityTransportResult Result = PlayToFrame(Segments[StopIndex].EndFrame);
    if (bRunThrough)
    {
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_RUN_THROUGH_PLAY from_segment=%d frame=%d target=%d result=%d"),
            SelectedSegmentIndex, GetCurrentMasterFrame().Value, Segments[StopIndex].EndFrame.Value,
            static_cast<int32>(Result));
    }
    if (Result == EInfinityTransportResult::Succeeded)
    {
        // The stop frame is also the next segment's first frame. Remember whose
        // END it is, so RIGHT there lands on that next segment instead of
        // skipping it (Gary, 5 Oct: S01's end, RIGHT, straight to P02).
        BoundaryEndRest.Set(StopIndex, Segments[StopIndex].EndFrame);
    }
    return Result;
}

int32 UInfinityStageTransportController::GetForwardStopSegmentIndex(const int32 FromSegmentIndex) const
{
    if (!Segments.IsValidIndex(FromSegmentIndex))
    {
        return INDEX_NONE;
    }
    if (bRunThrough)
    {
        // Run-Through: one PlayTo to the Show's end, or to the end of the next segment
        // the Cue Director marks as a stop; the tick still claims every camera at every seam.
        return RunThroughStopIndex(Segments, FromSegmentIndex, RunThroughStopAfter);
    }
    const int32 NextIndex = FromSegmentIndex + 1;
    if (bAutoPlaySceneAfterPassage
        && Segments[FromSegmentIndex].Type == EInfinityCueType::WingPair
        && Segments.IsValidIndex(NextIndex)
        && Segments[NextIndex].Type == EInfinityCueType::Scene
        && Segments[FromSegmentIndex].EndFrame == Segments[NextIndex].StartFrame)
    {
        return NextIndex;
    }
    return FromSegmentIndex;
}

int32 UInfinityStageTransportController::RunThroughStopIndex(
    const TArray<FInfinityTransportSegment>& InSegments,
    const int32 From,
    const TArray<FGuid>& StopAfter)
{
    if (!InSegments.IsValidIndex(From))
    {
        return INDEX_NONE;
    }
    for (int32 Index = From; Index < InSegments.Num(); ++Index)
    {
        if (StopAfter.Contains(InSegments[Index].SegmentGuid))
        {
            return Index;
        }
    }
    return InSegments.Num() - 1;
}

void UInfinityStageTransportController::ApplyCueDirector(
    const bool bInRunThrough,
    const TArray<FGuid>& StopAfter,
    const TArray<FString>& HoldGoNumbers)
{
    bRunThrough = bInRunThrough;
    RunThroughStopAfter = StopAfter;
    RunThroughHoldGoNumbers = HoldGoNumbers;
    GoHoldState.KeepNumbers = TSet<FString>(HoldGoNumbers);
    int32 Matched = 0;
    for (const FInfinityTransportSegment& Segment : Segments)
    {
        Matched += StopAfter.Contains(Segment.SegmentGuid) ? 1 : 0;
    }
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_CUE_DIRECTOR_APPLIED run_through=%d stops=%d matched=%d hold_go=%d"),
        bRunThrough ? 1 : 0, StopAfter.Num(), Matched, HoldGoNumbers.Num());
    if (Matched != StopAfter.Num())
    {
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_CUE_DIRECTOR_STOP_UNMATCHED %d stop(s) name no segment in this Show (re-save the Cue Director panel)"),
            StopAfter.Num() - Matched);
    }
}

EInfinityTransportResult UInfinityStageTransportController::PlayForwardThroughBoundaries()
{
    RefreshSelectedSegment();
    if (Segments.IsEmpty())
    {
        return LastResult = Player ? EInfinityTransportResult::NoSegment : EInfinityTransportResult::NoPlayer;
    }
    // The tick claims each segment's camera as the playhead crosses into it, so
    // one continuous play still hands the view over at every boundary.
    return PlayToFrame(Segments.Last().EndFrame);
}

EInfinityTransportResult UInfinityStageTransportController::PlayReverseToBoundary()
{
    RefreshSelectedSegment();
    if (!Segments.IsValidIndex(SelectedSegmentIndex))
    {
        return LastResult = Player ? EInfinityTransportResult::NoSegment : EInfinityTransportResult::NoPlayer;
    }
    const FFrameNumber Current = GetCurrentMasterFrame();
    const int32 TargetIndex = Current <= Segments[SelectedSegmentIndex].StartFrame
        ? SelectedSegmentIndex - 1
        : SelectedSegmentIndex;
    if (!Segments.IsValidIndex(TargetIndex))
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }
    return PlayToFrame(Segments[TargetIndex].StartFrame);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToCurrentStart()
{
    RefreshSelectedSegment();
    return JumpToSegment(GetOperatorCurrentSegmentIndex(), false);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToCurrentEnd()
{
    RefreshSelectedSegment();
    return JumpToSegment(GetOperatorCurrentSegmentIndex(), true);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToNextSegment()
{
    RefreshSelectedSegment();
    return JumpToSegment(ResolveAdvanceTargetIndex(SelectedSegmentIndex, GetHeldAtEndSegmentIndex()), false);
}

EInfinityTransportResult UInfinityStageTransportController::AdvanceToNextSegment()
{
    RefreshSelectedSegment();

    // A transition that RIGHT landed on and is holding is the cue that is up:
    // this RIGHT is its GO. Space does the same through PlayForwardToBoundary.
    const int32 ArmedIndex = GetArmedSequenceSegmentIndex();
    if (ArmedIndex != INDEX_NONE && ArmedIndex == SelectedSegmentIndex)
    {
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_ADVANCE_PLAYS_ARMED segment=%d frame=%d"),
            ArmedIndex, GetCurrentMasterFrame().Value);
        return PlayForwardToBoundary();
    }

    const int32 HeldAtEndIndex = GetHeldAtEndSegmentIndex();
    const int32 TargetIndex = ResolveAdvanceTargetIndex(SelectedSegmentIndex, HeldAtEndIndex);
    const EInfinityTransportResult CueResult = JumpToSegment(TargetIndex, false);
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_ADVANCE selected=%d held_end=%d target=%d result=%d"),
        SelectedSegmentIndex, HeldAtEndIndex, TargetIndex, static_cast<int32>(CueResult));
    if (CueResult != EInfinityTransportResult::Succeeded)
    {
        return CueResult;
    }

    // A post-Scene curtain interstitial used to play the moment it was landed
    // on, so it could not be examined. Rehearsal now holds it on its first
    // frame; bAutoPlaySequenceOnAdvance restores the single-press transition.
    // The covered handoff is claimed by the tick as playback crosses it, so it
    // behaves the same whichever key starts the play.
    if (Segments.IsValidIndex(TargetIndex)
        && PlaysOnAdvanceLanding(Segments[TargetIndex].Type, bAutoPlaySequenceOnAdvance, bAutoPlaySceneAfterPassage, bRunThrough))
    {
        return PlayForwardToBoundary();
    }
    if (Segments.IsValidIndex(TargetIndex) && Segments[TargetIndex].Type == EInfinityCueType::Sequence)
    {
        ArmedSequenceRest.Set(TargetIndex, Segments[TargetIndex].StartFrame);
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_ADVANCE_ARMED segment=%d frame=%d label='%s': RIGHT or Space plays it."),
            TargetIndex, Segments[TargetIndex].StartFrame.Value, *Segments[TargetIndex].Label.ToString());
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

int32 UInfinityStageTransportController::GetHeldAtEndSegmentIndex() const
{
    const int32 Index = ResolveRestSegment(BoundaryEndRest, GetCurrentMasterFrame(), IsTransportPlaying());
    return Segments.IsValidIndex(Index) && Segments[Index].EndFrame == BoundaryEndRest.Frame ? Index : INDEX_NONE;
}

int32 UInfinityStageTransportController::GetArmedSequenceSegmentIndex() const
{
    const int32 Index = ResolveRestSegment(ArmedSequenceRest, GetCurrentMasterFrame(), IsTransportPlaying());
    return Segments.IsValidIndex(Index) && Segments[Index].StartFrame == ArmedSequenceRest.Frame ? Index : INDEX_NONE;
}

int32 UInfinityStageTransportController::GetOperatorCurrentSegmentIndex() const
{
    const int32 HeldAtEndIndex = GetHeldAtEndSegmentIndex();
    return HeldAtEndIndex != INDEX_NONE ? HeldAtEndIndex : SelectedSegmentIndex;
}

void UInfinityStageTransportController::ClearTransportRests()
{
    BoundaryEndRest.Reset();
    ArmedSequenceRest.Reset();
}

EInfinityTransportResult UInfinityStageTransportController::StepShotForward()
{
    RefreshSelectedSegment();
    // Held at the end of K, the playhead is already on K+1's first shot: a shot
    // step from here would skip that shot (or, past the last, the whole cue).
    if (GetHeldAtEndSegmentIndex() != INDEX_NONE)
    {
        return AdvanceToNextSegment();
    }
    if (!Segments.IsValidIndex(SelectedSegmentIndex)
        || Segments[SelectedSegmentIndex].Type != EInfinityCueType::Scene)
    {
        return AdvanceToNextSegment();
    }

    const int32 SegmentIndex = SelectedSegmentIndex;
    const FFrameNumber Current = GetCurrentMasterFrame();
    const TArray<FFrameNumber>& Starts = Segments[SegmentIndex].ShotStartFrames;
    for (int32 ShotIndex = 0; ShotIndex < Starts.Num(); ++ShotIndex)
    {
        if (Starts[ShotIndex] <= Current)
        {
            continue;
        }
        const bool bWasPlaying = IsTransportPlaying();
        const EInfinityTransportResult Result = JumpToMasterFrame(
            SegmentIndex, Starts[ShotIndex], bWasPlaying);
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_SHOT_STEP dir=next segment=%d from=%d to=%d shot=%d/%d playing=%d result=%d"),
            SegmentIndex,
            Current.Value,
            Starts[ShotIndex].Value,
            ShotIndex + 1,
            Starts.Num(),
            bWasPlaying ? 1 : 0,
            static_cast<int32>(Result));
        return Result;
    }
    return AdvanceToNextSegment();
}

EInfinityTransportResult UInfinityStageTransportController::BeginFastForward()
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    RefreshSelectedSegment();
    if (Segments.IsEmpty())
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }

    const float Rate = FMath::Max(1.0f, FastForwardRate);
    if (!FMath::IsNearlyEqual(Rate, 1.0f) && IsUnsafeExternalHold())
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }

    JumpResettleState.bPending = false;
    bFastForwardActive = true;
    SetManagedMasterAudioMuted(!FMath::IsNearlyEqual(Rate, 1.0f));
    Player->SetPlayRate(Rate);
    // PlayTo the Master's final frame: unlike Advance, this never jumps across
    // authored time, and TickComponent still claims every camera at every seam.
    return PlayForwardThroughBoundaries();
}

EInfinityTransportResult UInfinityStageTransportController::EndFastForward(const bool bWasPlaying)
{
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("ff_end"), FString::Printf(TEXT("|was_playing=%d"), bWasPlaying ? 1 : 0));
    }
    StopFastForwardPlayback();
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }

    if (GoHoldState.IsActive())
    {
        // The hold already paused on its GO; key-up must not play through it.
        return LastResult = EInfinityTransportResult::Succeeded;
    }
    if (ResumesAfterFastForward(bWasPlaying, VampPlaybackState.IsActive(), GoHoldState.IsActive()))
    {
        Player->Play();
        return LastResult = EInfinityTransportResult::Succeeded;
    }
    return PauseTransport();
}

FFrameNumber UInfinityStageTransportController::ResolveRewindTargetFrame(
    const TArray<FInfinityTransportSegment>& InSegments,
    const int32 FromSegmentIndex,
    const bool bInPerformanceMode)
{
    if (InSegments.IsEmpty())
    {
        return 0;
    }
    if (!InSegments.IsValidIndex(FromSegmentIndex))
    {
        return InSegments[0].StartFrame;
    }
    int32 Index = FromSegmentIndex;
    while (Index > 0
        && !(bInPerformanceMode
            && InSegments[Index - 1].ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable))
    {
        --Index;
    }
    // In performance mode Index now follows the nearest earlier live-performer
    // segment: stopping on its start frame is stopping on that segment's END.
    return InSegments[Index].StartFrame;
}

EInfinityTransportResult UInfinityStageTransportController::BeginRewind()
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    RefreshSelectedSegment();
    if (!Segments.IsValidIndex(SelectedSegmentIndex))
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }
    // Reversing is both a move and a rate change: never inside a live clock.
    if (IsUnsafeExternalHold())
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }
    const FFrameNumber Current = GetCurrentMasterFrame();
    const FFrameNumber Target = ResolveRewindTargetFrame(Segments, SelectedSegmentIndex, bPerformanceMode);
    if (Target >= Current)
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }

    const float Rate = FMath::Max(1.0f, RewindRate);
    JumpResettleState.bPending = false;
    bFastForwardActive = false;
    bRewindActive = true;
    // Reverse audio is noise: mute exactly as fast-forward does, restored at 1x.
    SetManagedMasterAudioMuted(true);
    Player->SetPlayRate(Rate);
    // One PlayTo toward an earlier frame plays in reverse (as PlayReverseToBoundary
    // does); the tick claims each segment's camera as the playhead crosses back.
    const EInfinityTransportResult Result = PlayToFrame(Target);
    if (Result != EInfinityTransportResult::Succeeded)
    {
        StopFastForwardPlayback();
    }
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_REWIND_BEGIN from=%d target=%d rate=%.2f result=%d"),
        Current.Value, Target.Value, Rate, static_cast<int32>(Result));
    return Result;
}

EInfinityTransportResult UInfinityStageTransportController::EndRewind(const bool bWasPlaying)
{
    const bool bWasRewinding = bRewindActive;
    StopFastForwardPlayback();
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_REWIND_END frame=%d was_rewinding=%d resume=%d"),
        GetCurrentMasterFrame().Value, bWasRewinding ? 1 : 0, bWasPlaying ? 1 : 0);
    if (bWasPlaying)
    {
        return PlayForwardToBoundary();
    }
    return PauseTransport();
}

bool UInfinityStageTransportController::ReleaseActiveVamp()
{
    if (!Player)
    {
        return false;
    }
    const FFrameNumber CurrentFrame = GetCurrentMasterFrame();
    const int32 VampIndex = VampPlaybackState.ActiveVampIndex;
    if (!VampPlaybackState.Release(CurrentFrame, VampRanges)
        || !VampRanges.IsValidIndex(VampIndex)
        || !Segments.IsValidIndex(VampRanges[VampIndex].SegmentIndex))
    {
        return false;
    }

    StopFastForwardPlayback();
    JumpResettleState.bPending = false;
    const FFrameNumber SegmentEnd = Segments[VampRanges[VampIndex].SegmentIndex].EndFrame;
    // A forward play to a segment end, like PlayForwardToBoundary: RIGHT at the
    // stop must land on the next cue, not skip it.
    ClearTransportRests();
    BoundaryEndRest.Set(VampRanges[VampIndex].SegmentIndex, SegmentEnd);
    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(SegmentEnd), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(SegmentEnd);
    FMovieSceneSequencePlayToParams PlayToParams;
    PlayToParams.bExclusive = false;
    Player->PlayTo(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Play), PlayToParams);
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_VAMP_RELEASE index=%d frame=%d segment_end=%d"),
        VampIndex, CurrentFrame.Value, SegmentEnd.Value);
    return true;
}

EInfinityTransportResult UInfinityStageTransportController::JumpToPreviousSegment()
{
    RefreshSelectedSegment();
    const FFrameNumber Current = GetCurrentMasterFrame();
    const bool bPastSelectedStart =
        Segments.IsValidIndex(SelectedSegmentIndex) && Current > Segments[SelectedSegmentIndex].StartFrame;
    // Held at the end of K this already resolved to K's start (Selected is K+1
    // and the playhead is on its first frame); the rest makes that explicit and
    // keeps it true if a compiled gap ever separates K's end from K+1's start.
    const int32 TargetIndex =
        ResolvePreviousTargetIndex(SelectedSegmentIndex, bPastSelectedStart, GetHeldAtEndSegmentIndex());
    return JumpToSegment(TargetIndex, false);
}

EInfinityTransportResult UInfinityStageTransportController::StepShotBack()
{
    RefreshSelectedSegment();
    if (!Segments.IsValidIndex(SelectedSegmentIndex)
        || Segments[SelectedSegmentIndex].Type != EInfinityCueType::Scene)
    {
        return JumpToPreviousSegment();
    }

    const int32 SegmentIndex = SelectedSegmentIndex;
    const FFrameNumber Current = GetCurrentMasterFrame();
    const TArray<FFrameNumber>& Starts = Segments[SegmentIndex].ShotStartFrames;
    int32 CurrentShotIndex = INDEX_NONE;
    for (int32 ShotIndex = 0; ShotIndex < Starts.Num() && Starts[ShotIndex] <= Current; ++ShotIndex)
    {
        CurrentShotIndex = ShotIndex;
    }
    if (CurrentShotIndex == INDEX_NONE)
    {
        return JumpToPreviousSegment();
    }

    const FFrameNumber GraceFrames = ShowAsset
        ? FFrameRate::TransformTime(
            FFrameTime(FFrameNumber(FMath::Max(0, ShotRestartGraceDisplayFrames))),
            ShowAsset->DisplayRate,
            ShowAsset->TickResolution).RoundToFrame()
        : FFrameNumber(FMath::Max(0, ShotRestartGraceDisplayFrames));
    const int32 TargetShotIndex = Current > Starts[CurrentShotIndex] + GraceFrames
        ? CurrentShotIndex
        : CurrentShotIndex - 1;
    if (!Starts.IsValidIndex(TargetShotIndex))
    {
        return JumpToPreviousSegment();
    }

    const bool bWasPlaying = IsTransportPlaying();
    const EInfinityTransportResult Result = JumpToMasterFrame(
        SegmentIndex, Starts[TargetShotIndex], bWasPlaying);
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_SHOT_STEP dir=prev segment=%d from=%d to=%d shot=%d/%d playing=%d result=%d"),
        SegmentIndex,
        Current.Value,
        Starts[TargetShotIndex].Value,
        TargetShotIndex + 1,
        Starts.Num(),
        bWasPlaying ? 1 : 0,
        static_cast<int32>(Result));
    return Result;
}

EInfinityTransportResult UInfinityStageTransportController::PauseTransport()
{
    if (!Player)
    {
        LastResult = EInfinityTransportResult::NoPlayer;
    }
    else if (IsUnsafeExternalHold())
    {
        LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }
    else
    {
        // Sequencer's own Pause (not a zero play rate): the Master stops; anything
        // timed by the world (camera-manager blends, the cat's animation, dog/mouse
        // look) keeps running. The seam diagnostic logs both clocks here.
        Player->Pause();
        LastResult = EInfinityTransportResult::Succeeded;
    }
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("pause"), FString::Printf(TEXT("|result=%d"), static_cast<int32>(LastResult)));
    }
    return LastResult;
}

EInfinityTransportResult UInfinityStageTransportController::ResumeForward()
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    JumpResettleState.bPending = false;
    ClearTransportRests();
    Player->SetPlayRate(FMath::Max(0.001f, FMath::Abs(Player->GetPlayRate())));
    Player->Play();
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("resume"), FString());
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

EInfinityTransportResult UInfinityStageTransportController::Shuttle(const float Rate)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    JumpResettleState.bPending = false;
    ClearTransportRests();
    if (FMath::IsNearlyZero(Rate))
    {
        return PauseTransport();
    }
    if (IsUnsafeExternalHold() && (!FMath::IsNearlyEqual(Rate, 1.0f)))
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }
    Player->SetPlayRate(FMath::Abs(Rate));
    if (Rate < 0.0f)
    {
        Player->PlayReverse();
    }
    else
    {
        Player->Play();
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

EInfinityTransportResult UInfinityStageTransportController::ScrubToMasterFrame(const FFrameNumber TargetFrame)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    const int32 TargetIndex = FindSegmentAtFrame(TargetFrame);
    if (!Segments.IsValidIndex(TargetIndex))
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }
    if (!Segments[TargetIndex].bReady)
    {
        return LastResult = EInfinityTransportResult::NotReady;
    }
    if (IsUnsafeExternalMove(TargetFrame))
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }

    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(TargetFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(TargetFrame);
    Player->Pause();
    Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Jump));
    ClearTransportRests();
    VampPlaybackState.OnNavigation(TargetFrame);
    GoHoldState.OnNavigation(TargetFrame);
    JumpResettleState = {true, TargetFrame, 0.0f, 0};
    SelectedSegmentIndex = TargetIndex;
    bCoveredHandoffActive = IsCoveredHandoffActive(TargetIndex, TargetFrame);
    ClaimSegmentCamera(TargetIndex, TargetFrame);
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("scrub"), FString::Printf(TEXT("|target=%d"), TargetFrame.Value));
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

bool UInfinityStageTransportController::IsTransportPlaying() const
{
    return Player && Player->IsPlaying();
}

FFrameNumber UInfinityStageTransportController::GetCurrentMasterFrame() const
{
    if (!Player)
    {
        return 0;
    }
    const FQualifiedFrameTime Current = Player->GetCurrentTime();
    if (!ShowAsset || !Current.Rate.IsValid() || !ShowAsset->TickResolution.IsValid())
    {
        return Current.Time.FloorToFrame();
    }
    // Frame-rate conversion travels through FFrameTime's fractional representation. Round back to
    // the authored Master tick so a mathematically exact boundary cannot report one tick early.
    return FFrameRate::TransformTime(Current.Time, Current.Rate, ShowAsset->TickResolution).RoundToFrame();
}

int32 UInfinityStageTransportController::FindSegmentAtFrame(const FFrameNumber Frame) const
{
    for (int32 Index = 0; Index < Segments.Num(); ++Index)
    {
        if (Frame >= Segments[Index].StartFrame && Frame < Segments[Index].EndFrame)
        {
            return Index;
        }
    }
    if (!Segments.IsEmpty() && Frame == Segments.Last().EndFrame)
    {
        return Segments.Num() - 1;
    }
    return INDEX_NONE;
}

int32 UInfinityStageTransportController::FindNextPassageSegment(const int32 FromSegmentIndex) const
{
    for (int32 Index = FromSegmentIndex + 1; Index < Segments.Num(); ++Index)
    {
        if (Segments[Index].Type == EInfinityCueType::WingPair)
        {
            return Index;
        }
    }
    return INDEX_NONE;
}

bool UInfinityStageTransportController::IsCoveredHandoffActive(
    const int32 SegmentIndex,
    const FFrameNumber MasterFrame) const
{
    return Segments.IsValidIndex(SegmentIndex)
        && Segments[SegmentIndex].bRevealNextPassageWhenCovered
        && MasterFrame >= Segments[SegmentIndex].CoveredHandoffFrame;
}

EInfinityTransportResult UInfinityStageTransportController::JumpToSegment(const int32 SegmentIndex, const bool bToEnd)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    if (!Segments.IsValidIndex(SegmentIndex))
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }
    const FFrameNumber Target = bToEnd ? Segments[SegmentIndex].EndFrame : Segments[SegmentIndex].StartFrame;
    return JumpToMasterFrame(SegmentIndex, Target, false);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToMasterFrame(
    const int32 SegmentIndex,
    const FFrameNumber TargetFrame,
    const bool bKeepPlaying)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    if (!Segments.IsValidIndex(SegmentIndex))
    {
        return LastResult = EInfinityTransportResult::NoSegment;
    }
    if (!Segments[SegmentIndex].bReady)
    {
        return LastResult = EInfinityTransportResult::NotReady;
    }
    if (IsUnsafeExternalMove(TargetFrame))
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }

    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(TargetFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(TargetFrame);
    Player->Pause();
    Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Jump));
    // Before the keep-playing branch: its PlayForwardToBoundary records a new rest.
    ClearTransportRests();
    VampPlaybackState.OnNavigation(TargetFrame);
    GoHoldState.OnNavigation(TargetFrame);
    SelectedSegmentIndex = SegmentIndex;
    bCoveredHandoffActive = IsCoveredHandoffActive(SegmentIndex, TargetFrame);
    if (bKeepPlaying)
    {
        const EInfinityTransportResult PlayResult = PlayForwardToBoundary();
        if (PlayResult != EInfinityTransportResult::Succeeded)
        {
            return PlayResult;
        }
    }
    // PlayToFrame clears any older pending re-pose. Arm this jump's re-pose
    // after restoring bounded playback so Geometry Caches still resettle.
    JumpResettleState = {true, TargetFrame, 0.0f, 0};
    ClaimSegmentCamera(SegmentIndex, TargetFrame);
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("jump"), FString::Printf(TEXT("|target=%d|keep_playing=%d"),
            TargetFrame.Value, bKeepPlaying ? 1 : 0));
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

FInfinityCameraHandover UInfinityStageTransportController::ResolveHandover(
    const int32 SegmentIndex,
    const FFrameNumber MasterFrame) const
{
    FInfinityCameraHandover Out;
    Out.RequestedSegmentIndex = SegmentIndex;
    Out.Frame = MasterFrame;
    if (!Segments.IsValidIndex(SegmentIndex))
    {
        Out.Resolution = EInfinityHandoverResolution::NoSuchSegment;
        return Out;
    }

    const auto Finish = [this](FInfinityCameraHandover& Handover, const FInfinityCameraHandoverBlend& Blend)
    {
        Handover.Resolution = EInfinityHandoverResolution::Resolved;
        Handover.Blend = Blend;
        // Nothing is on screen to dissolve behind a closed curtain, and a blend
        // still running when the curtain lifts reads as an unexplained drift.
        if (Handover.bCovered && bCutWhenCovered)
        {
            Handover.Blend.BlendSeconds = 0.0f;
        }
    };

    int32 Index = SegmentIndex;
    FFrameNumber Frame = MasterFrame;
    // A retain chain only ever walks backwards and a reveal only ever forwards
    // into a Passage, so the segment count bounds the walk. The guard exists so
    // a malformed compile reports itself instead of hanging the show.
    const int32 MaxSteps = Segments.Num() + 1;
    for (int32 Step = 0; Step < MaxSteps; ++Step)
    {
        const FInfinityTransportSegment& Segment = Segments[Index];
        Out.SegmentIndex = Index;
        Out.Frame = Frame;

        // A sequence-authored Camera Cut is explicit creative intent and always
        // wins over retained-camera and covered-handoff defaults.
        if (Segment.Type != EInfinityCueType::WingPair && FindSceneCameraCut(Index, Frame))
        {
            Out.Source = EInfinityHandoverSource::SceneCameraCut;
            Finish(Out, SceneEntryBlend);
            return Out;
        }

        // An opening reveal has no preceding Scene to retain. Establish the next
        // Passage's frozen opening view behind the closed curtain, while still
        // allowing an explicitly authored Camera Cut above to take priority.
        if (Segment.CurtainMode == EInfinityCurtainCueMode::OpeningReveal)
        {
            const int32 NextPassage = FindNextPassageSegment(Index);
            if (NextPassage == INDEX_NONE)
            {
                Out.Resolution = EInfinityHandoverResolution::NoFollowingPassage;
                return Out;
            }
            Out.bCovered = true;
            Index = NextPassage;
            Frame = Segments[NextPassage].StartFrame;
            continue;
        }

        if (Segment.bRetainPreviousCamera)
        {
            if (IsCoveredHandoffActive(Index, Frame))
            {
                const int32 NextPassage = FindNextPassageSegment(Index);
                if (NextPassage == INDEX_NONE)
                {
                    Out.Resolution = EInfinityHandoverResolution::NoFollowingPassage;
                    return Out;
                }
                Out.bCovered = true;
                Index = NextPassage;
                Frame = Segments[NextPassage].StartFrame;
                continue;
            }
            if (!Segments.IsValidIndex(Index - 1))
            {
                Out.Resolution = EInfinityHandoverResolution::RetainWithoutPrevious;
                return Out;
            }
            // Chained retains resolve transitively: the previous segment's own
            // rule runs on the next pass round this loop.
            --Index;
            Frame = Segments[Index].EndFrame;
            continue;
        }

        if (Segment.Type == EInfinityCueType::WingPair)
        {
            Out.Source = EInfinityHandoverSource::PassageRig;
            Finish(Out, PassageEntryBlend);
            return Out;
        }

        // A Scene or Sequence cue with no Camera Cut, no retain and no Passage
        // of its own supplies no camera at all. This was the silent return.
        Out.Resolution = EInfinityHandoverResolution::NoRuleForSegment;
        return Out;
    }

    Out.Resolution = EInfinityHandoverResolution::ChainTooLong;
    return Out;
}

void UInfinityStageTransportController::ClaimSegmentCamera(
    const int32 SegmentIndex,
    const FFrameNumber MasterFrame)
{
    const FInfinityCameraHandover Handover = ResolveHandover(SegmentIndex, MasterFrame);
    LastHandover = Handover;

    const UWorld* World = GetWorld();
    const bool bGameWorld = World && World->IsGameWorld();
    if (!Handover.IsResolved())
    {
        const FString Requested = Segments.IsValidIndex(Handover.RequestedSegmentIndex)
            ? Segments[Handover.RequestedSegmentIndex].Label.ToString()
            : FString(TEXT("<none>"));
        const FString Message = FString::Printf(
            TEXT("INFINITY_HANDOVER_UNRESOLVED requested=%d ('%s') stopped=%d frame=%d reason=%s ")
            TEXT("- no camera was claimed and the previous one stays live."),
            Handover.RequestedSegmentIndex,
            *Requested,
            Handover.SegmentIndex,
            MasterFrame.Value,
            LexHandoverResolution(Handover.Resolution));
        UE_CLOG(bGameWorld, LogInfinityStageTransport, Warning, TEXT("%s"), *Message);
        UE_CLOG(!bGameWorld, LogInfinityStageTransport, Log, TEXT("%s"), *Message);
        return;
    }

    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_HANDOVER requested=%d frame=%d source=%s from=%d at=%d blend=%.3fs covered=%d"),
        Handover.RequestedSegmentIndex,
        MasterFrame.Value,
        LexHandoverSource(Handover.Source),
        Handover.SegmentIndex,
        Handover.Frame.Value,
        Handover.Blend.BlendSeconds,
        Handover.bCovered ? 1 : 0);
    const bool bApplied = ApplyHandover(Handover);
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("claim"), FString::Printf(TEXT("|requested=%d|source=%s|from=%d|at=%d|blend=%.3f|applied=%d"),
            Handover.RequestedSegmentIndex, LexHandoverSource(Handover.Source), Handover.SegmentIndex,
            Handover.Frame.Value, Handover.Blend.BlendSeconds, bApplied ? 1 : 0));
    }
}

bool UInfinityStageTransportController::ApplyHandover(const FInfinityCameraHandover& Handover)
{
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld() || !Segments.IsValidIndex(Handover.SegmentIndex))
    {
        return false;
    }

    switch (Handover.Source)
    {
    case EInfinityHandoverSource::SceneCameraCut:
        return ClaimSceneCameraCut(Handover);

    case EInfinityHandoverSource::PassageRig:
    {
        const FInfinityTransportSegment& Segment = Segments[Handover.SegmentIndex];
        AInfinityStageCameraRig* CameraRig = FindCameraRigForPassage(Segment.SegmentGuid);
        if (!CameraRig)
        {
            UE_LOG(LogInfinityStageTransport, Warning,
                TEXT("INFINITY_HANDOVER_NO_RIG segment=%d ('%s') has no Camera Rig bound to its Passage; ")
                TEXT("the previous camera stays live."),
                Handover.SegmentIndex, *Segment.Label.ToString());
            return false;
        }
        CameraRig->EvaluateAtMasterFrame(Handover.Frame);
        return ClaimViewTarget(CameraRig, Handover.Blend, TEXT("PassageRig"));
    }

    default:
        return false;
    }
}

const UMovieSceneCameraCutSection* UInfinityStageTransportController::FindSceneCameraCut(
    const int32 SegmentIndex,
    const FFrameNumber MasterFrame,
    ULevelSequence** OutSequence) const
{
    if (OutSequence)
    {
        *OutSequence = nullptr;
    }
    if (!ShowAsset || !Segments.IsValidIndex(SegmentIndex))
    {
        return nullptr;
    }
    const FInfinityTransportSegment& Segment = Segments[SegmentIndex];
    if (!ShowAsset->Cues.IsValidIndex(Segment.CueIndex))
    {
        return nullptr;
    }

    const FInfinityShowCue& Cue = ShowAsset->Cues[Segment.CueIndex];
    ULevelSequence* SceneSequence = Cue.Scene.Sequence.LoadSynchronous();
    UMovieScene* MovieScene = SceneSequence ? SceneSequence->GetMovieScene() : nullptr;
    const UMovieSceneCameraCutTrack* CutTrack = MovieScene
        ? Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack())
        : nullptr;
    if (!CutTrack || !ShowAsset->TickResolution.IsValid() || !MovieScene->GetTickResolution().IsValid())
    {
        return nullptr;
    }

    const FFrameNumber ScenePlaybackStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    const FFrameNumber ScenePlaybackEnd = MovieScene->GetPlaybackRange().GetUpperBoundValue();
    const FFrameNumber LocalFrame = ScenePlaybackStart + FFrameRate::TransformTime(
        FFrameTime(MasterFrame - Segment.StartFrame),
        ShowAsset->TickResolution,
        MovieScene->GetTickResolution()).RoundToFrame();

    const TArray<UMovieSceneSection*>& Sections = CutTrack->GetAllSections();
    const UMovieSceneCameraCutSection* ActiveCut = nullptr;
    for (UMovieSceneSection* BaseSection : Sections)
    {
        const UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(BaseSection);
        if (Cut && Cut->IsActive() && Cut->GetRange().Contains(LocalFrame))
        {
            if (!ActiveCut || Cut->GetInclusiveStartFrame() > ActiveCut->GetInclusiveStartFrame())
            {
                ActiveCut = Cut;
            }
        }
    }
    // Cut ranges are half-open, so the exact last frame of a Scene - which is
    // where a retained handover samples the outgoing camera - belongs to no cut.
    if (!ActiveCut && LocalFrame == ScenePlaybackEnd)
    {
        for (UMovieSceneSection* BaseSection : Sections)
        {
            const UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(BaseSection);
            if (Cut && Cut->IsActive()
                && (!ActiveCut || Cut->GetExclusiveEndFrame() > ActiveCut->GetExclusiveEndFrame()))
            {
                ActiveCut = Cut;
            }
        }
    }
    if (!ActiveCut || !ActiveCut->GetCameraBindingID().IsValid())
    {
        return nullptr;
    }
    if (OutSequence)
    {
        *OutSequence = SceneSequence;
    }
    return ActiveCut;
}

bool UInfinityStageTransportController::ClaimSceneCameraCut(const FInfinityCameraHandover& Handover)
{
    UWorld* World = GetWorld();
    ULevelSequence* SceneSequence = nullptr;
    const UMovieSceneCameraCutSection* ActiveCut =
        FindSceneCameraCut(Handover.SegmentIndex, Handover.Frame, &SceneSequence);
    if (!World || !ActiveCut || !SceneSequence)
    {
        return false;
    }

    // Resolve through the player first: locating on the sequence directly cannot
    // find Spawnable cameras or custom bindings, which silently left the previous
    // segment's camera live. The direct lookup stays as a fallback for the
    // pre-Begin-Play claim, when no player evaluation exists yet.
    TArray<UObject*> BoundObjects;
    if (Player)
    {
        BoundObjects = Player->GetBoundObjects(ActiveCut->GetCameraBindingID());
    }
    if (BoundObjects.IsEmpty())
    {
        TArray<UObject*, TInlineAllocator<1>> DirectObjects;
        SceneSequence->LocateBoundObjects(
            ActiveCut->GetCameraBindingID().GetGuid(),
            UE::UniversalObjectLocator::FResolveParams(World),
            nullptr,
            DirectObjects);
        BoundObjects.Append(DirectObjects);
    }

    for (UObject* Object : BoundObjects)
    {
        AActor* CameraActor = Cast<AActor>(Object);
        if (!CameraActor)
        {
            if (const UCameraComponent* CameraComponent = Cast<UCameraComponent>(Object))
            {
                CameraActor = CameraComponent->GetOwner();
            }
        }
        if (CameraActor)
        {
            return ClaimViewTarget(CameraActor, Handover.Blend, TEXT("SceneCameraCut"));
        }
    }

    const FString Label = Segments.IsValidIndex(Handover.SegmentIndex)
        ? Segments[Handover.SegmentIndex].Label.ToString()
        : FString(TEXT("<none>"));
    UE_LOG(LogInfinityStageTransport, Warning,
        TEXT("INFINITY_HANDOVER_UNBOUND_CUT segment=%d ('%s') frame=%d has a Camera Cut whose binding ")
        TEXT("resolves to no camera; the previous camera stays live."),
        Handover.SegmentIndex,
        *Label,
        Handover.Frame.Value);
    return false;
}

AInfinityStageCameraRig* UInfinityStageTransportController::FindCameraRigForPassage(const FGuid& PassageGuid)
{
    if (!PassageGuid.IsValid())
    {
        return nullptr;
    }
    if (const TWeakObjectPtr<AInfinityStageCameraRig>* Cached = CameraRigCache.Find(PassageGuid))
    {
        AInfinityStageCameraRig* Rig = Cached->Get();
        if (Rig && Rig->PassageActor && Rig->PassageActor->PassageGuid == PassageGuid)
        {
            return Rig;
        }
        CameraRigCache.Remove(PassageGuid);
    }

    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    // Walking the world happens once per Passage, not once per handover and
    // certainly not once per evaluated frame.
    for (TActorIterator<AInfinityStageCameraRig> It(World); It; ++It)
    {
        AInfinityStageCameraRig* Rig = *It;
        if (Rig && Rig->PassageActor && Rig->PassageActor->PassageGuid == PassageGuid)
        {
            CameraRigCache.Add(PassageGuid, Rig);
            return Rig;
        }
    }
    return nullptr;
}

bool UInfinityStageTransportController::ClaimViewTarget(
    AActor* Target,
    const FInfinityCameraHandoverBlend& Blend,
    const TCHAR* Reason)
{
    UWorld* World = GetWorld();
    if (!Target || !World || !World->IsGameWorld())
    {
        return false;
    }
    APlayerController* PlayerController = World->GetFirstPlayerController();
    if (!PlayerController)
    {
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_VIEW_TARGET_NO_CONTROLLER reason=%s target=%s"), Reason, *GetNameSafe(Target));
        return false;
    }

    const double Now = World->GetTimeSeconds();
    const bool bAlreadyLive = PlayerController->GetViewTarget() == Target;
    // A blend in flight leaves GetViewTarget() reporting the OUTGOING camera
    // until it completes, so an equality test on its own re-issues the claim on
    // every frame and restarts the blend forever - nothing would ever finish
    // blending. Remembering what was asked for is what makes a blend possible.
    const bool bBlendStillRunning = ClaimedBlendSeconds > 0.0f
        && ClaimedAtWorldSeconds >= 0.0
        && (Now - ClaimedAtWorldSeconds) < static_cast<double>(ClaimedBlendSeconds);
    if (ClaimedViewTarget.Get() == Target && (bAlreadyLive || bBlendStillRunning))
    {
        return true;
    }

    const float BlendSeconds = FMath::Max(0.0f, Blend.BlendSeconds);
    PlayerController->SetViewTargetWithBlend(
        Target,
        BlendSeconds,
        ToEngineBlendFunction(Blend.Function),
        FMath::Max(0.0f, Blend.Exponent),
        Blend.bLockOutgoing);

    // A cut has no in-between frames, so the renderer has to be told not to
    // carry temporal history across it or the incoming shot arrives smeared
    // with the outgoing one.
    if (BlendSeconds <= 0.0f && PlayerController->PlayerCameraManager)
    {
        PlayerController->PlayerCameraManager->SetGameCameraCutThisFrame();
    }

    ClaimedViewTarget = Target;
    ClaimedAtWorldSeconds = Now;
    ClaimedBlendSeconds = BlendSeconds;
    UE_LOG(LogInfinityStageTransport, Verbose,
        TEXT("INFINITY_VIEW_TARGET reason=%s target=%s blend=%.3fs"),
        Reason, *GetNameSafe(Target), BlendSeconds);
    return true;
}

void UInfinityStageTransportController::ReassertPassageClaimIfLost()
{
    // Only a Passage rig inside its own Passage is defended. Sequencer's Camera
    // Cut track owns the view inside any cue that has a sequence, and
    // re-claiming there would fight it and break every Scene with more than one
    // shot. A Passage has no cue sequence, so nothing else is entitled to the
    // view and reasserting is unambiguous.
    if (LastHandover.Source != EInfinityHandoverSource::PassageRig
        || !Segments.IsValidIndex(SelectedSegmentIndex)
        || Segments[SelectedSegmentIndex].Type != EInfinityCueType::WingPair)
    {
        return;
    }
    AActor* Claimed = ClaimedViewTarget.Get();
    UWorld* World = GetWorld();
    if (!Claimed || !World || !World->IsGameWorld())
    {
        return;
    }
    APlayerController* PlayerController = World->GetFirstPlayerController();
    if (!PlayerController || PlayerController->GetViewTarget() == Claimed)
    {
        return;
    }
    const double Now = World->GetTimeSeconds();
    if (ClaimedBlendSeconds > 0.0f
        && ClaimedAtWorldSeconds >= 0.0
        && (Now - ClaimedAtWorldSeconds) < static_cast<double>(ClaimedBlendSeconds))
    {
        return;
    }

    // Sequencer restores its pre-animated view target when a Camera Cut section
    // ends. The Passage token used to paper over that by re-claiming on every
    // evaluated frame; with one authority the transport has to notice instead.
    UE_LOG(LogInfinityStageTransport, Verbose,
        TEXT("INFINITY_VIEW_TARGET_RECLAIM expected=%s found=%s"),
        *GetNameSafe(Claimed), *GetNameSafe(PlayerController->GetViewTarget()));
    // Recovering a view that was taken away is never a dissolve.
    ClaimViewTarget(Claimed, FInfinityCameraHandoverBlend(), TEXT("Reassert"));
}

UInfinityStageTransportController* UInfinityStageTransportController::FindForWorld(const UWorld* World)
{
    if (!World)
    {
        return nullptr;
    }
    const TMap<FObjectKey, TWeakObjectPtr<UInfinityStageTransportController>>& Registry = GetTransportRegistry();
    const TWeakObjectPtr<UInfinityStageTransportController>* Found = Registry.Find(FObjectKey(World));
    return Found ? Found->Get() : nullptr;
}

void UInfinityStageTransportController::RegisterForWorld()
{
    const UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }
    TMap<FObjectKey, TWeakObjectPtr<UInfinityStageTransportController>>& Registry = GetTransportRegistry();
    for (auto It = Registry.CreateIterator(); It; ++It)
    {
        if (!It.Value().IsValid())
        {
            It.RemoveCurrent();
        }
    }
    Registry.Add(FObjectKey(World), this);
}

void UInfinityStageTransportController::UnregisterForWorld()
{
    TMap<FObjectKey, TWeakObjectPtr<UInfinityStageTransportController>>& Registry = GetTransportRegistry();
    for (auto It = Registry.CreateIterator(); It; ++It)
    {
        if (!It.Value().IsValid() || It.Value().Get() == this)
        {
            It.RemoveCurrent();
        }
    }
}

EInfinityTransportResult UInfinityStageTransportController::PlayToFrame(const FFrameNumber TargetFrame)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    JumpResettleState.bPending = false;
    // An externally clocked Scene may continue normally at 1x toward its next
    // boundary. Only reverse/seek/hold/rate-changing operations are unsafe.
    if (IsUnsafeExternalMove(TargetFrame) && TargetFrame < GetCurrentMasterFrame())
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }
    // Any play, forward or reverse, starts from a fresh rest; a forward boundary
    // play records its own after this returns.
    ClearTransportRests();

    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(TargetFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(TargetFrame);
    FMovieSceneSequencePlayToParams PlayToParams;
    PlayToParams.bExclusive = false;
    LastPlayToTargetForTests = TargetFrame;
    Player->PlayTo(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Play), PlayToParams);
    // Starting playback can restore Sequencer's pre-animated view target. Claim
    // the current shot after PlayTo as well, so a seek/Next followed by Play
    // cannot silently revert to the camera from the preceding Passage.
    const FFrameNumber CurrentFrame = GetCurrentMasterFrame();
    const int32 CurrentIndex = FindSegmentAtFrame(CurrentFrame);
    if (Segments.IsValidIndex(CurrentIndex))
    {
        ClaimSegmentCamera(CurrentIndex, CurrentFrame);
    }
    if (SeamDiagOn())
    {
        // A resume from Space/GO arrives here: PlayTo, then a re-claim of the
        // segment camera at the current frame (a hard cut unless already live).
        EmitSeamDiag(TEXT("playto"), FString::Printf(TEXT("|target=%d"), TargetFrame.Value));
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

bool UInfinityStageTransportController::ShouldLogSeamFrame(
    const double SecondsToNearestBoundary,
    const double WindowSeconds,
    const double WorldDeltaSeconds,
    const double StepCm,
    const double StepDeg,
    const double StepThresholdCm,
    const double StepThresholdDeg)
{
    return FMath::Abs(SecondsToNearestBoundary) <= FMath::Max(0.0, WindowSeconds)
        || WorldDeltaSeconds >= 0.25
        || StepCm > StepThresholdCm
        || StepDeg > StepThresholdDeg;
}

int32 UInfinityStageTransportController::FindRangeIndex(
    const TArray<TRange<FFrameNumber>>& Ranges, const FFrameNumber Frame)
{
    int32 Found = INDEX_NONE;
    for (int32 Index = 0; Index < Ranges.Num(); ++Index)
    {
        if (Ranges[Index].Contains(Frame))
        {
            Found = Index;
        }
    }
    return Found;
}

int32 UInfinityStageTransportController::FindMasterSectionSegment(const FFrameNumber Frame) const
{
    // The Master's OWN clock: which managed Passage/Scene section the player is
    // evaluating at this frame, mapped back to the compiled segment by GUID. The
    // rebuild writes these from the same compile (SequenceBuilderLibrary
    // MakeSectionRange), so a disagreement here means the Master is stale.
    const UMovieScene* MovieScene = Player && Player->GetSequence() ? Player->GetSequence()->GetMovieScene() : nullptr;
    if (!MovieScene)
    {
        return INDEX_NONE;
    }
    FGuid Found;
    if (const UMovieSceneInfinityPassageTrack* Track = MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>())
    {
        for (const UMovieSceneSection* Section : Track->GetAllSections())
        {
            const UMovieSceneInfinityPassageSection* Passage = Cast<UMovieSceneInfinityPassageSection>(Section);
            if (Passage && Passage->GetRange().Contains(Frame))
            {
                Found = Passage->PassageGuid;
            }
        }
    }
    if (const UMovieSceneInfinitySceneTrack* Track = MovieScene->FindTrack<UMovieSceneInfinitySceneTrack>())
    {
        for (const UMovieSceneSection* Section : Track->GetAllSections())
        {
            const UMovieSceneInfinitySceneSection* Scene = Cast<UMovieSceneInfinitySceneSection>(Section);
            if (Scene && Scene->GetRange().Contains(Frame))
            {
                Found = Scene->BlockGuid;
            }
        }
    }
    return Found.IsValid()
        ? Segments.IndexOfByPredicate([&Found](const FInfinityTransportSegment& Segment) { return Segment.SegmentGuid == Found; })
        : INDEX_NONE;
}

void UInfinityStageTransportController::EmitSeamDiag(const TCHAR* Event, const FString& Extra)
{
    const UWorld* World = GetWorld();
    const FFrameNumber Frame = GetCurrentMasterFrame();
    const double TickRate = ShowAsset && ShowAsset->TickResolution.IsValid() ? ShowAsset->TickResolution.AsDecimal() : 0.0;
    const int32 Compiled = FindSegmentAtFrame(Frame);
    const int32 ByMaster = FindMasterSectionSegment(Frame);

    FString View = TEXT("|vt=none");
    if (const APlayerController* PlayerController = World ? World->GetFirstPlayerController() : nullptr)
    {
        const APlayerCameraManager* CameraManager = PlayerController->PlayerCameraManager;
        const AActor* Target = PlayerController->GetViewTarget();
        double LookOffsetDeg = 0.0;
        if (Target)
        {
            // A dog / mouse look is written onto the camera COMPONENT, so its
            // angle from the actor is the look offset a hard cut would drop.
            if (const UCameraComponent* CameraComponent = Target->FindComponentByClass<UCameraComponent>())
            {
                LookOffsetDeg = FMath::RadiansToDegrees(
                    CameraComponent->GetComponentQuat().AngularDistance(Target->GetActorQuat()));
            }
        }
        View = FString::Printf(TEXT("|vt=%s|blend_to_go=%.3f|pov=%s|rot=%s|step_cm=%.2f|step_deg=%.2f|cam_vs_actor_deg=%.2f"),
            *GetNameSafe(Target),
            CameraManager ? CameraManager->BlendTimeToGo : -1.0f,
            CameraManager ? *CameraManager->GetCameraCacheView().Location.ToCompactString() : TEXT("-"),
            CameraManager ? *CameraManager->GetCameraCacheView().Rotation.ToCompactString() : TEXT("-"),
            SeamDiagLastStepCm, SeamDiagLastStepDeg, LookOffsetDeg);
        if (const AInfinityStageCameraRig* Rig = Cast<AInfinityStageCameraRig>(Target))
        {
            View += FString::Printf(TEXT("|rig_settle=%.3f|rig_bob_cm=%.2f|rig_walk_w=%.3f|rig_speed=%.1f"),
                Rig->CurrentCrossingSettleWeight, Rig->CurrentShadowCatCameraBobCm,
                Rig->CurrentShadowCatBobWalkWeight, Rig->CurrentShadowCatCameraSpeedCmPerSecond);
        }
    }

    FString Music = TEXT("|music=none");
    if (const UMovieScene* MovieScene = Player && Player->GetSequence() ? Player->GetSequence()->GetMovieScene() : nullptr)
    {
        if (const UMovieSceneInfinityAudioTrack* MusicTrack = MovieScene->FindTrack<UMovieSceneInfinityAudioTrack>())
        {
            for (const UMovieSceneSection* Section : MusicTrack->GetAllSections())
            {
                const UMovieSceneInfinityAudioSection* Audio = Cast<UMovieSceneInfinityAudioSection>(Section);
                if (Audio && Audio->GetRange().Contains(Frame) && Audio->HasStartFrame() && TickRate > 0.0)
                {
                    // Where the music SHOULD be by Master time; the real cursor is internal to Sequencer.
                    Music = FString::Printf(TEXT("|music_block=%s|music_expect_s=%.3f|music_eval_disabled=%d"),
                        *Audio->BlockGuid.ToString(EGuidFormats::Short),
                        (Audio->GetStartOffset().Value + (Frame - Audio->GetInclusiveStartFrame()).Value) / TickRate,
                        MusicTrack->IsEvalDisabled() ? 1 : 0);
                }
            }
        }
    }

    const FString Line = FString::Printf(
        TEXT("INFINITY_SEAM_DIAG|ev=%s|frame=%d|master_s=%.4f|seg=%d|seg_by_master=%d|world_s=%.4f|unpaused_s=%.4f|real_s=%.4f|dt=%.4f")
        TEXT("|playing=%d|rev=%d|rate=%.2f|ff=%d|rw=%d|hold=%d|claimed=%s|claimed_at_world_s=%.3f|claimed_blend=%.3f%s%s%s"),
        Event, Frame.Value, TickRate > 0.0 ? Frame.Value / TickRate : 0.0, Compiled, ByMaster,
        World ? World->GetTimeSeconds() : 0.0,
        World ? World->GetUnpausedTimeSeconds() : 0.0,
        World ? World->GetRealTimeSeconds() : 0.0,
        World ? World->GetDeltaSeconds() : 0.0,
        IsTransportPlaying() ? 1 : 0,
        Player && Player->IsReversed() ? 1 : 0,
        Player ? Player->GetPlayRate() : 0.0f,
        bFastForwardActive ? 1 : 0,
        bRewindActive ? 1 : 0,
        GoHoldState.IsActive() ? 1 : 0,
        *GetNameSafe(ClaimedViewTarget.Get()),
        ClaimedAtWorldSeconds,
        ClaimedBlendSeconds,
        *View, *Music, *Extra);
    UE_LOG(LogInfinityStageTransport, Display, TEXT("%s"), *Line);
    if (SeamDiagSinkForTests)
    {
        SeamDiagSinkForTests(Line);
    }
}

void UInfinityStageTransportController::TickSeamDiag(const FFrameNumber CurrentFrame, const float DeltaTime)
{
    const UWorld* World = GetWorld();
    const APlayerController* PlayerController = World ? World->GetFirstPlayerController() : nullptr;
    const APlayerCameraManager* CameraManager = PlayerController ? PlayerController->PlayerCameraManager : nullptr;
    SeamDiagLastStepCm = 0.0;
    SeamDiagLastStepDeg = 0.0;
    if (CameraManager)
    {
        // The cache is the last view the camera manager produced (the frame
        // actually rendered last), so consecutive ticks give the on-screen step.
        const FMinimalViewInfo& Pov = CameraManager->GetCameraCacheView();
        if (bSeamDiagHasPov)
        {
            SeamDiagLastStepCm = FVector::Distance(Pov.Location, SeamDiagLastPov);
            SeamDiagLastStepDeg = FMath::RadiansToDegrees(
                Pov.Rotation.Quaternion().AngularDistance(SeamDiagLastRot.Quaternion()));
        }
        SeamDiagLastPov = Pov.Location;
        SeamDiagLastRot = Pov.Rotation;
        bSeamDiagHasPov = true;
    }
    const double TickRate = ShowAsset && ShowAsset->TickResolution.IsValid() ? ShowAsset->TickResolution.AsDecimal() : 0.0;
    double Nearest = TNumericLimits<double>::Max();
    if (TickRate > 0.0)
    {
        for (const FInfinityTransportSegment& Segment : Segments)
        {
            Nearest = FMath::Min(Nearest, FMath::Abs((CurrentFrame - Segment.StartFrame).Value / TickRate));
        }
    }
    if (ShouldLogSeamFrame(Nearest, CVarInfinityStageSeamDiagWindow.GetValueOnGameThread(),
        DeltaTime, SeamDiagLastStepCm, SeamDiagLastStepDeg,
        CVarInfinityStageSeamDiagStepCm.GetValueOnGameThread(), CVarInfinityStageSeamDiagStepDeg.GetValueOnGameThread()))
    {
        EmitSeamDiag(TEXT("tick"), FString::Printf(TEXT("|to_boundary_s=%.3f|tick_dt=%.4f"), Nearest, DeltaTime));
    }
}

bool UInfinityStageTransportController::IsUnsafeExternalHold() const
{
    // Holding or rate-changing a segment whose sound a live musician owns is the
    // unsafe act, whatever the playhead reads. PauseTransport and Shuttle used to
    // call IsUnsafeExternalMove(GetCurrentMasterFrame()), whose final clause is
    // "TargetFrame != GetCurrentMasterFrame()" -- false by construction -- so the
    // guard ALWAYS passed and pause was permitted on a DeclaredUnpausable segment
    // while Right could not leave it. Exactly backwards from the stated intent.
    if (!bPerformanceMode)
    {
        return false;
    }
    const int32 CurrentIndex = FindSegmentAtFrame(GetCurrentMasterFrame());
    return Segments.IsValidIndex(CurrentIndex)
        && Segments[CurrentIndex].ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable;
}

bool UInfinityStageTransportController::IsUnsafeExternalMove(const FFrameNumber TargetFrame) const
{
    if (!bPerformanceMode)
    {
        return false;
    }
    const int32 CurrentIndex = FindSegmentAtFrame(GetCurrentMasterFrame());
    return Segments.IsValidIndex(CurrentIndex)
        && Segments[CurrentIndex].ExternalSound == EInfinityExternalSoundAuthority::DeclaredUnpausable
        && TargetFrame != GetCurrentMasterFrame();
}

void UInfinityStageTransportController::RefreshSelectedSegment()
{
    SelectedSegmentIndex = FindSegmentAtFrame(GetCurrentMasterFrame());
    bCoveredHandoffActive = IsCoveredHandoffActive(SelectedSegmentIndex, GetCurrentMasterFrame());
}

bool UInfinityStageTransportController::HandleVampPlayback(const FFrameNumber CurrentFrame)
{
    FFrameNumber LoopFrame = CurrentFrame;
    // Run-through, and fast-forward (a skim): a vamp plays once instead of looping.
    VampPlaybackState.bPlayOnce = bRunThrough || bFastForwardActive;
    const EInfinityVampPlaybackAction Action = VampPlaybackState.Tick(
        CurrentFrame,
        Player && Player->IsPlaying(),
        Player && Player->IsReversed(),
        Player ? Player->GetPlayRate() : 1.0f,
        VampRanges,
        LoopFrame);
    if (Action == EInfinityVampPlaybackAction::NormalizeToOne)
    {
        StopFastForwardPlayback();
        const FInfinityVampRange& Range = VampRanges[VampPlaybackState.ActiveVampIndex];
        const FFrameTime EndDisplayFrame = ShowAsset
            ? FFrameRate::TransformTime(FFrameTime(Range.EndFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
            : FFrameTime(Range.EndFrame);
        FMovieSceneSequencePlayToParams PlayToParams;
        PlayToParams.bExclusive = false;
        Player->PlayTo(
            FMovieSceneSequencePlaybackParams(EndDisplayFrame, EUpdatePositionMethod::Play),
            PlayToParams);
        UE_LOG(LogInfinityStageTransport, Log,
            TEXT("INFINITY_VAMP_NORMALIZE index=%d frame=%d"),
            VampPlaybackState.ActiveVampIndex, CurrentFrame.Value);
        return false;
    }
    if (Action != EInfinityVampPlaybackAction::LoopToStart
        || !VampRanges.IsValidIndex(VampPlaybackState.ActiveVampIndex))
    {
        return false;
    }

    const FInfinityVampRange& Range = VampRanges[VampPlaybackState.ActiveVampIndex];
    StopFastForwardPlayback();
    JumpResettleState.bPending = false;

    const FFrameTime LoopDisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(LoopFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(LoopFrame);
    Player->SetPlaybackPosition(
        FMovieSceneSequencePlaybackParams(LoopDisplayFrame, EUpdatePositionMethod::Jump));

    const FFrameTime EndDisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(Range.EndFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(Range.EndFrame);
    FMovieSceneSequencePlayToParams PlayToParams;
    PlayToParams.bExclusive = false;
    Player->PlayTo(
        FMovieSceneSequencePlaybackParams(EndDisplayFrame, EUpdatePositionMethod::Play),
        PlayToParams);
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_VAMP_LOOP index=%d count=%d from=%d to=%d"),
        VampPlaybackState.ActiveVampIndex,
        VampPlaybackState.LoopCount,
        CurrentFrame.Value,
        LoopFrame.Value);
    // Deliberately no ClaimSegmentCamera: the same Scene shot remains authoritative
    // across the seam, avoiding a camera cut/re-claim hitch.
    return true;
}

bool UInfinityStageTransportController::HandleGoHold(const FFrameNumber CurrentFrame)
{
    if (GoCues.IsEmpty() || !Player)
    {
        return false;
    }
    // Run-through passes unkept holds; a fast-forward skim passes every hold, kept ones too,
    // and the kept ones hold again once RIGHT is released.
    GoHoldState.bPassAll = bRunThrough || bFastForwardActive;
    GoHoldState.KeepNumbers = bFastForwardActive ? TSet<FString>() : TSet<FString>(RunThroughHoldGoNumbers);
    const int32 Hit = GoHoldState.Tick(
        CurrentFrame,
        Player->IsPlaying() && !Player->IsReversed(),
        GoCues);
    if (!GoCues.IsValidIndex(Hit))
    {
        return false;
    }
    const FInfinityGoCue& Cue = GoCues[Hit];
    if (IsUnsafeExternalHold())
    {
        // Belt and braces: BuildSegments already lists these as PASS.
        GoHoldState.Consume(Hit);
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_GO_HOLD_REFUSED_INTERLOCK number=%s frame=%d"), *Cue.Number, Cue.Frame.Value);
        return false;
    }
    StopFastForwardPlayback();
    Player->Pause();
    // Playback overshoots by up to a tick. Settle one display frame BEFORE the GO,
    // so the held picture is the pre-cue state, and re-evaluate it once more
    // after the jump (GeometryCache decode is async: a stale frame otherwise).
    const FFrameNumber SettleFrame = GoHoldState.SettleFrame(Cue);
    const FFrameTime HoldDisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(SettleFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(SettleFrame);
    Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(HoldDisplayFrame, EUpdatePositionMethod::Jump));
    JumpResettleState = {true, SettleFrame, 0.0f, 0};
    if (SeamDiagOn())
    {
        EmitSeamDiag(TEXT("go_hold"), FString::Printf(TEXT("|go=%s|settle=%d"), *Cue.Number, SettleFrame.Value));
    }
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_GO_HOLD number=%s frame=%d crossed_at=%d label='%s'"),
        *Cue.Number, Cue.Frame.Value, CurrentFrame.Value, *Cue.Label);
    return true;
}

bool UInfinityStageTransportController::ReleaseActiveHold()
{
    const int32 Index = GoHoldState.ActiveIndex;
    if (!Player || !GoHoldState.IsActive() || !GoCues.IsValidIndex(Index))
    {
        return false;
    }
    const EInfinityTransportResult Result = PlayForwardToBoundary();
    if (Result != EInfinityTransportResult::Succeeded)
    {
        // The key is consumed (RIGHT must never advance past a hold) but the hold stays.
        UE_LOG(LogInfinityStageTransport, Warning,
            TEXT("INFINITY_GO_REFUSED number=%s result=%d: still holding."),
            *GoCues[Index].Number, static_cast<int32>(Result));
        return true;
    }
    GoHoldState.Consume(Index);
    UE_LOG(LogInfinityStageTransport, Log,
        TEXT("INFINITY_GO number=%s frame=%d result=%d label='%s'"),
        *GoCues[Index].Number, GoCues[Index].Frame.Value, static_cast<int32>(Result), *GoCues[Index].Label);
    return true;
}

void UInfinityStageTransportController::SetVideoAudioMuted(const bool bMuted)
{
    bVideoAudioMuted = bMuted;
    SetManagedMasterAudioMuted(bFastForwardActive || bRewindActive);
}

void UInfinityStageTransportController::SetManagedMasterAudioMuted(const bool bRequestedMuted)
{
    // A Scene showing its fallback video keeps the Master's own sound muted whatever
    // fast-forward or rewind ask for (Cue Director CD4): no double sound.
    const bool bMuted = bRequestedMuted || bVideoAudioMuted;
    // Restore nested mutes first and unconditionally: EndPlay may arrive with no
    // Player, and the early return below must not strand a muted Scene or Choreo.
    if (!bMuted && !NestedAudioMutedForFastForward.IsEmpty())
    {
        for (const TPair<TWeakObjectPtr<UMovieSceneTrack>, bool>& Entry : NestedAudioMutedForFastForward)
        {
            if (UMovieSceneTrack* Track = Entry.Key.Get())
            {
#if WITH_EDITOR
                Track->SetLocalEvalDisabled(Entry.Value);
#else
                Track->SetEvalDisabled(Entry.Value);
#endif
                Track->MarkAsChanged();
            }
        }
        NestedAudioMutedForFastForward.Reset();
    }
    if (bMasterAudioMutedForFastForward == bMuted || !Player || !Player->GetSequence())
    {
        return;
    }
    UMovieScene* MovieScene = Player->GetSequence()->GetMovieScene();

    // Every other audio track in the Master and its nested sequences (Scene and
    // Choreography sound) is muted with it, through the same transient local flag,
    // and each is restored to exactly its own prior state when 1x resumes.
    if (bMuted)
    {
        NestedAudioMutedForFastForward.Reset();
        TSet<const UMovieSceneSequence*> Visited;
        TArray<UMovieSceneTrack*> AudioTracks;
        CollectAudioTracks(Player->GetSequence(), Visited, AudioTracks, 0);
        const UMovieSceneTrack* ManagedMusic = MovieScene ? MovieScene->FindTrack<UMovieSceneInfinityAudioTrack>() : nullptr;
        for (UMovieSceneTrack* Track : AudioTracks)
        {
            if (Track == ManagedMusic)
            {
                continue;
            }
#if WITH_EDITOR
            NestedAudioMutedForFastForward.Emplace(Track, Track->IsLocalEvalDisabled());
            Track->SetLocalEvalDisabled(true);
#else
            NestedAudioMutedForFastForward.Emplace(Track, Track->IsEvalDisabled(false));
            Track->SetEvalDisabled(true);
#endif
            Track->MarkAsChanged();
        }
    }

    UMovieSceneInfinityAudioTrack* MusicTrack = MovieScene
        ? MovieScene->FindTrack<UMovieSceneInfinityAudioTrack>()
        : nullptr;
    if (!MusicTrack)
    {
        bMasterAudioMutedForFastForward = bMuted;
        return;
    }

    if (bMuted)
    {
#if WITH_EDITOR
        bMasterAudioWasEvalDisabled = MusicTrack->IsLocalEvalDisabled();
        MusicTrack->SetLocalEvalDisabled(true);
#else
        bMasterAudioWasEvalDisabled = MusicTrack->IsEvalDisabled(false);
        MusicTrack->SetEvalDisabled(true);
#endif
    }
    else
    {
#if WITH_EDITOR
        MusicTrack->SetLocalEvalDisabled(bMasterAudioWasEvalDisabled);
#else
        MusicTrack->SetEvalDisabled(bMasterAudioWasEvalDisabled);
#endif
    }
    // The editor path uses its explicitly transient local mute. Packaged games
    // have no save path, so their runtime-only eval flag cannot alter the asset
    // on disk. Invalidate compiled evaluation so an already-playing managed
    // section stops or resumes on the next evaluation.
    MusicTrack->MarkAsChanged();
    MovieScene->MarkAsChanged();
    bMasterAudioMutedForFastForward = bMuted;
}

void UInfinityStageTransportController::StopFastForwardPlayback()
{
    // Ends any rate-changed playback: a fast-forward or a rewind.
    bFastForwardActive = false;
    bRewindActive = false;
    SetManagedMasterAudioMuted(false);
    if (Player)
    {
        Player->SetPlayRate(1.0f);
    }
}
