#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneMarkedFrame.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneSubTrack.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
constexpr int32 SceneDuration = 400;

ULevelSequence* MakeSequence(const FFrameRate Rate, const int32 Duration = SceneDuration)
{
    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    Sequence->GetMovieScene()->SetDisplayRate(Rate);
    Sequence->GetMovieScene()->SetTickResolutionDirectly(Rate);
    Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(0), Duration);
    return Sequence;
}

UMovieSceneCameraCutSection* AddCut(
    ULevelSequence& Sequence,
    const int32 Start,
    const int32 End,
    const bool bActive = true)
{
    UMovieScene* MovieScene = Sequence.GetMovieScene();
    UMovieSceneCameraCutTrack* Track = Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack());
    if (!Track)
    {
        Track = CastChecked<UMovieSceneCameraCutTrack>(
            MovieScene->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
        Track->SetIsAutoManagingSections(false);
    }
    const FGuid CameraGuid = MovieScene->AddPossessable(TEXT("Synthetic Shot Camera"), AActor::StaticClass());
    UMovieSceneCameraCutSection* Cut = Track->AddNewCameraCut(
        FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(CameraGuid)),
        FFrameNumber(Start));
    Cut->SetRange(TRange<FFrameNumber>(FFrameNumber(Start), FFrameNumber(End)));
    Cut->SetIsActive(bActive);
    return Cut;
}

void AddMarker(ULevelSequence& Sequence, const TCHAR* Label, const int32 Frame)
{
    FMovieSceneMarkedFrame Marker;
    Marker.Label = Label;
    Marker.FrameNumber = FFrameNumber(Frame);
    Sequence.GetMovieScene()->AddMarkedFrame(Marker);
}

ULevelSequence* MakeShotSequence(
    const FFrameRate Rate,
    const TArray<int32>& ActiveStarts,
    const bool bAddIgnoredCuts,
    const bool bAddVamp)
{
    ULevelSequence* Sequence = MakeSequence(Rate);
    for (int32 Index = 0; Index < ActiveStarts.Num(); ++Index)
    {
        const int32 End = ActiveStarts.IsValidIndex(Index + 1)
            ? ActiveStarts[Index + 1]
            : SceneDuration;
        AddCut(*Sequence, ActiveStarts[Index], End);
    }
    if (bAddIgnoredCuts)
    {
        // A second active section at the same boundary must not create a second stop.
        AddCut(*Sequence, 100, 150);

        // Root but inactive: it must not become a stop or an active handover.
        AddCut(*Sequence, 180, 200, false);

        // Active but nested: only the Scene sequence's root Camera Cut track counts.
        ULevelSequence* Nested = MakeSequence(Rate);
        AddCut(*Nested, 50, 75);
        Sequence->GetMovieScene()->AddTrack<UMovieSceneSubTrack>()->AddSequence(
            Nested, FFrameNumber(0), SceneDuration);
    }
    if (bAddVamp)
    {
        AddMarker(*Sequence, TEXT("InfinityStage.VampStart"), 100);
        AddMarker(*Sequence, TEXT("InfinityStage.VampEnd"), 200);
    }
    return Sequence;
}

UInfinityStageShowAsset* MakeSceneShow(ULevelSequence* SceneSequence)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Show->DisplayRate = FFrameRate(24, 1);
    Show->TickResolution = Show->DisplayRate;

    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Label = FText::FromString(TEXT("Synthetic Scene"));
    Scene.Scene.DurationFrames = SceneDuration;
    Scene.Scene.Sequence = SceneSequence;

    FInfinityShowCue& Next = Show->Cues.AddDefaulted_GetRef();
    Next.Type = EInfinityCueType::Scene;
    Next.CueGuid = FGuid::NewGuid();
    Next.Label = FText::FromString(TEXT("Following Cue"));
    Next.Scene.DurationFrames = 100;
    return Show;
}

void AddShotStepPassage(UInfinityStageShowAsset& Show)
{
    const int32 FirstCueIndex = Show.Cues.Num();
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 100;
        Cue.WingPair.GapToNextCm = 500.0;
    }
    FInfinityPassageSettings& Settings = Show.PassageSettings.AddDefaulted_GetRef();
    Settings.PassageGuid = FGuid::NewGuid();
    Settings.FirstCueGuid = Show.Cues[FirstCueIndex].CueGuid;
    Settings.LastCueGuid = Show.Cues[FirstCueIndex + 1].CueGuid;
    Settings.TailFrames = 100;
    Settings.TailDistanceCm = 500.0;
}

UInfinityStageShowAsset* MakePassageThenSceneShow()
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Show->DisplayRate = FFrameRate(24, 1);
    Show->TickResolution = Show->DisplayRate;
    AddShotStepPassage(*Show);
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 100;
    return Show;
}

struct FShotStepFixture
{
    UWorld* World = nullptr;
    UInfinityStageTransportController* Transport = nullptr;
    ULevelSequencePlayer* Player = nullptr;

    ~FShotStepFixture()
    {
        if (World)
        {
            World->DestroyWorld(false);
        }
    }

