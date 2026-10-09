#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class UWorld;
struct FInfinityTransportSegment;
struct FInfinityGoCue;

/**
 * Rehearsal bar (Gary, 8 Oct): "clarity around what cue we are on, cue timing and show timing,
 * notes on that cue, play pause etc buttons". One widget, shown at the bottom of the Cue Desk
 * and (toggled with B) at the bottom of the PIE viewport. It reads the running show; its
 * buttons do exactly what the keys do.
 */
struct INFINITYSTAGE_API FInfinityRehearsalState
{
    bool bHasShow = false;
    FString Cue;            // "4/19  Scene 1 - External Sound  [sheet cue 4]"
    double CueSeconds = 0.0;
    double CueLengthSeconds = 0.0;
    double ShowSeconds = 0.0;
    double ShowLengthSeconds = 0.0;
    FString NextStop;       // "GO at end of Scene 1 in 0:45.2" or "runs to show end"
    FString Notes;          // the cue sheet row's notes and department actions
    FString Script;         // the current script line
    FString Dog;            // current dog direction, including carried state
    FString NextDog;        // next row that changes the dog direction
    bool bPlaying = false;
    bool bHold = false;
    bool bRunThrough = false;
    /** 0..1 position in the current segment (the scrub slider). */
    float CueFraction = 0.0f;
};

struct INFINITYSTAGE_API FInfinityNextStop
{
    bool bValid = false;
    FFrameNumber Frame = 0;
    /** "end of <segment>", "GO <n> <label>" or "show end". */
    FString Label;
};

namespace InfinityStageRehearsal
{
/**
 * Pure: where the show will next wait for GO from Now. Run-through: the next ticked "stop after"
 * segment's end, or a kept GO hold, whichever comes first (the show end otherwise). Without
 * run-through: the current segment's end, or an earlier GO hold.
 */
INFINITYSTAGE_API FInfinityNextStop NextStop(
    const TArray<FInfinityTransportSegment>& Segments,
    const TArray<FInfinityGoCue>& GoCues,
    FFrameNumber Now,
    bool bRunThrough,
    const TArray<FGuid>& StopAfter,
    const TArray<FString>& HoldGoNumbers);

/** Everything the bar shows, for the world's running show (false when there is none). */
INFINITYSTAGE_API bool Gather(UWorld* World, FInfinityRehearsalState& Out);

enum class ECommand : uint8 { Back, PlayPause, Go, PreviousLine, NextLine };

/** Same as the keys: Back = LEFT, PlayPause = Space, Go = RIGHT (GO at a hold), lines = "," and ".". */
INFINITYSTAGE_API void Command(UWorld* World, ECommand Command);

/** Surtitle rehearsal controls (Gary 9 Oct: "part of the cue director interface to be adjustable and rehearsable").
 *  They call UInfinityStageSurtitleSubsystem; nothing here writes the Show or the level. */
enum class ESurtitleAction : uint8 { Previous, Next, StampIn, StampOut, InEarlier, InLater, OutEarlier, OutLater };

/** What one action calls: StepLine(Delta), StampAtPlayhead(bOut) or Nudge(bOut, Seconds). Pure, for tests. */
struct FInfinitySurtitleCall
{
    enum class EKind : uint8 { Step, Stamp, Nudge };
    EKind Kind = EKind::Step;
    int32 Delta = 0;
    bool bOut = false;
    double Seconds = 0.0;
};
inline constexpr double SurtitleNudgeSeconds = 0.25;
INFINITYSTAGE_API FInfinitySurtitleCall PlanSurtitleAction(ESurtitleAction Action);

/** Runs the action on the world's surtitle subsystem; returns the line it now describes, or why it refused. */
INFINITYSTAGE_API FString SurtitleAction(UWorld* World, ESurtitleAction Action);

/** "S5 row 12 [T3k] 1:14.00-1:25.00 West: ...", or empty when the world has no surtitle subsystem. */
INFINITYSTAGE_API FString DescribeSurtitle(UWorld* World);

/** "m:ss.s". */
INFINITYSTAGE_API FString Clock(double Seconds);

/** Scrub within the current segment: 0 = its start, 1 = its end (one frame short). Rehearsal use. */
INFINITYSTAGE_API void ScrubCurrentSegment(UWorld* World, float Fraction);

/** Jump to the start of segment Index (0-based, show order). */
INFINITYSTAGE_API void JumpToSegmentStart(UWorld* World, int32 Index);

/** Segment labels in show order, for the jump menu. */
INFINITYSTAGE_API TArray<FString> SegmentLabels(UWorld* World);

/** Pure: the Master frame for a fraction of a segment, clamped one frame inside its end. */
INFINITYSTAGE_API FFrameNumber FrameAtFraction(FFrameNumber Start, FFrameNumber End, float Fraction);
}

class INFINITYSTAGE_API SInfinityStageRehearsalBar final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageRehearsalBar) {}
        /** The world whose show the bar follows (PIE, or the game). Polled every paint. */
        SLATE_ARGUMENT(TFunction<UWorld*()>, World)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

private:
    const FInfinityRehearsalState& State() const;

    TFunction<UWorld*()> GetWorldFn;
    mutable FInfinityRehearsalState Cached;
    mutable uint64 CachedFrame = MAX_uint64;
    /** The last surtitle action's result (a refusal stays on screen until the next action). */
    FString SurtitleMessage;
};
