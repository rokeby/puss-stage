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
    bool bPlaying = false;
    bool bHold = false;
    bool bRunThrough = false;
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

/** Same as the keys: Back = LEFT, PlayPause = Space, Go = RIGHT (GO at a hold), lines = PageUp/Down. */
INFINITYSTAGE_API void Command(UWorld* World, ECommand Command);

/** "m:ss.s". */
INFINITYSTAGE_API FString Clock(double Seconds);
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
};
