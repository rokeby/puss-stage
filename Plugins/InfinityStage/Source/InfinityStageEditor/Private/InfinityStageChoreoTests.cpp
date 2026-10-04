#include "InfinityStageCompiler.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneInfinityChoreoTrack.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieSceneSubTrack.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageChoreoFollowsRetimeTest,
    "InfinityStage.Cueing.Choreo.FollowsRetime",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// A Passage's Choreography is nested over its segment, 0:00 at the Passage start,
// and moves with it when an earlier Scene grows. An absolute section placed by
// hand at the same frame is the control: it stays behind.
bool FInfinityStageChoreoFollowsRetimeTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 24000;
        Cue.WingPair.GapToNextCm = 500.0;
    }
    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 48000;
    Scene.Scene.Sequence = SceneSequence;
    FInfinityShowCue& FinalWing = Show->Cues.AddDefaulted_GetRef();
    FinalWing.Type = EInfinityCueType::WingPair;
    FinalWing.CueGuid = FGuid::NewGuid();
    FinalWing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();
    TestEqual(TEXT("Fixture has two Passages"), Show->PassageSettings.Num(), 2);
    if (Show->PassageSettings.Num() != 2)
    {
        return false;
    }

    // The Choreo goes on the Passage AFTER the Scene, so growing the Scene retimes it.
    const FInfinityCompileResult Before = FInfinityStageCompiler::Compile(*Show);
    const FInfinityCompiledPassage* LaterBefore = Before.Passages.FindByPredicate(
        [](const FInfinityCompiledPassage& P) { return P.SegmentStartFrame > 0; });
    TestNotNull(TEXT("Fixture has a Passage after the Scene"), LaterBefore);
    if (!LaterBefore)
    {
        return false;
    }
    const FGuid LaterGuid = LaterBefore->PassageGuid;
    const FFrameNumber StartBefore = LaterBefore->SegmentStartFrame;

    ULevelSequence* Choreo = NewObject<ULevelSequence>(GetTransientPackage());
    Choreo->Initialize();
    Choreo->GetMovieScene()->SetPlaybackRange(0, Show->TickResolution.AsFrameNumber(600.0).Value);
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        if (Settings.PassageGuid == LaterGuid)
        {
            Settings.Choreography = Choreo;
        }
    }

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    // Control: the same Choreo placed by hand at an absolute frame.
    UMovieSceneSubSection* Absolute = Master->GetMovieScene()->AddTrack<UMovieSceneSubTrack>()
        ->AddSequence(Choreo, StartBefore, 1000);

    FString Report;
    TestTrue(TEXT("First build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    UMovieSceneInfinityChoreoTrack* Track = Master->GetMovieScene()->FindTrack<UMovieSceneInfinityChoreoTrack>();
    TestNotNull(TEXT("A Choreography track is made"), Track);
    if (!Track)
    {
        return false;
    }
    TestEqual(TEXT("Only the Passage with a Choreo gets a section"), Track->GetAllSections().Num(), 1);
    UMovieSceneInfinityChoreoSection* Section = Cast<UMovieSceneInfinityChoreoSection>(Track->GetAllSections()[0]);
    TestTrue(TEXT("Section plays the Choreo"), Section && Section->GetSequence() == Choreo);
    TestTrue(TEXT("Section is keyed by the Passage"), Section && Section->BlockGuid == LaterGuid);
    TestTrue(TEXT("Section starts at the Passage start (0:00 = Passage start)"),
        Section && Section->GetInclusiveStartFrame() == StartBefore);

    // Retime: the Scene grows by 10 s.
    const FFrameNumber Grow = Show->TickResolution.AsFrameNumber(10.0);
    Show->Cues[2].Scene.DurationFrames += Grow.Value;
    TestTrue(TEXT("Second build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestEqual(TEXT("Still one section"), Track->GetAllSections().Num(), 1);
    TestTrue(TEXT("Same section object (identity is stable)"), Track->GetAllSections()[0] == Section);
    TestTrue(TEXT("The Choreo moved with its Passage"),
        Section->GetInclusiveStartFrame() == StartBefore + Grow);
    TestTrue(TEXT("Control: the absolute section did not move"), Absolute->GetInclusiveStartFrame() == StartBefore);

    // Clearing the field removes the nesting on the next build.
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.Choreography.Reset();
    }
    TestTrue(TEXT("Third build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestEqual(TEXT("No Choreo, no section"), Track->GetAllSections().Num(), 0);
    TestTrue(TEXT("The artist's own sub track is untouched"), Absolute->GetSequence() == Choreo);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageChoreoAbsentIsUnchangedTest,
    "InfinityStage.Cueing.Choreo.AbsentLeavesMasterUnchanged",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// A Show with no Choreography must build exactly the Master it built before the
// Choreo patch: no Choreography track, and the same track list on every rebuild.
bool FInfinityStageChoreoAbsentIsUnchangedTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 24000;
        Cue.WingPair.GapToNextCm = 500.0;
    }
    Show->ReconcilePassageSettings();
    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    FString Report;
    TestTrue(TEXT("Build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestNull(TEXT("No Choreography track without a Choreo"),
        Master->GetMovieScene()->FindTrack<UMovieSceneInfinityChoreoTrack>());
    const TArray<UMovieSceneTrack*> First = Master->GetMovieScene()->GetTracks();
    TestTrue(TEXT("Rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestTrue(TEXT("Same tracks, same objects, same order"), Master->GetMovieScene()->GetTracks() == First);
    for (const UMovieSceneTrack* Track : First)
    {
        TestFalse(TEXT("No track of the Choreography class"), Track && Track->IsA<UMovieSceneInfinityChoreoTrack>());
    }
    return true;
}

#endif
