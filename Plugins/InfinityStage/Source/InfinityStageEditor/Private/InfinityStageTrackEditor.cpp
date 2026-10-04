#include "InfinityStageTrackEditor.h"

#include "Editor.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "ISequencer.h"
#include "MovieSceneInfinityAudioTrack.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MovieSceneInfinitySceneTrack.h"
#include "MovieSceneInfinityChoreoTrack.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "TrackEditors/SubTrackEditorBase.h"

namespace
{
/**
 * Managed Scene sections retain Infinity Stage ownership, but deliberately use
 * Unreal's exported subsequence section mixin for native painting, sequence
 * title, resizing and double-click navigation semantics.
 */
class FInfinityStageManagedSceneSection final : public TSubSectionMixin<>
{
public:
    FInfinityStageManagedSceneSection(
        const TSharedPtr<ISequencer>& InSequencer,
        UMovieSceneSubSection& InSection)
        : TSubSectionMixin(InSequencer, InSection)
    {
    }

    virtual bool IsReadOnly() const override
    {
        // The managed section's structure is rebuilt from the Cue Score, but it
        // must remain interactive so native subsequence double-click works.
        return false;
    }

    virtual void BuildSectionContextMenu(FMenuBuilder& MenuBuilder, const FGuid& ObjectBinding) override
    {
        ISequencerSection::BuildSectionContextMenu(MenuBuilder, ObjectBinding);

        TWeakPtr<ISequencer> WeakSequencer = GetSequencer();
        // Scene sections and Passage Choreography sections share this interface.
        TWeakObjectPtr<UMovieSceneSubSection> WeakSection(&GetSubSectionObject());
        TWeakObjectPtr<UMovieSceneSequence> WeakSequence(GetSubSectionObject().GetSequence());

        MenuBuilder.BeginSection(
            TEXT("InfinityStageSceneNavigation"),
            NSLOCTEXT("InfinityStage", "SceneNavigationSection", "Scene Sequence"));
        MenuBuilder.AddMenuEntry(
            NSLOCTEXT("InfinityStage", "FocusSceneSequence", "Open Scene Sequence"),
            NSLOCTEXT("InfinityStage", "FocusSceneSequenceTip", "Enter this Scene inside the current Sequencer. Use the breadcrumb/back button to return to the Master."),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateLambda([WeakSequencer, WeakSection]()
                {
                    const TSharedPtr<ISequencer> Sequencer = WeakSequencer.Pin();
                    if (Sequencer && WeakSection.IsValid())
                    {
                        Sequencer->FocusSequenceInstance(*WeakSection.Get());
                    }
                }),
                FCanExecuteAction::CreateLambda([WeakSequencer, WeakSection]()
                {
                    return WeakSequencer.IsValid() && WeakSection.IsValid()
                        && WeakSection->GetSequence() != nullptr;
                })));
        MenuBuilder.AddMenuEntry(
            NSLOCTEXT("InfinityStage", "OpenSceneSequenceSeparate", "Open in Separate Sequencer"),
            NSLOCTEXT("InfinityStage", "OpenSceneSequenceSeparateTip", "Open the assigned Scene Level Sequence in its own asset editor (the same result as Ctrl-double-click)."),
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateLambda([WeakSequence]()
                {
                    if (WeakSequence.IsValid() && GEditor)
                    {
                        GEditor->GetEditorSubsystem<UAssetEditorSubsystem>()->OpenEditorForAsset(WeakSequence.Get());
                    }
                }),
                FCanExecuteAction::CreateLambda([WeakSequence]() { return WeakSequence.IsValid(); })));
        MenuBuilder.EndSection();
    }
};
}

FInfinityStageTrackEditor::FInfinityStageTrackEditor(TSharedRef<ISequencer> InSequencer)
    : FMovieSceneTrackEditor(InSequencer)
{
}

TSharedRef<ISequencerTrackEditor> FInfinityStageTrackEditor::CreateTrackEditor(TSharedRef<ISequencer> InSequencer)
{
    return MakeShared<FInfinityStageTrackEditor>(InSequencer);
}

FText FInfinityStageTrackEditor::GetDisplayName() const
{
    return NSLOCTEXT("InfinityStage", "ManagedTrackEditorName", "Infinity Stage Managed Track");
}

bool FInfinityStageTrackEditor::SupportsType(const TSubclassOf<UMovieSceneTrack> TrackClass) const
{
    return TrackClass == UMovieSceneInfinityPassageTrack::StaticClass()
        || TrackClass == UMovieSceneInfinitySceneTrack::StaticClass()
        // Without an editor claiming it, opening a Master holding Choreography
        // sections crashed Sequencer (null SharedPtr, CueingB4 log, 4 Oct).
        || TrackClass == UMovieSceneInfinityChoreoTrack::StaticClass()
        || TrackClass == UMovieSceneInfinityAudioTrack::StaticClass();
}

TSharedRef<ISequencerSection> FInfinityStageTrackEditor::MakeSectionInterface(
    UMovieSceneSection& SectionObject,
    UMovieSceneTrack& Track,
    const FGuid ObjectBinding)
{
    if (UMovieSceneInfinitySceneSection* SceneSection = Cast<UMovieSceneInfinitySceneSection>(&SectionObject))
    {
        return MakeShared<FInfinityStageManagedSceneSection>(GetSequencer(), *SceneSection);
    }
    if (UMovieSceneInfinityChoreoSection* ChoreoSection = Cast<UMovieSceneInfinityChoreoSection>(&SectionObject))
    {
        return MakeShared<FInfinityStageManagedSceneSection>(GetSequencer(), *ChoreoSection);
    }
    return FMovieSceneTrackEditor::MakeSectionInterface(SectionObject, Track, ObjectBinding);
}
