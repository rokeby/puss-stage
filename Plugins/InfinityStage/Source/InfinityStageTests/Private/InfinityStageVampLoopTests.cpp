#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneMarkedFrame.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageVampLoopsUntilReleaseTest,
    "InfinityStage.Transport.VampLoopsUntilRelease",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageVampLoopsUntilReleaseTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::Scene;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.Label = FText::FromString(TEXT("Vamp Fixture"));
    Cue.Scene.DurationFrames = 500;

    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    Sequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(1000), 500);
    FMovieSceneMarkedFrame StartMarker;
    StartMarker.FrameNumber = FFrameNumber(1100);
    StartMarker.Label = TEXT("InfinityStage.VampStart");
    Sequence->GetMovieScene()->AddMarkedFrame(StartMarker);
    FMovieSceneMarkedFrame EndMarker;
    EndMarker.FrameNumber = FFrameNumber(1110);
    EndMarker.Label = TEXT("InfinityStage.VampEnd");
    Sequence->GetMovieScene()->AddMarkedFrame(EndMarker);
    Cue.Scene.Sequence = Sequence;

    UInfinityStageTransportController* Transport =
        NewObject<UInfinityStageTransportController>(GetTransientPackage());
    TestTrue(TEXT("The fixture with one marker pair compiles"), Transport->BuildSegments(Show));
    TestEqual(TEXT("One VampStart/VampEnd pair becomes one Master range"),
        Transport->VampRanges.Num(), 1);
    if (Transport->VampRanges.Num() != 1)
    {
        return false;
    }
    const TArray<FInfinityVampRange> Ranges = Transport->VampRanges;
    TestEqual(TEXT("VampStart is relative to the child playback start"),
        Ranges[0].StartFrame, FFrameNumber(100));
    TestEqual(TEXT("VampEnd is relative to the child playback start"),
        Ranges[0].EndFrame, FFrameNumber(110));
    TestEqual(TEXT("The vamp records its compiled segment"), Ranges[0].SegmentIndex, 0);

    FInfinityVampPlaybackState State;
    State.OnNavigation(90);

    FFrameNumber LoopFrame = 0;
    TestEqual(TEXT("Crossing VampStart arms without jumping"),
        State.Tick(100, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);
    for (int32 Loop = 1; Loop <= 3; ++Loop)
    {
        TestEqual(TEXT("VampEnd loops to VampStart"),
            State.Tick(110, true, false, 1.0f, Ranges, LoopFrame),
            EInfinityVampPlaybackAction::LoopToStart);
        TestEqual(TEXT("An exact seam preserves frame cadence"), LoopFrame, FFrameNumber(100));
        TestEqual(TEXT("Loop count advances once per seam"), State.LoopCount, Loop);
    }

    // Positive control for C3: UMovieSceneSequencePlayer::PlayTo pauses on its
    // target before the component can observe that frame. An armed VampEnd must
    // still win that arrival and replace the older Scene-end PlayTo.
    State.Reset();
    State.OnNavigation(90);
    TestEqual(TEXT("Paused-arrival fixture arms while crossing VampStart"),
        State.Tick(100, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);
    TestTrue(TEXT("Paused-arrival fixture has an active vamp"), State.IsActive());
    TestEqual(TEXT("A paused PlayTo arrival at VampEnd still loops"),
        State.Tick(110, false, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::LoopToStart);
    TestEqual(TEXT("The paused arrival returns to VampStart"), LoopFrame, FFrameNumber(100));

    // Negative control: pausing inside the range is an operator pause, not a
    // seam. It must remain paused and must not increment the loop count.
    State.Reset();
    State.OnNavigation(90);
    State.Tick(100, true, false, 1.0f, Ranges, LoopFrame);
    const int32 LoopsBeforeInteriorPause = State.LoopCount;
    TestEqual(TEXT("A pause before VampEnd does not loop"),
        State.Tick(109, false, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);
    TestEqual(TEXT("The interior pause does not change loop count"),
        State.LoopCount, LoopsBeforeInteriorPause);

    TestTrue(TEXT("RIGHT releases an active vamp"), State.Release(100, Ranges));
    TestEqual(TEXT("A released vamp plays through its end"),
        State.Tick(110, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);

    State.Reset();
    State.OnNavigation(90);
    TestEqual(TEXT("Fast-forward crossing VampStart yields to the vamp"),
        State.Tick(102, true, false, 4.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::NormalizeToOne);
    TestEqual(TEXT("The normalized vamp loops at its end"),
        State.Tick(110, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::LoopToStart);

    State.Reset();
    State.OnNavigation(105);
    TestEqual(TEXT("A scrub into the vamp never arms it"),
        State.Tick(110, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);

    State.Reset();
    State.OnNavigation(90);
    State.Tick(100, true, false, 1.0f, Ranges, LoopFrame);
    State.Tick(110, true, false, 1.0f, Ranges, LoopFrame);
    State.Release(100, Ranges);
    State.Tick(112, true, false, 1.0f, Ranges, LoopFrame);
    TestEqual(TEXT("Reverse playback into a released vamp re-arms it"),
        State.Tick(105, true, true, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::None);
    TestEqual(TEXT("The re-armed vamp loops on the next forward seam"),
        State.Tick(110, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::LoopToStart);

    State.Reset();
    State.OnNavigation(90);
    State.Tick(100, true, false, 1.0f, Ranges, LoopFrame);
    TestEqual(TEXT("Overshoot wraps to the same cadence inside the vamp"),
        State.Tick(112, true, false, 1.0f, Ranges, LoopFrame),
        EInfinityVampPlaybackAction::LoopToStart);
    TestEqual(TEXT("Two frames of overshoot land two frames after VampStart"),
        LoopFrame, FFrameNumber(102));

    return true;
}

#endif
