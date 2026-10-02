#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InfinityStageTypes.h"
#include "InfinityStageTransportController.generated.h"

class AActor;
class AInfinityStageCameraRig;
class UInfinityStageShowAsset;
class ULevelSequence;
class ULevelSequencePlayer;
class UMovieSceneCameraCutSection;

/**
 * Every camera handover the show performs is reported on this category,
 * including the ones that resolve to nothing. A seam that hands over to no
 * camera is a Warning, never silence.
 */
INFINITYSTAGE_API DECLARE_LOG_CATEGORY_EXTERN(LogInfinityStageTransport, Log, All);

UENUM(BlueprintType)
enum class EInfinityTransportResult : uint8
{
    Succeeded,
    NoPlayer,
    NoSegment,
    NotReady,
    UnsafeExternalClock
};

/** Pure input decisions for the viewport's tap-or-hold Right Arrow binding. */
enum class EInfinityHoldRightAction : uint8
{
    None,
    Advance,
    BeginFastForward,
    EndFastForwardPlaying,
    EndFastForwardHeld
};

/**
 * Converts key timing into transport intentions without requiring a world or
 * sequence player. The attempted hold is consumed even when the transport
 * refuses it, so an interlock refusal can never turn into a jump on release.
 */
struct INFINITYSTAGE_API FInfinityHoldRightState
{
    bool bPressed = false;
    bool bThresholdReached = false;
    bool bFastForwardActive = false;
    bool bWasPlaying = false;
    float HeldSeconds = 0.0f;

    void Press(bool bInWasPlaying);
    EInfinityHoldRightAction Tick(float DeltaSeconds, float HoldThresholdSeconds);
    void ResolveFastForwardStart(EInfinityTransportResult Result);
    EInfinityHoldRightAction Release();
    void Reset();
};

/** Mirrors the engine's view-target blend shapes, without the internal ones. */
UENUM(BlueprintType)
enum class EInfinityHandoverBlendFunction : uint8
{
    Linear,
    Cubic,
    EaseIn,
    EaseOut,
    EaseInOut
};

/**
 * How the view crosses one seam.
 *
 * A handover is a theatrical choice - a cut, a dissolve, or a match - so the
 * system has to be able to express all three. Zero seconds is a cut, and a cut
 * also resets the renderer's temporal history so the incoming shot does not
 * arrive smeared with the outgoing one.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityCameraHandoverBlend
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handover",
        meta = (ClampMin = "0.0", UIMax = "5.0", Units = "s"))
    float BlendSeconds = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handover",
        meta = (EditCondition = "BlendSeconds > 0.0"))
    EInfinityHandoverBlendFunction Function = EInfinityHandoverBlendFunction::EaseInOut;

    /** Ease strength. Linear and Cubic ignore it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handover",
        meta = (ClampMin = "0.0", UIMax = "8.0", EditCondition = "BlendSeconds > 0.0"))
    float Exponent = 2.0f;

    /** Freeze the outgoing camera for the blend instead of letting it keep travelling. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Handover",
        meta = (EditCondition = "BlendSeconds > 0.0"))
    bool bLockOutgoing = false;

    bool IsCut() const { return BlendSeconds <= 0.0f; }
};

/** Which rule finally supplied the camera for a segment. */
UENUM(BlueprintType)
enum class EInfinityHandoverSource : uint8
{
    /** Nothing supplied one. */
    None,
    /** An authored Camera Cut inside the cue's own Level Sequence. */
    SceneCameraCut,
    /** The travelling camera rig of a Passage. */
    PassageRig
};

/**
 * Why a handover ended where it did.
 *
 * Everything other than Resolved used to be a silent return, which is why a
 * wrong camera could stay live for a whole segment without a line in the log.
 */
UENUM(BlueprintType)
enum class EInfinityHandoverResolution : uint8
{
    Resolved,
    /** The requested segment index is not in the compiled table. */
    NoSuchSegment,
    /** The segment retains the previous camera but nothing precedes it. */
    RetainWithoutPrevious,
    /** A covered changeover or opening reveal found no Passage to reveal. */
    NoFollowingPassage,
    /** A Scene or Sequence cue with no Camera Cut, no retain and no Passage of its own. */
    NoRuleForSegment,
    /** The retain chain exceeded the segment count - a malformed compile. */
    ChainTooLong
};

