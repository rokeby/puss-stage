#pragma once

#include "MovieSceneTrackEditor.h"

/**
 * Minimal Sequencer editor for plugin-owned Master tracks.
 *
 * These tracks are generated from the Cue Score, so the editor deliberately exposes standard
 * section selection/inspection without adding duplicate authoring controls to Sequencer.
 */
class FInfinityStageTrackEditor final : public FMovieSceneTrackEditor
{
public:
    explicit FInfinityStageTrackEditor(TSharedRef<ISequencer> InSequencer);

    static TSharedRef<ISequencerTrackEditor> CreateTrackEditor(TSharedRef<ISequencer> InSequencer);

    virtual FText GetDisplayName() const override;
    virtual bool SupportsType(TSubclassOf<UMovieSceneTrack> TrackClass) const override;
    virtual TSharedRef<ISequencerSection> MakeSectionInterface(
        UMovieSceneSection& SectionObject,
        UMovieSceneTrack& Track,
        FGuid ObjectBinding) override;
};
