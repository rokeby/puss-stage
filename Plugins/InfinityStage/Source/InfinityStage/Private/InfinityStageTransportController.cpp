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
#include "MovieSceneSequencePlayer.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "UObject/ObjectKey.h"
#include "UniversalObjectLocatorResolveParams.h"

DEFINE_LOG_CATEGORY(LogInfinityStageTransport);

namespace
{
constexpr TCHAR HiddenChangeoverMarker[] = TEXT("InfinityStage.HiddenChangeover");

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

void UInfinityStageTransportController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    UnregisterForWorld();
    CameraRigCache.Reset();
    ClaimedViewTarget.Reset();
    ClaimedAtWorldSeconds = -1.0;
    ClaimedBlendSeconds = 0.0f;
    Super::EndPlay(EndPlayReason);
}

void UInfinityStageTransportController::BeginDestroy()
{
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
    ReassertPassageClaimIfLost();
}

bool UInfinityStageTransportController::BuildSegments(UInfinityStageShowAsset* InShowAsset)
{
    ShowAsset = InShowAsset;
    Segments.Reset();
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

    return !Segments.IsEmpty();
}

bool UInfinityStageTransportController::InitializeTransport(ULevelSequencePlayer* InPlayer, UInfinityStageShowAsset* InShowAsset)
{
    Player = InPlayer;
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
    return PlayToFrame(Segments[StopIndex].EndFrame);
}

int32 UInfinityStageTransportController::GetForwardStopSegmentIndex(const int32 FromSegmentIndex) const
{
    if (!Segments.IsValidIndex(FromSegmentIndex))
    {
        return INDEX_NONE;
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
    return JumpToSegment(SelectedSegmentIndex, false);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToCurrentEnd()
{
    RefreshSelectedSegment();
    return JumpToSegment(SelectedSegmentIndex, true);
}

EInfinityTransportResult UInfinityStageTransportController::JumpToNextSegment()
{
    RefreshSelectedSegment();
    return JumpToSegment(SelectedSegmentIndex + 1, false);
}

EInfinityTransportResult UInfinityStageTransportController::AdvanceToNextSegment()
{
    RefreshSelectedSegment();

    const int32 TargetIndex = SelectedSegmentIndex + 1;
    const EInfinityTransportResult CueResult = JumpToSegment(TargetIndex, false);
    if (CueResult != EInfinityTransportResult::Succeeded)
    {
        return CueResult;
    }

    // Sequence cues are authored transitions, not static operator holds. In
    // particular, post-Scene curtain interstitials must lower, perform their
    // covered handoff, and rise without requiring a second Play command.
    if (Segments.IsValidIndex(TargetIndex)
        && (Segments[TargetIndex].Type == EInfinityCueType::Sequence
            || (bAutoPlaySceneAfterPassage && Segments[TargetIndex].Type == EInfinityCueType::Scene)))
    {
        return PlayForwardToBoundary();
    }
    return LastResult = EInfinityTransportResult::Succeeded;
}

EInfinityTransportResult UInfinityStageTransportController::JumpToPreviousSegment()
{
    RefreshSelectedSegment();
    const FFrameNumber Current = GetCurrentMasterFrame();
    const int32 TargetIndex = Segments.IsValidIndex(SelectedSegmentIndex) && Current > Segments[SelectedSegmentIndex].StartFrame
        ? SelectedSegmentIndex
        : SelectedSegmentIndex - 1;
    return JumpToSegment(TargetIndex, false);
}

EInfinityTransportResult UInfinityStageTransportController::PauseTransport()
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    if (IsUnsafeExternalHold())
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }
    Player->Pause();
    return LastResult = EInfinityTransportResult::Succeeded;
}

EInfinityTransportResult UInfinityStageTransportController::ResumeForward()
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
    Player->SetPlayRate(FMath::Max(0.001f, FMath::Abs(Player->GetPlayRate())));
    Player->Play();
    return LastResult = EInfinityTransportResult::Succeeded;
}

EInfinityTransportResult UInfinityStageTransportController::Shuttle(const float Rate)
{
    if (!Player)
    {
        return LastResult = EInfinityTransportResult::NoPlayer;
    }
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
    SelectedSegmentIndex = TargetIndex;
    bCoveredHandoffActive = IsCoveredHandoffActive(TargetIndex, TargetFrame);
    ClaimSegmentCamera(TargetIndex, TargetFrame);
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
    if (!Segments[SegmentIndex].bReady)
    {
        return LastResult = EInfinityTransportResult::NotReady;
    }
    const FFrameNumber Target = bToEnd ? Segments[SegmentIndex].EndFrame : Segments[SegmentIndex].StartFrame;
    if (IsUnsafeExternalMove(Target))
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }

    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(Target), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(Target);
    Player->Pause();
    Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(DisplayFrame, EUpdatePositionMethod::Jump));
    SelectedSegmentIndex = SegmentIndex;
    bCoveredHandoffActive = IsCoveredHandoffActive(SegmentIndex, Target);
    ClaimSegmentCamera(SegmentIndex, Target);
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
    ApplyHandover(Handover);
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
        if (Cut && Cut->GetRange().Contains(LocalFrame))
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
            if (Cut && (!ActiveCut || Cut->GetExclusiveEndFrame() > ActiveCut->GetExclusiveEndFrame()))
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
    // An externally clocked Scene may continue normally at 1x toward its next
    // boundary. Only reverse/seek/hold/rate-changing operations are unsafe.
    if (IsUnsafeExternalMove(TargetFrame) && TargetFrame < GetCurrentMasterFrame())
    {
        return LastResult = EInfinityTransportResult::UnsafeExternalClock;
    }

    const FFrameTime DisplayFrame = ShowAsset
        ? FFrameRate::TransformTime(FFrameTime(TargetFrame), ShowAsset->TickResolution, ShowAsset->DisplayRate)
        : FFrameTime(TargetFrame);
    FMovieSceneSequencePlayToParams PlayToParams;
    PlayToParams.bExclusive = false;
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
    return LastResult = EInfinityTransportResult::Succeeded;
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