    bool Initialize(FAutomationTestBase& Test, UInfinityStageShowAsset* Show)
    {
        World = UWorld::CreateWorld(EWorldType::Game, false);
        AActor* Host = World ? World->SpawnActor<AActor>() : nullptr;
        Transport = Host ? NewObject<UInfinityStageTransportController>(Host) : nullptr;
        if (Host && Transport)
        {
            Host->AddInstanceComponent(Transport);
            Transport->RegisterComponent();
        }
        const bool bBuilt = Transport && Transport->BuildSegments(Show);
        ULevelSequence* Master = MakeSequence(Show->TickResolution,
            bBuilt ? Transport->Segments.Last().EndFrame.Value : 1);
        FMovieSceneSequencePlaybackSettings Settings;
        ALevelSequenceActor* SequenceActor = nullptr;
        Player = World
            ? ULevelSequencePlayer::CreateLevelSequencePlayer(World, Master, Settings, SequenceActor)
            : nullptr;

        Test.TestNotNull(TEXT("Fixture: game world"), World);
        Test.TestTrue(TEXT("Fixture: segments compile"), bBuilt);
        Test.TestNotNull(TEXT("Fixture: real Level Sequence player"), Player);
        const bool bInitialized = Transport && Player && Transport->InitializeTransport(Player, Show);
        Test.TestTrue(TEXT("Fixture: transport initializes"), bInitialized);
        if (Transport)
        {
            Transport->bPerformanceMode = false;
        }
        return bInitialized;
    }

    bool SetFrame(const FFrameNumber Frame, const bool bPlaying)
    {
        if (!Transport || Transport->ScrubToMasterFrame(Frame) != EInfinityTransportResult::Succeeded)
        {
            return false;
        }
        if (bPlaying)
        {
            Player->Play();
        }
        return Transport->IsTransportPlaying() == bPlaying;
    }

