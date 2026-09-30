#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneSequence.h"
#include "Sections/MovieSceneSubSection.h"
#include "Variants/MovieSceneTimeWarpVariant.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** Scene 4's hangar sequence: v1 the fold, v2 (29 Sep) the rise; Scene 4 plays one of them. */
bool IsScene4Hangar(const UMovieSceneSequence& Sequence)
{
    return Sequence.GetName() == TEXT("LS_S4_HangarFold") || Sequence.GetName() == TEXT("LS_S4_HangarRise");
}

/** The fix to print for a known nested section, so a failure costs nobody twenty minutes. */
FString FixForNestedSection(const UMovieSceneSequence& Parent, const UMovieSceneSequence& Child)
{
    if (IsScene4Hangar(Child))
    {
        return TEXT("run Saved/CodexStructure/scene4_fold_nest.py (it keeps the sequence Scene 4 plays, resizes the section, "
                    "the Scene and its camera cuts from the Time Scale, then rebuilds the Master)");
    }
    if (IsScene4Hangar(Parent))
    {
        return TEXT("the Scene 4 hangar sequence hosts this section (Look & camera's score): keep it inside that "
                    "sequence's playback range, then run Saved/CodexStructure/scene4_fold_nest.py");
    }
    return TEXT("extend the parent's playback end or trim the section; for a Scene, then rebuild the Master "
                "(RebuildManagedMaster) and check InfinityStage.Editor.SavedMasterMatchesShow");
}

/** Walks the Master's nested sequences once each and checks every active sub-section against its parent. */
struct FNestedSequenceFitCheck
{
    FAutomationTestBase& Test;
    TSet<const UMovieSceneSequence*> Visited;
    int32 SectionsChecked = 0;

    explicit FNestedSequenceFitCheck(FAutomationTestBase& InTest) : Test(InTest) {}

    void Walk(const UMovieSceneSequence& Parent)
    {
        if (Visited.Contains(&Parent))
        {
            return;
        }
        Visited.Add(&Parent);
        const UMovieScene* Scene = Parent.GetMovieScene();
        if (!Scene)
        {
            return;
        }
        const FFrameRate Ticks = Scene->GetTickResolution();
        const double PlaybackEndSeconds = Ticks.AsSeconds(FFrameTime(Scene->GetPlaybackRange().GetUpperBoundValue()));
        const double OneFrameSeconds = Scene->GetDisplayRate().AsInterval() + 1.0e-3;
        for (const UMovieSceneTrack* Track : Scene->GetTracks())
        {
            if (!Track)
            {
                continue;
            }
            for (const UMovieSceneSection* Section : Track->GetAllSections())
            {
                const UMovieSceneSubSection* Sub = Cast<UMovieSceneSubSection>(Section);
                const UMovieSceneSequence* Child = Sub ? Sub->GetSequence() : nullptr;
                if (!Child || !Sub->IsActive() || !Sub->HasStartFrame() || !Sub->HasEndFrame())
                {
                    continue;
                }
                ++SectionsChecked;
                const double StartSeconds = Ticks.AsSeconds(FFrameTime(Sub->GetInclusiveStartFrame()));
                const double EndSeconds = Ticks.AsSeconds(FFrameTime(Sub->GetExclusiveEndFrame()));

                // Always: a section must end inside its parent's playback range, or its content is cut
                // (Scene 1 lost 195.8 s of Gary's content this way until 29 Sep).
                Test.TestTrue(
                    FString::Printf(TEXT("%s: %s ends at %.2f s, inside the parent's playback end %.2f s. If not: %s"),
                        *Parent.GetName(), *Child->GetName(), EndSeconds, PlaybackEndSeconds,
                        *FixForNestedSection(Parent, *Child)),
                    EndSeconds <= PlaybackEndSeconds + OneFrameSeconds);

                // Only when retimed (Time Scale != 1): the scaled content must fit its section. At 1.0 a
                // shorter section is a trim, an authoring decision, and is left alone. This is the Scene 4
                // speed dial's failure: slowing the fold without re-running scene4_fold_nest.py.
                const FMovieSceneTimeWarpVariant& Scale = Sub->Parameters.TimeScale;
                const UMovieScene* ChildScene = Child->GetMovieScene();
                if (ChildScene && Scale.GetType() == EMovieSceneTimeWarpType::FixedPlayRate)
                {
                    const double Rate = Scale.AsFixedPlayRate();
                    if (Rate > 0.0 && !FMath::IsNearlyEqual(Rate, 1.0, 1.0e-4))
                    {
                        const TRange<FFrameNumber> ChildPlayback = ChildScene->GetPlaybackRange();
                        const double ContentSeconds = ChildScene->GetTickResolution().AsSeconds(FFrameTime(
                            ChildPlayback.GetUpperBoundValue() - ChildPlayback.GetLowerBoundValue()
                            - Sub->Parameters.StartFrameOffset - Sub->Parameters.EndFrameOffset)) / Rate;
                        Test.TestTrue(
                            FString::Printf(TEXT("%s: %s at Time Scale %.3f needs %.2f s, and its section is %.2f s. If not: %s"),
                                *Parent.GetName(), *Child->GetName(), Rate, ContentSeconds, EndSeconds - StartSeconds,
                                *FixForNestedSection(Parent, *Child)),
                            EndSeconds - StartSeconds >= ContentSeconds - OneFrameSeconds);
                    }
                }
                Walk(*Child);
            }
        }
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageNestedSequencesFitTest,
    "InfinityStage.Editor.NestedSequencesFitTheirParents",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Every nested sequence under the saved Master must fit its parent: each sub-section ends inside its parent's
// playback range, and a retimed one (Time Scale != 1) has room for its scaled content. Generic, so it covers
// every Scene, the Scene 4 fold's speed dial, and a camera section hosted inside the fold. Read-only.
bool FInfinityStageNestedSequencesFitTest::RunTest(const FString& Parameters)
{
    ULevelSequence* Master = LoadObject<ULevelSequence>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"));
    TestNotNull(TEXT("Saved Master resolves"), Master);
    if (!Master)
    {
        return false;
    }
    FNestedSequenceFitCheck Check(*this);
    Check.Walk(*Master);
    TestTrue(FString::Printf(TEXT("Nested sections were checked (%d)"), Check.SectionsChecked), Check.SectionsChecked > 0);
    return true;
}

#endif