/** Where a covered changeover's timing actually came from. */
UENUM(BlueprintType)
enum class EInfinityCoveredHandoffSource : uint8
{
    /** An InfinityStage.HiddenChangeover marked frame in the cue's sequence. */
    SequenceMarker,
    /** Entry + hold: no sequence is assigned to the cue. */
    FallbackNoSequenceAssigned,
    /** Entry + hold: a sequence is assigned but failed to load. */
    FallbackSequenceFailedToLoad,
    /** Entry + hold: the sequence or the Show has an unusable tick resolution. */
    FallbackInvalidTickResolution,
    /** Entry + hold: the sequence loaded and carries no marker. */
    FallbackNoMarker,
    /** Not a covered changeover. */
    NotApplicable
};

/**
 * One resolved handover: which segment supplies the camera, at which Master
 * frame it should be sampled, by which rule, and how the view gets there.
 *
 * Resolution is deliberately separate from effect. This is computed without a
 * world, a player controller or a rendered frame, so every handover rule in the
 * show is unit-testable.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityCameraHandover
{
    GENERATED_BODY()

    /** Segment whose camera is claimed. Not necessarily the one asked about. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    int32 SegmentIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    int32 RequestedSegmentIndex = INDEX_NONE;

    /** Master frame at which the claimed camera is evaluated. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    FFrameNumber Frame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    EInfinityHandoverSource Source = EInfinityHandoverSource::None;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    EInfinityHandoverResolution Resolution = EInfinityHandoverResolution::NoSuchSegment;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    FInfinityCameraHandoverBlend Blend;

    /** True when the audience cannot see this seam because the curtain is in. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Handover")
    bool bCovered = false;

    bool IsResolved() const { return Resolution == EInfinityHandoverResolution::Resolved; }
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityTransportSegment
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FGuid SegmentGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FText Label;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityCueType Type = EInfinityCueType::WingPair;

    /** Index of this segment's first cue in the Show, so no handover has to
     * search the cue list by GUID while the playhead is crossing a seam. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    int32 CueIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber StartFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber EndFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityExternalSoundAuthority ExternalSound = EInfinityExternalSoundAuthority::None;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityCurtainCueMode CurtainMode = EInfinityCurtainCueMode::None;

    /** Re-claim the preceding segment camera instead of selecting a new view. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    bool bRetainPreviousCamera = false;

    /** Switch to the following Passage once this interstitial is fully covered. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    bool bRevealNextPassageWhenCovered = false;

    /** Absolute Master frame at which the covered handoff becomes active.
     * Sequence cues can author this with an InfinityStage.HiddenChangeover
     * marked frame; entry + hold timing is the fallback. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    FFrameNumber CoveredHandoffFrame = 0;

    /** Which of those two it actually was. A marker and a failed asset load used
     * to be indistinguishable, which presents as intermittent timing. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityCoveredHandoffSource CoveredHandoffSource = EInfinityCoveredHandoffSource::NotApplicable;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bReady = true;
};

/** One authored, absolute-Master interval that repeats until the operator releases it. */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityVampRange
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Vamp")
    FFrameNumber StartFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Vamp")
    FFrameNumber EndFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Vamp")
    int32 SegmentIndex = INDEX_NONE;

    bool IsValid() const { return SegmentIndex != INDEX_NONE && EndFrame > StartFrame; }
};

enum class EInfinityVampPlaybackAction : uint8
{
    None,
    NormalizeToOne,
    LoopToStart
};

/**
 * Pure vamp arming/release decisions. Navigation resets observation without
 * arming; only 1x forward playback through VampStart arms a loop. Reverse
 * playback into a released range re-arms it.
 */
struct INFINITYSTAGE_API FInfinityVampPlaybackState
{
    int32 ActiveVampIndex = INDEX_NONE;
    int32 LoopCount = 0;

    void Reset();
    void OnNavigation(FFrameNumber TargetFrame);
    EInfinityVampPlaybackAction Tick(
        FFrameNumber CurrentFrame,
        bool bPlaying,
        bool bReversed,
        float PlayRate,
        const TArray<FInfinityVampRange>& Ranges,
        FFrameNumber& OutLoopFrame);
    bool Release(FFrameNumber CurrentFrame, const TArray<FInfinityVampRange>& Ranges);
    bool IsActive() const { return ActiveVampIndex != INDEX_NONE; }

private:
    TSet<int32> ReleasedVamps;
    FFrameNumber PreviousFrame = 0;
    bool bHasPreviousFrame = false;
};

/** Pending one-shot re-evaluation of a frame after an operator jump. */
struct INFINITYSTAGE_API FInfinityJumpResettle
{
    bool bPending = false;
    FFrameNumber Frame = 0;
    float Elapsed = 0.0f;
    int32 Ticks = 0;
};

UCLASS(ClassGroup = "Infinity Stage", BlueprintType, meta = (BlueprintSpawnableComponent))
class INFINITYSTAGE_API UInfinityStageTransportController : public UActorComponent
{
    GENERATED_BODY()

public:
    UInfinityStageTransportController();

