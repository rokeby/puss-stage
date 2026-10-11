#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBreathAudioRampTest,
    "InfinityStage.CueDirector.BreathAudioRampTable",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBreathAudioRampTest::RunTest(const FString& Parameters)
{
    FInfinityBreathAudio Ramp;
    Ramp.RampSeconds = 4.0f;
    Ramp.PitchFloor = 0.5f;
    Ramp.VolumeFloor = 0.0f;
    Ramp.EaseExponent = 2.0f;
    Ramp.StrangePitchDip = 0.1f;
    const FInfinityBreathAudioValue Full;
    FInfinityBreathAudioValue Floor;
    Floor.Volume = 0.0f;
    Floor.Pitch = 0.5f;
    Floor.bMute = true;

    const FInfinityBreathAudioValue AtStart = Ramp.Evaluate(0.0, Full, Floor, true);
    const FInfinityBreathAudioValue AtMiddle = Ramp.Evaluate(2.0, Full, Floor, true);
    const FInfinityBreathAudioValue AtEnd = Ramp.Evaluate(4.0, Full, Floor, true);
    TestEqual(TEXT("Wind-down starts at full volume"), AtStart.Volume, 1.0f);
    TestEqual(TEXT("Wind-down starts at natural pitch"), AtStart.Pitch, 1.0f);
    TestTrue(TEXT("Mid-ramp volume lies between its endpoints"), AtMiddle.Volume > 0.0f && AtMiddle.Volume < 1.0f);
    TestTrue(TEXT("The strange arc dips below the plain eased pitch"), AtMiddle.Pitch < 0.875f);
    TestEqual(TEXT("Wind-down reaches silence"), AtEnd.Volume, 0.0f);
    TestEqual(TEXT("Wind-down reaches its pitch floor"), AtEnd.Pitch, 0.5f);
    TestTrue(TEXT("Silence requests the managed music mute"), AtEnd.bMute);

    const FInfinityBreathAudioValue UpStart = Ramp.Evaluate(0.0, Floor, Full, false);
    const FInfinityBreathAudioValue UpEnd = Ramp.Evaluate(4.0, Floor, Full, false);
    TestEqual(TEXT("Exit starts from the floor"), UpStart.Volume, 0.0f);
    TestEqual(TEXT("Exit restores full volume"), UpEnd.Volume, 1.0f);
    TestEqual(TEXT("Exit restores natural pitch"), UpEnd.Pitch, 1.0f);
    TestFalse(TEXT("Exit never asks for mute"), UpEnd.bMute);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRoomToneGainTest,
    "InfinityStage.CueDirector.RoomToneIndependentGain",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRoomToneGainTest::RunTest(const FString& Parameters)
{
    using Root = AInfinityStageShowRoot;
    TestEqual(TEXT("Outside S6 the low base level is unchanged"),
        Root::ComputeRoomToneGainDb(-18.0f, -12.0f, 0.0f, true), -18.0f);
    TestEqual(TEXT("Half Weird applies half the additional dip"),
        Root::ComputeRoomToneGainDb(-18.0f, -12.0f, 0.5f, true), -24.0f);
    TestEqual(TEXT("Full Weird reaches -30 dB rather than silence"),
        Root::ComputeRoomToneGainDb(-18.0f, -12.0f, 1.0f, true), -30.0f);
    TestEqual(TEXT("The operator can disable the optional dip"),
        Root::ComputeRoomToneGainDb(-18.0f, -12.0f, 1.0f, false), -18.0f);
    TestEqual(TEXT("Weird is clamped above one"),
        Root::ComputeRoomToneGainDb(-18.0f, -12.0f, 4.0f, true), -30.0f);
    TestEqual(TEXT("A positive dip value cannot make room tone louder"),
        Root::ComputeRoomToneGainDb(-18.0f, 12.0f, 1.0f, true), -18.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBreathClockTest,
    "InfinityStage.CueDirector.BreathClockFrozenMasterAdvancesMechanisms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBreathClockTest::RunTest(const FString& Parameters)
{
    FInfinityBreathClock Clock;
    const double FrozenShowSeconds = 17.25;
    Clock.Begin(100.0);
    const double PhaseA = FInfinityBreathClock::PhaseSeconds(
        FrozenShowSeconds, Clock.Elapsed(100.0), Clock.bActive);
    const double PhaseB = FInfinityBreathClock::PhaseSeconds(
        FrozenShowSeconds, Clock.Elapsed(102.5), Clock.bActive);
    TestEqual(TEXT("Frozen Master is the phase origin"), PhaseA, FrozenShowSeconds);
    TestEqual(TEXT("Real breath time advances mechanism phase"), PhaseB, FrozenShowSeconds + 2.5);

    Clock.End();
    const double Outside = FInfinityBreathClock::PhaseSeconds(
        FrozenShowSeconds, 123456.0, Clock.bActive);
    TestTrue(TEXT("Negative control: outside a breath the double is bit-identical"),
        FMemory::Memcmp(&Outside, &FrozenShowSeconds, sizeof(double)) == 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBreathRefusalTest,
    "InfinityStage.CueDirector.BreathRefusesScenesAndInteractions",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBreathRefusalTest::RunTest(const FString& Parameters)
{
    using T = UInfinityStageTransportController;
    TestEqual(TEXT("A Passage is allowed in rehearsal"),
        T::CanBeginBreath(EInfinityCueType::WingPair, false, true), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("A Passage is allowed in performance by default"),
        T::CanBeginBreath(EInfinityCueType::WingPair, true, true), EInfinityTransportResult::Succeeded);
    TestEqual(TEXT("Performance can explicitly lock breath out"),
        T::CanBeginBreath(EInfinityCueType::WingPair, true, false), EInfinityTransportResult::BreathNotAllowed);
    TestEqual(TEXT("A Scene refuses breath"),
        T::CanBeginBreath(EInfinityCueType::Scene, false, true), EInfinityTransportResult::BreathNotAllowed);
    TestEqual(TEXT("An Interaction/Sequence refuses breath"),
        T::CanBeginBreath(EInfinityCueType::Sequence, false, true), EInfinityTransportResult::BreathNotAllowed);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBreathMarkerTest,
    "InfinityStage.CueDirector.BreathMarkerPositiveAndGarbageNegative",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBreathMarkerTest::RunTest(const FString& Parameters)
{
    FString Number;
    FString Label;
    int32 Mode = -1;
    TestTrue(TEXT("LIVEBREATH marker parses"), InfinityStageGoCues::ParseMarkerLabel(
        TEXT("GO 12.5 LIVEBREATH listen to the room"), Number, Label, Mode));
    TestEqual(TEXT("BREATH mode"), Mode, 2);
    TestEqual(TEXT("BREATH number"), Number, FString(TEXT("12.5")));
    TestEqual(TEXT("BREATH label"), Label, FString(TEXT("listen to the room")));
    TestFalse(TEXT("Negative: prose is not a marker"), InfinityStageGoCues::ParseMarkerLabel(
        TEXT("please GO BREATH now"), Number, Label, Mode));
    TestFalse(TEXT("Negative: BREATH still requires an upper-case GO"), InfinityStageGoCues::ParseMarkerLabel(
        TEXT("go 12 LIVEBREATH"), Number, Label, Mode));
    // An authored-breath note (plain BREATH) is documentation only: never a GO, never a live breath.
    TestFalse(TEXT("Plain BREATH is an annotation, not a GO"), InfinityStageGoCues::ParseMarkerLabel(
        TEXT("GO 22 BREATH sit with the rain"), Number, Label, Mode));

    TArray<FInfinityGoCue> Cues;
    FInfinityGoCue& Breath = Cues.AddDefaulted_GetRef();
    Breath.Frame = 100;
    Breath.bBreath = true;
    Breath.bHold = false;
    FInfinityBreathCueState State;
    TestEqual(TEXT("First tick observes only"), State.Tick(90, true, Cues), INDEX_NONE);
    TestEqual(TEXT("Crossing the marker requests breath"), State.Tick(101, true, Cues), 0);
    TestEqual(TEXT("It fires only once while continuing"), State.Tick(120, true, Cues), INDEX_NONE);
    State.OnNavigation(50);
    TestEqual(TEXT("Navigation itself never fires"), State.Tick(50, false, Cues), INDEX_NONE);
    TestEqual(TEXT("Re-running the marker fires it again"), State.Tick(101, true, Cues), 0);
    return true;
}

#endif
