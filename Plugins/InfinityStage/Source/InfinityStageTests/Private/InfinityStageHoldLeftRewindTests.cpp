#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"

#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Hold-Left rewind (Gary, 6 Oct: "Left button hold should take us backwards the
 * same way right takes us fastforward"). Tap = Previous (unchanged), hold = a
 * muted reverse play at RewindRate, with fast-forward's interlocks.
 */
namespace InfinityStageHoldLeftRewindTests
{
ULevelSequence* MakeMaster(const FFrameRate Rate, const int32 Duration)
{
    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    Sequence->GetMovieScene()->SetDisplayRate(Rate);
    Sequence->GetMovieScene()->SetTickResolutionDirectly(Rate);
    Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(0), Duration);
    return Sequence;
}

void AddPassage(UInfinityStageShowAsset& Show)
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

void AddScene(UInfinityStageShowAsset& Show, const TCHAR* Label, const bool bLiveClock)
{
    FInfinityShowCue& Scene = Show.Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Label = FText::FromString(Label);
    Scene.Scene.DurationFrames = 100;
    Scene.Scene.bRetainPreviousCamera = true;
    if (bLiveClock)
    {
        Scene.Scene.ExternalSound = EInfinityExternalSoundAuthority::DeclaredUnpausable;
    }
}

/** P01, S1 (optionally a live-performer clock), P02, S2. */
UInfinityStageShowAsset* MakeShow(const bool bLiveS1)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Show->DisplayRate = FFrameRate(24, 1);
    Show->TickResolution = Show->DisplayRate;
    AddPassage(*Show);
    AddScene(*Show, TEXT("Scene 1"), bLiveS1);
    AddPassage(*Show);
    AddScene(*Show, TEXT("Scene 2"), false);
    return Show;
}

struct FRewindFixture
{
    UWorld* World = nullptr;
    UInfinityStageTransportController* Transport = nullptr;
    ULevelSequencePlayer* Player = nullptr;

    ~FRewindFixture()
    {
        if (World)
        {
            World->DestroyWorld(false);
        }
    }

