#include "InfinityStageTransportController.h"

#include "EngineUtils.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequencePlayer.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneSequencePlayer.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "UniversalObjectLocatorResolveParams.h"

namespace
{
constexpr TCHAR HiddenChangeoverMarker[] = TEXT("InfinityStage.HiddenChangeover");

FFrameNumber ResolveCoveredHandoffOffset(
    const UInfinityStageShowAsset& Show,
    const FInfinityShowCue& Cue)
{
    const FFrameNumber Fallback(
        FMath::Max(0, Cue.Scene.CurtainEntryTransitionFrames.Value)
        + FMath::Max(0, Cue.Scene.CurtainHoldFrames.Value));
    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid() || !Show.TickResolution.IsValid())
    {
        return Fallback;
    }

    for (const FMovieSceneMarkedFrame& MarkedFrame : MovieScene->GetMarkedFrames())
    {
        if (MarkedFrame.Label.Equals(HiddenChangeoverMarker, ESearchCase::IgnoreCase))
        {
            return FFrameRate::TransformTime(
                FFrameTime(MarkedFrame.FrameNumber),
                MovieScene->GetTickResolution(),
                Show.TickResolution).RoundToFrame();
        }
    }
    return Fallback;
}
}

UInfinityStageTransportController::UInfinityStageTransportController()
{
    // The camera claim used to happen only on init, scrub and jump, so playing
    // across a Passage/Scene boundary never handed the view over: the previous
    // segment's camera stayed live for the whole next segment. One component
    // tick watches for that crossing. Wings remain tick-free.
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
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
    if (FrameSegment == INDEX_NONE
        || (FrameSegment == SelectedSegmentIndex && bCoveredHandoff == bCoveredHandoffActive))
    {
        return;
    }
    // A claim happens at segment boundaries and at the deterministic covered
    // threshold inside an interstitial. Reverse playback crosses it as well.
    SelectedSegmentIndex = FrameSegment;
    bCoveredHandoffActive = bCoveredHandoff;
    ClaimSegmentCamera(Segments[FrameSegment], CurrentFrame);
}

bool UInfinityStageTransportController::InitializeTransport(ULevelSequencePlayer* InPlayer, UInfinityStageShowAsset* InShowAsset)
{
    Player = InPlayer;
    ShowAsset = InShowAsset;
    Segments.Reset();
    SelectedSegmentIndex = INDEX_NONE;
    bCoveredHandoffActive = false;
    LastResult = EInfinityTransportResult::NoPlayer;

    if (!Player || !ShowAsset)
    {
        return false;
    }

    ShowAsset->EnsureStableIds();
    ShowAsset->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    if (Compiled.HasErrors())
    {
        LastResult = EInfinityTransportResult::NoSegment;
        return false;
    }

    for (const FInfinityCompiledSegment& CompiledSegment : Compiled.Segments)
    {
        FInfinityTransportSegment& Segment = Segments.AddDefaulted_GetRef();
        Segment.SegmentGuid = CompiledSegment.SegmentGuid;
        Segment.Type = CompiledSegment.Type;
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
        }
        else if (ShowAsset->Cues.IsValidIndex(CompiledSegment.FirstCueIndex))
        {
            const FInfinityShowCue& Cue = ShowAsset->Cues[CompiledSegment.FirstCueIndex];
            Segment.Label = Cue.Label;
            Segment.bRetainPreviousCamera = Cue.Scene.bRetainPreviousCamera;
            Segment.bRevealNextPassageWhenCovered =
                Cue.Scene.CurtainMode == EInfinityCurtainCueMode::PostSceneInterstitial
                && Cue.Scene.bRevealNextPassageWhenCovered;
            const FFrameNumber HandoffOffset = ResolveCoveredHandoffOffset(*ShowAsset, Cue);
            const int32 SegmentLength =
                FMath::Max(0, (Segment.EndFrame - Segment.StartFrame).Value);
            Segment.CoveredHandoffFrame = Segment.StartFrame + FFrameNumber(
                FMath::Clamp(HandoffOffset.Value, 0, SegmentLength));
        }
    }

    RefreshSelectedSegment();
    LastResult = Segments.IsEmpty() ? EInfinityTransportResult::NoSegment : EInfinityTransportResult::Succeeded;
    if (LastResult == EInfinityTransportResult::Succeeded
        && Segments.IsValidIndex(SelectedSegmentIndex))
    {
        // Claim the correct view target during PIE initialization even before
        // the first evaluated Sequencer frame. This makes both auto-play and a
        // held-at-frame-zero rehearsal begin through the Passage camera.
        ClaimSegmentCamera(Segments[SelectedSegmentIndex], GetCurrentMasterFrame());
    }
    return LastResult == EInfinityTransportResult::Succeeded;
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
    if (IsUnsafeExternalMove(GetCurrentMasterFrame()))
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
    if (IsUnsafeExternalMove(GetCurrentMasterFrame()) && (!FMath::IsNearlyEqual(Rate, 1.0f)))
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
    ClaimSegmentCamera(Segments[TargetIndex], TargetFrame);
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
    ClaimSegmentCamera(Segments[SegmentIndex], Target);
    return LastResult = EInfinityTransportResult::Succeeded;
}

