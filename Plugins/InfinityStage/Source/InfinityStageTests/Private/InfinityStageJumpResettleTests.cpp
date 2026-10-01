#include "InfinityStageTransportController.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageJumpResettlesOnceTest,
    "InfinityStage.Transport.JumpResettlesOnce",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageJumpResettlesOnceTest::RunTest(const FString& Parameters)
{
    constexpr FFrameNumber FirstFrame(1200);
    constexpr FFrameNumber SecondFrame(2400);
    constexpr float Dt = 1.0f / 60.0f;
    constexpr float SettleSeconds = 0.1f;
    constexpr int32 MinTicks = 2;

    // Held paused on one frame: due once, and only after both gates are met.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        int32 Fires = 0;
        int32 FireTick = INDEX_NONE;
        for (int32 Tick = 1; Tick <= 60; ++Tick)
        {
            if (UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, Dt, SettleSeconds, MinTicks))
            {
                ++Fires;
                FireTick = Tick;
                TestTrue(TEXT("The elapsed-time gate has passed before the resettle fires"), State.Elapsed >= SettleSeconds);
                TestTrue(TEXT("The minimum-tick gate has passed before the resettle fires"), State.Ticks >= MinTicks);
            }
        }
        TestEqual(TEXT("A held paused jump resettles exactly once"), Fires, 1);
        TestTrue(TEXT("The resettle does not fire before the minimum tick count"), FireTick >= MinTicks);
        TestFalse(TEXT("The pending flag is cleared after firing"), State.bPending);
    }

    // Starting playback cancels the pending re-evaluation permanently.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        TestFalse(TEXT("Playing never fires a pending resettle"),
            UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, true, Dt, SettleSeconds, MinTicks));
        TestFalse(TEXT("Playing clears the pending resettle"), State.bPending);
        bool bFiredLater = false;
        for (int32 Tick = 0; Tick < 60; ++Tick)
        {
            bFiredLater = bFiredLater || UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, Dt, SettleSeconds, MinTicks);
        }
        TestFalse(TEXT("A cancelled playing resettle never fires later"), bFiredLater);
    }

    // Leaving the target frame before the deadline cancels it.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        UInfinityStageTransportController::StepJumpResettle(
            State, FirstFrame, false, Dt, SettleSeconds, MinTicks);
        TestFalse(TEXT("Changing frame never fires the old target"),
            UInfinityStageTransportController::StepJumpResettle(
                State, SecondFrame, false, Dt, SettleSeconds, MinTicks));
        TestFalse(TEXT("Changing frame clears the pending resettle"), State.bPending);
        bool bFiredLater = false;
        for (int32 Tick = 0; Tick < 60; ++Tick)
        {
            bFiredLater = bFiredLater || UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, Dt, SettleSeconds, MinTicks);
        }
        TestFalse(TEXT("Returning to the old target does not revive the cancelled resettle"), bFiredLater);
    }

    // A new jump replaces the old target and restarts both countdowns.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        for (int32 Tick = 0; Tick < 3; ++Tick)
        {
            TestFalse(TEXT("The first jump is not due before it is replaced"),
                UInfinityStageTransportController::StepJumpResettle(
                    State, FirstFrame, false, Dt, SettleSeconds, MinTicks));
        }
        State = {true, SecondFrame, 0.0f, 0};
        int32 Fires = 0;
        for (int32 Tick = 1; Tick <= 60; ++Tick)
        {
            Fires += UInfinityStageTransportController::StepJumpResettle(
                State, SecondFrame, false, Dt, SettleSeconds, MinTicks) ? 1 : 0;
        }
        TestEqual(TEXT("The replacement jump fires exactly once"), Fires, 1);
        TestEqual(TEXT("Only the replacement frame is retained"), State.Frame, SecondFrame);
    }

    // Zero disables the feature and clears an already armed request.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        TestFalse(TEXT("A zero settle time never fires"),
            UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, 1.0f, 0.0f, MinTicks));
        TestFalse(TEXT("A zero settle time clears the pending resettle"), State.bPending);
    }

    // A long first tick satisfies time but never bypasses the two-tick gate.
    {
        FInfinityJumpResettle State{true, FirstFrame, 0.0f, 0};
        TestFalse(TEXT("A single 0.5 second tick is still only one tick"),
            UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, 0.5f, SettleSeconds, MinTicks));
        TestTrue(TEXT("The request remains pending after that first large tick"), State.bPending);
        TestTrue(TEXT("The second tick may now fire"),
            UInfinityStageTransportController::StepJumpResettle(
                State, FirstFrame, false, 0.0f, SettleSeconds, MinTicks));
    }

    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageJumpResettleReassertsPassageSameTickTest,
    "InfinityStage.Transport.JumpResettleReassertsPassageSameTick",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageJumpResettleReassertsPassageSameTickTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    APlayerController* PlayerController = World ? World->SpawnActor<APlayerController>() : nullptr;
    if (PlayerController && !PlayerController->PlayerCameraManager)
    {
        FActorSpawnParameters ManagerSpawn;
        ManagerSpawn.Owner = PlayerController;
        PlayerController->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>(ManagerSpawn);
        if (PlayerController->PlayerCameraManager)
        {
            PlayerController->PlayerCameraManager->InitializeFor(PlayerController);
        }
    }
    if (World && PlayerController && World->GetFirstPlayerController() != PlayerController)
    {
        World->AddController(PlayerController);
    }

    AActor* Host = World ? World->SpawnActor<AActor>() : nullptr;
    UInfinityStageTransportController* Transport = Host
        ? NewObject<UInfinityStageTransportController>(Host)
        : nullptr;
    if (Host && Transport)
    {
        Host->AddInstanceComponent(Transport);
        Transport->RegisterComponent();
    }

    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }

    const bool bSegmentsBuilt = Transport && Transport->BuildSegments(Show);
    const FGuid PassageGuid = bSegmentsBuilt && !Transport->Segments.IsEmpty()
        ? Transport->Segments[0].SegmentGuid
        : FGuid();
    AInfinityStagePassageActor* Passage = World ? World->SpawnActor<AInfinityStagePassageActor>() : nullptr;
    AInfinityStageCameraRig* ClaimedRig = World ? World->SpawnActor<AInfinityStageCameraRig>() : nullptr;
    AActor* StolenTarget = World ? World->SpawnActor<AActor>() : nullptr;
    if (Passage)
    {
        Passage->ShowAsset = Show;
        Passage->PassageGuid = PassageGuid;
    }
    if (ClaimedRig)
    {
        ClaimedRig->PassageActor = Passage;
    }

    ULevelSequence* MasterSequence = NewObject<ULevelSequence>(GetTransientPackage());
    MasterSequence->Initialize();
    MasterSequence->GetMovieScene()->SetDisplayRate(Show->DisplayRate);
    MasterSequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    MasterSequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(0), 48000);
    FMovieSceneSequencePlaybackSettings PlaybackSettings;
    ALevelSequenceActor* SequenceActor = nullptr;
    ULevelSequencePlayer* SequencePlayer = World
        ? ULevelSequencePlayer::CreateLevelSequencePlayer(
            World, MasterSequence, PlaybackSettings, SequenceActor)
        : nullptr;

    TestNotNull(TEXT("Fixture: Game world"), World);
    TestNotNull(TEXT("Fixture: player controller"), PlayerController);
    TestTrue(TEXT("Fixture: camera manager"), PlayerController && PlayerController->PlayerCameraManager);
    TestTrue(TEXT("Fixture: controller is player 0"),
        World && World->GetFirstPlayerController() == PlayerController);
    TestTrue(TEXT("Fixture: Passage segments compile"), bSegmentsBuilt);
    TestTrue(TEXT("Fixture: Passage GUID"), PassageGuid.IsValid());
    TestTrue(TEXT("Fixture: Passage rig and steal target"), ClaimedRig && StolenTarget);
    TestNotNull(TEXT("Fixture: real Level Sequence player"), SequencePlayer);

    const bool bInitialized = Transport && SequencePlayer
        && Transport->InitializeTransport(SequencePlayer, Show);
    TestTrue(TEXT("Fixture: transport initializes"), bInitialized);
    TestTrue(TEXT("Fixture: reassert gates describe a selected Passage rig"),
        bInitialized
        && Transport->LastHandover.Source == EInfinityHandoverSource::PassageRig
        && Transport->Segments.IsValidIndex(Transport->SelectedSegmentIndex)
        && Transport->Segments[Transport->SelectedSegmentIndex].Type == EInfinityCueType::WingPair);
    TestTrue(TEXT("Fixture: the Passage rig is initially claimed"),
        PlayerController && PlayerController->GetViewTarget() == ClaimedRig);

    if (bInitialized && PlayerController && ClaimedRig && StolenTarget)
    {
        Transport->JumpResettleSeconds = 0.001f;
        TestEqual(TEXT("A paused scrub arms the delayed same-frame evaluation"),
            Transport->ScrubToMasterFrame(FFrameNumber(0)), EInfinityTransportResult::Succeeded);

        // Prime the two-tick gate without firing; the next tick-tail call is the
        // single observed operation that both evaluates and repairs the steal.
        Transport->RunTickTailForTests(FFrameNumber(0), 0.001f);
        TestEqual(TEXT("Fixture: the priming tick does not resettle"), Transport->JumpResettleCount, 0);

        bool bSeamRan = false;
        bool bStealVisible = false;
        Transport->JumpResettlePostEvaluationTestSeam = [PlayerController, StolenTarget, &bSeamRan, &bStealVisible]()
        {
            bSeamRan = true;
            PlayerController->SetViewTarget(StolenTarget);
            bStealVisible = PlayerController->GetViewTarget() == StolenTarget;
        };
        Transport->RunTickTailForTests(FFrameNumber(0), 0.0f);

        TestTrue(TEXT("The post-evaluation seam ran"), bSeamRan);
        // Control: the steal must really take effect inside the seam, or the
        // restore assertion below would pass whatever order the tail used.
        TestTrue(TEXT("Control: the seam's steal is visible before the tail continues"), bStealVisible);
        TestEqual(TEXT("The due same-frame jump evaluated once"), Transport->JumpResettleCount, 1);
        // This is deliberately order-sensitive. With S v1's reassert-before-jump
        // order, the seam steals after the last reclaim and this remains StolenTarget.
        TestTrue(TEXT("The Passage claim is restored in the same tick tail"),
            PlayerController->GetViewTarget() == ClaimedRig);
        Transport->JumpResettlePostEvaluationTestSeam = nullptr;
    }

    if (World)
    {
        World->DestroyWorld(false);
    }
    return true;
}

#endif
