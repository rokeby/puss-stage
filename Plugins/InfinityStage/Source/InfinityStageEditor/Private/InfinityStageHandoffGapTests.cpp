#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/**
 * Passage -> Scene -> retained curtain interstitial -> Passage, as in
 * RetainedCameraCurtainInterstitial: a 240000-frame Scene with a 24000-frame
 * Exit hold. With ArtistCutEnd > 0 the Scene carries one designed shot from
 * 24000 to ArtistCutEnd.
 */
struct FRetainedSceneFixture
{
    UWorld* World = nullptr;
    UInfinityStageShowAsset* Show = nullptr;
    FGuid SceneCueGuid;
    ULevelSequence* SceneSequence = nullptr;
    UMovieSceneCameraCutTrack* CutTrack = nullptr;
    UMovieSceneCameraCutSection* ArtistCut = nullptr;

    bool Build(FAutomationTestBase& Test, const int32 ArtistCutEnd)
    {
        World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
        WorldContext.SetCurrentWorld(World);
        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());

        FInfinityShowCue& IncomingCue = Show->Cues.AddDefaulted_GetRef();
        IncomingCue.Type = EInfinityCueType::WingPair;
        IncomingCue.CueGuid = FGuid::NewGuid();
        IncomingCue.WingPair.OccurrenceGuid = FGuid::NewGuid();

        FInfinityShowCue& SceneCue = Show->Cues.AddDefaulted_GetRef();
        SceneCue.Type = EInfinityCueType::Scene;
        SceneCue.CueGuid = FGuid::NewGuid();
        SceneCue.Label = FText::FromString(TEXT("Retained Handoff Test Scene"));
        SceneCue.Scene.DurationFrames = 240000;
        SceneCue.Scene.ExitHandoffHoldFrames = 24000;
        SceneCueGuid = SceneCue.CueGuid;
        SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
        SceneSequence->Initialize();
        SceneSequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
        SceneSequence->GetMovieScene()->SetPlaybackRange(0, SceneCue.Scene.DurationFrames.Value);
        SceneCue.Scene.Sequence = SceneSequence;

        FInfinityShowCue& InteractionCue = Show->Cues.AddDefaulted_GetRef();
        InteractionCue.Type = EInfinityCueType::Sequence;
        InteractionCue.CueGuid = FGuid::NewGuid();
        InteractionCue.Label = FText::FromString(TEXT("Post-Scene Interstitial"));
        InteractionCue.Scene.DurationFrames = 360000;
        InteractionCue.Scene.bRetainPreviousCamera = true;
        InteractionCue.Scene.CurtainMode = EInfinityCurtainCueMode::PostSceneInterstitial;
        InteractionCue.Scene.bRevealNextPassageWhenCovered = true;
        InteractionCue.Scene.CurtainEntryTransitionFrames = 48000;
        InteractionCue.Scene.CurtainHoldFrames = 240000;
        InteractionCue.Scene.CurtainExitTransitionFrames = 48000;

        FInfinityShowCue& OutgoingCue = Show->Cues.AddDefaulted_GetRef();
        OutgoingCue.Type = EInfinityCueType::WingPair;
        OutgoingCue.CueGuid = FGuid::NewGuid();
        OutgoingCue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Show->ReconcilePassageSettings();

        AInfinityStagePassageActor* IncomingPassage = World->SpawnActor<AInfinityStagePassageActor>();
        IncomingPassage->ShowAsset = Show;
        IncomingPassage->PassageGuid = Show->PassageSettings[0].PassageGuid;
        Test.TestTrue(TEXT("Fixture incoming Passage materializes"), IncomingPassage->MaterializePassage());
        AInfinityStageCameraRig* IncomingRig = World->SpawnActor<AInfinityStageCameraRig>();
        IncomingRig->PassageActor = IncomingPassage;

        AInfinityStagePassageActor* OutgoingPassage = World->SpawnActor<AInfinityStagePassageActor>(
            FVector(9000.0, 12000.0, 0.0), FRotator(0.0, 90.0, 0.0));
        OutgoingPassage->ShowAsset = Show;
        OutgoingPassage->PassageGuid = Show->PassageSettings[1].PassageGuid;
        Test.TestTrue(TEXT("Fixture outgoing Passage materializes"), OutgoingPassage->MaterializePassage());
        AInfinityStageCameraRig* OutgoingRig = World->SpawnActor<AInfinityStageCameraRig>();
        OutgoingRig->PassageActor = OutgoingPassage;

