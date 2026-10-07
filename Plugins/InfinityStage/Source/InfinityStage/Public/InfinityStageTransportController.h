#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InfinityStageTypes.h"
#include "InfinityStageTransportController.generated.h"

class AActor;
class AInfinityStageCameraRig;
class UInfinityStageShowAsset;
class UMovieSceneTrack;
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

    /** Active root Camera Cut starts, transformed once into absolute Master frames. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Shots")
    TArray<FFrameNumber> ShotStartFrames;

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

    /** Run-Through: no vamp arms, and an active one is released on the next tick,
     * so its range plays once and the show continues (nobody is there to release it). */
    bool bPlayOnce = false;

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

/**
 * One GO point: a marked frame labelled "GO <number> [HOLD|PASS] <label>" in a
 * Scene/Sequence cue's sequence or a Passage's Choreography, resolved to an
 * absolute Master frame. A HOLD stops playback on its frame until GO; a PASS is
 * listed for the operator but never stops the music. Unmarked: HOLD in Scenes,
 * PASS in Passages.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityGoCue
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    FFrameNumber Frame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    FString Number;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    FString Label;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    bool bHold = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    int32 SegmentIndex = INDEX_NONE;

    /** Its segment's first frame: a hold never settles before it (review N1). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    FFrameNumber SegmentStartFrame = 0;
};

namespace InfinityStageGoCues
{
/** Parses "GO <number> [HOLD|PASS] <label>". OutMode: -1 unmarked, 0 PASS, 1 HOLD. */
INFINITYSTAGE_API bool ParseMarkerLabel(const FString& Text, FString& OutNumber, FString& OutLabel, int32& OutMode);
}

/**
 * Pure hold arming/release. A HOLD arms only when forward playback crosses its
 * frame; navigation never arms one. A released hold re-arms once the playhead is
 * back before it, so "re-run this cue" stops at the same GO again.
 */
struct INFINITYSTAGE_API FInfinityGoHoldState
{
    int32 ActiveIndex = INDEX_NONE;

    /** Run-Through: every HOLD is crossed as a PASS (none arms). A hold that is
     * already active is left alone; whatever resumes play spends it as usual. */
    bool bPassAll = false;

    /** A hold settles this many ticks BEFORE its GO frame (one display frame), so
     * the held picture is the state before the cue, and the cue's content starts
     * when GO plays through the marker. */
    FFrameNumber SettleOffset = 0;

    /** One display frame before the GO, but never before the GO's own segment:
     * settling in the previous segment would show its last frame and camera, and
     * GO would then only play to that segment's end. */
    FFrameNumber SettleFrame(const FInfinityGoCue& Cue) const
    {
        const FFrameNumber Before = Cue.Frame - SettleOffset;
        const FFrameNumber Floor = Cue.SegmentStartFrame < Cue.Frame ? Cue.SegmentStartFrame : Cue.Frame;
        return Before < Floor ? Floor : Before;
    }

    void Reset();
    void OnNavigation(FFrameNumber TargetFrame);
    /** Returns the index of a hold to stop on now, or INDEX_NONE. */
    int32 Tick(FFrameNumber CurrentFrame, bool bPlayingForward, const TArray<FInfinityGoCue>& Cues);
    bool Release();
    /** Marks a cue spent whether or not it is the active hold (a navigation may already have cleared it). */
    void Consume(int32 Index);
    bool IsActive() const { return ActiveIndex != INDEX_NONE; }

private:
    TSet<int32> Released;
    FFrameNumber PreviousFrame = 0;
    bool bHasPreviousFrame = false;
};

/**
 * Where the transport last came to rest by its own doing, so a key pressed there
 * can be read the way the operator sees it (Gary, 5 Oct).
 *
 * A segment's EndFrame is exclusive and equals the next segment's StartFrame, so
 * the frame alone cannot say whether the show is "at the end of K" (playback
 * stopped there) or "at the start of K+1" (a jump landed there). The rest is only
 * believed while the player is stopped on exactly that frame; anything else makes
 * it stale, and every jump, scrub, reverse or play clears it outright.
 */
struct INFINITYSTAGE_API FInfinityTransportRest
{
    int32 SegmentIndex = INDEX_NONE;
    FFrameNumber Frame = 0;

