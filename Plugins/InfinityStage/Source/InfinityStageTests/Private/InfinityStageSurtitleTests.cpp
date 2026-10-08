#include "InfinityStageSurtitles.h"
#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
constexpr double Ticks = 24000.0;

FInfinityTransportSegment MakeSegment(const EInfinityCueType Type, const TCHAR* Label, const double StartSeconds, const double EndSeconds)
{
    FInfinityTransportSegment Segment;
    Segment.Type = Type;
    Segment.Label = FText::FromString(Label);
    Segment.StartFrame = FFrameNumber(int32(StartSeconds * Ticks));
    Segment.EndFrame = FFrameNumber(int32(EndSeconds * Ticks));
    return Segment;
}

/** Passage 1 [0,100), Scene 1 [100,200), Passage 2 [200,300), Scene 2 "Mountains" [300,452.341). */
TArray<FInfinityTransportSegment> MakeShow()
{
    return {
        MakeSegment(EInfinityCueType::WingPair, TEXT("Passage 1"), 0.0, 100.0),
        MakeSegment(EInfinityCueType::Scene, TEXT("S1 Animals"), 100.0, 200.0),
        MakeSegment(EInfinityCueType::WingPair, TEXT("Passage 2"), 200.0, 300.0),
        MakeSegment(EInfinityCueType::Scene, TEXT("Mountains"), 300.0, 452.341),
    };
}

int64 At(const double MasterSeconds)
{
    return int64(MasterSeconds * Ticks);
}