    /** Watches for the playhead crossing a segment boundary during playback. */
    virtual void TickComponent(
        float DeltaTime,
        ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void BeginDestroy() override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    TArray<FInfinityTransportSegment> Segments;

    /** Marker pairs compiled from cue sequences into absolute Master frames. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Vamp")
    TArray<FInfinityVampRange> VampRanges;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bPerformanceMode = true;

    /** Continue a playing Passage into its immediately following cinematic Scene.
     * The Scene still holds at its end; this never starts the next Passage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bAutoPlaySceneAfterPassage = false;

    /** A shorter Right Arrow press keeps the existing advance-to-next-cue action. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "0.0", Units = "s"))
    float HoldThresholdSeconds = 0.30f;

    /** Continuous Master playback rate while Right Arrow is held past the threshold. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "1.0", UIMax = "8.0"))
    float FastForwardRate = 4.0f;

    /**
     * Delay before one same-frame re-evaluation after a paused jump or scrub.
     * Geometry Caches decode asynchronously and otherwise keep drawing their
     * previous sample while held (Gary, 30 Sep: "takes ages to load up a slot").
     * Zero disables the re-evaluation.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport",
        meta = (ClampMin = "0.0", Units = "s"))
    float JumpResettleSeconds = 0.1f;

    /** Number of delayed same-frame jump re-evaluations fired by this instance. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Transport")
    int32 JumpResettleCount = 0;

    /**
     * How the view arrives at a Passage's travelling camera - a Scene or a
     * mechanism handing back to the route.
     *
     * The Master Level Sequence still owns time and camera placement; this only
     * describes the crossing. Set BlendSeconds to zero for a cut.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Handover")
    FInfinityCameraHandoverBlend PassageEntryBlend;

    /** How the view arrives at an authored Scene shot. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Handover")
    FInfinityCameraHandoverBlend SceneEntryBlend;

    /**
     * A handover the audience cannot see is always a cut.
     *
     * There is nothing on screen to dissolve behind a closed curtain, and a
     * blend still running when the curtain lifts reads as an unexplained drift.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Handover")
    bool bCutWhenCovered = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    int32 SelectedSegmentIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport")
    EInfinityTransportResult LastResult = EInfinityTransportResult::NoPlayer;

    /** The last handover this controller resolved, successful or not. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Handover")
    FInfinityCameraHandover LastHandover;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    bool InitializeTransport(ULevelSequencePlayer* InPlayer, UInfinityStageShowAsset* InShowAsset);

    /**
     * Compiles the Show into the segment table without binding a player.
     *
     * Playback goes through InitializeTransport, which also binds the player and
     * claims the opening camera. This exists so the handover rules can be
     * resolved and asserted without a world, a viewport or PIE.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    bool BuildSegments(UInfinityStageShowAsset* InShowAsset);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayForwardToBoundary();

    /** Resolves the operator stop without moving or evaluating the player. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 GetForwardStopSegmentIndex(int32 FromSegmentIndex) const;

    /**
     * Plays forward through segment boundaries to the end of the Show, so a
     * Passage-to-Scene handover can be watched continuously. This bypasses all
     * operator stops, including the hold after a cinematic Scene.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayForwardThroughBoundaries();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PlayReverseToBoundary();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToCurrentStart();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToCurrentEnd();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToNextSegment();

    /** Operator advance: play a sequence/interstitial, or a Scene when automatic
     * Scene playback is enabled. A new Passage remains held at its first frame. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult AdvanceToNextSegment();

    /** Plays continuously to the end of the Master at FastForwardRate. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult BeginFastForward();

    /** Restores 1x and either resumes or holds according to the pre-hold state. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult EndFastForward(bool bWasPlaying);

    /** RIGHT inside an armed vamp consumes that vamp and continues to this segment's end at 1x. */
    bool ReleaseActiveVamp();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToPreviousSegment();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult PauseTransport();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult ResumeForward();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult Shuttle(float Rate);

    /** Absolute-frame rehearsal/editor scrub on the one root Sequence Player.
     * Performance external-clock and readiness rules still apply. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult ScrubToMasterFrame(FFrameNumber TargetFrame);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    FFrameNumber GetCurrentMasterFrame() const;

    /** Advances a pending same-frame resettle without requiring a world or player. */
    static bool StepJumpResettle(
        FInfinityJumpResettle& State,
        FFrameNumber CurrentFrame,
        bool bPlaying,
        float DeltaSeconds,
        float SettleSeconds,
        int32 MinTicks);

    /**
     * TEST SEAM: runs immediately after the resettle evaluation and before the
     * Passage camera reassert. Automation uses it to emulate Sequencer restoring
     * its pre-animated view target during SetPlaybackPosition.
     */
    TFunction<void()> JumpResettlePostEvaluationTestSeam;

    /** TEST ONLY: exercises the ordered tick tail without boundary detection. */
    void RunTickTailForTests(FFrameNumber CurrentFrame, float DeltaTime)
    {
        RunTickTail(CurrentFrame, DeltaTime);
    }

    /** True while the Master player is running, so a toggle can tell play from pause. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    bool IsTransportPlaying() const;

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 FindSegmentAtFrame(FFrameNumber Frame) const;

    /** First WingPair segment after the given index, or INDEX_NONE. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 FindNextPassageSegment(int32 FromSegmentIndex) const;

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    bool IsCoveredHandoffActive(int32 SegmentIndex, FFrameNumber MasterFrame) const;

    /**
     * Which camera the show uses for a segment at a frame, and how it gets
     * there. Pure: no world, no player controller, no evaluation.
     */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport|Handover")
    FInfinityCameraHandover ResolveHandover(int32 SegmentIndex, FFrameNumber MasterFrame) const;

    /** Cached rig lookup by Passage GUID, so a handover never walks the world. */
    AInfinityStageCameraRig* FindCameraRigForPassage(const FGuid& PassageGuid);

    /**
     * The transport driving a world, or null.
     *
     * Sequence evaluation uses this to hand the view over through the one
     * authority instead of setting a view target of its own.
     */
    static UInfinityStageTransportController* FindForWorld(const UWorld* World);

    /**
     * The single point through which every Infinity Stage view-target change
     * passes.
     *
     * Re-issuing a target that is already live, or that a blend is already on
     * its way to, restarts the blend from the current pose - so a claim that
     * would change nothing is dropped instead. Returns true when the requested
     * target is live or becoming live.
     */
    bool ClaimViewTarget(AActor* Target, const FInfinityCameraHandoverBlend& Blend, const TCHAR* Reason);

private:
    UPROPERTY(Transient)
    TObjectPtr<ULevelSequencePlayer> Player;

    UPROPERTY(Transient)
    TObjectPtr<UInfinityStageShowAsset> ShowAsset;

    bool bCoveredHandoffActive = false;

    FInfinityJumpResettle JumpResettleState;

    FInfinityVampPlaybackState VampPlaybackState;

    bool bFastForwardActive = false;
    bool bMasterAudioMutedForFastForward = false;
    bool bMasterAudioWasEvalDisabled = false;

    /** What ClaimViewTarget last asked for, and when, so a running blend is not
     * restarted every frame by a repeat of the same request. */
    TWeakObjectPtr<AActor> ClaimedViewTarget;
    double ClaimedAtWorldSeconds = -1.0;
    float ClaimedBlendSeconds = 0.0f;

    TMap<FGuid, TWeakObjectPtr<AInfinityStageCameraRig>> CameraRigCache;

    EInfinityTransportResult JumpToSegment(int32 SegmentIndex, bool bToEnd);
    EInfinityTransportResult PlayToFrame(FFrameNumber TargetFrame);

    /** Resolves the handover for a segment and applies it to the view. */
    void ClaimSegmentCamera(int32 SegmentIndex, FFrameNumber MasterFrame);
    bool ApplyHandover(const FInfinityCameraHandover& Handover);

    /** The Camera Cut section live in a cue's own sequence at a Master frame. */
    const UMovieSceneCameraCutSection* FindSceneCameraCut(
        int32 SegmentIndex,
        FFrameNumber MasterFrame,
        ULevelSequence** OutSequence = nullptr) const;
    bool ClaimSceneCameraCut(const FInfinityCameraHandover& Handover);

    /** Restores a Passage claim that Sequencer's Camera Cut restore took away. */
    void ReassertPassageClaimIfLost();

    /** Resettles the held frame before repairing any Passage view-target steal. */
    void RunTickTail(FFrameNumber CurrentFrame, float DeltaTime);

    /** Returns true when this tick looped and no camera boundary work should run. */
    bool HandleVampPlayback(FFrameNumber CurrentFrame);
    void SetManagedMasterAudioMuted(bool bMuted);
    void StopFastForwardPlayback();

    bool IsUnsafeExternalMove(FFrameNumber TargetFrame) const;
    /** True when holding or rate-changing would disturb a segment whose sound a live
     * performer owns. Unlike IsUnsafeExternalMove this takes no target frame, because
     * a hold has no target -- passing the current frame in made the test vacuous. */
    bool IsUnsafeExternalHold() const;
    void RefreshSelectedSegment();

    void RegisterForWorld();
    void UnregisterForWorld();
};
