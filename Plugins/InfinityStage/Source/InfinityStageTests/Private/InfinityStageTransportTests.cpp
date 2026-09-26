#include "InfinityStageShowAsset.h"
#include "InfinityStageTransportController.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneMarkedFrame.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Handover rules, asserted without a world.
 *
 * ResolveHandover answers "which camera does the show use here, and how does
 * the view get to it" from the compiled segment table alone. That is what makes
 * the seams testable: no PIE, no player controller, no rendered frame, and no
 * dependence on editor screenshots.
 */
namespace
{
constexpr int32 WingIntervalFrames = 48000;
constexpr int32 CueDurationFrames = 240000;

UInfinityStageShowAsset* MakeShow()
{
    return NewObject<UInfinityStageShowAsset>(GetTransientPackage());
}

UInfinityStageTransportController* MakeTransport()
{
    return NewObject<UInfinityStageTransportController>(GetTransientPackage());
}

/** A Passage of two wing pairs, so the segment has a non-zero length. */
void AddPassage(UInfinityStageShowAsset& Show)
{
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = WingIntervalFrames;
    }
}

/** Returns the cue index; the array reference would not survive the next add. */
int32 AddCue(UInfinityStageShowAsset& Show, const EInfinityCueType Type, const TCHAR* Label)
{
    const int32 Index = Show.Cues.Num();
    FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
    Cue.Type = Type;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.Label = FText::FromString(Label);
    Cue.Scene.DurationFrames = CueDurationFrames;
    return Index;
}

/** A post-Scene interstitial that reveals the next Passage once it is covered. */
int32 AddCoveredInterstitial(UInfinityStageShowAsset& Show, const TCHAR* Label)
{
    const int32 Index = AddCue(Show, EInfinityCueType::Sequence, Label);
    FInfinitySceneCueData& Scene = Show.Cues[Index].Scene;
    Scene.DurationFrames = 360000;
    Scene.CurtainMode = EInfinityCurtainCueMode::PostSceneInterstitial;
    Scene.bRetainPreviousCamera = true;
    Scene.bRevealNextPassageWhenCovered = true;
    Scene.CurtainEntryTransitionFrames = 48000;
    Scene.CurtainHoldFrames = 240000;
    Scene.CurtainExitTransitionFrames = 48000;
    return Index;
}

/**
 * A sequence whose playback range deliberately does not start at frame zero.
 *
 * A Scene sub-section places the sequence's playback start on the segment's
 * first frame, so a marker's offset has to be measured from the playback range.
 * Starting at zero would hide the arithmetic this asserts.
 */
ULevelSequence* MakeSequence(
    const UInfinityStageShowAsset& Show,
    const int32 PlaybackStart,
    const int32 Duration)
{
    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    Sequence->GetMovieScene()->SetTickResolutionDirectly(Show.TickResolution);
    Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(PlaybackStart), Duration);
    return Sequence;
}