    void MovePlayerWithoutNavigation(const FFrameNumber Frame)
    {
        Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(
            FFrameTime(Frame), EUpdatePositionMethod::Jump));
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShotStepNextAndPreviousTest,
    "InfinityStage.Transport.ShotStepNextAndPrevious",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShotStepNextAndPreviousTest::RunTest(const FString& Parameters)
{
    FShotStepFixture Fixture;
    ULevelSequence* Sequence = MakeShotSequence(FFrameRate(24, 1), {0, 100, 250}, true, false);
    if (!Fixture.Initialize(*this, MakeSceneShow(Sequence)))
    {
        return false;
    }
    Fixture.Transport->ShotRestartGraceDisplayFrames = 5;
    const TArray<FFrameNumber>& Starts = Fixture.Transport->Segments[0].ShotStartFrames;
    TestEqual(TEXT("Active root starts are sorted and de-duplicated"), Starts.Num(), 3);
    if (Starts.Num() == 3)
    {
        TestEqual(TEXT("First root cut"), Starts[0], FFrameNumber(0));
        TestEqual(TEXT("Nested cut at 50 is ignored"), Starts[1], FFrameNumber(100));
        TestEqual(TEXT("Inactive root cut at 180 is ignored"), Starts[2], FFrameNumber(250));
    }

    TestTrue(TEXT("Fixture: playing at Scene frame 10"), Fixture.SetFrame(10, true));
    TestEqual(TEXT("RIGHT steps 10 to 100"),
        Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("First RIGHT lands on shot 2"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(100));
    TestTrue(TEXT("A playing forward step keeps playing"), Fixture.Transport->IsTransportPlaying());
    const TOptional<FFrameNumber> FirstStepStop = Fixture.Transport->GetLastPlayToTargetForTests();
    TestTrue(TEXT("A playing shot step retains a bounded PlayTo stop"), FirstStepStop.IsSet());
    if (FirstStepStop.IsSet())
    {
        TestEqual(TEXT("The bounded stop remains the Scene end"),
            FirstStepStop.GetValue(), Fixture.Transport->Segments[0].EndFrame);
    }
    TestEqual(TEXT("RIGHT steps 100 to 250"),
        Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("Second RIGHT lands on shot 3"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(250));
    TestTrue(TEXT("The second forward step also keeps playing"), Fixture.Transport->IsTransportPlaying());
    TestEqual(TEXT("RIGHT from the last shot falls through to the next cue"),
        Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("The fall-through uses the next cue start"),
        Fixture.Transport->GetCurrentMasterFrame(), Fixture.Transport->Segments[1].StartFrame);

    TestTrue(TEXT("Fixture: paused at 260"), Fixture.SetFrame(260, false));
    TestEqual(TEXT("LEFT after the grace window restarts shot 3"),
        Fixture.Transport->StepShotBack(), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("260 goes to 250"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(250));
    TestFalse(TEXT("A paused backward step stays paused"), Fixture.Transport->IsTransportPlaying());

    TestTrue(TEXT("Fixture: playing at 252"), Fixture.SetFrame(252, true));
    TestEqual(TEXT("LEFT inside the grace window selects the preceding shot"),
        Fixture.Transport->StepShotBack(), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("252 goes to 100"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(100));
    TestTrue(TEXT("A playing backward step keeps playing"), Fixture.Transport->IsTransportPlaying());

    TestTrue(TEXT("Fixture: paused at 10 for paused-forward state"), Fixture.SetFrame(10, false));
    TestEqual(TEXT("Paused RIGHT still steps inside the Scene"),
        Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
    TestFalse(TEXT("A paused forward step stays paused"), Fixture.Transport->IsTransportPlaying());

    // Negative controls: old Advance from frame 10 lands on segment 1 at frame 400,
    // while replacing bounded PlayForwardToBoundary with bare Play leaves the
    // PlayTo-target seam unset. Either regression makes this test fail.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShotStepEngagesVampAtStartTest,
    "InfinityStage.Transport.ShotStepEngagesVampAtStart",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShotStepEngagesVampAtStartTest::RunTest(const FString& Parameters)
{
    {
        FShotStepFixture Fixture;
        ULevelSequence* Sequence = MakeShotSequence(FFrameRate(24, 1), {0, 100, 105}, false, true);
        if (!Fixture.Initialize(*this, MakeSceneShow(Sequence)))
        {
            return false;
        }
        TestTrue(TEXT("Fixture: playing before VampStart"), Fixture.SetFrame(10, true));
        TestEqual(TEXT("Shot step lands exactly on VampStart"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Exact landing is frame 100"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(100));
        Fixture.MovePlayerWithoutNavigation(101);
        Fixture.Transport->TickComponent(0.0f, LEVELTICK_All, nullptr);
        TestTrue(TEXT("The next tick arms the vamp landed on exactly"), Fixture.Transport->ReleaseActiveVamp());
    }

    {
        FShotStepFixture Fixture;
        ULevelSequence* Sequence = MakeShotSequence(FFrameRate(24, 1), {0, 100, 105}, false, true);
        if (!Fixture.Initialize(*this, MakeSceneShow(Sequence)))
        {
            return false;
        }
        TestTrue(TEXT("Fixture: playing on VampStart"), Fixture.SetFrame(100, true));
        TestEqual(TEXT("Shot step can land past VampStart"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Past landing is frame 105"), Fixture.Transport->GetCurrentMasterFrame(), FFrameNumber(105));
        Fixture.MovePlayerWithoutNavigation(106);
        Fixture.Transport->TickComponent(0.0f, LEVELTICK_All, nullptr);
        TestFalse(TEXT("Landing past VampStart does not arm it"), Fixture.Transport->ReleaseActiveVamp());
    }

    // Negative control: old Advance lands at the following cue (frame 400), so
    // a StepShotForward stub fails both exact landing assertions before vamp release.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShotStepOutsideSceneUnchangedTest,
    "InfinityStage.Transport.ShotStepOutsideSceneUnchanged",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShotStepOutsideSceneUnchangedTest::RunTest(const FString& Parameters)
{
    // Feature sentinel for the negative control: this same test must go red if
    // StepShotForward is stubbed to the old Advance implementation.
    {
        FShotStepFixture SceneFixture;
        ULevelSequence* Sequence = MakeShotSequence(FFrameRate(24, 1), {0, 100}, false, false);
        if (!SceneFixture.Initialize(*this, MakeSceneShow(Sequence)))
        {
            return false;
        }
        TestTrue(TEXT("Sentinel fixture: paused inside the Scene"), SceneFixture.SetFrame(10, false));
        TestEqual(TEXT("Sentinel: Scene RIGHT lands on its next shot, not its next cue"),
            SceneFixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Sentinel landing is frame 100"),
            SceneFixture.Transport->GetCurrentMasterFrame(), FFrameNumber(100));
    }

    UInfinityStageShowAsset* Show = MakePassageThenSceneShow();
    FShotStepFixture Expected;
    FShotStepFixture Actual;
    if (!Expected.Initialize(*this, Show) || !Actual.Initialize(*this, Show))
    {
        return false;
    }
    const FFrameNumber InsidePassage = Expected.Transport->Segments[0].StartFrame + FFrameNumber(10);
    TestTrue(TEXT("Expected fixture: paused inside WingPair segment"), Expected.SetFrame(InsidePassage, false));
    TestTrue(TEXT("Actual fixture: paused inside WingPair segment"), Actual.SetFrame(InsidePassage, false));

    const EInfinityTransportResult ExpectedResult = Expected.Transport->AdvanceToNextSegment();
    const EInfinityTransportResult ActualResult = Actual.Transport->StepShotForward();
    TestEqual(TEXT("Outside a Scene, shot-step RIGHT returns Advance's result"), ActualResult, ExpectedResult);
    TestEqual(TEXT("Outside a Scene, shot-step RIGHT lands where Advance lands"),
        Actual.Transport->GetCurrentMasterFrame(), Expected.Transport->GetCurrentMasterFrame());
    TestEqual(TEXT("Outside a Scene, shot-step RIGHT keeps Advance's play state"),
        Actual.Transport->IsTransportPlaying(), Expected.Transport->IsTransportPlaying());

    // Negative control: the outside-Scene comparison intentionally still passes
    // with the stub, while the Scene sentinel above then lands at frame 400 and fails.
    return true;
}

#endif
