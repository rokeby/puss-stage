#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Run-Through (Gary, 7 Oct): one checkbox for unattended recordings. Play once
 * at the start and the show runs to the end of the Closing: GO HOLDs pass, vamps
 * play once, Scenes do not hold at their end. Off, nothing changes.
 */
namespace InfinityStageRunThroughTests
{
TArray<FInfinityGoCue> RunThroughHoldCues()
{
    TArray<FInfinityGoCue> Cues;
    const int32 Frames[] = {100, 150, 200};
    const bool Holds[] = {true, false, true};
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Frames); ++Index)
    {
        FInfinityGoCue& Cue = Cues.AddDefaulted_GetRef();
        Cue.Frame = Frames[Index];
        Cue.bHold = Holds[Index];
        Cue.Number = FString::FromInt(Index + 1);
    }
    return Cues;
}

/** Opening, Passage, Scene, Interaction, Passage, Scene, Closing: contiguous. */
UInfinityStageTransportController* MakeRunThroughTransport()
{
    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>(GetTransientPackage());
    const EInfinityCueType Types[] = {
        EInfinityCueType::Sequence, EInfinityCueType::WingPair, EInfinityCueType::Scene,
        EInfinityCueType::Sequence, EInfinityCueType::WingPair, EInfinityCueType::Scene,
        EInfinityCueType::Sequence };
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Types); ++Index)
    {
        FInfinityTransportSegment& Segment = Transport->Segments.AddDefaulted_GetRef();
        Segment.Type = Types[Index];
        Segment.StartFrame = Index * 100;
        Segment.EndFrame = (Index + 1) * 100;
    }
    return Transport;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRunThroughHoldsPassTest,
    "InfinityStage.Transport.RunThrough.HoldsPassAndVampsPlayOnce",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRunThroughHoldsPassTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageRunThroughTests;
    const TArray<FInfinityGoCue> Cues = RunThroughHoldCues();

    // Run-through: a 1x forward sweep across every HOLD never returns one.
    FInfinityGoHoldState RunState;
    RunState.SettleOffset = 2;
    RunState.bPassAll = true;
    RunState.Tick(0, true, Cues);
    int32 HoldsReturned = 0;
    for (int32 Frame = 5; Frame <= 300; Frame += 5)
    {
        HoldsReturned += RunState.Tick(Frame, true, Cues) != INDEX_NONE ? 1 : 0;
    }
    TestEqual(TEXT("Run-through: no HOLD ever stops the sweep"), HoldsReturned, 0);
    TestFalse(TEXT("Run-through: no hold is active at the end"), RunState.IsActive());
    // One big step across both holds as well (a long frame hitch).
    RunState.OnNavigation(0);
    RunState.Tick(0, true, Cues);
    TestEqual(TEXT("Run-through: one tick across both holds returns none"), RunState.Tick(300, true, Cues), int32(INDEX_NONE));

    // Control (off): the same sweep stops on GO 1 - the existing expectation.
    FInfinityGoHoldState OffState;
    OffState.SettleOffset = 2;
    OffState.Tick(0, true, Cues);
    TestEqual(TEXT("Control off: crossing GO 1 holds"), OffState.Tick(105, true, Cues), 0);

    // Switched off mid-show: only the holds still ahead arm.
    FInfinityGoHoldState Toggle;
    Toggle.SettleOffset = 2;
    Toggle.bPassAll = true;
    Toggle.Tick(0, true, Cues);
    TestEqual(TEXT("On: GO 1 passes"), Toggle.Tick(120, true, Cues), int32(INDEX_NONE));
    Toggle.bPassAll = false;
    TestEqual(TEXT("Off again: GO 1, already behind, does not fire late"), Toggle.Tick(125, true, Cues), int32(INDEX_NONE));
    TestEqual(TEXT("Off again: GO 3 ahead holds"), Toggle.Tick(205, true, Cues), 2);

    // Vamps: run-through plays the range once and continues.
    TArray<FInfinityVampRange> Ranges;
    FInfinityVampRange& Range = Ranges.AddDefaulted_GetRef();
    Range.StartFrame = 100;
    Range.EndFrame = 200;
    Range.SegmentIndex = 0;
    FFrameNumber LoopFrame;

    FInfinityVampPlaybackState RunVamp;
    RunVamp.bPlayOnce = true;
    RunVamp.Tick(90, true, false, 1.0f, Ranges, LoopFrame);
    int32 NonNoneActions = 0;
    for (int32 Frame = 95; Frame <= 260; Frame += 5)
    {
        NonNoneActions += RunVamp.Tick(Frame, true, false, 1.0f, Ranges, LoopFrame) != EInfinityVampPlaybackAction::None ? 1 : 0;
    }
    NonNoneActions += RunVamp.Tick(265, true, false, 4.0f, Ranges, LoopFrame) != EInfinityVampPlaybackAction::None ? 1 : 0;
    TestEqual(TEXT("Run-through: a vamp never loops or normalizes"), NonNoneActions, 0);
    TestFalse(TEXT("Run-through: no vamp is active"), RunVamp.IsActive());

    // Control (off): the same crossing loops.
    FInfinityVampPlaybackState OffVamp;
    OffVamp.Tick(90, true, false, 1.0f, Ranges, LoopFrame);
    OffVamp.Tick(110, true, false, 1.0f, Ranges, LoopFrame);
    TestTrue(TEXT("Control off: the vamp is armed"), OffVamp.IsActive());
    TestEqual(TEXT("Control off: reaching its end loops"),
        OffVamp.Tick(205, true, false, 1.0f, Ranges, LoopFrame), EInfinityVampPlaybackAction::LoopToStart);

    // Switched on while a vamp is looping: it is released and play continues.
    OffVamp.bPlayOnce = true;
    TestEqual(TEXT("Switched on mid-vamp: no loop"),
        OffVamp.Tick(150, true, false, 1.0f, Ranges, LoopFrame), EInfinityVampPlaybackAction::None);
    TestFalse(TEXT("Switched on mid-vamp: released"), OffVamp.IsActive());
    TestEqual(TEXT("Switched on mid-vamp: its end passes"),
        OffVamp.Tick(205, true, false, 1.0f, Ranges, LoopFrame), EInfinityVampPlaybackAction::None);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRunThroughSceneEndContinuesTest,
    "InfinityStage.Transport.RunThrough.SceneEndContinuesToShowEnd",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRunThroughSceneEndContinuesTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageRunThroughTests;
    using UTransport = UInfinityStageTransportController;
    UInfinityStageTransportController* Transport = MakeRunThroughTransport();
    const int32 Last = Transport->Segments.Num() - 1;

    TestFalse(TEXT("Shipped default: run-through is off"), Transport->bRunThrough);
    // Controls (off): the existing stops are unchanged.
    TestEqual(TEXT("Off: the Opening stops at its end"), Transport->GetForwardStopSegmentIndex(0), 0);
    TestEqual(TEXT("Off: a Passage stops at its end"), Transport->GetForwardStopSegmentIndex(1), 1);
    TestEqual(TEXT("Off: a Scene holds at its end"), Transport->GetForwardStopSegmentIndex(2), 2);
    Transport->bAutoPlaySceneAfterPassage = true;
    TestEqual(TEXT("Off, auto Scene: Passage plays through its Scene only"), Transport->GetForwardStopSegmentIndex(1), 2);
    Transport->bAutoPlaySceneAfterPassage = false;

    Transport->bRunThrough = true;
    for (int32 Index = 0; Index <= Last; ++Index)
    {
        TestEqual(FString::Printf(TEXT("Run-through: segment %d plays to the Show's end"), Index),
            Transport->GetForwardStopSegmentIndex(Index), Last);
    }
    TestEqual(TEXT("Run-through: the Scene end is not a stop"), Transport->GetForwardStopSegmentIndex(5), Last);
    TestEqual(TEXT("Run-through: invalid selection still has no target"),
        Transport->GetForwardStopSegmentIndex(INDEX_NONE), int32(INDEX_NONE));

    const EInfinityCueType Types[] = { EInfinityCueType::Sequence, EInfinityCueType::Scene, EInfinityCueType::WingPair };
    for (const EInfinityCueType Type : Types)
    {
        TestTrue(TEXT("Run-through: every Advance landing plays"),
            UTransport::PlaysOnAdvanceLanding(Type, false, false, true));
        for (int32 Bits = 0; Bits < 4; ++Bits)
        {
            const bool bSequence = (Bits & 1) != 0;
            const bool bScene = (Bits & 2) != 0;
            TestEqual(TEXT("Off: landing rule identical to AutoPlaysOnAdvance"),
                UTransport::PlaysOnAdvanceLanding(Type, bSequence, bScene, false),
                UTransport::AutoPlaysOnAdvance(Type, bSequence, bScene));
        }
    }
    return true;
}

#endif
