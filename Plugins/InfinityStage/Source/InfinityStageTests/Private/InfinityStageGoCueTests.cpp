#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
TArray<FInfinityGoCue> ThreeCues()
{
    TArray<FInfinityGoCue> Cues;
    const auto Add = [&Cues](const int32 Frame, const bool bHold)
    {
        FInfinityGoCue& Cue = Cues.AddDefaulted_GetRef();
        Cue.Frame = Frame;
        Cue.bHold = bHold;
        Cue.Number = FString::FromInt(Cues.Num());
    };
    Add(100, true);
    Add(150, false);
    Add(200, true);
    return Cues;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoMarkerParseTest,
    "InfinityStage.Cueing.GO.MarkerLabelParses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageGoMarkerParseTest::RunTest(const FString& Parameters)
{
    FString Number;
    FString Label;
    int32 Mode = 7;
    TestTrue(TEXT("Plain GO parses"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GO 12 Warmers out, Puss enters"), Number, Label, Mode));
    TestEqual(TEXT("Number"), Number, FString(TEXT("12")));
    TestEqual(TEXT("Label"), Label, FString(TEXT("Warmers out, Puss enters")));
    TestEqual(TEXT("Unmarked mode"), Mode, -1);

    TestTrue(TEXT("Decimal number, PASS"), InfinityStageGoCues::ParseMarkerLabel(TEXT("  GO 3.5 PASS distant fire "), Number, Label, Mode));
    TestEqual(TEXT("Decimal cue numbers survive"), Number, FString(TEXT("3.5")));
    TestEqual(TEXT("PASS mode"), Mode, 0);
    TestEqual(TEXT("Label after the mode"), Label, FString(TEXT("distant fire")));

    TestTrue(TEXT("HOLD with no label"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GO 4 HOLD"), Number, Label, Mode));
    TestEqual(TEXT("HOLD mode"), Mode, 1);
    TestTrue(TEXT("Empty label"), Label.IsEmpty());
    TestTrue(TEXT("Lower-case pass is label text, not a mode"),
        InfinityStageGoCues::ParseMarkerLabel(TEXT("GO 5 pass the cup"), Number, Label, Mode) && Mode == -1
        && Label == TEXT("pass the cup"));

    TestFalse(TEXT("Control: a Scene note 'go on' is never a GO"), InfinityStageGoCues::ParseMarkerLabel(TEXT("go on"), Number, Label, Mode));
    TestFalse(TEXT("Control: 'GO on' needs a numeric cue number"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GO on"), Number, Label, Mode));
    TestFalse(TEXT("Control: lower-case go is not GO"), InfinityStageGoCues::ParseMarkerLabel(TEXT("go 3 fire"), Number, Label, Mode));
    TestFalse(TEXT("Control: a vamp marker is not a GO"), InfinityStageGoCues::ParseMarkerLabel(TEXT("InfinityStage.VampStart"), Number, Label, Mode));
    TestFalse(TEXT("Control: GOAT is not GO"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GOAT 1"), Number, Label, Mode));
    TestFalse(TEXT("Control: GO needs a number"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GO"), Number, Label, Mode));
    TestFalse(TEXT("Control: a lone dot is not a number"), InfinityStageGoCues::ParseMarkerLabel(TEXT("GO . x"), Number, Label, Mode));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoHoldStateTest,
    "InfinityStage.Cueing.GO.HoldArmsReleasesAndReruns",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageGoHoldStateTest::RunTest(const FString& Parameters)
{
    const TArray<FInfinityGoCue> Cues = ThreeCues();
    FInfinityGoHoldState State;
    State.SettleOffset = 2;   // holds settle at Frame - 2

    TestEqual(TEXT("First tick only observes"), State.Tick(90, true, Cues), INDEX_NONE);
    TestEqual(TEXT("Playing forward across 100 holds on GO 1"), State.Tick(105, true, Cues), 0);
    TestEqual(TEXT("It settles before the GO frame"), State.SettleFrame(Cues[0]), FFrameNumber(98));
    TestEqual(TEXT("Paused at the settle frame, still holding"), State.Tick(98, false, Cues), INDEX_NONE);
    TestTrue(TEXT("Hold is active"), State.IsActive());
    TestTrue(TEXT("GO releases"), State.Release());
    TestFalse(TEXT("A second GO has nothing to release"), State.Release());
    TestEqual(TEXT("Playing on from the settle frame does not re-hold GO 1"), State.Tick(104, true, Cues), INDEX_NONE);
    TestEqual(TEXT("A PASS cue never holds"), State.Tick(160, true, Cues), INDEX_NONE);
    TestEqual(TEXT("Next HOLD stops the show"), State.Tick(210, true, Cues), 2);
    State.Release();
    TestEqual(TEXT("Released holds do not re-fire going on"), State.Tick(260, true, Cues), INDEX_NONE);

    // Re-run: the operator jumps back before GO 1 and plays again.
    State.OnNavigation(50);
    TestEqual(TEXT("Jump back observes only"), State.Tick(50, false, Cues), INDEX_NONE);
    TestEqual(TEXT("Re-run stops at GO 1 again"), State.Tick(101, true, Cues), 0);
    State.Release();

    // Controls: crossing while paused, or by navigation, never arms.
    TestEqual(TEXT("Control: not playing forward never arms"), State.Tick(205, false, Cues), INDEX_NONE);
    State.OnNavigation(90);
    State.Tick(90, false, Cues);
    State.OnNavigation(300);
    TestEqual(TEXT("Control: a jump over holds never arms"), State.Tick(300, true, Cues), INDEX_NONE);

    FInfinityGoHoldState Empty;
    TArray<FInfinityGoCue> None;
    Empty.Tick(0, true, None);
    TestEqual(TEXT("Control: no GO markers, no hold ever"), Empty.Tick(100000, true, None), INDEX_NONE);
    TestFalse(TEXT("Control: no GO markers, nothing to release"), Empty.Release());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoStaleHoldTest,
    "InfinityStage.Cueing.GO.ResumeWithoutGoSpendsTheHold",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Review M2: resuming from the Cue Desk or Blueprint (not GO) must spend the hold,
// so it neither disarms every later hold nor eats the next RIGHT as GO.
bool FInfinityStageGoStaleHoldTest::RunTest(const FString& Parameters)
{
    const TArray<FInfinityGoCue> Cues = ThreeCues();
    FInfinityGoHoldState State;
    State.SettleOffset = 2;
    State.Tick(90, true, Cues);
    TestEqual(TEXT("GO 1 holds"), State.Tick(103, true, Cues), 0);
    TestEqual(TEXT("Control: playing yet still ON the settle frame keeps the hold"), State.Tick(98, true, Cues), INDEX_NONE);
    TestTrue(TEXT("Control: ...and it is still active"), State.IsActive());

    // Someone resumes without GO: the playhead moves on while the hold is active.
    TestEqual(TEXT("Resumed past the settle frame: nothing new to hold yet"), State.Tick(120, true, Cues), INDEX_NONE);
    TestFalse(TEXT("The stale hold is spent, so the next RIGHT is not eaten as GO"), State.IsActive());
    TestFalse(TEXT("...and Release has nothing to consume"), State.Release());
    TestEqual(TEXT("A later HOLD still stops the show"), State.Tick(205, true, Cues), 2);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoSettleClampTest,
    "InfinityStage.Cueing.GO.SettleNeverLeavesItsSegment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Review N1: a GO at (or within a display frame of) its segment's start must settle
// inside that segment, never on the previous segment's last frame.
bool FInfinityStageGoSettleClampTest::RunTest(const FString& Parameters)
{
    FInfinityGoHoldState State;
    State.SettleOffset = 1000;          // one display frame, in ticks

    FInfinityGoCue AtStart;
    AtStart.SegmentStartFrame = 48000;
    AtStart.Frame = 48000;
    TestEqual(TEXT("A GO at 0:00 of its Scene settles ON its frame"), State.SettleFrame(AtStart), FFrameNumber(48000));

    FInfinityGoCue JustIn;
    JustIn.SegmentStartFrame = 48000;
    JustIn.Frame = 48400;
    TestEqual(TEXT("A GO under one frame in settles at the segment start"), State.SettleFrame(JustIn), FFrameNumber(48000));

    FInfinityGoCue SecondIn;
    SecondIn.SegmentStartFrame = 48000;
    SecondIn.Frame = 72000;
    TestEqual(TEXT("Control: a GO a second in settles one display frame early"), State.SettleFrame(SecondIn), FFrameNumber(71000));

    // The clamped hold still arms on crossing and does not re-hold after GO.
    TArray<FInfinityGoCue> Cues;
    FInfinityGoCue& Hold = Cues.Add_GetRef(AtStart);
    Hold.bHold = true;
    State.Tick(47000, true, Cues);
    TestEqual(TEXT("Crossing the segment start holds"), State.Tick(48600, true, Cues), 0);
    TestEqual(TEXT("Held on its own frame"), State.Tick(48000, false, Cues), INDEX_NONE);
    State.Release();
    TestEqual(TEXT("Playing on from the settle frame does not re-hold"), State.Tick(49000, true, Cues), INDEX_NONE);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoFastForwardTest,
    "InfinityStage.Cueing.GO.FastForwardKeyUpNeverPlaysThroughAHold",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Review M1: hold RIGHT fast-forwards into a HOLD; the key-up must not resume.
bool FInfinityStageGoFastForwardTest::RunTest(const FString& Parameters)
{
    using T = UInfinityStageTransportController;
    TestFalse(TEXT("Was playing, but a hold is active: stay held"), T::ResumesAfterFastForward(true, false, true));
    TestFalse(TEXT("Vamping, but a hold is active: stay held"), T::ResumesAfterFastForward(false, true, true));
    TestTrue(TEXT("Control: was playing, no hold: resume as before"), T::ResumesAfterFastForward(true, false, false));
    TestTrue(TEXT("Control: vamp active, no hold: resume as before"), T::ResumesAfterFastForward(false, true, false));
    TestFalse(TEXT("Control: was paused, no hold: stay paused as before"), T::ResumesAfterFastForward(false, false, false));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGoBuildSegmentsTest,
    "InfinityStage.Cueing.GO.CollectedAndInterlockDemotes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Review M3: GO markers in a DeclaredUnpausable Scene (the result=4 interlock) are
// listed but can never hold. The same marker in an ordinary Scene is the control.
bool FInfinityStageGoBuildSegmentsTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::Scene;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Label = FText::FromString(Index == 0 ? TEXT("Ordinary") : TEXT("Live performer"));
        Cue.Scene.DurationFrames = 500;
        Cue.Scene.ExternalSound = Index == 0
            ? EInfinityExternalSoundAuthority::None
            : EInfinityExternalSoundAuthority::DeclaredUnpausable;
        ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
        Sequence->Initialize();
        Sequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
        Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(1000), 500);
        FMovieSceneMarkedFrame Go;
        Go.FrameNumber = FFrameNumber(1100);
        Go.Label = Index == 0 ? TEXT("GO 1 House to half") : TEXT("GO 2 Song");
        Sequence->GetMovieScene()->AddMarkedFrame(Go);
        FMovieSceneMarkedFrame Note;
        Note.FrameNumber = FFrameNumber(1200);
        Note.Label = TEXT("go on");     // control: a note, not a cue
        Sequence->GetMovieScene()->AddMarkedFrame(Note);
        Cue.Scene.Sequence = Sequence;
    }

    AddExpectedMessagePlain(TEXT("INFINITY_GO_HOLD_DEMOTED"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>(GetTransientPackage());
    TestTrue(TEXT("Fixture compiles"), Transport->BuildSegments(Show));
    TestEqual(TEXT("Two GO cues, the 'go on' note ignored"), Transport->GoCues.Num(), 2);
    if (Transport->GoCues.Num() != 2)
    {
        return false;
    }
    const FInfinityGoCue& First = Transport->GoCues[0];
    const FInfinityGoCue& Second = Transport->GoCues[1];
    TestEqual(TEXT("GO 1 sits 100 ticks into its Scene (relative to the playback start)"),
        First.Frame, Transport->Segments[0].StartFrame + FFrameNumber(100));
    TestTrue(TEXT("Control: in an ordinary Scene, GO holds by default"), First.bHold);
    TestFalse(TEXT("In a DeclaredUnpausable Scene the same GO is demoted to PASS"), Second.bHold);
    TestEqual(TEXT("Show order"), Second.Number, FString(TEXT("2")));
    TestFalse(TEXT("No hold is active after a build"), Transport->IsHoldActive());
    return true;
}

#endif
