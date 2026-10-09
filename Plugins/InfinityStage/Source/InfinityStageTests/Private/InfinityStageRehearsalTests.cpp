#include "InfinityStageRehearsalBar.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageShowTrims.h"
#include "InfinityStageSurtitles.h"
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSurtitleButtonsTest,
    "InfinityStage.CueDirector.SurtitleButtonsCallTheRightThing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Gary 9 Oct: surtitles "part of the cue director interface to be adjustable and rehearsable".
bool FInfinityStageSurtitleButtonsTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageRehearsal;
    using EKind = FInfinitySurtitleCall::EKind;
    const FInfinitySurtitleCall Prev = PlanSurtitleAction(ESurtitleAction::Previous);
    const FInfinitySurtitleCall Next = PlanSurtitleAction(ESurtitleAction::Next);
    TestTrue(TEXT("prev steps back one line"), Prev.Kind == EKind::Step && Prev.Delta == -1);
    TestTrue(TEXT("next steps on one line"), Next.Kind == EKind::Step && Next.Delta == 1);
    const FInfinitySurtitleCall StampIn = PlanSurtitleAction(ESurtitleAction::StampIn);
    const FInfinitySurtitleCall StampOut = PlanSurtitleAction(ESurtitleAction::StampOut);
    TestTrue(TEXT("Stamp In stamps the In"), StampIn.Kind == EKind::Stamp && !StampIn.bOut);
    TestTrue(TEXT("Stamp Out stamps the Out"), StampOut.Kind == EKind::Stamp && StampOut.bOut);
    const FInfinitySurtitleCall InEarlier = PlanSurtitleAction(ESurtitleAction::InEarlier);
    const FInfinitySurtitleCall OutLater = PlanSurtitleAction(ESurtitleAction::OutLater);
    TestTrue(TEXT("In - nudges the In 0.25 s earlier"),
        InEarlier.Kind == EKind::Nudge && !InEarlier.bOut && FMath::IsNearlyEqual(InEarlier.Seconds, -0.25));
    TestTrue(TEXT("Out + nudges the Out 0.25 s later"),
        OutLater.Kind == EKind::Nudge && OutLater.bOut && FMath::IsNearlyEqual(OutLater.Seconds, 0.25));
    // Control: the four nudges are four different calls (a copy-paste slip would collapse two of them).
    TSet<FString> Distinct;
    for (const ESurtitleAction A : {ESurtitleAction::InEarlier, ESurtitleAction::InLater, ESurtitleAction::OutEarlier, ESurtitleAction::OutLater})
    {
        const FInfinitySurtitleCall C = PlanSurtitleAction(A);
        Distinct.Add(FString::Printf(TEXT("%d/%.2f"), C.bOut ? 1 : 0, C.Seconds));
    }
    TestEqual(TEXT("Control: four distinct nudges"), Distinct.Num(), 4);
    // Negative control: without a game world nothing is called and the bar says why.
    TestTrue(TEXT("Control: no world -> refused, with a reason"), SurtitleAction(nullptr, ESurtitleAction::Next).StartsWith(TEXT("Not done")));
    TestTrue(TEXT("Control: no world -> nothing to describe"), DescribeSurtitle(nullptr).IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageP86AtParsingTest,
    "InfinityStage.Rehearsal.P86.AtParsing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageP86AtParsingTest::RunTest(const FString& Parameters)
{
    const FString TimedCsv =
        TEXT(",Light,Video Cue,Speaker,At\n")
        TEXT(",,,Klara,\n")
        TEXT(",up,Passage 1,,1:02.5\n")
        TEXT(",,,,00:00:03:12\n")
        TEXT(",,,bad row,1e3\n");
    FInfinityCueSheet Timed;
    TestTrue(TEXT("At sheet loads"), Timed.LoadFromCsvText(TimedCsv));
    TestEqual(TEXT("valid m:ss time is retained"), Timed.Rows[0].AtSeconds, 62.5);
    TestTrue(TEXT("valid time is marked present"), Timed.Rows[0].bHasAtTime);
    TestTrue(TEXT("At-only rows are retained for stepping and ticks"), Timed.Rows[1].bHasAtTime);
    TestTrue(TEXT("25 fps timecode matches Cue Book validation"), FMath::IsNearlyEqual(Timed.Rows[1].AtSeconds, 3.48));
    TestFalse(TEXT("bad At is ignored"), Timed.Rows[2].bHasAtTime);
    TestEqual(TEXT("bad At produces exactly one warning"), Timed.Warnings.Num(), 1);

    FInfinityCueSheet NoAt;
    TestTrue(TEXT("control: a sheet with no At column still loads"),
        NoAt.LoadFromCsvText(TEXT(",Light,Speaker\n,,Klara\n,up,line\n")));
    TestEqual(TEXT("control: absent At column produces no warning"), NoAt.Warnings.Num(), 0);
    TestFalse(TEXT("control: absent At leaves the row untimed"), NoAt.Rows[0].bHasAtTime);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageP86ScriptStepTest,
    "InfinityStage.Rehearsal.P86.ScriptStepScrubsTimedRows",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageP86ScriptStepTest::RunTest(const FString& Parameters)
{
    FInfinityCueSheet Sheet;
    Sheet.Rows.SetNum(3);
    for (FInfinityCueSheetRow& Row : Sheet.Rows)
    {
        Row.Action = TEXT("step");
        Row.SegmentOrdinal = 0;
    }
    Sheet.Rows[1].bHasAtTime = true;
    Sheet.Rows[1].AtSeconds = 2.5;
    FInfinityScriptCursor Cursor;
    TArray<FInfinityTransportSegment> Segments = FourSegments();
    Segments[0].StartFrame = 1000;
    Segments[0].EndFrame = 2000;

    InfinityStageRehearsal::FScriptStepPlan Plan = InfinityStageRehearsal::PlanScriptStep(Cursor, Sheet, 1, Segments, 100.0);
    TestTrue(TEXT("timed row moves the cursor"), Plan.bMoved && Cursor.Row == 1);
    TestTrue(TEXT("timed row requests a scrub"), Plan.ScrubFrame.IsSet());
    TestEqual(TEXT("At is relative to segment start"), Plan.ScrubFrame.Get(FFrameNumber(-1)), FFrameNumber(1250));

    Plan = InfinityStageRehearsal::PlanScriptStep(Cursor, Sheet, 1, Segments, 100.0);
    TestTrue(TEXT("untimed row still moves the pointer"), Plan.bMoved && Cursor.Row == 2);
    TestFalse(TEXT("untimed row leaves the playhead alone"), Plan.ScrubFrame.IsSet());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageP86DragMappingTest,
    "InfinityStage.Rehearsal.P86.DragMapsFractionToFrame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageP86DragMappingTest::RunTest(const FString& Parameters)
{
    using InfinityStageRehearsal::FrameAtFraction;
    TestEqual(TEXT("drag at start"), FrameAtFraction(1000, 2000, 0.0f), FFrameNumber(1000));
    TestEqual(TEXT("drag in middle"), FrameAtFraction(1000, 2000, 0.25f), FFrameNumber(1250));
    TestEqual(TEXT("negative control: end cannot spill into next segment"), FrameAtFraction(1000, 2000, 1.0f), FFrameNumber(1999));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageP86MarkerLayoutTest,
    "InfinityStage.Rehearsal.P86.MarkerLayout",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageP86MarkerLayoutTest::RunTest(const FString& Parameters)
{
    TArray<FInfinityTransportSegment> Segments = FourSegments();
    Segments[0].StartFrame = 1000;
    Segments[0].EndFrame = 2000;
    FInfinityCueSheet Sheet;
    FInfinityCueSheetRow& Row = Sheet.Rows.AddDefaulted_GetRef();
    Row.bHasAtTime = true;
    Row.AtSeconds = 2.5;
    Row.SegmentOrdinal = 0;
    FInfinitySurtitleScript Surtitles;
    FInfinitySurtitleLine& Line = Surtitles.Lines.AddDefaulted_GetRef();
    Line.Segment = TEXT("Seg0");
    Line.InSeconds = 2.0;
    Line.OutSeconds = 4.0;
    TArray<FInfinityGoCue> Gos;
    Gos.AddDefaulted_GetRef().Frame = 1500;

    const TArray<FInfinityRehearsalMarker> Marks = InfinityStageRehearsal::LayoutMarkers(
        Sheet, Surtitles, Segments, Gos, 0, 100.0);
    TestEqual(TEXT("script, surtitle and GO are all laid out"), Marks.Num(), 3);
    const FInfinityRehearsalMarker* Script = Marks.FindByPredicate([](const FInfinityRehearsalMarker& Mark) { return Mark.Kind == EInfinityRehearsalMarkerKind::Script; });
    const FInfinityRehearsalMarker* Surtitle = Marks.FindByPredicate([](const FInfinityRehearsalMarker& Mark) { return Mark.Kind == EInfinityRehearsalMarkerKind::Surtitle; });
    const FInfinityRehearsalMarker* Go = Marks.FindByPredicate([](const FInfinityRehearsalMarker& Mark) { return Mark.Kind == EInfinityRehearsalMarkerKind::Go; });
    TestTrue(TEXT("script tick is at 25%"), Script && FMath::IsNearlyEqual(Script->StartFraction, 0.25f));
    TestTrue(TEXT("surtitle is a 20%-40% span"), Surtitle && FMath::IsNearlyEqual(Surtitle->StartFraction, 0.2f)
        && FMath::IsNearlyEqual(Surtitle->EndFraction, 0.4f));
    TestTrue(TEXT("GO tick is at 50%"), Go && FMath::IsNearlyEqual(Go->StartFraction, 0.5f));
    TestTrue(TEXT("negative control: invalid segment yields no markers"),
        InfinityStageRehearsal::LayoutMarkers(Sheet, Surtitles, Segments, Gos, 99, 100.0).IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageP86LongHoldFastForwardTest,
    "InfinityStage.Rehearsal.P86.LongHoldFastForward",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageP86LongHoldFastForwardTest::RunTest(const FString& Parameters)
{
    FInfinityHoldRightState Hold;
    Hold.Press(false);
    TestEqual(TEXT("4x begins at the ordinary threshold"), Hold.Tick(0.30f, 0.30f, 5.0f), EInfinityHoldRightAction::BeginFastForward);
    Hold.ResolveFastForwardStart(EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("still 4x before five seconds"), Hold.Tick(4.69f, 0.30f, 5.0f), EInfinityHoldRightAction::None);
    TestEqual(TEXT("8x begins after five continuous seconds"), Hold.Tick(0.02f, 0.30f, 5.0f), EInfinityHoldRightAction::BeginLongHoldFastForward);
    TestEqual(TEXT("release uses today's held-release path"), Hold.Release(), EInfinityHoldRightAction::EndFastForwardHeld);
    TestEqual(TEXT("release resets the machine"), Hold.Tick(10.0f, 0.30f, 5.0f), EInfinityHoldRightAction::None);

    FInfinityHoldRightState Refused;
    Refused.Press(true);
    TestEqual(TEXT("negative control reaches the ordinary hold"), Refused.Tick(0.30f, 0.30f, 5.0f), EInfinityHoldRightAction::BeginFastForward);
    Refused.ResolveFastForwardStart(EInfinityTransportResult::UnsafeExternalClock);
    TestEqual(TEXT("negative control: refused 4x never escalates"), Refused.Tick(10.0f, 0.30f, 5.0f), EInfinityHoldRightAction::None);
    TestEqual(TEXT("refused hold stays consumed on release"), Refused.Release(), EInfinityHoldRightAction::None);
    return true;
}

#endif
