#include "InfinityStageMechanismSound.h"

#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTypes.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Wing mechanism sound cues (patch 2026-10-07 mechanism_sound_cues): a sound placed
 * on a mechanism's phase fires once when real forward playback crosses it, never
 * on a scrub, jump, rewind or fast-forward, re-arms after a rewind, respects the
 * pair and Passage mutes, and an empty list changes nothing.
 */
namespace
{
FInfinityMechanismSoundCue MakeSoundCue(
    const TCHAR* Label,
    const double Phase,
    const EInfinityMechanismSoundCueSide Side = EInfinityMechanismSoundCueSide::Pair)
{
    FInfinityMechanismSoundCue Cue;
    Cue.Label = FName(Label);
    Cue.Phase = Phase;
    Cue.Side = Side;
    // Never loaded: the tests run the actor in dry run, which records instead.
    Cue.Sound = TSoftObjectPtr<USoundBase>(FSoftObjectPath(TEXT("/Game/InfinityStageTests/NoSuchSound.NoSuchSound")));
    return Cue;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismSoundCrossingRuleTest,
    "InfinityStage.MechanismSound.CrossingRule",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismSoundCrossingRuleTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageMechanismSound;

    // OneShot: Prev < Cue <= Curr.
    TestTrue(TEXT("Forward step over the cue crosses"), CrossesForward(0.20, 0.30, 0.25, false));
    TestTrue(TEXT("Landing exactly on the cue crosses"), CrossesForward(0.20, 0.25, 0.25, false));
    TestFalse(TEXT("Starting on the cue does not cross again"), CrossesForward(0.25, 0.30, 0.25, false));
    TestFalse(TEXT("A rewind over the cue never crosses"), CrossesForward(0.30, 0.20, 0.25, false));
    TestFalse(TEXT("A paused step never crosses"), CrossesForward(0.25, 0.25, 0.25, false));
    TestTrue(TEXT("A cue at 1 fires when the OneShot reaches its end"), CrossesForward(0.99, 1.0, 1.0, false));
    TestFalse(TEXT("A cue at 0 never fires on a OneShot (the phase starts there)"), CrossesForward(0.0, 0.01, 0.0, false));

    // Loops read the unwrapped phase; the cue repeats every cycle.
    TestTrue(TEXT("Loop: crosses a cue near 0 across the wrap"), CrossesForward(0.95, 1.02, 0.0, true));
    TestFalse(TEXT("Loop: the wrap alone does not cross a mid cue"), CrossesForward(0.95, 1.02, 0.5, true));
    TestTrue(TEXT("Loop: second cycle crosses again"), CrossesForward(1.40, 1.60, 0.5, true));
    TestTrue(TEXT("Loop: third cycle"), CrossesForward(2.30, 2.40, 0.35, true));
    TestFalse(TEXT("Loop: rewind never crosses"), CrossesForward(1.60, 1.40, 0.5, true));

    // A sampled forward run fires each cue exactly once per pass / cycle.
    int32 OneShotFires = 0;
    int32 LoopFires = 0;
    for (int32 Step = 1; Step <= 300; ++Step)
    {
        const double Prev = (Step - 1) * 0.01;
        const double Curr = Step * 0.01;
        OneShotFires += CrossesForward(FMath::Min(Prev, 1.0), FMath::Min(Curr, 1.0), 0.37, false) ? 1 : 0;
        LoopFires += CrossesForward(Prev, Curr, 0.37, true) ? 1 : 0;
    }
    TestEqual(TEXT("A OneShot run fires its cue once"), OneShotFires, 1);
    TestEqual(TEXT("Three loop cycles fire the cue three times"), LoopFires, 3);

    // Forward-playback gate.
    constexpr double Frame60 = 1.0 / 60.0;
    TestTrue(TEXT("1x at 60 fps is playback"), IsForwardPlaybackStep(Frame60, Frame60, 1.5, 0.25));
    TestTrue(TEXT("1x through a 0.2 s hitch is playback"), IsForwardPlaybackStep(0.2, 0.2, 1.5, 0.25));
    TestFalse(TEXT("Paused is not playback"), IsForwardPlaybackStep(0.0, Frame60, 1.5, 0.25));
    TestFalse(TEXT("Rewind is not playback"), IsForwardPlaybackStep(-Frame60, Frame60, 1.5, 0.25));
    TestFalse(TEXT("4x hold-right fast-forward is not playback"), IsForwardPlaybackStep(4.0 * Frame60, Frame60, 1.5, 0.25));
    TestFalse(TEXT("A jump within one frame is not playback"), IsForwardPlaybackStep(3.0, Frame60, 1.5, 0.25));
    TestFalse(TEXT("A step over MaxStepSeconds is not playback, however long the gap"), IsForwardPlaybackStep(1.0, 1.0, 1.5, 0.25));

    // Movement-set start threshold, by magnitude and upward only.
    TestTrue(TEXT("Travel rising through the threshold"), CrossesThresholdUpward(0.0, 0.05, 0.02));
    TestTrue(TEXT("Negative travel (topple away) by magnitude"), CrossesThresholdUpward(0.0, -0.05, 0.02));
    TestFalse(TEXT("Already moving"), CrossesThresholdUpward(0.05, 0.1, 0.02));
    TestFalse(TEXT("Settling back is not a start"), CrossesThresholdUpward(0.05, 0.0, 0.02));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismSoundCollectTest,
    "InfinityStage.MechanismSound.CollectRespectsSideMuteAndEmpty",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismSoundCollectTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageMechanismSound;
    TArray<int32> Fired;

    const FInfinityMechanismMotion Defaults;
    TestTrue(TEXT("SoundCues are empty by default"), Defaults.SoundCues.IsEmpty());
    const FInfinityMechanismSoundSet SetDefaults;
    TestFalse(TEXT("The Passage cue mute is off by default"), SetDefaults.bMuteSoundCues);
    CollectCrossedCues(Defaults.SoundCues, EInfinityMechanismSoundCueSide::Pair, 0.0, 1.0, false, false, Fired);
    TestTrue(TEXT("An empty list fires nothing"), Fired.IsEmpty());

    TArray<FInfinityMechanismSoundCue> Cues;
    Cues.Add(MakeSoundCue(TEXT("pair_slam"), 0.5));
    Cues.Add(MakeSoundCue(TEXT("left_hit"), 0.5, EInfinityMechanismSoundCueSide::Left));
    FInfinityMechanismSoundCue Silent = MakeSoundCue(TEXT("no_sound"), 0.5);
    Silent.Sound.Reset();
    Cues.Add(Silent);
    Cues.Add(MakeSoundCue(TEXT("later"), 0.9));

    CollectCrossedCues(Cues, EInfinityMechanismSoundCueSide::Pair, 0.4, 0.6, false, false, Fired);
    TestTrue(TEXT("Pair side: only the pair cue with a sound fires"), Fired.Num() == 1 && Fired[0] == 0);
    CollectCrossedCues(Cues, EInfinityMechanismSoundCueSide::Left, 0.4, 0.6, false, false, Fired);
    TestTrue(TEXT("Left side: only the Left cue fires"), Fired.Num() == 1 && Fired[0] == 1);
    CollectCrossedCues(Cues, EInfinityMechanismSoundCueSide::Right, 0.4, 0.6, false, false, Fired);
    TestTrue(TEXT("Right side: nothing authored, nothing fires"), Fired.IsEmpty());
    CollectCrossedCues(Cues, EInfinityMechanismSoundCueSide::Pair, 0.4, 0.95, false, false, Fired);
    TestTrue(TEXT("A long forward step fires both pair cues in authored order"),
        Fired.Num() == 2 && Fired[0] == 0 && Fired[1] == 3);
    CollectCrossedCues(Cues, EInfinityMechanismSoundCueSide::Pair, 0.4, 0.95, false, true, Fired);
    TestTrue(TEXT("Muted: nothing fires"), Fired.IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismSoundPassageTest,
    "InfinityStage.MechanismSound.PassageFiresOnForwardPlaybackOnlyInGame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismSoundPassageTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetLocation(FVector(0.0, -400.0, 0.0));
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Right.LocalTransform.SetLocation(FVector(0.0, 400.0, 0.0));
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    // Pair 1: a 0.5 s OneShot from the Passage start, a pair slam at half way and
    // a Left-panel hit at three quarters. Pairs 0 and 2 author no sound.
    FInfinityMechanismMotion& Motion = Show->Cues[1].WingPair.Mechanism;
    Motion.PlaybackMode = EInfinityMotionPlaybackMode::OneShot;
    Motion.PhaseOrigin = EInfinityMotionPhaseOrigin::PassageStart;
    Motion.CycleRateHz = 2.0;
    Motion.SoundCues.Add(MakeSoundCue(TEXT("slam"), 0.5));
    Motion.SoundCues.Add(MakeSoundCue(TEXT("left_hit"), 0.75, EInfinityMechanismSoundCueSide::Left));
    Show->ReconcilePassageSettings();

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (!TestTrue(TEXT("Fixture compiles to one Passage of three wings"),
            Compiled.Passages.Num() == 1 && Compiled.Passages[0].Wings.Num() == 3))
    {
        return false;
    }
    const int32 Start = Compiled.Passages[0].SegmentStartFrame.Value;
    const int32 End = Compiled.Passages[0].SegmentEndFrame.Value;
    // 0.01 s per step. The test world never ticks, so its clock stands still and
    // only the gate's one-frame slack (1/60 s) admits a step: 0.01 s passes, a jump fails.
    const int32 Step = FMath::Max(1, FMath::RoundToInt32(Show->TickResolution.AsDecimal() * 0.01));
    const int32 RunEnd = Start + 70 * Step;
    if (!TestTrue(TEXT("The Passage is long enough for the 0.7 s run"), End > RunEnd))
    {
        return false;
    }

    // Built in an editor-type world, then retyped to Game (what PIE's copy is),
    // exactly as InfinityStage.BulbBody.GlassFollowsTheStrikeInGameOnly does.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    if (!TestTrue(TEXT("The Passage materializes"), Passage->MaterializePassage()))
    {
        World->DestroyWorld(false);
        return false;
    }
    Passage->SetMechanismSoundDryRunForTests(true);
    const TArray<FName>& Fired = Passage->GetFiredMechanismSoundsForTests();
    const auto PlayForward = [Passage, Step](const int32 From, const int32 To)
    {
        for (int32 Frame = From; Frame <= To; Frame += Step)
        {
            Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Frame));
        }
    };