void AddHiddenChangeoverMarker(ULevelSequence& Sequence, const int32 AbsoluteFrame)
{
    FMovieSceneMarkedFrame Marker(FFrameNumber(AbsoluteFrame));
    Marker.Label = TEXT("InfinityStage.HiddenChangeover");
    Sequence.GetMovieScene()->AddMarkedFrame(Marker);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHandoverRetainChainTest,
    "InfinityStage.Transport.HandoverResolvesRetainChain",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHandoverRetainChainTest::RunTest(const FString& Parameters)
{
    // Passage, then a Scene that retains, then an interstitial that retains too.
    // Two retaining segments in a row must walk all the way back to a camera
    // that actually exists, not stop at a segment that was itself borrowing one.
    UInfinityStageShowAsset* Show = MakeShow();
    AddPassage(*Show);
    const int32 SceneCue = AddCue(*Show, EInfinityCueType::Scene, TEXT("Scene One"));
    Show->Cues[SceneCue].Scene.bRetainPreviousCamera = true;
    const int32 HoldCue = AddCue(*Show, EInfinityCueType::Sequence, TEXT("Held Interstitial"));
    Show->Cues[HoldCue].Scene.bRetainPreviousCamera = true;
    AddPassage(*Show);

    UInfinityStageTransportController* Transport = MakeTransport();
    TestTrue(TEXT("The retain-chain Show compiles into segments"), Transport->BuildSegments(Show));
    TestEqual(TEXT("Passage, Scene, interstitial, Passage"), Transport->Segments.Num(), 4);
    if (Transport->Segments.Num() != 4)
    {
        return false;
    }

    const FFrameNumber Inside = Transport->Segments[2].StartFrame + FFrameNumber(1000);
    const FInfinityCameraHandover Handover = Transport->ResolveHandover(2, Inside);
    TestEqual(TEXT("A chained retain resolves"),
        Handover.Resolution, EInfinityHandoverResolution::Resolved);
    TestEqual(TEXT("It lands on a camera that exists, not on the borrowing segment"),
        Handover.Source, EInfinityHandoverSource::PassageRig);
    TestEqual(TEXT("Both retains are followed back to the first Passage"),
        Handover.SegmentIndex, 0);
    TestEqual(TEXT("The Passage camera is sampled at its own last frame"),
        Handover.Frame, Transport->Segments[0].EndFrame);
    TestEqual(TEXT("The request is reported alongside the answer"),
        Handover.RequestedSegmentIndex, 2);
    TestFalse(TEXT("An uncovered seam is not marked covered"), Handover.bCovered);

    // The same rule, one link shorter, so a single retain is not a special case.
    const FInfinityCameraHandover Single = Transport->ResolveHandover(1, Transport->Segments[1].StartFrame);
    TestEqual(TEXT("A single retain resolves to the Passage too"),
        Single.SegmentIndex, 0);
    TestEqual(TEXT("A single retain resolves"),
        Single.Resolution, EInfinityHandoverResolution::Resolved);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHandoverNamesFailuresTest,
    "InfinityStage.Transport.HandoverNamesItsFailures",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHandoverNamesFailuresTest::RunTest(const FString& Parameters)
{
    // Every one of these used to be a silent return: the previous camera stayed
    // live, the show carried on looking almost right, and nothing was logged.
    {
        UInfinityStageShowAsset* Show = MakeShow();
        const int32 HoldCue = AddCue(*Show, EInfinityCueType::Sequence, TEXT("Opening Hold"));
        Show->Cues[HoldCue].Scene.bRetainPreviousCamera = true;
        AddPassage(*Show);

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The leading-retain Show compiles"), Transport->BuildSegments(Show));
        const FInfinityCameraHandover Handover = Transport->ResolveHandover(0, 0);
        TestEqual(TEXT("Retaining with nothing in front of you is named, not silent"),
            Handover.Resolution, EInfinityHandoverResolution::RetainWithoutPrevious);
        TestFalse(TEXT("It does not claim to have resolved"), Handover.IsResolved());
        TestEqual(TEXT("No camera source is invented"),
            Handover.Source, EInfinityHandoverSource::None);
    }

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        AddCoveredInterstitial(*Show, TEXT("Final Changeover"));

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The trailing-interstitial Show compiles"), Transport->BuildSegments(Show));
        TestEqual(TEXT("Passage then interstitial"), Transport->Segments.Num(), 2);
        if (Transport->Segments.Num() != 2)
        {
            return false;
        }
        TestEqual(TEXT("There is no Passage after the last segment"),
            Transport->FindNextPassageSegment(1), INDEX_NONE);

        const FFrameNumber Covered = Transport->Segments[1].CoveredHandoffFrame;
        TestTrue(TEXT("The covered changeover is active at its own frame"),
            Transport->IsCoveredHandoffActive(1, Covered));
        const FInfinityCameraHandover Handover = Transport->ResolveHandover(1, Covered);
        TestEqual(TEXT("A reveal with nothing to reveal is named, not silent"),
            Handover.Resolution, EInfinityHandoverResolution::NoFollowingPassage);
        TestFalse(TEXT("A failed reveal does not resolve"), Handover.IsResolved());
    }

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        AddCue(*Show, EInfinityCueType::Scene, TEXT("Scene With No Shot"));

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The unshot-Scene Show compiles"), Transport->BuildSegments(Show));
        const FInfinityCameraHandover Handover = Transport->ResolveHandover(1, Transport->Segments[1].StartFrame);
        TestEqual(TEXT("A Scene with no Camera Cut and no retain supplies no camera, and says so"),
            Handover.Resolution, EInfinityHandoverResolution::NoRuleForSegment);
        TestEqual(TEXT("The unresolved segment is reported"), Handover.SegmentIndex, 1);
    }

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The single-Passage Show compiles"), Transport->BuildSegments(Show));
        const FInfinityCameraHandover Handover = Transport->ResolveHandover(7, 0);
        TestEqual(TEXT("An out-of-range request is named"),
            Handover.Resolution, EInfinityHandoverResolution::NoSuchSegment);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCoveredHandoffSourceTest,
    "InfinityStage.Transport.CoveredHandoffOffsetSource",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCoveredHandoffSourceTest::RunTest(const FString& Parameters)
{
    // A marker and a fallback are both legitimate. A sequence that failed to
    // load looking exactly like a sequence with no marker is not: it makes the
    // changeover move with load state, which reads as unreproducible timing.
    constexpr int32 PlaybackStart = 1000;
    constexpr int32 MarkerOffset = 72000;
    constexpr int32 EntryPlusHold = 48000 + 240000;

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        const int32 HoldCue = AddCoveredInterstitial(*Show, TEXT("Marked Changeover"));
        ULevelSequence* Sequence = MakeSequence(*Show, PlaybackStart, 360000);
        AddHiddenChangeoverMarker(*Sequence, PlaybackStart + MarkerOffset);
        Show->Cues[HoldCue].Scene.Sequence = Sequence;
        AddPassage(*Show);

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The marked Show compiles"), Transport->BuildSegments(Show));
        TestEqual(TEXT("Passage, interstitial, Passage"), Transport->Segments.Num(), 3);
        if (Transport->Segments.Num() != 3)
        {
            return false;
        }
        TestEqual(TEXT("The marker is used, and the segment records that it was"),
            Transport->Segments[1].CoveredHandoffSource,
            EInfinityCoveredHandoffSource::SequenceMarker);
        // The sub-section puts the sequence's playback start on the segment's
        // first frame, so the offset is measured from there. Measuring it from
        // the sequence's own frame zero handed off late by PlaybackStart.
        TestEqual(TEXT("The marker offset is measured from the sequence's playback start"),
            Transport->Segments[1].CoveredHandoffFrame,
            Transport->Segments[1].StartFrame + FFrameNumber(MarkerOffset));
    }

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        const int32 HoldCue = AddCoveredInterstitial(*Show, TEXT("Unmarked Changeover"));
        Show->Cues[HoldCue].Scene.Sequence = MakeSequence(*Show, PlaybackStart, 360000);
        AddPassage(*Show);

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The unmarked Show compiles"), Transport->BuildSegments(Show));
        TestEqual(TEXT("A loaded sequence with no marker is distinguishable"),
            Transport->Segments[1].CoveredHandoffSource,
            EInfinityCoveredHandoffSource::FallbackNoMarker);
        TestEqual(TEXT("It falls back to entry plus hold"),
            Transport->Segments[1].CoveredHandoffFrame,
            Transport->Segments[1].StartFrame + FFrameNumber(EntryPlusHold));
    }

    {
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        AddCoveredInterstitial(*Show, TEXT("Sequenceless Changeover"));
        AddPassage(*Show);

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The sequenceless Show compiles"), Transport->BuildSegments(Show));
        TestEqual(TEXT("A cue with no sequence at all is distinguishable from one with no marker"),
            Transport->Segments[1].CoveredHandoffSource,
            EInfinityCoveredHandoffSource::FallbackNoSequenceAssigned);
        TestEqual(TEXT("It falls back to the same entry plus hold"),
            Transport->Segments[1].CoveredHandoffFrame,
            Transport->Segments[1].StartFrame + FFrameNumber(EntryPlusHold));
    }

    {
        // A cue that is not a covered changeover must not claim a timing source.
        UInfinityStageShowAsset* Show = MakeShow();
        AddPassage(*Show);
        AddCue(*Show, EInfinityCueType::Scene, TEXT("Ordinary Scene"));

        UInfinityStageTransportController* Transport = MakeTransport();
        TestTrue(TEXT("The ordinary Show compiles"), Transport->BuildSegments(Show));
        TestEqual(TEXT("A cue with no covered changeover reports no timing source"),
            Transport->Segments[1].CoveredHandoffSource,
            EInfinityCoveredHandoffSource::NotApplicable);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCoveredSeamIsACutTest,
    "InfinityStage.Transport.CoveredSeamIsACut",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCoveredSeamIsACutTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = MakeShow();
    AddPassage(*Show);
    AddCoveredInterstitial(*Show, TEXT("Changeover"));
    AddPassage(*Show);

    UInfinityStageTransportController* Transport = MakeTransport();
    TestTrue(TEXT("The changeover Show compiles"), Transport->BuildSegments(Show));
    TestEqual(TEXT("Passage, interstitial, Passage"), Transport->Segments.Num(), 3);
    if (Transport->Segments.Num() != 3)
    {
        return false;
    }

    // Shipped default: every seam is the cut it has always been, so nothing in
    // the show changes look until someone chooses a blend and watches it.
    TestTrue(TEXT("Handovers ship as cuts"), Transport->PassageEntryBlend.IsCut());
    TestTrue(TEXT("Scene handovers ship as cuts"), Transport->SceneEntryBlend.IsCut());

    Transport->PassageEntryBlend.BlendSeconds = 1.25f;
    Transport->PassageEntryBlend.Function = EInfinityHandoverBlendFunction::EaseInOut;

    const FFrameNumber BeforeCover = Transport->Segments[1].StartFrame;
    const FFrameNumber AfterCover = Transport->Segments[1].CoveredHandoffFrame;
    TestTrue(TEXT("The fixture has a covered threshold inside the interstitial"),
        AfterCover > BeforeCover && AfterCover < Transport->Segments[1].EndFrame);

    const FInfinityCameraHandover Visible = Transport->ResolveHandover(1, BeforeCover);
    TestEqual(TEXT("Before cover the interstitial keeps the outgoing Passage camera"),
        Visible.SegmentIndex, 0);
    TestFalse(TEXT("That seam is in front of the audience"), Visible.bCovered);
    TestEqual(TEXT("A visible seam carries the authored blend"),
        Visible.Blend.BlendSeconds, 1.25f);
    TestFalse(TEXT("A visible seam is not a cut"), Visible.Blend.IsCut());

    const FInfinityCameraHandover Hidden = Transport->ResolveHandover(1, AfterCover);
    TestEqual(TEXT("Once covered, the next Passage is revealed"), Hidden.SegmentIndex, 2);
    TestEqual(TEXT("It is established at the Passage's own first frame"),
        Hidden.Frame, Transport->Segments[2].StartFrame);
    TestTrue(TEXT("That seam is behind the curtain"), Hidden.bCovered);
    TestTrue(TEXT("A seam nobody can see is always a cut"), Hidden.Blend.IsCut());

    // The rule is a default, not a law: an author can still blend behind cloth.
    Transport->bCutWhenCovered = false;
    const FInfinityCameraHandover Forced = Transport->ResolveHandover(1, AfterCover);
    TestEqual(TEXT("Turning the rule off restores the authored blend"),
        Forced.Blend.BlendSeconds, 1.25f);
    TestEqual(TEXT("The blend shape survives the round trip"),
        Forced.Blend.Function, EInfinityHandoverBlendFunction::EaseInOut);
    return true;
}

#endif
