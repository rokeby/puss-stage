#pragma once

#include "CoreMinimal.h"

class AActor;
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

    /**
     * What the open Sequencers animate on this Show attachment (by tag), through
     * any root or nested sequence. Returns true when any of them binds it. The
     * light capture uses this so a keyed value is never written into the Show as
     * authored, while hand edits of un-keyed settings still are.
     */
    static bool CollectAnimatedInOpenSequencers(
        AActor* Actor, FName AttachmentTag, TSet<FName>& OutProperties, bool& bOutTransform);

private:
    static void HandleSequencerCreated(TSharedRef<ISequencer> InSequencer);

    static TArray<TWeakPtr<ISequencer>> TrackedSequencers;
    static FDelegateHandle CreatedHandle;
    /** Guards against a push re-entering through Sequencer's own time change. */
    static bool bPushing;
};
