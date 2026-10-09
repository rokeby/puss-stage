#include "InfinityStageCueSheet.h"
#include "InfinityStageDirectorHud.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
// The shape of Gary's Puss_Master_cue_sheet (7 Oct): a blank first row, the header row,
// speaker names under the Speaker columns, number-only separator rows, a multi-line cell.
const TCHAR* SheetCsv =
    TEXT(",,,,,,,,,,\n")
    TEXT(",Light,Sound tech,Action,Sound cue,Video Cue,Speaker,Speaker,Speaker,Beats,Notes\n")
    TEXT(",,,,,,Klara,Gary,Cameron,,\n")
    TEXT("1,Black out / lamps on table on,,,,,,,,,\n")
    TEXT(",,,world elements,,,\"Once upon a time, there lived an old man.\",,,,\n")
    TEXT(",,\"Lav mic 2 (GZZ) off\nGZZ mic on table on\",Cameron passes control of the dog to Gary,,,,,,,\n")
    TEXT(",,,,,,,\"here my boy, take this \"\"cat\"\"\",,,\n")
    TEXT("3,,,,,,,,,,\n")
    TEXT(",,,,Opening,Curtain opening to fully lit stage/passage,,,,,\n")
    TEXT(",(State 2) warm from the sides,,,,Passage 1,,,,,Klara needs sound cue\n")
    TEXT(",,,,,,Puss walked for four days,,,,\n")
    TEXT(",(State 3) green and yellow,,,,S1 Animals,,,,,\n")
    TEXT(",,,,,,,,,B1: establish,\n")
    TEXT(",,,,,,,,whimper,,\n");
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueSheetCsvTest,
    "InfinityStage.CueDirector.CsvParses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueSheetCsvTest::RunTest(const FString& Parameters)
{
    TArray<TArray<FString>> Table;
    FInfinityCueSheet::ParseCsv(TEXT("a,\"b, c\",\"say \"\"hi\"\"\"\r\nx,\"two\nlines\",z"), Table);
    TestEqual(TEXT("Two records (a quoted newline is not a record break)"), Table.Num(), 2);
    if (Table.Num() == 2)
    {
        TestEqual(TEXT("Quoted comma stays in the cell"), Table[0][1], FString(TEXT("b, c")));
        TestEqual(TEXT("Doubled quotes become one"), Table[0][2], FString(TEXT("say \"hi\"")));
        TestEqual(TEXT("CRLF does not leak into the last cell"), Table[0].Last(), FString(TEXT("say \"hi\"")));
        TestEqual(TEXT("Quoted newline kept inside the cell"), Table[1][1], FString(TEXT("two\nlines")));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueSheetLoadTest,
    "InfinityStage.CueDirector.SheetMapsRolesSpeakersSegments",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueSheetLoadTest::RunTest(const FString& Parameters)
{
    FInfinityCueSheet Sheet;
    TestTrue(TEXT("The sheet loads"), Sheet.LoadFromCsvText(SheetCsv));
    TestEqual(TEXT("Speakers come from the row under the header"), FString::Join(Sheet.Speakers, TEXT(",")), FString(TEXT("Klara,Gary,Cameron")));
    TestEqual(TEXT("Three digital segments (Video Cue rows)"), Sheet.SegmentLabels.Num(), 3);
    TestEqual(TEXT("Segment 1 is Passage 1"), Sheet.SegmentLabels.IsValidIndex(1) ? Sheet.SegmentLabels[1] : FString(), FString(TEXT("Passage 1")));
    TestEqual(TEXT("Blank rows are dropped; number-only rows kept"), Sheet.Rows.Num(), 11);
    if (Sheet.Rows.Num() == 11)
    {
        TestEqual(TEXT("Column A is the cue number"), Sheet.Rows[0].Number, FString(TEXT("1")));
        TestEqual(TEXT("Light column"), Sheet.Rows[0].Light, FString(TEXT("Black out / lamps on table on")));
        TestEqual(TEXT("Klara's line is attributed to Klara"),
            Sheet.Rows[1].Lines.Num() == 1 ? Sheet.Rows[1].Lines[0].Speaker : FString(), FString(TEXT("Klara")));
        TestTrue(TEXT("A multi-line Sound tech cell survives"), Sheet.Rows[2].SoundTech.Contains(TEXT("\n")));
        TestEqual(TEXT("Gary's quoted line keeps its quotes"),
            Sheet.Rows[3].Lines.Num() == 1 ? Sheet.Rows[3].Lines[0].Text : FString(), FString(TEXT("here my boy, take this \"cat\"")));
        TestEqual(TEXT("Rows before the first Video Cue are pre-show"), Sheet.Rows[3].SegmentOrdinal, int32(INDEX_NONE));
        TestEqual(TEXT("A Video Cue row starts its segment"), Sheet.Rows[5].SegmentOrdinal, 0);
        TestEqual(TEXT("Rows carry the segment in force"), Sheet.Rows[7].Segment, FString(TEXT("Passage 1")));
        TestEqual(TEXT("Cameron's whimper is in S1"), Sheet.Rows[10].SegmentOrdinal, 2);
        TestEqual(TEXT("Segment starts point at their rows"), Sheet.SegmentStartRow(2), 8);
    }

    FInfinityCueSheet NotASheet;
    TestFalse(TEXT("Control: a CSV without the header row is refused"), NotASheet.LoadFromCsvText(TEXT("a,b\nc,d\n")));
    TestEqual(TEXT("...with one warning saying why"), NotASheet.Warnings.Num(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageScriptCursorTest,
    "InfinityStage.CueDirector.CursorStepsAndNeverRunsBackByItself",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageScriptCursorTest::RunTest(const FString& Parameters)
{
    FInfinityCueSheet Sheet;
    Sheet.LoadFromCsvText(SheetCsv);
    FInfinityScriptCursor Cursor;
    TestTrue(TEXT("Next steps forward"), Cursor.Next(Sheet));
    TestEqual(TEXT("...to the next row with content"), Cursor.Row, 1);
    Cursor.Row = 3;
    Cursor.Next(Sheet);
    TestEqual(TEXT("Number-only separator rows are skipped"), Cursor.Row, 5);

    Cursor.SyncToSegment(Sheet, 2);
    TestEqual(TEXT("The stage reaching S1 pulls the script cursor forward"), Cursor.Row, 8);
    Cursor.SyncToSegment(Sheet, 1);
    TestEqual(TEXT("The stage going back does NOT pull the cursor back"), Cursor.Row, 8);
    TestTrue(TEXT("The operator can step back"), Cursor.Prev(Sheet));
    TestEqual(TEXT("...to the previous row with content"), Cursor.Row, 7);
    Cursor.Row = 9;
    Cursor.SyncToSegment(Sheet, 2);
    TestEqual(TEXT("Control: re-syncing the same segment never moves the operator's place"), Cursor.Row, 9);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDirectorHudCycleTest,
    "InfinityStage.CueDirector.HCyclesStripScriptOff",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDirectorHudCycleTest::RunTest(const FString& Parameters)
{
    bool bStrip = false;
    bool bScript = false;
    InfinityStageDirectorHud::NextMode(false, false, bStrip, bScript);
    TestTrue(TEXT("Off -> strip"), bStrip && !bScript);
    InfinityStageDirectorHud::NextMode(true, false, bStrip, bScript);
    TestTrue(TEXT("Strip -> strip + script (H twice)"), bStrip && bScript);
    InfinityStageDirectorHud::NextMode(true, true, bStrip, bScript);
    TestTrue(TEXT("Script -> off (H a third time)"), !bStrip && !bScript);

    const TArray<FString> Wrapped = InfinityStageDirectorHud::WrapText(TEXT("one two three four five six seven"), 10);
    TestTrue(TEXT("Wrapping keeps every line within the budget"),
        Wrapped.Num() > 1 && Wrapped.FindByPredicate([](const FString& L) { return L.Len() > 10; }) == nullptr);
    TestEqual(TEXT("...and loses no words"), FString::Join(Wrapped, TEXT(" ")), FString(TEXT("one two three four five six seven")));

    FInfinityCueSheet Sheet;
    Sheet.LoadFromCsvText(SheetCsv);
    TestEqual(TEXT("Standby after the opening finds the next numbered or staged row"),
        InfinityStageCueSheet::NextStandbyRow(Sheet, 0), 4);
    TestTrue(TEXT("Actions are tagged by department"),
        InfinityStageCueSheet::DescribeActions(Sheet.Rows[2]).Contains(TEXT("SND: Lav mic 2 (GZZ) off / GZZ mic on table on")));
    return true;
}

#endif