void UInfinityStageTransportController::ClaimSegmentCamera(
    const FInfinityTransportSegment& Segment,
    const FFrameNumber MasterFrame) const
{
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld())
    {
        return;
    }

    // A sequence-authored Camera Cut is explicit creative intent and always
    // wins over retained-camera and covered-handoff defaults.
    if (Segment.Type != EInfinityCueType::WingPair
        && TryClaimSceneSequenceCamera(Segment, MasterFrame))
    {
        return;
    }

    // An opening reveal has no preceding Scene to retain. Establish the next
    // Passage's frozen opening view before revealing it, while still allowing
    // an explicitly authored Camera Cut above to take priority.
    const FInfinityShowCue* Cue = ShowAsset ? ShowAsset->Cues.FindByPredicate(
        [&Segment](const FInfinityShowCue& Candidate)
        { return Candidate.CueGuid == Segment.SegmentGuid; }) : nullptr;
    if (Cue && Cue->Scene.CurtainMode == EInfinityCurtainCueMode::OpeningReveal)
    {
        const int32 OpeningIndex = Segments.IndexOfByPredicate(
            [&Segment](const FInfinityTransportSegment& Candidate)
            { return Candidate.SegmentGuid == Segment.SegmentGuid; });
        for (int32 NextIndex = OpeningIndex + 1; NextIndex < Segments.Num(); ++NextIndex)
        {
            if (Segments[NextIndex].Type == EInfinityCueType::WingPair)
            {
                ClaimSegmentCamera(Segments[NextIndex], Segments[NextIndex].StartFrame);
                return;
            }
        }
    }

    if (Segment.bRetainPreviousCamera)
    {
        const int32 SegmentIndex = Segments.IndexOfByPredicate([&Segment](const FInfinityTransportSegment& Candidate)
        {
            return Candidate.SegmentGuid == Segment.SegmentGuid;
        });
        if (IsCoveredHandoffActive(SegmentIndex, MasterFrame))
        {
            for (int32 NextIndex = SegmentIndex + 1; NextIndex < Segments.Num(); ++NextIndex)
            {
                if (Segments[NextIndex].Type == EInfinityCueType::WingPair)
                {
                    ClaimSegmentCamera(Segments[NextIndex], Segments[NextIndex].StartFrame);
                    return;
                }
            }
        }
        if (Segments.IsValidIndex(SegmentIndex - 1))
        {
            const FInfinityTransportSegment& Previous = Segments[SegmentIndex - 1];
            ClaimSegmentCamera(Previous, Previous.EndFrame);
        }
        return;
    }

    if (Segment.Type == EInfinityCueType::WingPair)
    {
        for (TActorIterator<AInfinityStageCameraRig> It(World); It; ++It)
        {
            AInfinityStageCameraRig* CameraRig = *It;
            if (CameraRig && CameraRig->PassageActor
                && CameraRig->PassageActor->PassageGuid == Segment.SegmentGuid)
            {
                CameraRig->EvaluateAtMasterFrame(MasterFrame);
                if (APlayerController* PlayerController = World->GetFirstPlayerController())
                {
                    PlayerController->SetViewTarget(CameraRig);
                }
                break;
            }
        }
    }
}

bool UInfinityStageTransportController::TryClaimSceneSequenceCamera(
    const FInfinityTransportSegment& Segment,
    const FFrameNumber MasterFrame) const
{
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld() || !ShowAsset)
    {
        return false;
    }
    const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate([&Segment](const FInfinityShowCue& Candidate)
    {
        return Candidate.CueGuid == Segment.SegmentGuid;
    });
    ULevelSequence* SceneSequence = Cue ? Cue->Scene.Sequence.LoadSynchronous() : nullptr;
    UMovieScene* MovieScene = SceneSequence ? SceneSequence->GetMovieScene() : nullptr;
    UMovieSceneCameraCutTrack* CutTrack = MovieScene
        ? Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack())
        : nullptr;
    UE_LOG(LogTemp, Verbose, TEXT("INFINITY_CAMERA_CLAIM scene=%s frame=%d start=%d sequence=%s cuttrack=%s"),
        *Segment.Label.ToString(), MasterFrame.Value, Segment.StartFrame.Value, *GetNameSafe(SceneSequence), *GetNameSafe(CutTrack));
    if (!SceneSequence || !MovieScene || !CutTrack)
    {
        return false;
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
        UE_LOG(LogTemp, Verbose, TEXT("INFINITY_CAMERA_CLAIM no active cut local=%d"), LocalFrame.Value);
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
    UE_LOG(LogTemp, Verbose, TEXT("INFINITY_CAMERA_CLAIM resolved=%d local=%d"), BoundObjects.Num(), LocalFrame.Value);
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
            if (APlayerController* PlayerController = World->GetFirstPlayerController())
            {
                PlayerController->SetViewTarget(CameraActor);
                UE_LOG(LogTemp, Verbose, TEXT("INFINITY_CAMERA_CLAIM target=%s"), *GetNameSafe(CameraActor));
            }
            return true;
        }
    }
    return false;
}

bool UInfinityStageTransportController::IsCoveredHandoffActive(
    const int32 SegmentIndex,
    const FFrameNumber MasterFrame) const
{
    return Segments.IsValidIndex(SegmentIndex)
        && Segments[SegmentIndex].bRevealNextPassageWhenCovered
        && MasterFrame >= Segments[SegmentIndex].CoveredHandoffFrame;
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
        ClaimSegmentCamera(Segments[CurrentIndex], CurrentFrame);
    }
    return LastResult = EInfinityTransportResult::Succeeded;
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
