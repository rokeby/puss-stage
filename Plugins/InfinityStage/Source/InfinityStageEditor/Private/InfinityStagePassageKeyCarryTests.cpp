#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * A Master rebuild that moves a Passage must carry its channel keys with it.
 *
 * Keys are stored at absolute Master frames and the rebuild used to call only
 * SetRange, so lengthening a Scene left every later Passage's camera score early
 * by the added length (30 Sep: P02 carried keys 195.8 s before its section after
 * Scene 1 was lengthened). The rebuild now calls MoveSection first. That
 * MoveSection offsets the proxy's channels is inferred from its declaration, since
 * the engine .cpp is not shipped; this test is what measures it.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStagePassageKeysFollowSectionTest,
    "InfinityStage.Editor.PassageKeysFollowSection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStagePassageKeysFollowSectionTest::RunTest(const FString& Parameters)
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
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.bUseSequenceLength = false;
    Scene.Scene.DurationFrames = 48000;
    const FGuid SceneGuid = Scene.CueGuid;
    FInfinityShowCue& FinalWing = Show->Cues.AddDefaulted_GetRef();
    FinalWing.Type = EInfinityCueType::WingPair;
    FinalWing.CueGuid = FGuid::NewGuid();
    FinalWing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.TailFrames = 24000;
        Settings.TailDistanceCm = 250.0;
    }

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    FString Report;
    if (!TestTrue(TEXT("First build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report)))
    {
        return false;
    }
    UMovieSceneInfinityPassageTrack* Track = Master->GetMovieScene()->FindTrack<UMovieSceneInfinityPassageTrack>();
    if (!TestNotNull(TEXT("Passage track exists"), Track) || !TestEqual(TEXT("Two Passages"), Track->GetAllSections().Num(), 2))
    {
        return false;
    }
    TArray<UMovieSceneInfinityPassageSection*> Sections;
    for (UMovieSceneSection* Base : Track->GetAllSections())
    {
        Sections.Add(CastChecked<UMovieSceneInfinityPassageSection>(Base));
    }
    Sections.Sort([](const UMovieSceneInfinityPassageSection& A, const UMovieSceneInfinityPassageSection& B)
    {
        return A.GetInclusiveStartFrame() < B.GetInclusiveStartFrame();
    });
    UMovieSceneInfinityPassageSection* Before = Sections[0];
    UMovieSceneInfinityPassageSection* After = Sections[1];
    const FFrameNumber BeforeStart = Before->GetInclusiveStartFrame();
    const FFrameNumber AfterStart = After->GetInclusiveStartFrame();

    // A two-key score on the Passage after the Scene (the channel that changes
    // how the walk feels), one on a Wing channel, and one on the Passage before.
    After->SpeedMultiplier.AddCubicKey(AfterStart + FFrameNumber(12000), 1.0);
    After->SpeedMultiplier.AddCubicKey(AfterStart + FFrameNumber(36000), 2.0);
    After->WingPhaseBiasCycles.AddCubicKey(AfterStart + FFrameNumber(6000), 0.25);
    Before->HeightOffsetCm.AddCubicKey(BeforeStart + FFrameNumber(6000), 222.0);

    const int32 Added = 24000;
    Show->Cues.FindByPredicate([SceneGuid](const FInfinityShowCue& Cue) { return Cue.CueGuid == SceneGuid; })
        ->Scene.DurationFrames = 48000 + Added;
    TestTrue(TEXT("Rebuild after lengthening the Scene succeeds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestEqual(TEXT("The later Passage moved by the added length"),
        After->GetInclusiveStartFrame().Value, AfterStart.Value + Added);
    TestEqual(TEXT("The earlier Passage did not move"), Before->GetInclusiveStartFrame().Value, BeforeStart.Value);

    const auto ExpectKeys = [this](const TCHAR* What, const FMovieSceneDoubleChannel& Channel,
        const FFrameNumber SectionStart, const TArray<TPair<int32, double>>& Expected)
    {
        const TArrayView<const FFrameNumber> Times = Channel.GetData().GetTimes();
        const TArrayView<const FMovieSceneDoubleValue> Values = Channel.GetData().GetValues();
        if (!TestEqual(FString::Printf(TEXT("%s key count"), What), Times.Num(), Expected.Num()))
        {
            return;
        }
        for (int32 Index = 0; Index < Expected.Num(); ++Index)
        {
            TestEqual(FString::Printf(TEXT("%s key %d stays at the same section-relative frame"), What, Index),
                (Times[Index] - SectionStart).Value, Expected[Index].Key);
            TestEqual(FString::Printf(TEXT("%s key %d keeps its value"), What, Index),
                Values[Index].Value, Expected[Index].Value);
        }
    };
    ExpectKeys(TEXT("Later Passage speed"), After->SpeedMultiplier, After->GetInclusiveStartFrame(),
        { TPair<int32, double>(12000, 1.0), TPair<int32, double>(36000, 2.0) });
    ExpectKeys(TEXT("Later Passage wing phase"), After->WingPhaseBiasCycles, After->GetInclusiveStartFrame(),
        { TPair<int32, double>(6000, 0.25) });
    ExpectKeys(TEXT("Earlier Passage height"), Before->HeightOffsetCm, Before->GetInclusiveStartFrame(),
        { TPair<int32, double>(6000, 222.0) });

    // Idempotence: a rebuild that moves nothing must not move keys again.
    TestTrue(TEXT("Unchanged rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    ExpectKeys(TEXT("Later Passage speed after an unchanged rebuild"), After->SpeedMultiplier,
        After->GetInclusiveStartFrame(), { TPair<int32, double>(12000, 1.0), TPair<int32, double>(36000, 2.0) });
    return true;
}

#endif
