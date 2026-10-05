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
 * Boundary rest (Gary, 5 Oct): "I come to the end of S01 and the camera stops,
 * implying the next cue is up. When I hit Right arrow I jump straight [to P02]."
 *
 * A segment's EndFrame is exclusive and is the next segment's StartFrame, so at
 * the stop the playhead already reads as the NEXT segment and Advance went one
 * further. The transport now remembers that it came to rest at K's end, so RIGHT
 * lands on K+1, and a landed transition (Sequence cue) holds to be examined.
 *
 * Fixture: P01 (Passage), S1 (Scene), I1 (covered post-Scene interstitial,
 * Sequence), P02 (Passage), S2 (Scene) - the shape of the show's first seam.
 */
namespace InfinityStageTransportBoundaryTests
{
constexpr int32 P01 = 0;
constexpr int32 S1 = 1;
constexpr int32 I1 = 2;
constexpr int32 P02 = 3;
constexpr int32 S2 = 4;
constexpr int32 SegmentCount = 5;

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

void AddScene(UInfinityStageShowAsset& Show, const TCHAR* Label)
{
    FInfinityShowCue& Scene = Show.Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Label = FText::FromString(Label);
    Scene.Scene.DurationFrames = 100;
    Scene.Scene.bRetainPreviousCamera = true;
}

/** A post-Scene curtain interstitial that reveals the next Passage once covered. */
void AddInterstitial(UInfinityStageShowAsset& Show)
{
    FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::Sequence;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.Label = FText::FromString(TEXT("Interaction 1"));
    Cue.Scene.DurationFrames = 100;
    Cue.Scene.CurtainMode = EInfinityCurtainCueMode::PostSceneInterstitial;
    Cue.Scene.bRetainPreviousCamera = true;
    Cue.Scene.bRevealNextPassageWhenCovered = true;
    Cue.Scene.CurtainEntryTransitionFrames = 20;
    Cue.Scene.CurtainHoldFrames = 30;
    Cue.Scene.CurtainExitTransitionFrames = 20;
}

UInfinityStageShowAsset* MakeFirstSeamShow()
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Show->DisplayRate = FFrameRate(24, 1);
    Show->TickResolution = Show->DisplayRate;
    AddPassage(*Show);
    AddScene(*Show, TEXT("Scene 1"));
    AddInterstitial(*Show);
    AddPassage(*Show);
    AddScene(*Show, TEXT("Scene 2"));
    return Show;
}

struct FBoundaryFixture
{
    UWorld* World = nullptr;
    UInfinityStageTransportController* Transport = nullptr;
    ULevelSequencePlayer* Player = nullptr;

    ~FBoundaryFixture()
    {
        if (World)
        {
            World->DestroyWorld(false);
        }
    }

    bool Initialize(FAutomationTestBase& Test)
    {
        UInfinityStageShowAsset* Show = MakeFirstSeamShow();
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

        Test.TestNotNull(TEXT("Fixture: game world"), World);
        Test.TestTrue(TEXT("Fixture: segments compile"), bBuilt);
        Test.TestNotNull(TEXT("Fixture: real Level Sequence player"), Player);
        const bool bInitialized = Transport && Player && Transport->InitializeTransport(Player, Show);
        Test.TestTrue(TEXT("Fixture: transport initializes"), bInitialized);
        if (!bInitialized)
        {
            return false;
        }
        Transport->bPerformanceMode = false;

        // The fixture is only meaningful with the show's shape and with seams
        // that touch: an exclusive end equal to the next start is the whole bug.
        const TArray<FInfinityTransportSegment>& Segments = Transport->Segments;
        Test.TestEqual(TEXT("Fixture: P01, S1, I1, P02, S2"), Segments.Num(), SegmentCount);
        if (Segments.Num() != SegmentCount)
        {
            return false;
        }
        const EInfinityCueType Expected[SegmentCount] = {
            EInfinityCueType::WingPair, EInfinityCueType::Scene, EInfinityCueType::Sequence,
            EInfinityCueType::WingPair, EInfinityCueType::Scene};
        bool bShape = true;
        for (int32 Index = 0; Index < SegmentCount; ++Index)
        {
            bShape &= Segments[Index].Type == Expected[Index];
            if (Index + 1 < SegmentCount)
            {
                bShape &= Segments[Index].EndFrame == Segments[Index + 1].StartFrame;
            }
        }
        Test.TestTrue(TEXT("Fixture: segment types in show order, seams touching"), bShape);
        Test.TestTrue(TEXT("Fixture: I1 has a covered threshold inside it"),
            Segments[I1].bRevealNextPassageWhenCovered
            && Segments[I1].CoveredHandoffFrame > Segments[I1].StartFrame
            && Segments[I1].CoveredHandoffFrame < Segments[I1].EndFrame);
        return bShape;
    }