    void Set(const int32 InSegmentIndex, const FFrameNumber InFrame)
    {
        SegmentIndex = InSegmentIndex;
        Frame = InFrame;
    }
    void Reset() { SegmentIndex = INDEX_NONE; Frame = 0; }
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

    /**
     * What Advance (RIGHT, Cue Desk Next) does when it lands on a Sequence cue -
     * the Opening, an Interaction, the Closing.
     *
     * False (rehearsal default, Gary 5 Oct: "the transitions [are] their own cue
     * moment that I can move to with transport and examine"): the transition holds
     * on its first frame, like a Passage. The next RIGHT, or Space, plays it to its
     * boundary, stopping at its GO HOLD markers; Left goes back.
     *
     * True: the pre-5-Oct behaviour. Landing plays the Sequence at once, so a
     * post-Scene curtain interstitial lowers, makes its covered handoff and rises
     * on a single key press. Use it for performance.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Cues")
    bool bAutoPlaySequenceOnAdvance = false;

    /**
     * Run-Through, for unattended recordings (Gary, 7 Oct): play once at the start
     * and the show runs to the end of the Closing.
     *
     * When on: every GO HOLD behaves as a PASS; a vamp plays its range once and
     * continues; Space/GO plays to the end of the Show rather than to the current
     * segment's end, so Scenes do not hold at their end and each Sequence cue plays
     * as it is reached; Advance plays whatever it lands on. Off: no change at all.
     * The live-performer interlock is unaffected (it only refuses holds, rate
     * changes and backward moves; run-through only plays forward at 1x).
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport")
    bool bRunThrough = false;

    /** A shorter Right Arrow press keeps the existing advance-to-next-cue action. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "0.0", Units = "s"))
    float HoldThresholdSeconds = 0.30f;

    /** Continuous Master playback rate while Right Arrow is held past the threshold. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "1.0", UIMax = "8.0"))
    float FastForwardRate = 4.0f;

    /** Continuous reverse Master playback rate while Left Arrow is held past the
     * threshold (Gary, 6 Oct: "Left button hold should take us backwards the same
     * way right takes us fastforward"). A shorter Left press keeps Previous. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "1.0", UIMax = "8.0"))
    float RewindRate = 4.0f;

    /** LEFT restarts the current shot after this many display frames; before
     * that it steps to the preceding shot. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Viewport Input",
        meta = (ClampMin = "0"))
    int32 ShotRestartGraceDisplayFrames = 12;

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

    /** Operator advance to the next cue, as the operator sees it: at the end of a
     * segment that playback stopped on, the next cue is the one starting on this
     * frame, not the one after it. A landed Sequence holds (armed) unless
     * bAutoPlaySequenceOnAdvance; Advance at an armed Sequence plays it. A Scene
     * plays on landing only with bAutoPlaySceneAfterPassage. A Passage holds. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult AdvanceToNextSegment();

    /** The segment the transport is held at the END of (playback stopped on its
     * exclusive end frame), or -1. Stale the moment anything moves the playhead. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 GetHeldAtEndSegmentIndex() const;

    /** The Sequence segment Advance landed on and is holding at its first frame,
     * waiting for RIGHT or Space to play it, or -1. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    int32 GetArmedSequenceSegmentIndex() const;

    /** Pure: the segment a rest still applies to - only while stopped on its exact frame. */
    static int32 ResolveRestSegment(const FInfinityTransportRest& Rest, FFrameNumber CurrentFrame, bool bPlaying)
    {
        return Rest.SegmentIndex != INDEX_NONE && !bPlaying && CurrentFrame == Rest.Frame
            ? Rest.SegmentIndex
            : INDEX_NONE;
    }

    /** Pure: Advance/Next target. Held at the end of K -> K+1 (the cue starting on
     * this frame); anywhere else -> the segment after the one under the playhead. */
    static int32 ResolveAdvanceTargetIndex(int32 SelectedIndex, int32 HeldAtEndIndex)
    {
        return HeldAtEndIndex != INDEX_NONE ? HeldAtEndIndex + 1 : SelectedIndex + 1;
    }

