#include "InfinityStageCueSheet.h"
#include "InfinityStageDirectorHud.h"
#include "InfinityStageShowGameMode.h"
#include "InfinityStageTransportController.h"
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDogDirectionTest,
    "InfinityStage.CueDirector.DogDirectionsCarryForward",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDogDirectionTest::RunTest(const FString& Parameters)
{
    FInfinityCueSheet Sheet;
    const FString Csv =
        TEXT(",Light,Video Cue,Dog action,Dog mode,Treadmill\n")
        TEXT(",,,,,\n")
        TEXT("1,,Passage 1,trotting,walk_trot,on\n")
        TEXT("2,,,,,\n")
        TEXT("3,,,still,,off\n");
    TestTrue(TEXT("Dog cue sheet loads"), Sheet.LoadFromCsvText(Csv));
    TestEqual(TEXT("Three non-blank dog rows"), Sheet.Rows.Num(), 3);
    if (Sheet.Rows.Num() == 3)
    {
        TestEqual(TEXT("Direct direction is compact"), InfinityStageCueSheet::DescribeDogDirection(Sheet.Rows[0]),
            FString(TEXT("DOG: trotting | Walk / trot | treadmill on")));
        TestEqual(TEXT("Mode and treadmill carry to the next row"), InfinityStageCueSheet::DescribeDogDirection(Sheet.Rows[1]),
            FString(TEXT("DOG: Walk / trot | treadmill on")));
        TestEqual(TEXT("Action does not carry; treadmill change does"), InfinityStageCueSheet::DescribeDogDirection(Sheet.Rows[2]),
            FString(TEXT("DOG: still | Walk / trot | treadmill off")));
        TestEqual(TEXT("Next dog direction skips an unstated row"), InfinityStageCueSheet::NextDogDirectionRow(Sheet, 0), 2);
        TestEqual(TEXT("Negative control: no later dog direction"), InfinityStageCueSheet::NextDogDirectionRow(Sheet, 2), int32(INDEX_NONE));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueDirectorSettingsTest,
    "InfinityStage.CueDirector.SettingsRoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueDirectorSettingsTest::RunTest(const FString& Parameters)
{
    FInfinityCueDirectorSettings Settings;
    Settings.bRunThrough = true;
    Settings.bAllowBreathInPerformance = false;
    const FGuid SceneOne = FGuid::NewGuid();
    const FGuid SceneTwo = FGuid::NewGuid();
    Settings.StopAfterSegments = {SceneOne, SceneTwo};
    Settings.HoldGoNumbers = {TEXT("10")};
    const FString Text = Settings.Serialize([](const FGuid&) { return FString(TEXT("Scene label")); });
    TestTrue(TEXT("The file names each stop for a human"), Text.Contains(TEXT("# Scene label")));

    FInfinityCueDirectorSettings Read;
    TArray<FString> Warnings;
    Read.Parse(Text, Warnings);
    TestEqual(TEXT("No warnings on our own output"), Warnings.Num(), 0);
    TestTrue(TEXT("Run-through survives"), Read.bRunThrough);
    TestFalse(TEXT("Performance breath setting survives"), Read.bAllowBreathInPerformance);
    TestTrue(TEXT("Stops survive, in order"), Read.StopAfterSegments == Settings.StopAfterSegments);
    TestTrue(TEXT("Held GO numbers survive"), Read.HoldGoNumbers == Settings.HoldGoNumbers);

    FInfinityCueDirectorSettings Bad;
    Bad.Parse(TEXT("run_through = yes\nstop_after = not-a-guid\nbanana = 3\njust text\n"), Warnings);
    TestEqual(TEXT("Control: bad lines warn (bad GUID, unknown key, no '='), never throw"), Warnings.Num(), 3);
    TestTrue(TEXT("...and the good line still counts"), Bad.bRunThrough);
    TestEqual(TEXT("...and nothing bogus is kept"), Bad.StopAfterSegments.Num(), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRunThroughStopsTest,
    "InfinityStage.CueDirector.RunThroughStopsWhereTicked",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRunThroughStopsTest::RunTest(const FString& Parameters)
{
    TArray<FInfinityTransportSegment> Segments;
    for (int32 Index = 0; Index < 6; ++Index)
    {
        FInfinityTransportSegment& Segment = Segments.AddDefaulted_GetRef();
        Segment.SegmentGuid = FGuid::NewGuid();
    }
    using T = UInfinityStageTransportController;
    TestEqual(TEXT("Control: no stops = play to the Show's end (run-through as built)"),
        T::RunThroughStopIndex(Segments, 0, {}), 5);
    const TArray<FGuid> Stops = {Segments[2].SegmentGuid, Segments[4].SegmentGuid};
    TestEqual(TEXT("From the Opening, stop at the end of the first ticked segment"), T::RunThroughStopIndex(Segments, 0, Stops), 2);
    TestEqual(TEXT("Starting inside a ticked segment stops at its own end"), T::RunThroughStopIndex(Segments, 2, Stops), 2);
    TestEqual(TEXT("After GO, run on to the next ticked one"), T::RunThroughStopIndex(Segments, 3, Stops), 4);
    TestEqual(TEXT("Past the last stop, run to the end"), T::RunThroughStopIndex(Segments, 5, Stops), 5);
    TestEqual(TEXT("A stale GUID is ignored"), T::RunThroughStopIndex(Segments, 0, {FGuid::NewGuid()}), 5);

    TArray<FInfinityGoCue> Cues;
    for (const int32 Frame : {100, 200})
    {
        FInfinityGoCue& Cue = Cues.AddDefaulted_GetRef();
        Cue.Frame = Frame;
        Cue.bHold = true;
        Cue.Number = Frame == 100 ? TEXT("9") : TEXT("10");
    }
    FInfinityGoHoldState Hold;
    Hold.bPassAll = true;
    Hold.KeepNumbers.Add(TEXT("10"));
    Hold.Tick(50, true, Cues);
    TestEqual(TEXT("Run-through passes an unlisted GO"), Hold.Tick(150, true, Cues), int32(INDEX_NONE));
    TestEqual(TEXT("...but a kept GO still holds for Klara"), Hold.Tick(250, true, Cues), 1);
    FInfinityGoHoldState PassAll;
    PassAll.bPassAll = true;
    PassAll.Tick(50, true, Cues);
    TestEqual(TEXT("Control: run-through with nothing kept passes everything (as built)"), PassAll.Tick(250, true, Cues), int32(INDEX_NONE));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageScriptKeysTest,
    "InfinityStage.CueDirector.ScriptKeysAreCommaAndFullStop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Gary, 9 Oct: the script cursor must not need PageUp/PageDown (some keyboards lack them).
bool FInfinityStageScriptKeysTest::RunTest(const FString& Parameters)
{
    TestTrue(TEXT("Back is the comma key"), InfinityStageShowKeys::ScriptPreviousName() == FName(TEXT("Comma")));
    TestTrue(TEXT("On is the full-stop key"), InfinityStageShowKeys::ScriptNextName() == FName(TEXT("Period")));
    TestTrue(TEXT("Passage breath is P"), InfinityStageShowKeys::BreathName() == FName(TEXT("P")));
    // Compared by name: this test module does not link InputCore (EKeys, FKey::GetFName).
    const TArray<FName> Bound = InfinityStageShowKeys::AllBoundNames();
    TestFalse(TEXT("PageUp is not bound"), Bound.Contains(FName(TEXT("PageUp"))));
    TestFalse(TEXT("PageDown is not bound"), Bound.Contains(FName(TEXT("PageDown"))));
    TestTrue(TEXT("The script keys are in the bound set"), Bound.Contains(FName(TEXT("Comma"))) && Bound.Contains(FName(TEXT("Period"))));
    TestTrue(TEXT("The breath key is in the bound set"), Bound.Contains(FName(TEXT("P"))));
    // Control: no key does two jobs (a clash would make one of them silently win).
    TSet<FName> Unique(Bound);
    TestEqual(TEXT("Control: every bound key is distinct"), Unique.Num(), Bound.Num());
    return true;
}

#endif