        CutTrack = Cast<UMovieSceneCameraCutTrack>(
            SceneSequence->GetMovieScene()->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
        if (!Test.TestNotNull(TEXT("Fixture Camera Cut Track"), CutTrack))
        {
            return false;
        }
        if (ArtistCutEnd > 0)
        {
            ACineCameraActor* ArtistCamera = World->SpawnActor<ACineCameraActor>(
                FVector(1111.0, 2222.0, 333.0),
                FRotator(-7.0, 33.0, 0.0));
            const FGuid ArtistGuid = SceneSequence->GetMovieScene()->AddPossessable(
                TEXT("Designed Shot"),
                ACineCameraActor::StaticClass());
            SceneSequence->BindPossessableObject(ArtistGuid, *ArtistCamera, World);
            ArtistCut = CutTrack->AddNewCameraCut(
                FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(ArtistGuid)),
                FFrameNumber(24000));
            ArtistCut->SetRange(TRange<FFrameNumber>(FFrameNumber(24000), FFrameNumber(ArtistCutEnd)));  // exclusive end; SetEndFrame(FFrameNumber) is INCLUSIVE
        }
        return true;
    }

    bool Match(FAutomationTestBase& Test, const TCHAR* When)
    {
        FString Report;
        return Test.TestTrue(FString::Printf(TEXT("%s: the retained Scene matches"), When),
            FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, Report));
    }

    /** The cuts sorted by start; checks they cover [0, SceneEnd) with no gap. */
    TArray<UMovieSceneSection*> CheckCoverage(FAutomationTestBase& Test, const TCHAR* When, const int32 SceneEnd) const
    {
        TArray<UMovieSceneSection*> Cuts = CutTrack->GetAllSections();
        Cuts.Sort([](const UMovieSceneSection& A, const UMovieSceneSection& B)
        {
            return A.GetInclusiveStartFrame() < B.GetInclusiveStartFrame();
        });
        int32 Cursor = 0;
        int32 Uncovered = 0;
        for (const UMovieSceneSection* Cut : Cuts)
        {
            Uncovered += FMath::Max(0, FMath::Min(Cut->GetInclusiveStartFrame().Value, SceneEnd) - Cursor);
            Cursor = FMath::Max(Cursor, Cut->GetExclusiveEndFrame().Value);
        }
        Uncovered += FMath::Max(0, SceneEnd - Cursor);
        Test.TestEqual(FString::Printf(TEXT("%s: cuts cover the whole Scene"), When), Uncovered, 0);
        return Cuts;
    }

    void Destroy()
    {
        GEngine->DestroyWorldContext(World);
        World->DestroyWorld(false);
    }
};
}

/**
 * A retained Exit whose last designed shot ends before the hold must leave no gap.
 *
 * The Exit used to start at max(SceneEnd - hold, LastInteriorEnd), so a designed
 * shot ending before the hold left a stretch no cut covered (Scene 3, 30 Sep:
 * 1501-1549). A jump into that stretch claims no camera. A retained Exit copies
 * the last shot's camera, so it now starts where that shot ends. Red without the
 * fix: the Exit would be [216000, 240000], leaving 120000-216000 uncovered.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRetainedExitLeavesNoGapTest,
    "InfinityStage.Editor.RetainedExitLeavesNoGap",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRetainedExitLeavesNoGapTest::RunTest(const FString& Parameters)
{
    FRetainedSceneFixture Fixture;
    if (Fixture.Build(*this, 120000) && Fixture.ArtistCut)
    {
        for (const TCHAR* When : { TEXT("First match"), TEXT("Second match") })
        {
            if (!Fixture.Match(*this, When))
            {
                break;
            }
            const TArray<UMovieSceneSection*> Cuts = Fixture.CheckCoverage(*this, When, 240000);
            const UMovieSceneSection* Exit = Cuts.Last();
            TestTrue(FString::Printf(TEXT("%s: the last cut is the Exit, not the designed shot"), When), Exit != Fixture.ArtistCut);
            TestEqual(FString::Printf(TEXT("%s: the retained Exit starts where the designed shot ends"), When),
                Exit->GetInclusiveStartFrame().Value, 120000);
            TestEqual(FString::Printf(TEXT("%s: the Exit runs to the Scene end"), When), Exit->GetExclusiveEndFrame().Value, 240000);
            TestEqual(FString::Printf(TEXT("%s: the designed shot is left as authored"), When),
                Fixture.ArtistCut->GetExclusiveEndFrame().Value, 120000);
        }
    }
    Fixture.Destroy();
    return true;
}

/**
 * Rematching a LENGTHENED Scene must keep the Exit a hold at the new end.
 *
 * The Exit used to be placed with SetStartFrame then SetEndFrame. SetStartFrame
 * clamps to the current end, so a new start past the old end stuck there and the
 * Exit ran from the OLD end to the new one (Scene 1, 30 Sep: [375, 5270] instead
 * of [5245, 5270]). Coverage stays whole, so only this catches it. Red without
 * the fix: the Exit would be [240000, 480000].
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageExitHoldSurvivesLengtheningTest,
    "InfinityStage.Editor.ExitHoldSurvivesLengthening",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageExitHoldSurvivesLengtheningTest::RunTest(const FString& Parameters)
{
    FRetainedSceneFixture Fixture;
    if (Fixture.Build(*this, 0) && Fixture.Match(*this, TEXT("Before lengthening")))
    {
        const TArray<UMovieSceneSection*> Before = Fixture.CheckCoverage(*this, TEXT("Before lengthening"), 240000);
        TestEqual(TEXT("Before lengthening: the Exit is the 24000-frame hold"),
            Before.Last()->GetInclusiveStartFrame().Value, 216000);

        FInfinityShowCue* SceneCue = Fixture.Show->Cues.FindByPredicate(
            [&Fixture](const FInfinityShowCue& Cue) { return Cue.CueGuid == Fixture.SceneCueGuid; });
        SceneCue->Scene.DurationFrames = 480000;
        Fixture.SceneSequence->GetMovieScene()->SetPlaybackRange(0, 480000);
        if (Fixture.Match(*this, TEXT("After lengthening")))
        {
            const TArray<UMovieSceneSection*> After = Fixture.CheckCoverage(*this, TEXT("After lengthening"), 480000);
            TestEqual(TEXT("After lengthening: still two cuts"), After.Num(), 2);
            TestEqual(TEXT("After lengthening: the Exit is still a 24000-frame hold at the new end"),
                After.Last()->GetInclusiveStartFrame().Value, 456000);
            TestEqual(TEXT("After lengthening: the Exit ends at the new end"),
                After.Last()->GetExclusiveEndFrame().Value, 480000);
            TestEqual(TEXT("After lengthening: the Entry runs up to the Exit"),
                After[0]->GetExclusiveEndFrame().Value, 456000);
        }
    }
    Fixture.Destroy();
    return true;
}

#endif
