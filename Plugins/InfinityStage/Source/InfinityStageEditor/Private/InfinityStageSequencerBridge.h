#pragma once

#include "CoreMinimal.h"

class ISequencer;
class UMovieSceneSequence;

/**
 * Tracks open Sequencer instances so the Cue Desk playhead can drive them.
 *
 * The Cue Desk, Sequencer and PIE all evaluate the same absolute Master frame,
 * but each keeps its own playhead. This pushes one to the others rather than
 * introducing a second clock: the Master frame remains the only authority.
 *
 * Pushes are filtered by root sequence, so scrubbing the Cue Desk never moves a
 * Sequencer that has some unrelated asset open.
 */
class FInfinityStageSequencerBridge
{
public:
    static void Register();
    static void Unregister();

    /**
     * Moves every tracked Sequencer whose root sequence is ExpectedRoot to the
     * given root-time frame. Returns how many were moved.
     */
    static int32 PushRootFrame(const UMovieSceneSequence* ExpectedRoot, FFrameTime RootTime);

private:
    static void HandleSequencerCreated(TSharedRef<ISequencer> InSequencer);

    static TArray<TWeakPtr<ISequencer>> TrackedSequencers;
    static FDelegateHandle CreatedHandle;
    /** Guards against a push re-entering through Sequencer's own time change. */
    static bool bPushing;
};