    /** Pure: Previous target. Held at the end of K -> K's start (the cue the
     * operator is looking at); past a segment's start -> its start; else the one before. */
    static int32 ResolvePreviousTargetIndex(int32 SelectedIndex, bool bPastSelectedStart, int32 HeldAtEndIndex)
    {
        if (HeldAtEndIndex != INDEX_NONE)
        {
            return HeldAtEndIndex;
        }
        return bPastSelectedStart ? SelectedIndex : SelectedIndex - 1;
    }

    /** Pure: whether landing on a segment of this type by Advance starts playing it. */
    static bool AutoPlaysOnAdvance(EInfinityCueType TargetType, bool bAutoPlaySequence, bool bAutoPlayScene)
    {
        return (TargetType == EInfinityCueType::Sequence && bAutoPlaySequence)
            || (TargetType == EInfinityCueType::Scene && bAutoPlayScene);
    }

    /** Pure: AutoPlaysOnAdvance, except that Run-Through plays every landing. */
    static bool PlaysOnAdvanceLanding(EInfinityCueType TargetType, bool bAutoPlaySequence, bool bAutoPlayScene, bool bInRunThrough)
    {
        return bInRunThrough || AutoPlaysOnAdvance(TargetType, bAutoPlaySequence, bAutoPlayScene);
    }

    /** Steps to the next root Camera Cut in a Scene, then falls through to Advance. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult StepShotForward();

    /** Plays continuously to the end of the Master at FastForwardRate. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult BeginFastForward();

    /** Restores 1x and either resumes or holds according to the pre-hold state. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult EndFastForward(bool bWasPlaying);

    /**
     * Plays the Master BACKWARDS at RewindRate toward the Show start, muted like
     * fast-forward, and every seam still claims its camera on the way (the tick
     * handles reverse crossings). The same interlocks as fast-forward: refused
     * (UnsafeExternalClock, result=4) inside a DeclaredUnpausable segment in
     * performance mode, and it never rewinds INTO one - it stops at that segment's
     * end instead. NoSegment when there is nothing behind the playhead.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult BeginRewind();

    /** Restores 1x forward. bWasPlaying: play on to the boundary; else hold where the rewind got to. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult EndRewind(bool bWasPlaying);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Transport")
    bool IsRewindActive() const { return bRewindActive; }

    /** Pure: where a rewind from FromSegmentIndex stops - the Show start, or in
     * performance mode the end of the nearest earlier DeclaredUnpausable segment. */
    static FFrameNumber ResolveRewindTargetFrame(
        const TArray<FInfinityTransportSegment>& InSegments, int32 FromSegmentIndex, bool bInPerformanceMode);

    /** RIGHT inside an armed vamp consumes that vamp and continues to this segment's end at 1x. */
    bool ReleaseActiveVamp();

    /** Every GO point in show order (absolute Master frames). Rebuilt with the segments. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Transport|Cues")
    TArray<FInfinityGoCue> GoCues;

    /** Performance safety: Space never pauses, it only fires GO or resumes;
     * pause from the Cue Desk. Off by default so rehearsal keeps Space = pause. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Transport|Cues")
    bool bSpaceNeverPauses = false;

    /** GO at a HOLD: plays on and consumes it. False when no hold is active. */
    bool ReleaseActiveHold();

    /** Ending a fast-forward resumes only if it was playing or vamping, and never
     * while a GO hold has stopped the show (a hold reached under fast-forward stays held). */
    static bool ResumesAfterFastForward(bool bWasPlaying, bool bVampActive, bool bHoldActive)
    {
        return !bHoldActive && (bWasPlaying || bVampActive);
    }

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    bool IsHoldActive() const { return GoHoldState.IsActive(); }