    bool Initialize(FAutomationTestBase& Test, const bool bLiveS1)
    {
        UInfinityStageShowAsset* Show = MakeShow(bLiveS1);
        World = UWorld::CreateWorld(EWorldType::Game, false);
        AActor* Host = World ? World->SpawnActor<AActor>() : nullptr;
        Transport = Host ? NewObject<UInfinityStageTransportController>(Host) : nullptr;
        if (Host && Transport)
        {
            Host->AddInstanceComponent(Transport);
            Transport->RegisterComponent();
        }
        const bool bBuilt = Transport && Transport->BuildSegments(Show);
        ULevelSequence* Master = MakeMaster(Show->TickResolution,
            bBuilt ? Transport->Segments.Last().EndFrame.Value : 1);
        FMovieSceneSequencePlaybackSettings Settings;
        ALevelSequenceActor* SequenceActor = nullptr;
        Player = World
            ? ULevelSequencePlayer::CreateLevelSequencePlayer(World, Master, Settings, SequenceActor)
            : nullptr;
        const bool bInitialized = bBuilt && Player && Transport->InitializeTransport(Player, Show);
        Test.TestTrue(TEXT("Fixture: transport initializes"), bInitialized);
        return bInitialized && Transport->Segments.Num() == 4;
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRewindTargetTest,
    "InfinityStage.Transport.HoldLeftRewind.TargetRespectsLiveClocks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRewindTargetTest::RunTest(const FString& Parameters)
{
    TArray<FInfinityTransportSegment> Segments;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        FInfinityTransportSegment& Segment = Segments.AddDefaulted_GetRef();
        Segment.StartFrame = 100 * Index;
        Segment.EndFrame = 100 * (Index + 1);
    }
    TestEqual(TEXT("Rehearsal: rewinds to the Show start"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(Segments, 3, false), FFrameNumber(0));
    TestEqual(TEXT("Performance, no live clocks: the Show start"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(Segments, 3, true), FFrameNumber(0));
    Segments[1].ExternalSound = EInfinityExternalSoundAuthority::DeclaredUnpausable;
    TestEqual(TEXT("Performance: stops at the END of the earlier live segment (= next start)"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(Segments, 3, true), FFrameNumber(200));
    TestEqual(TEXT("Rehearsal ignores the live clock, as every other interlock does"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(Segments, 3, false), FFrameNumber(0));
    TestEqual(TEXT("Directly after the live segment: nothing behind (its own start)"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(Segments, 2, true), FFrameNumber(200));
    TestEqual(TEXT("Empty table: frame 0"),
        UInfinityStageTransportController::ResolveRewindTargetFrame(TArray<FInfinityTransportSegment>(), 0, true),
        FFrameNumber(0));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRewindPlaysBackTest,
    "InfinityStage.Transport.HoldLeftRewind.PlaysBackwardsAndRestores",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRewindPlaysBackTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageHoldLeftRewindTests;
    FRewindFixture Fixture;
    if (!Fixture.Initialize(*this, false))
    {
        return false;
    }
    UInfinityStageTransportController& Transport = *Fixture.Transport;
    Transport.bPerformanceMode = false;
    TestEqual(TEXT("RewindRate defaults to fast-forward's 4x"), Transport.RewindRate, 4.0f);

    // Control: at the very start there is nothing behind the playhead.
    Transport.ScrubToMasterFrame(Transport.Segments[0].StartFrame);
    TestEqual(TEXT("Control: no rewind from the Show start"),
        Transport.BeginRewind(), EInfinityTransportResult::NoSegment);
    TestFalse(TEXT("Control: a refused rewind leaves nothing active"), Transport.IsRewindActive());

    const FFrameNumber Middle = Transport.Segments[2].StartFrame + FFrameNumber(30);
    TestEqual(TEXT("Scrub into P02"), Transport.ScrubToMasterFrame(Middle), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("Hold-Left begins a rewind"), Transport.BeginRewind(), EInfinityTransportResult::Succeeded);
    TestTrue(TEXT("The rewind is active"), Transport.IsRewindActive());
    TestTrue(TEXT("The Master is playing"), Transport.IsTransportPlaying());
    TestEqual(TEXT("At RewindRate"), Fixture.Player->GetPlayRate(), 4.0f);
    const TOptional<FFrameNumber> Target = Transport.GetLastPlayToTargetForTests();
    TestTrue(TEXT("Toward the Show start (an earlier frame: a reverse play)"),
        Target.IsSet() && Target.GetValue() == Transport.Segments[0].StartFrame && Target.GetValue() < Middle);

    TestEqual(TEXT("Key-up (was held) ends it"), Transport.EndRewind(false), EInfinityTransportResult::Succeeded);
    TestFalse(TEXT("No rewind after key-up"), Transport.IsRewindActive());
    TestEqual(TEXT("1x restored"), Fixture.Player->GetPlayRate(), 1.0f);
    TestFalse(TEXT("A held start stays held"), Transport.IsTransportPlaying());

    Transport.ScrubToMasterFrame(Middle);
    Transport.BeginRewind();
    TestEqual(TEXT("Key-up (was playing) plays forward again"), Transport.EndRewind(true), EInfinityTransportResult::Succeeded);
    TestTrue(TEXT("Playing again"), Transport.IsTransportPlaying());
    TestEqual(TEXT("...forward at 1x"), Fixture.Player->GetPlayRate(), 1.0f);
    TestFalse(TEXT("...not reversed"), Fixture.Player->IsReversed());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRewindInterlockTest,
    "InfinityStage.Transport.HoldLeftRewind.RespectsPerformanceInterlock",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRewindInterlockTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageHoldLeftRewindTests;
    FRewindFixture Fixture;
    if (!Fixture.Initialize(*this, true))
    {
        return false;
    }
    UInfinityStageTransportController& Transport = *Fixture.Transport;
    TestEqual(TEXT("Fixture: S1 is a live-performer clock"),
        Transport.Segments[1].ExternalSound, EInfinityExternalSoundAuthority::DeclaredUnpausable);

    // Inside the live segment in performance mode: refused like fast-forward (result=4).
    Transport.bPerformanceMode = false;
    Transport.ScrubToMasterFrame(Transport.Segments[1].StartFrame + FFrameNumber(10));
    Transport.bPerformanceMode = true;
    TestEqual(TEXT("Refused inside a live clock"), Transport.BeginRewind(), EInfinityTransportResult::UnsafeExternalClock);
    TestEqual(TEXT("...exactly as fast-forward is"), Transport.BeginFastForward(), EInfinityTransportResult::UnsafeExternalClock);
    TestFalse(TEXT("Nothing left active"), Transport.IsRewindActive());

    // From P02: never rewinds INTO S1; it stops on S1's end.
    Transport.bPerformanceMode = false;
    Transport.ScrubToMasterFrame(Transport.Segments[2].StartFrame + FFrameNumber(30));
    Transport.bPerformanceMode = true;
    TestEqual(TEXT("Allowed from P02"), Transport.BeginRewind(), EInfinityTransportResult::Succeeded);
    const TOptional<FFrameNumber> Target = Transport.GetLastPlayToTargetForTests();
    TestTrue(TEXT("Stops at S1's end, not inside it"),
        Target.IsSet() && Target.GetValue() == Transport.Segments[1].EndFrame);
    Transport.EndRewind(false);

    // Control: rehearsal mode lifts the interlock, as it does for every other move.
    Transport.bPerformanceMode = false;
    Transport.ScrubToMasterFrame(Transport.Segments[2].StartFrame + FFrameNumber(30));
    TestEqual(TEXT("Rehearsal: allowed"), Transport.BeginRewind(), EInfinityTransportResult::Succeeded);
    const TOptional<FFrameNumber> RehearsalTarget = Transport.GetLastPlayToTargetForTests();
    TestTrue(TEXT("Rehearsal: all the way to the start"),
        RehearsalTarget.IsSet() && RehearsalTarget.GetValue() == Transport.Segments[0].StartFrame);
    Transport.EndRewind(false);
    return true;
}

#endif