// The Google Sheet export shape: a title row, the header, carry-down segments, a quoted
// multi-line cell, a clear row (time, no text), a bad time, and a Passage line by label.
const TCHAR* SheetCsv =
    TEXT("Surtitles,,,,,\n")
    TEXT("Segment,In,Out,Speaker,Text,Notes\n")
    TEXT("S2,1:14,1:25,West,\"We have been here\na while.\",slow\n")
    TEXT(",1:40,,East,Yes.,\n")
    TEXT(",2:01,,,,clear\n")
    TEXT(",2:10,2:05,West,Out before In,\n")
    TEXT(",soon,,West,Bad time,\n")
    TEXT("Passage 2,00:00:10:12,,,On the road,\n")
    TEXT(",,,,No time at all,\n");
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSurtitleTimeTest,
    "InfinityStage.Surtitles.ParseTime",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSurtitleTimeTest::RunTest(const FString& Parameters)
{
    double Seconds = -1.0;
    TestTrue(TEXT("Plain seconds"), InfinityStageSurtitles::ParseTime(TEXT("74.5"), 25.0, Seconds));
    TestEqual(TEXT("...74.5"), Seconds, 74.5);
    TestTrue(TEXT("m:ss.s"), InfinityStageSurtitles::ParseTime(TEXT(" 1:14.5 "), 25.0, Seconds));
    TestEqual(TEXT("...74.5"), Seconds, 74.5);
    TestTrue(TEXT("h:mm:ss"), InfinityStageSurtitles::ParseTime(TEXT("1:00:01"), 25.0, Seconds));
    TestEqual(TEXT("...3601"), Seconds, 3601.0);
    TestTrue(TEXT("hh:mm:ss:ff at 25 fps"), InfinityStageSurtitles::ParseTime(TEXT("00:02:01:05"), 25.0, Seconds));
    TestEqual(TEXT("...121.2"), Seconds, 121.2, 1e-9);
    TestFalse(TEXT("Control: frame 25 is out of range at 25 fps"), InfinityStageSurtitles::ParseTime(TEXT("00:00:01:25"), 25.0, Seconds));
    TestFalse(TEXT("Control: words are not a time"), InfinityStageSurtitles::ParseTime(TEXT("soon"), 25.0, Seconds));
    TestFalse(TEXT("Control: negative is not a time"), InfinityStageSurtitles::ParseTime(TEXT("-3"), 25.0, Seconds));
    TestFalse(TEXT("Control: empty is not a time"), InfinityStageSurtitles::ParseTime(TEXT(""), 25.0, Seconds));
    TestEqual(TEXT("FormatTime"), InfinityStageSurtitles::FormatTime(74.5), FString(TEXT("1:14.50")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSurtitleSheetTest,
    "InfinityStage.Surtitles.SheetLoads",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSurtitleSheetTest::RunTest(const FString& Parameters)
{
    FInfinitySurtitleScript Script;
    TestTrue(TEXT("The sheet loads"), Script.LoadFromCsvText(SheetCsv));
    // Kept: 1:14, 1:40, 2:01 (clear), Passage 2. Dropped with a warning: Out<In, bad time, no time.
    TestEqual(TEXT("Four lines kept"), Script.Lines.Num(), 4);
    TestEqual(TEXT("Three warnings"), Script.Warnings.Num(), 3);
    if (Script.Lines.Num() == 4)
    {
        TestEqual(TEXT("Row numbers are the sheet's, 1-based"), Script.Lines[0].SourceRow, 3);
        TestEqual(TEXT("Multi-line cell kept"), Script.Lines[0].Text, FString(TEXT("We have been here\na while.")));
        TestEqual(TEXT("Explicit Out"), Script.Lines[0].OutSeconds, 85.0);
        TestEqual(TEXT("Segment carries down"), Script.Lines[1].Segment, FString(TEXT("S2")));
        TestTrue(TEXT("Blank Out holds"), Script.Lines[1].OutSeconds < 0.0);
        TestTrue(TEXT("A clear row has no text"), Script.Lines[2].Text.IsEmpty());
        TestEqual(TEXT("Label segment"), Script.Lines[3].Segment, FString(TEXT("Passage 2")));
        TestEqual(TEXT("SMPTE In"), Script.Lines[3].InSeconds, 10.48, 1e-9);
    }

    FInfinitySurtitleScript NoHeader;
    TestFalse(TEXT("Control: a sheet with no Segment header fails"), NoHeader.LoadFromCsvText(TEXT("a,b\n1,2\n")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSurtitleSegmentTest,
    "InfinityStage.Surtitles.SegmentCodesMatchCueDirector",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSurtitleSegmentTest::RunTest(const FString& Parameters)
{
    const TArray<FInfinityTransportSegment> Show = MakeShow();
    TestEqual(TEXT("P1"), InfinityStageSurtitles::SegmentCode(Show, 0), FString(TEXT("P1")));
    TestEqual(TEXT("S1 counts Scenes only"), InfinityStageSurtitles::SegmentCode(Show, 1), FString(TEXT("S1")));
    TestEqual(TEXT("P2"), InfinityStageSurtitles::SegmentCode(Show, 2), FString(TEXT("P2")));
    TestEqual(TEXT("S2"), InfinityStageSurtitles::SegmentCode(Show, 3), FString(TEXT("S2")));
    TestEqual(TEXT("Code, any case"), InfinityStageSurtitles::ResolveSegment(TEXT("s2"), Show), 3);
    TestEqual(TEXT("Cue label, any case"), InfinityStageSurtitles::ResolveSegment(TEXT(" mountains "), Show), 3);
    TestEqual(TEXT("Control: S3 does not exist"), InfinityStageSurtitles::ResolveSegment(TEXT("S3"), Show), INDEX_NONE);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSurtitleEvaluateTest,
    "InfinityStage.Surtitles.EvaluateFollowsPlayhead",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSurtitleEvaluateTest::RunTest(const FString& Parameters)
{
    const TArray<FInfinityTransportSegment> Show = MakeShow();
    FInfinitySurtitleScript Script;
    Script.LoadFromCsvText(SheetCsv);

    auto LineAt = [&](const double MasterSeconds, const double Fade = 0.0)
    {
        return InfinityStageSurtitles::Evaluate(Script, Show, At(MasterSeconds), Ticks, Fade);
    };

    // Mountains (S2) starts at Master 300 s.
    TestEqual(TEXT("Control: nothing before the first line"), LineAt(300.0 + 73.9).LineIndex, INDEX_NONE);
    TestEqual(TEXT("First line at its In"), LineAt(300.0 + 74.0).LineIndex, 0);
    TestEqual(TEXT("First line ends at its explicit Out"), LineAt(300.0 + 85.0).LineIndex, INDEX_NONE);
    TestEqual(TEXT("Second line held (blank Out)"), LineAt(300.0 + 120.0).LineIndex, 1);
    TestEqual(TEXT("A clear row ends the held line"), LineAt(300.0 + 121.0).LineIndex, 2);
    TestTrue(TEXT("...and shows no text"), Script.Lines[LineAt(300.0 + 121.0).LineIndex].Text.IsEmpty());
    TestEqual(TEXT("Passage line by label, held to the segment end"), LineAt(200.0 + 99.9).LineIndex, 3);
    TestEqual(TEXT("Control: the same offset in another segment shows nothing"), LineAt(100.0 + 74.0).LineIndex, INDEX_NONE);
    TestEqual(TEXT("Control: past the show end shows nothing"), LineAt(500.0).LineIndex, INDEX_NONE);

    // Pure function of the playhead: a seek back lands on the same answer.
    const FInfinitySurtitleShown Forward = LineAt(300.0 + 80.0, 0.3);
    LineAt(300.0 + 140.0, 0.3);
    const FInfinitySurtitleShown Back = LineAt(300.0 + 80.0, 0.3);
    TestEqual(TEXT("Seek back: same line"), Back.LineIndex, Forward.LineIndex);
    TestEqual(TEXT("Seek back: same opacity"), Back.Opacity, Forward.Opacity);

    TestEqual(TEXT("Fade: half in at 0.15 s"), LineAt(300.0 + 74.15, 0.3).Opacity, 0.5f, 1e-3f);
    TestEqual(TEXT("Fade: full mid-line"), LineAt(300.0 + 80.0, 0.3).Opacity, 1.0f);
    TestEqual(TEXT("Fade: half out 0.15 s before Out"), LineAt(300.0 + 84.85, 0.3).Opacity, 0.5f, 1e-3f);

    // A retime moves the Scene; the line moves with it.
    TArray<FInfinityTransportSegment> Retimed = Show;
    Retimed[3].StartFrame = FFrameNumber(int32(310.0 * Ticks));
    Retimed[3].EndFrame = FFrameNumber(int32(462.341 * Ticks));
    TestEqual(TEXT("Retime: line follows its segment"),
        InfinityStageSurtitles::Evaluate(Script, Retimed, At(310.0 + 74.0), Ticks, 0.0).LineIndex, 0);
    TestEqual(TEXT("Control: the old Master time no longer shows it"),
        InfinityStageSurtitles::Evaluate(Script, Retimed, At(300.0 + 74.0), Ticks, 0.0).LineIndex, INDEX_NONE);
    return true;
}

#endif