    /** Index into GoCues of the hold the show is waiting on, or -1. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    int32 GetActiveHoldIndex() const { return GoHoldState.ActiveIndex; }

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult JumpToPreviousSegment();

    /** Restarts/steps root Camera Cuts in a Scene, then falls through to Previous. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Transport")
    EInfinityTransportResult StepShotBack();

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

    /**
     * Seam diagnostic (6 Oct, Gary: "arriving at the hangar the camera switch
     * sometimes SNAPS - seems to happen after pausing play"). Off by default.
     * Console: InfinityStage.SeamDiag 1. Logs INFINITY_SEAM_DIAG lines on
     * LogInfinityStageTransport at every pause, resume, play-to, jump, scrub,
     * GO hold, fast-forward/rewind end and camera claim, and every tick within
     * InfinityStage.SeamDiag.WindowSeconds of a segment boundary, on a hitch
     * (world dt >= 0.25 s) or on a view step (> StepCm / StepDeg). Each line
     * carries both clocks (Master frame and seconds; world, unpaused and real
     * seconds; world dt), the segment by the COMPILED table and by the Master's
     * OWN section ranges, the player state, the view target and blend, the
     * transport's claim bookkeeping, the rendered POV and its step, the live
     * camera component's offset from its actor (a dog/mouse look shows here),
     * the rig's settle weight / bob / distance, and the expected position in the
     * managed music section (by Master time; the real audio cursor is not
     * readable from here).
     */
    static bool ShouldLogSeamFrame(
        double SecondsToNearestBoundary, double WindowSeconds,
        double WorldDeltaSeconds, double StepCm, double StepDeg,
        double StepThresholdCm, double StepThresholdDeg);

    /** Pure: the index of the half-open range containing Frame, or INDEX_NONE (last match wins). */
    static int32 FindRangeIndex(const TArray<TRange<FFrameNumber>>& Ranges, FFrameNumber Frame);

    /** TEST SEAM: receives every seam-diagnostic line. */
    TFunction<void(const FString& Line)> SeamDiagSinkForTests;

    /** TEST ONLY: exercises the ordered tick tail without boundary detection. */
    void RunTickTailForTests(FFrameNumber CurrentFrame, float DeltaTime)
    {
        RunTickTail(CurrentFrame, DeltaTime);
    }

    /** TEST ONLY: the last absolute Master frame supplied to PlayToFrame. */
    TOptional<FFrameNumber> GetLastPlayToTargetForTests() const
    {
        return LastPlayToTargetForTests;
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

    FInfinityGoHoldState GoHoldState;

    /** Set by a forward boundary play: the segment whose end it will stop on. */
    FInfinityTransportRest BoundaryEndRest;

    /** Set when Advance lands on a Sequence and holds it instead of playing it. */
    FInfinityTransportRest ArmedSequenceRest;

    /** Every jump, scrub, reverse and play forgets how the transport came to rest. */
    void ClearTransportRests();

    /** The segment the operator regards as current: K when held at K's end. */
    int32 GetOperatorCurrentSegmentIndex() const;

    /** Nested audio tracks muted for fast-forward, with their prior local mute. */
    TArray<TPair<TWeakObjectPtr<UMovieSceneTrack>, bool>> NestedAudioMutedForFastForward;

    bool bFastForwardActive = false;
    bool bRewindActive = false;
    bool bMasterAudioMutedForFastForward = false;
    bool bMasterAudioWasEvalDisabled = false;

    TOptional<FFrameNumber> LastPlayToTargetForTests;

    /** What ClaimViewTarget last asked for, and when, so a running blend is not
     * restarted every frame by a repeat of the same request. */
    TWeakObjectPtr<AActor> ClaimedViewTarget;
    double ClaimedAtWorldSeconds = -1.0;
    float ClaimedBlendSeconds = 0.0f;

    TMap<FGuid, TWeakObjectPtr<AInfinityStageCameraRig>> CameraRigCache;

    /** Seam diagnostic state (InfinityStage.SeamDiag). */
    bool bSeamDiagHasPov = false;
    FVector SeamDiagLastPov = FVector::ZeroVector;
    FRotator SeamDiagLastRot = FRotator::ZeroRotator;
    double SeamDiagLastStepCm = 0.0;
    double SeamDiagLastStepDeg = 0.0;
    void EmitSeamDiag(const TCHAR* Event, const FString& Extra);
    void TickSeamDiag(FFrameNumber CurrentFrame, float DeltaTime);
    /** The segment index whose Master Passage/Scene section range contains Frame (the Master's own clock). */
    int32 FindMasterSectionSegment(FFrameNumber Frame) const;

    EInfinityTransportResult JumpToSegment(int32 SegmentIndex, bool bToEnd);
    EInfinityTransportResult JumpToMasterFrame(int32 SegmentIndex, FFrameNumber TargetFrame, bool bKeepPlaying);
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
    bool HandleGoHold(FFrameNumber CurrentFrame);
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