    FFrameNumber Start(const int32 Index) const { return Transport->Segments[Index].StartFrame; }
    FFrameNumber End(const int32 Index) const { return Transport->Segments[Index].EndFrame; }

    /** Stops the player on a frame without telling the transport, as a PlayTo arrival does. */
    void StopPlayerAt(const FFrameNumber Frame)
    {
        Player->Pause();
        Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(
            FFrameTime(Frame), EUpdatePositionMethod::Jump));
    }

    /**
     * Comes to rest at the end of segment K the way the operator does: a jump to
     * K's start, then Space (PlayForwardToBoundary), then the PlayTo arrival -
     * Sequencer pauses on the target - and the boundary tick that follows it.
     */
    bool RestAtEndOf(FAutomationTestBase& Test, const int32 K)
    {
        const bool bScrubbed = Transport->ScrubToMasterFrame(Start(K)) == EInfinityTransportResult::Succeeded;
        const bool bPlayed = Transport->PlayForwardToBoundary() == EInfinityTransportResult::Succeeded;
        const TOptional<FFrameNumber> Target = Transport->GetLastPlayToTargetForTests();
        StopPlayerAt(End(K));
        Transport->TickComponent(0.0f, LEVELTICK_All, nullptr);
        const bool bAtRest = bScrubbed && bPlayed
            && Target.IsSet() && Target.GetValue() == End(K)
            && !Transport->IsTransportPlaying()
            && Transport->GetCurrentMasterFrame() == End(K);
        Test.TestTrue(FString::Printf(TEXT("Fixture: played to rest at the end of segment %d"), K), bAtRest);
        return bAtRest;
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestPureRulesTest,
    "InfinityStage.Transport.BoundaryRest.PureRules",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestPureRulesTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    using UTransport = UInfinityStageTransportController;
    FInfinityTransportRest Rest;
    Rest.Set(1, FFrameNumber(400));
    TestEqual(TEXT("Stopped on the rest frame: the rest applies"),
        UTransport::ResolveRestSegment(Rest, FFrameNumber(400), false), 1);
    TestEqual(TEXT("Still playing: not at rest yet"),
        UTransport::ResolveRestSegment(Rest, FFrameNumber(400), true), int32(INDEX_NONE));
    TestEqual(TEXT("Stopped anywhere else (a pause, a GO hold): stale"),
        UTransport::ResolveRestSegment(Rest, FFrameNumber(399), false), int32(INDEX_NONE));
    Rest.Reset();
    TestEqual(TEXT("A cleared rest never applies"),
        UTransport::ResolveRestSegment(Rest, FFrameNumber(0), false), int32(INDEX_NONE));

    // Held at the end of S1 (K=1) the playhead reads as I1 (selected=2).
    TestEqual(TEXT("Held at the end of K: Advance targets K+1"),
        UTransport::ResolveAdvanceTargetIndex(I1, S1), I1);
    // Control: the pre-5-Oct rule was selected+1, i.e. P02 from here.
    TestNotEqual(TEXT("Control: the two rules disagree exactly at the rest"),
        UTransport::ResolveAdvanceTargetIndex(I1, S1), I1 + 1);
    TestEqual(TEXT("At a genuine start (no rest), Advance targets selected+1"),
        UTransport::ResolveAdvanceTargetIndex(I1, INDEX_NONE), P02);

    TestEqual(TEXT("Previous held at the end of K returns to K"),
        UTransport::ResolvePreviousTargetIndex(I1, false, S1), S1);
    TestEqual(TEXT("Previous past a segment's start restarts it"),
        UTransport::ResolvePreviousTargetIndex(I1, true, INDEX_NONE), I1);
    TestEqual(TEXT("Previous on a segment's first frame goes to the one before"),
        UTransport::ResolvePreviousTargetIndex(I1, false, INDEX_NONE), S1);

    TestFalse(TEXT("Rehearsal: a landed Sequence holds"),
        UTransport::AutoPlaysOnAdvance(EInfinityCueType::Sequence, false, true));
    TestTrue(TEXT("Performance: a landed Sequence plays"),
        UTransport::AutoPlaysOnAdvance(EInfinityCueType::Sequence, true, false));
    TestTrue(TEXT("Scene autoplay is still its own switch"),
        UTransport::AutoPlaysOnAdvance(EInfinityCueType::Scene, false, true));
    TestFalse(TEXT("A Scene holds without it"),
        UTransport::AutoPlaysOnAdvance(EInfinityCueType::Scene, true, false));
    TestFalse(TEXT("A Passage always holds"),
        UTransport::AutoPlaysOnAdvance(EInfinityCueType::WingPair, true, true));

    UInfinityStageTransportController* Defaults = NewObject<UInfinityStageTransportController>(GetTransientPackage());
    TestFalse(TEXT("The shipped default holds transitions for examination"), Defaults->bAutoPlaySequenceOnAdvance);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestAdvanceLandsOnNextCueTest,
    "InfinityStage.Transport.BoundaryRest.AdvanceFromPlayedEndLandsOnNextCue",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestAdvanceLandsOnNextCueTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    {
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        const int32 OldRuleTarget = Fixture.Transport->FindSegmentAtFrame(Fixture.End(S1)) + 1;
        TestEqual(TEXT("Control: at S1's end the frame alone reads as I1, so the old rule targets P02"),
            OldRuleTarget, P02);
        TestEqual(TEXT("The rest is reported as the end of S1"), Fixture.Transport->GetHeldAtEndSegmentIndex(), S1);

        TestEqual(TEXT("Advance at S1's end succeeds"),
            Fixture.Transport->AdvanceToNextSegment(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("...and selects Interaction 1, not P02"), Fixture.Transport->SelectedSegmentIndex, I1);
        TestEqual(TEXT("...on Interaction 1's first frame"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(I1));
        TestNotEqual(TEXT("...which is not where the old rule went"),
            Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(OldRuleTarget));
    }

    {
        // The viewport RIGHT path: StepShotForward, which falls through to Advance.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        TestEqual(TEXT("RIGHT at S1's end succeeds"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("RIGHT at S1's end lands on Interaction 1"), Fixture.Transport->SelectedSegmentIndex, I1);
        TestEqual(TEXT("RIGHT at S1's end lands on its first frame"),
            Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(I1));
    }

    {
        // Every boundary, not only Scene to Interaction: a Passage played to its end.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, P01))
        {
            return false;
        }
        TestEqual(TEXT("Control: at P01's end the old rule targets I1"),
            Fixture.Transport->FindSegmentAtFrame(Fixture.End(P01)) + 1, I1);
        TestEqual(TEXT("RIGHT at P01's end succeeds"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("RIGHT at P01's end lands on Scene 1, not Interaction 1"),
            Fixture.Transport->SelectedSegmentIndex, S1);
        TestEqual(TEXT("...on Scene 1's first frame"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(S1));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestAdvanceWalksEverySegmentTest,
    "InfinityStage.Transport.BoundaryRest.AdvanceWalksEverySegmentOnce",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestAdvanceWalksEverySegmentTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    {
        // At a jumped-to start of K+1 there is no rest: Advance goes to K+2.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this))
        {
            return false;
        }
        TestEqual(TEXT("Fixture: scrub to Interaction 1's first frame"),
            Fixture.Transport->ScrubToMasterFrame(Fixture.Start(I1)), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("A scrub is not a rest"), Fixture.Transport->GetHeldAtEndSegmentIndex(), int32(INDEX_NONE));
        TestEqual(TEXT("Advance at a genuine I1 start succeeds"),
            Fixture.Transport->AdvanceToNextSegment(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Advance at a genuine I1 start goes on to P02"), Fixture.Transport->SelectedSegmentIndex, P02);
        TestEqual(TEXT("...on P02's first frame"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(P02));
    }

    {
        // Repeated RIGHT from the top: every segment is landed on once, in order.
        // The held transition takes one extra RIGHT (its GO) and is not skipped.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this))
        {
            return false;
        }
        TestEqual(TEXT("Fixture: scrub to the top"),
            Fixture.Transport->ScrubToMasterFrame(Fixture.Start(P01)), EInfinityTransportResult::Succeeded);
        TArray<int32> Landed;
        int32 Plays = 0;
        for (int32 Press = 0; Press < 2 * SegmentCount; ++Press)
        {
            const int32 Armed = Fixture.Transport->GetArmedSequenceSegmentIndex();
            const EInfinityTransportResult Result = Fixture.Transport->StepShotForward();
            if (Result == EInfinityTransportResult::NoSegment)
            {
                break;
            }
            TestEqual(FString::Printf(TEXT("RIGHT %d succeeds"), Press + 1), Result, EInfinityTransportResult::Succeeded);
            if (Armed != INDEX_NONE)
            {
                ++Plays;
                TestTrue(TEXT("RIGHT at an armed transition plays it"), Fixture.Transport->IsTransportPlaying());
                const TOptional<FFrameNumber> Target = Fixture.Transport->GetLastPlayToTargetForTests();
                TestTrue(TEXT("...bounded at the transition's own end"),
                    Target.IsSet() && Target.GetValue() == Fixture.End(Armed));
                continue;
            }
            Landed.Add(Fixture.Transport->SelectedSegmentIndex);
            TestEqual(FString::Printf(TEXT("RIGHT %d lands on a first frame"), Press + 1),
                Fixture.Transport->GetCurrentMasterFrame(),
                Fixture.Start(Fixture.Transport->SelectedSegmentIndex));
        }
        const TArray<int32> Expected = {S1, I1, P02, S2};
        TestEqual(TEXT("RIGHT visits S1, I1, P02, S2 exactly once each, in order"), Landed, Expected);
        TestEqual(TEXT("Only the transition took a GO press"), Plays, 1);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestSequenceHoldsTest,
    "InfinityStage.Transport.BoundaryRest.SequenceHoldsUnlessAutoPlay",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestSequenceHoldsTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    {
        // Rehearsal default: land, hold, then RIGHT plays - and the covered
        // handoff still happens as playback crosses its threshold.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        TestFalse(TEXT("Fixture: default is hold"), Fixture.Transport->bAutoPlaySequenceOnAdvance);
        TestEqual(TEXT("RIGHT at S1's end lands"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestFalse(TEXT("The landed transition holds"), Fixture.Transport->IsTransportPlaying());
        TestEqual(TEXT("...armed"), Fixture.Transport->GetArmedSequenceSegmentIndex(), I1);
        TestEqual(TEXT("...on its first frame"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(I1));

        TestEqual(TEXT("A second RIGHT is its GO"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestTrue(TEXT("The transition now plays"), Fixture.Transport->IsTransportPlaying());
        const TOptional<FFrameNumber> Target = Fixture.Transport->GetLastPlayToTargetForTests();
        TestTrue(TEXT("...to its own boundary, not through P02"),
            Target.IsSet() && Target.GetValue() == Fixture.End(I1));
        TestEqual(TEXT("Playing disarms it"), Fixture.Transport->GetArmedSequenceSegmentIndex(), int32(INDEX_NONE));

        const FFrameNumber Covered = Fixture.Transport->Segments[I1].CoveredHandoffFrame;
        Fixture.Player->SetPlaybackPosition(FMovieSceneSequencePlaybackParams(
            FFrameTime(Covered), EUpdatePositionMethod::Jump));
        Fixture.Transport->TickComponent(0.0f, LEVELTICK_All, nullptr);
        TestTrue(TEXT("Crossing the covered threshold still hands over behind the curtain"),
            Fixture.Transport->LastHandover.bCovered);
        TestEqual(TEXT("...to P02, revealed at its first frame"), Fixture.Transport->LastHandover.SegmentIndex, P02);
        TestEqual(TEXT("...sampled at P02's start"), Fixture.Transport->LastHandover.Frame, Fixture.Start(P02));
    }

    {
        // Space at the held transition does the same as the GO press.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        Fixture.Transport->AdvanceToNextSegment();
        TestFalse(TEXT("Space fixture: the transition holds"), Fixture.Transport->IsTransportPlaying());
        TestEqual(TEXT("Space plays the held transition"),
            Fixture.Transport->PlayForwardToBoundary(), EInfinityTransportResult::Succeeded);
        const TOptional<FFrameNumber> Target = Fixture.Transport->GetLastPlayToTargetForTests();
        TestTrue(TEXT("Space plays it to its own boundary"),
            Fixture.Transport->IsTransportPlaying() && Target.IsSet() && Target.GetValue() == Fixture.End(I1));
    }

    {
        // Control: with the performance switch on, landing plays at once.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        Fixture.Transport->bAutoPlaySequenceOnAdvance = true;
        TestEqual(TEXT("Performance RIGHT at S1's end succeeds"),
            Fixture.Transport->StepShotForward(), EInfinityTransportResult::Succeeded);
        TestTrue(TEXT("Performance: the landed transition plays at once"), Fixture.Transport->IsTransportPlaying());
        const TOptional<FFrameNumber> Target = Fixture.Transport->GetLastPlayToTargetForTests();
        TestTrue(TEXT("Performance: bounded at I1's end"), Target.IsSet() && Target.GetValue() == Fixture.End(I1));
        TestEqual(TEXT("Performance: nothing is left armed"),
            Fixture.Transport->GetArmedSequenceSegmentIndex(), int32(INDEX_NONE));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestPreviousTest,
    "InfinityStage.Transport.BoundaryRest.PreviousAtHeldEndReturnsToItsStart",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestPreviousTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    {
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        TestEqual(TEXT("Previous at S1's end succeeds"),
            Fixture.Transport->JumpToPreviousSegment(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Previous at S1's end restarts S1"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(S1));
    }
    {
        // The viewport LEFT path (S1 has no shots, so it falls through to Previous).
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        TestEqual(TEXT("LEFT at S1's end succeeds"),
            Fixture.Transport->StepShotBack(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("LEFT at S1's end restarts S1"), Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(S1));
    }
    {
        // Control: Previous is not a constant - inside I1 it restarts I1.
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this))
        {
            return false;
        }
        TestEqual(TEXT("Control fixture: scrub inside I1"),
            Fixture.Transport->ScrubToMasterFrame(Fixture.Start(I1) + FFrameNumber(10)),
            EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Control: Previous inside I1 succeeds"),
            Fixture.Transport->JumpToPreviousSegment(), EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Control: Previous inside I1 restarts I1"),
            Fixture.Transport->GetCurrentMasterFrame(), Fixture.Start(I1));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBoundaryRestClearedByNavigationTest,
    "InfinityStage.Transport.BoundaryRest.NavigationClearsHeldEnd",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBoundaryRestClearedByNavigationTest::RunTest(const FString& Parameters)
{
    // Block scope: a file-scope using-directive would leak into the unity blob.
    using namespace InfinityStageTransportBoundaryTests;
    // After each operation the player is put back on S1's end WITHOUT telling the
    // transport. Only an explicit clear can then make the rest go away - a rest
    // that was merely stale (moved, playing) would come back and fail here.
    struct FOperation
    {
        const TCHAR* Name;
        TFunction<EInfinityTransportResult(FBoundaryFixture&)> Run;
    };
    const TArray<FOperation> Operations = {
        {TEXT("Scrub to the same frame"), [](FBoundaryFixture& F) { return F.Transport->ScrubToMasterFrame(F.End(S1)); }},
        {TEXT("Next"), [](FBoundaryFixture& F) { return F.Transport->JumpToNextSegment(); }},
        {TEXT("Previous"), [](FBoundaryFixture& F) { return F.Transport->JumpToPreviousSegment(); }},
        {TEXT("Current start"), [](FBoundaryFixture& F) { return F.Transport->JumpToCurrentStart(); }},
        {TEXT("Reverse to boundary"), [](FBoundaryFixture& F) { return F.Transport->PlayReverseToBoundary(); }},
        {TEXT("Resume forward"), [](FBoundaryFixture& F) { return F.Transport->ResumeForward(); }},
        {TEXT("Shuttle reverse"), [](FBoundaryFixture& F) { return F.Transport->Shuttle(-1.0f); }},
        {TEXT("Play through boundaries"), [](FBoundaryFixture& F) { return F.Transport->PlayForwardThroughBoundaries(); }},
    };
    for (const FOperation& Operation : Operations)
    {
        FBoundaryFixture Fixture;
        if (!Fixture.Initialize(*this) || !Fixture.RestAtEndOf(*this, S1))
        {
            return false;
        }
        TestEqual(FString::Printf(TEXT("%s: positive control, the rest is S1's end before it"), Operation.Name),
            Fixture.Transport->GetHeldAtEndSegmentIndex(), S1);
        TestEqual(FString::Printf(TEXT("%s: succeeds"), Operation.Name),
            Operation.Run(Fixture), EInfinityTransportResult::Succeeded);
        Fixture.StopPlayerAt(Fixture.End(S1));
        TestEqual(FString::Printf(TEXT("%s: clears the rest"), Operation.Name),
            Fixture.Transport->GetHeldAtEndSegmentIndex(), int32(INDEX_NONE));
        TestEqual(FString::Printf(TEXT("%s: Advance from that frame is a genuine-start Advance"), Operation.Name),
            Fixture.Transport->AdvanceToNextSegment(), EInfinityTransportResult::Succeeded);
        TestEqual(FString::Printf(TEXT("%s: ...which goes on to P02"), Operation.Name),
            Fixture.Transport->SelectedSegmentIndex, P02);
    }
    return true;
}

#endif