    PlayForward(Start, RunEnd);
    TestEqual(TEXT("Editor world: a full forward run never makes a sound"), Fired.Num(), 0);

    World->WorldType = EWorldType::Game;
    TestTrue(TEXT("Fixture: the world now reads as a game world"), World->IsGameWorld());

    PlayForward(Start, RunEnd);
    TestEqual(TEXT("Forward playback fires each cue once"), Fired.Num(), 2);
    TestTrue(TEXT("...the slam at phase 0.5, then the Left hit at 0.75"),
        Fired.Num() == 2 && Fired[0] == FName(TEXT("slam")) && Fired[1] == FName(TEXT("left_hit")));

    for (int32 Repeat = 0; Repeat < 5; ++Repeat)
    {
        Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(RunEnd));
    }
    TestEqual(TEXT("Paused on a held frame: nothing more"), Fired.Num(), 2);

    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    TestEqual(TEXT("A rewind over both cues fires nothing"), Fired.Num(), 2);
    PlayForward(Start + Step, RunEnd);
    TestEqual(TEXT("After the rewind both cues are re-armed and fire again"), Fired.Num(), 4);

    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(RunEnd));
    TestEqual(TEXT("A forward jump over both cues fires nothing"), Fired.Num(), 4);

    // Phase = 0.02 per step here: step 37 is 0.74, step 38 is 0.76 (the Left hit is at 0.75).
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    PlayForward(Start + Step, Start + 37 * Step);
    TestEqual(TEXT("Stopping short of a cue does not fire it (only the slam)"), Fired.Num(), 5);
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(End + Step));
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start + 38 * Step));
    TestEqual(TEXT("Leaving the Passage forgets history: arriving just past a cue fires nothing"),
        Fired.Num(), 5);
    PlayForward(Start + 39 * Step, RunEnd);
    TestEqual(TEXT("...and the rest of the run has nothing left to fire"), Fired.Num(), 5);

    Show->Cues[1].WingPair.bMuteMechanismSound = true;
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    PlayForward(Start + Step, RunEnd);
    TestEqual(TEXT("A muted pair is silent"), Fired.Num(), 5);
    Show->Cues[1].WingPair.bMuteMechanismSound = false;

    Show->PassageSettings[0].MechanismSound.bMuteSoundCues = true;
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    PlayForward(Start + Step, RunEnd);
    TestEqual(TEXT("The Passage cue mute silences every pair"), Fired.Num(), 5);
    Show->PassageSettings[0].MechanismSound.bMuteSoundCues = false;

    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    PlayForward(Start + Step, RunEnd);
    TestEqual(TEXT("Positive control: unmuted, both cues fire again"), Fired.Num(), 7);

    Show->Cues[1].WingPair.Mechanism.SoundCues.Reset();
    Passage->EvaluateMechanismsAtMasterFrame(FFrameNumber(Start));
    PlayForward(Start + Step, RunEnd);
    TestEqual(TEXT("With no cues authored nothing fires"), Fired.Num(), 7);

    World->WorldType = EWorldType::EditorPreview;
    World->DestroyWorld(false);
    return true;
}

#endif
