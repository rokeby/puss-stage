#include "InfinityStageRehearsalBar.h"
#include "InfinityStageShowTrims.h"
#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
TArray<FInfinityTransportSegment> FourSegments()
{
    TArray<FInfinityTransportSegment> Segments;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        FInfinityTransportSegment& Segment = Segments.AddDefaulted_GetRef();
        Segment.SegmentGuid = FGuid::NewGuid();
        Segment.Label = FText::FromString(FString::Printf(TEXT("Seg%d"), Index));
        Segment.StartFrame = Index * 1000;
        Segment.EndFrame = (Index + 1) * 1000;
    }
    return Segments;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRehearsalNextStopTest,
    "InfinityStage.CueDirector.RehearsalBarNextStop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRehearsalNextStopTest::RunTest(const FString& Parameters)
{
    using InfinityStageRehearsal::NextStop;
    const TArray<FInfinityTransportSegment> Segments = FourSegments();
    TArray<FInfinityGoCue> Gos;
    FInfinityGoCue& Go = Gos.AddDefaulted_GetRef();
    Go.Frame = 1500;
    Go.bHold = true;
    Go.Number = TEXT("10");
    Go.Label = TEXT("curtain");

    FInfinityNextStop Stop = NextStop(Segments, Gos, 1200, false, {}, {});
    TestEqual(TEXT("Segment mode: a held GO before the segment end comes first"), Stop.Frame, FFrameNumber(1500));
    TestEqual(TEXT("...and is named"), Stop.Label, FString(TEXT("GO 10 curtain")));
    Stop = NextStop(Segments, Gos, 1600, false, {}, {});
    TestEqual(TEXT("Past the GO: the segment end"), Stop.Frame, FFrameNumber(2000));
    TestEqual(TEXT("...named by its segment"), Stop.Label, FString(TEXT("end of Seg1")));

    Stop = NextStop(Segments, Gos, 1200, true, {Segments[2].SegmentGuid}, {});
    TestEqual(TEXT("Run-through passes the unkept GO and stops after the ticked segment"), Stop.Frame, FFrameNumber(3000));
    Stop = NextStop(Segments, Gos, 1200, true, {Segments[2].SegmentGuid}, {TEXT("10")});
    TestEqual(TEXT("A kept GO still stops the run-through"), Stop.Frame, FFrameNumber(1500));
    Stop = NextStop(Segments, Gos, 3200, true, {Segments[2].SegmentGuid}, {});
    TestEqual(TEXT("Control: past the last stop it runs to the show end"), Stop.Label, FString(TEXT("show end")));
    TestEqual(TEXT("...at the last frame"), Stop.Frame, FFrameNumber(4000));
    TestFalse(TEXT("Control: no segments, no stop"), NextStop({}, Gos, 0, false, {}, {}).bValid);
    TestEqual(TEXT("Clock format"), InfinityStageRehearsal::Clock(125.36), FString(TEXT("2:05.4")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShowTrimsTest,
    "InfinityStage.CueDirector.ShowTrimsNeutralLeavesTheLook",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShowTrimsTest::RunTest(const FString& Parameters)
{
    FPostProcessSettings Settings;
    const FInfinityShowTrimValues Neutral;
    TestEqual(TEXT("Neutral trims override nothing: the show's own look stays"), InfinityStageShowTrims::BuildPostProcess(Neutral, Settings), 0);
    TestFalse(TEXT("...no colour gain override"), static_cast<bool>(Settings.bOverride_ColorGain));
    TestFalse(TEXT("...no saturation override"), static_cast<bool>(Settings.bOverride_ColorSaturation));

    FInfinityShowTrimValues Darker;
    Darker.ExposureEv = -1.0f;
    Darker.Saturation = 0.8f;
    TestEqual(TEXT("Two trims away from neutral, two overrides"), InfinityStageShowTrims::BuildPostProcess(Darker, Settings), 2);
    TestTrue(TEXT("-1 EV is half the gain"), FMath::IsNearlyEqual(static_cast<float>(Settings.ColorGain.X), 0.5f, 1.0e-4f));
    TestTrue(TEXT("Saturation applied"), FMath::IsNearlyEqual(static_cast<float>(Settings.ColorSaturation.Y), 0.8f, 1.0e-4f));

    TestEqual(TEXT("Back to neutral clears the overrides again"), InfinityStageShowTrims::BuildPostProcess(Neutral, Settings), 0);
    TestFalse(TEXT("...gain override off"), static_cast<bool>(Settings.bOverride_ColorGain));

    TestTrue(TEXT("0 dB is unity"), FMath::IsNearlyEqual(InfinityStageShowTrims::DbToGain(0.0f), 1.0f, 1.0e-5f));
    TestTrue(TEXT("-6 dB is about half"), FMath::IsNearlyEqual(InfinityStageShowTrims::DbToGain(-6.0f), 0.501f, 1.0e-3f));
    TestEqual(TEXT("-80 dB is silence"), InfinityStageShowTrims::DbToGain(-80.0f), 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRehearsalScrubTest,
    "InfinityStage.CueDirector.ScrubFractionStaysInsideTheSegment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRehearsalScrubTest::RunTest(const FString& Parameters)
{
    using InfinityStageRehearsal::FrameAtFraction;
    TestEqual(TEXT("0 is the segment start"), FrameAtFraction(1000, 2000, 0.0f), FFrameNumber(1000));
    TestEqual(TEXT("Half way"), FrameAtFraction(1000, 2000, 0.5f), FFrameNumber(1500));
    TestEqual(TEXT("1 stays one frame inside (never the next segment)"), FrameAtFraction(1000, 2000, 1.0f), FFrameNumber(1999));
    TestEqual(TEXT("Control: out-of-range fractions clamp"), FrameAtFraction(1000, 2000, 7.0f), FFrameNumber(1999));
    TestEqual(TEXT("Control: negative clamps to the start"), FrameAtFraction(1000, 2000, -1.0f), FFrameNumber(1000));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageFastForwardSkimTest,
    "InfinityStage.CueDirector.FastForwardSkimPassesKeptHolds",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Gary (8 Oct): fast-forward should skim the show without stopping. The transport sets
// bPassAll and empties KeepNumbers while RIGHT is held; this is the hold state's side of it.
bool FInfinityStageFastForwardSkimTest::RunTest(const FString& Parameters)
{
    TArray<FInfinityGoCue> Cues;
    FInfinityGoCue& Cue = Cues.AddDefaulted_GetRef();
    Cue.Frame = 100;
    Cue.bHold = true;
    Cue.Number = TEXT("10");

    FInfinityGoHoldState Skim;
    Skim.bPassAll = true;          // fast-forward
    Skim.Tick(50, true, Cues);
    TestEqual(TEXT("A skim passes even a kept GO"), Skim.Tick(150, true, Cues), int32(INDEX_NONE));

    FInfinityGoHoldState Kept;
    Kept.bPassAll = true;          // run-through at 1x
    Kept.KeepNumbers.Add(TEXT("10"));
    Kept.Tick(50, true, Cues);
    TestEqual(TEXT("Control: at 1x run-through the kept GO holds"), Kept.Tick(150, true, Cues), 0);
    return true;
}

#endif
