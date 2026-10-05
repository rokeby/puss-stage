#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "MovieSceneInfinityAudioTrack.h"
#include "MovieSceneInfinityChoreoTrack.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MovieSceneInfinitySceneTrack.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "MovieScene.h"
#include "Sections/MovieSceneSubSection.h"
#include "Sound/SoundWave.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/*
 * InfinityStage.Editor.RetimeEverythingFollows
 *
 * The safety net proposed in Docs/Conductor/RETIME_ROBUSTNESS_AUDIT_2026-10-04.md sec. 4(1).
 * Everything here is TRANSIENT: a small Show + Master built in the transient package,
 * one EditorPreview world for the Passage actors / camera rigs / handoff cameras, and
 * nothing is saved. The saved Show and Master are never touched.
 *
 * Fixture (TickResolution 24000):
 *   P_A [A1 A2] | S1 Scene | P_B [B1 B2 B3] | S2 Scene | P_C [C1 C2]
 *   intervals 24000, tails 24000, no lead-in, Scenes 48000.
 *   P_A [0,48000)  S1 [48000,96000)  P_B [96000,168000)  S2 [168000,216000)  P_C [216000,264000)
 *   Choreo on P_B and P_C; music (one rail) on P_B and on S2; keys + pins on P_A and P_B;
 *   an UNMANAGED absolute sub-section at Master frame 200000 is the negative control.
 *
 * Part 1: S1 grows by 2 s (+48000). Everything after S1 must move by exactly +48000,
 *         nothing before it may move, Passage keys keep their section-relative frames.
 * Part 2: P_B's B2 IntervalToNext 24000 -> 12000 (-12000). Downstream moves by exactly
 *         -12000. The Passage's OWN content shows today's known-unsafe behaviour, which is
 *         asserted as-is and reported as RETIME_PASSAGE_KNOWN_GAP warnings (green, visible).
 */

namespace InfinityStageRetimeEverythingFollowsTest
{
struct FRetimeRange
{
    int32 Start = 0;
    int32 End = 0;
};

struct FRetimeKey
{
    int32 RelativeFrame = 0;
    double Value = 0.0;
};

struct FRetimePassageSnapshot
{
    FRetimeRange Range;
    /** One entry per EInfinityPassageCameraChannel, First..Last. */
    TArray<TArray<FRetimeKey>> ChannelKeys;
    TArray<int32> PinnedPassageFrames;
    TArray<FGuid> PinnedWingCueGuids;
};

struct FRetimeMusicSnapshot
{
    FRetimeRange Range;
    int32 StartOffset = 0;
    TArray<int32> EnvelopeTimes;
};

struct FRetimeSnapshot
{
    bool bCompiled = false;
    int32 ShowEnd = 0;
    FRetimeRange MasterPlayback;
    TMap<FGuid, FRetimeRange> Segments;
    /** Wing pass frames relative to their Passage's segment start, in wing order. */
    TMap<FGuid, TArray<int32>> RelativePassFrames;
    TMap<FGuid, FRetimePassageSnapshot> Passages;
    TMap<FGuid, FRetimeRange> SceneSections;
    TMap<FGuid, FRetimeRange> ChoreoSections;
    TMap<FGuid, FRetimeMusicSnapshot> MusicSections;
    FRetimeRange Control;
};

const TCHAR* const RetimeChannelNames[] = {
    TEXT("SpeedMultiplier"), TEXT("LongitudinalOffsetCm"), TEXT("LateralOffsetCm"), TEXT("HeightOffsetCm"),
    TEXT("PitchDegrees"), TEXT("YawDegrees"), TEXT("RollDegrees"), TEXT("LookAheadDistanceCm"),
    TEXT("FocalLengthMm"), TEXT("FocusDistanceCm"), TEXT("WingInwardTravelScale"), TEXT("WingCycleRateScale"),
    TEXT("WingPhaseBiasCycles") };

const TCHAR* RetimeChannelName(const int32 ChannelIndex)
{
    return ChannelIndex >= 0 && ChannelIndex < static_cast<int32>(UE_ARRAY_COUNT(RetimeChannelNames))
        ? RetimeChannelNames[ChannelIndex] : TEXT("UnknownChannel");
}

FRetimeRange RetimeSectionRange(const UMovieSceneSection& Section)
{
    FRetimeRange Range;
    Range.Start = Section.HasStartFrame() ? Section.GetInclusiveStartFrame().Value : TNumericLimits<int32>::Lowest();
    Range.End = Section.HasEndFrame() ? Section.GetExclusiveEndFrame().Value : TNumericLimits<int32>::Max();
    return Range;
}

FGuid RetimeAddWing(UInfinityStageShowAsset& Show, const int32 IntervalToNext)
{
    FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.IntervalToNext = IntervalToNext;
    Cue.WingPair.GapToNextCm = 500.0;
    return Cue.CueGuid;
}

FGuid RetimeAddScene(UInfinityStageShowAsset& Show, const TCHAR* Label, ULevelSequence* Sequence, const int32 DurationFrames)
{
    FInfinityShowCue& Cue = Show.Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::Scene;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.Label = FText::FromString(Label);
    Cue.Scene.bUseSequenceLength = false;
    Cue.Scene.DurationFrames = DurationFrames;
    Cue.Scene.ExitHandoffHoldFrames = 12000;
    Cue.Scene.Sequence = Sequence;
    return Cue.CueGuid;
}

FInfinityShowCue* RetimeFindCue(UInfinityStageShowAsset& Show, const FGuid CueGuid)
{
    return Show.Cues.FindByPredicate([CueGuid](const FInfinityShowCue& Cue) { return Cue.CueGuid == CueGuid; });
}

ULevelSequence* RetimeNewSequence(const FFrameRate TickResolution, const int32 PlaybackFrames)
{
    ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
    Sequence->Initialize();
    Sequence->GetMovieScene()->SetTickResolutionDirectly(TickResolution);
    Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(0), PlaybackFrames);
    return Sequence;
}

UMovieSceneInfinityPassageSection* RetimeFindPassageSection(ULevelSequence& Master, const FGuid PassageGuid)
{
    UMovieSceneInfinityPassageTrack* Track = Master.GetMovieScene()->FindTrack<UMovieSceneInfinityPassageTrack>();
    if (!Track)
    {
        return nullptr;
    }
    for (UMovieSceneSection* Base : Track->GetAllSections())
    {
        UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(Base);
        if (Section && Section->BlockGuid == PassageGuid)
        {
            return Section;
        }
    }
    return nullptr;
}

FRetimeSnapshot RetimeCapture(const UInfinityStageShowAsset& Show, ULevelSequence& Master, const UMovieSceneSubSection* Control)
{
    FRetimeSnapshot Out;
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(Show);
    Out.bCompiled = !Compiled.HasErrors();
    Out.ShowEnd = Compiled.ShowEndFrame.Value;
    for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
    {
        Out.Segments.Add(Segment.SegmentGuid, FRetimeRange{ Segment.StartFrame.Value, Segment.EndFrame.Value });
    }
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        TArray<int32>& Relative = Out.RelativePassFrames.Add(Passage.PassageGuid);
        for (const FInfinityCompiledWing& Wing : Passage.Wings)
        {
            Relative.Add(Wing.PassFrame.Value - Passage.SegmentStartFrame.Value);
        }
    }

    UMovieScene* MovieScene = Master.GetMovieScene();
    Out.MasterPlayback = FRetimeRange{
        MovieScene->GetPlaybackRange().GetLowerBoundValue().Value,
        MovieScene->GetPlaybackRange().GetUpperBoundValue().Value };

    if (UMovieSceneInfinityPassageTrack* Track = MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>())
    {
        for (UMovieSceneSection* Base : Track->GetAllSections())
        {
            UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(Base);
            if (!Section)
            {
                continue;
            }
            FRetimePassageSnapshot& Passage = Out.Passages.Add(Section->BlockGuid);
            Passage.Range = RetimeSectionRange(*Section);
            const int32 SectionStart = Passage.Range.Start;
            for (uint8 Raw = static_cast<uint8>(InfinityFirstPassageChannel);
                Raw <= static_cast<uint8>(InfinityLastPassageChannel);
                ++Raw)
            {
                TArray<FRetimeKey>& Keys = Passage.ChannelKeys.AddDefaulted_GetRef();
                const FMovieSceneDoubleChannel* Channel =
                    Section->GetCameraChannel(static_cast<EInfinityPassageCameraChannel>(Raw));
                if (!Channel)
                {
                    continue;
                }
                const TArrayView<const FFrameNumber> Times = Channel->GetData().GetTimes();
                const TArrayView<const FMovieSceneDoubleValue> Values = Channel->GetData().GetValues();
                for (int32 Index = 0; Index < Times.Num(); ++Index)
                {
                    Keys.Add(FRetimeKey{ Times[Index].Value - SectionStart, Values[Index].Value });
                }
            }
            for (const FFrameNumber Pin : Section->PinnedPassageFrames)
            {
                Passage.PinnedPassageFrames.Add(Pin.Value);
            }
            Passage.PinnedWingCueGuids = Section->PinnedWingCueGuids;
        }
    }
    if (UMovieSceneInfinitySceneTrack* Track = MovieScene->FindTrack<UMovieSceneInfinitySceneTrack>())
    {
        for (UMovieSceneSection* Base : Track->GetAllSections())
        {
            if (const UMovieSceneInfinitySceneSection* Section = Cast<UMovieSceneInfinitySceneSection>(Base))
            {
                Out.SceneSections.Add(Section->BlockGuid, RetimeSectionRange(*Section));
            }
        }
    }
    if (UMovieSceneInfinityChoreoTrack* Track = MovieScene->FindTrack<UMovieSceneInfinityChoreoTrack>())
    {
        for (UMovieSceneSection* Base : Track->GetAllSections())
        {
            if (const UMovieSceneInfinityChoreoSection* Section = Cast<UMovieSceneInfinityChoreoSection>(Base))
            {
                Out.ChoreoSections.Add(Section->BlockGuid, RetimeSectionRange(*Section));
            }
        }
    }
    if (UMovieSceneInfinityAudioTrack* Track = MovieScene->FindTrack<UMovieSceneInfinityAudioTrack>())
    {
        for (UMovieSceneSection* Base : Track->GetAllSections())
        {
            UMovieSceneInfinityAudioSection* Section = Cast<UMovieSceneInfinityAudioSection>(Base);
            if (!Section)
            {
                continue;
            }
            FRetimeMusicSnapshot& Music = Out.MusicSections.Add(Section->BlockGuid);
            Music.Range = RetimeSectionRange(*Section);
            Music.StartOffset = Section->GetStartOffset().Value;
            // Same lookup the builder uses for the envelope (Builder.cpp ApplyVolumeEnvelope).
            if (const FMovieSceneFloatChannel* Volume = Section->GetChannelProxy().GetChannel<FMovieSceneFloatChannel>(0))
            {
                for (const FFrameNumber Time : Volume->GetData().GetTimes())
                {
                    Music.EnvelopeTimes.Add(Time.Value);
                }
            }
        }
    }
    if (Control)
    {
        Out.Control = RetimeSectionRange(*Control);
    }
    return Out;
}

/** Every entry of Before must reappear in After at Start+StartDelta[guid], End+EndDelta[guid]. */
void RetimeExpectShifted(
    FAutomationTestBase& Test,
    const TCHAR* Phase,
    const TCHAR* Kind,
    const TMap<FGuid, FRetimeRange>& Before,
    const TMap<FGuid, FRetimeRange>& After,
    const TMap<FGuid, int32>& StartDelta,
    const TMap<FGuid, int32>& EndDelta,
    const TMap<FGuid, FString>& Names)
{
    Test.TestEqual(FString::Printf(TEXT("%s: %s count unchanged"), Phase, Kind), After.Num(), Before.Num());
    for (const TPair<FGuid, FRetimeRange>& Entry : Before)
    {
        const FString* Name = Names.Find(Entry.Key);
        const FString Label = Name ? *Name : Entry.Key.ToString();
        const FRetimeRange* Now = After.Find(Entry.Key);
        if (!Test.TestNotNull(FString::Printf(TEXT("%s: %s %s still present (by GUID)"), Phase, Kind, *Label), Now))
        {
            continue;
        }
        const int32* DS = StartDelta.Find(Entry.Key);
        const int32* DE = EndDelta.Find(Entry.Key);
        if (!Test.TestTrue(FString::Printf(TEXT("%s: %s %s has an expected delta"), Phase, Kind, *Label), DS && DE))
        {
            continue;
        }
        Test.TestEqual(FString::Printf(TEXT("%s: %s %s start moved by exactly %d"), Phase, Kind, *Label, *DS),
            Now->Start, Entry.Value.Start + *DS);
        Test.TestEqual(FString::Printf(TEXT("%s: %s %s end moved by exactly %d"), Phase, Kind, *Label, *DE),
            Now->End, Entry.Value.End + *DE);
    }
}

/** Every managed section must equal its recompiled segment (BlockGuid == segment GUID). */
void RetimeExpectMatchesCompiled(
    FAutomationTestBase& Test,
    const TCHAR* Phase,
    const TCHAR* Kind,
    const TMap<FGuid, FRetimeRange>& Sections,
    const TMap<FGuid, FRetimeRange>& Segments)
{
    for (const TPair<FGuid, FRetimeRange>& Entry : Sections)
    {
        const FRetimeRange* Segment = Segments.Find(Entry.Key);
        if (!Test.TestNotNull(FString::Printf(TEXT("%s: %s %s has a compiled segment"), Phase, Kind, *Entry.Key.ToString()), Segment))
        {
            continue;
        }
        Test.TestEqual(FString::Printf(TEXT("%s: %s section start == recompiled segment start"), Phase, Kind),
            Entry.Value.Start, Segment->Start);
        Test.TestEqual(FString::Printf(TEXT("%s: %s section end == recompiled segment end"), Phase, Kind),
            Entry.Value.End, Segment->End);
    }
}

TMap<FGuid, FRetimeRange> RetimePassageRanges(const FRetimeSnapshot& Snapshot)
{
    TMap<FGuid, FRetimeRange> Ranges;
    for (const TPair<FGuid, FRetimePassageSnapshot>& Entry : Snapshot.Passages)
    {
        Ranges.Add(Entry.Key, Entry.Value.Range);
    }
    return Ranges;
}

TMap<FGuid, FRetimeRange> RetimeMusicRanges(const FRetimeSnapshot& Snapshot)
{
    TMap<FGuid, FRetimeRange> Ranges;
    for (const TPair<FGuid, FRetimeMusicSnapshot>& Entry : Snapshot.MusicSections)
    {
        Ranges.Add(Entry.Key, Entry.Value.Range);
    }
    return Ranges;
}

void RetimeExpectSameKeys(
    FAutomationTestBase& Test,
    const FString& What,
    const FRetimePassageSnapshot& Before,
    const FRetimePassageSnapshot& After)
{
    if (!Test.TestEqual(FString::Printf(TEXT("%s: channel count"), *What), After.ChannelKeys.Num(), Before.ChannelKeys.Num()))
    {
        return;
    }
    for (int32 Channel = 0; Channel < Before.ChannelKeys.Num(); ++Channel)
    {
        const TArray<FRetimeKey>& B = Before.ChannelKeys[Channel];
        const TArray<FRetimeKey>& A = After.ChannelKeys[Channel];
        if (!Test.TestEqual(FString::Printf(TEXT("%s: %s key count"), *What, RetimeChannelName(Channel)), A.Num(), B.Num()))
        {
            continue;
        }
        for (int32 Key = 0; Key < B.Num(); ++Key)
        {
            Test.TestEqual(FString::Printf(TEXT("%s: %s key %d keeps its section-relative frame"), *What, RetimeChannelName(Channel), Key),
                A[Key].RelativeFrame, B[Key].RelativeFrame);
            Test.TestEqual(FString::Printf(TEXT("%s: %s key %d keeps its value"), *What, RetimeChannelName(Channel), Key),
                A[Key].Value, B[Key].Value);
        }
    }
}

int32 RetimeUncovered(TArray<FRetimeRange> Intervals, const int32 From, const int32 To)
{
    Intervals.Sort([](const FRetimeRange& L, const FRetimeRange& R) { return L.Start < R.Start; });
    int32 Cursor = From;
    int32 Uncovered = 0;
    for (const FRetimeRange& Interval : Intervals)
    {
        Uncovered += FMath::Max(0, FMath::Min(Interval.Start, To) - Cursor);
        Cursor = FMath::Max(Cursor, Interval.End);
    }
    Uncovered += FMath::Max(0, To - Cursor);
    return Uncovered;
}

/**
 * Camera-cut coverage after a rematch: each Scene's own Camera Cut track covers its
 * playback range, and the render wrapper's Passage cuts plus the Scene intervals
 * (nested Scene cut authority) cover the whole Master [0, ShowEnd) with no gap.
 */
void RetimeExpectCutCoverage(
    FAutomationTestBase& Test,
    const TCHAR* Phase,
    UInfinityStageShowAsset& Show,
    ULevelSequence& Master,
    UWorld& World,
    const TArray<ULevelSequence*>& SceneSequences,
    const FGuid FirstWingCueGuid,
    const FGuid LastWingCueGuid,
    const FRetimeSnapshot& Snapshot)
{
    for (ULevelSequence* SceneSequence : SceneSequences)
    {
        UMovieScene* SceneMovieScene = SceneSequence->GetMovieScene();
        UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(SceneMovieScene->GetCameraCutTrack());
        if (!Test.TestNotNull(FString::Printf(TEXT("%s: Scene %s has a Camera Cut track"), Phase, *SceneSequence->GetName()), CutTrack))
        {
            continue;
        }
        TArray<FRetimeRange> Cuts;
        for (const UMovieSceneSection* Cut : CutTrack->GetAllSections())
        {
            Cuts.Add(RetimeSectionRange(*Cut));
        }
        const int32 PlaybackStart = SceneMovieScene->GetPlaybackRange().GetLowerBoundValue().Value;
        const int32 PlaybackEnd = SceneMovieScene->GetPlaybackRange().GetUpperBoundValue().Value;
        Test.TestEqual(FString::Printf(TEXT("%s: Scene %s cuts cover its playback [%d,%d) with no gap"),
            Phase, *SceneSequence->GetName(), PlaybackStart, PlaybackEnd),
            RetimeUncovered(Cuts, PlaybackStart, PlaybackEnd), 0);
    }

    ULevelSequence* Wrapper = NewObject<ULevelSequence>(GetTransientPackage());
    Wrapper->Initialize();
    FFrameNumber Start;
    FFrameNumber End;
    FString Report;
    if (!Test.TestTrue(FString::Printf(TEXT("%s: whole-show render wrapper builds"), Phase),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
            &Show, &Master, Wrapper, &World, { FirstWingCueGuid, LastWingCueGuid }, FGuid(), Start, End, Report)))
    {
        Test.AddInfo(FString::Printf(TEXT("RETIME_WRAPPER_REPORT phase=%s %s"), Phase, *Report));
        return;
    }
    Test.TestEqual(FString::Printf(TEXT("%s: wrapper starts at Master 0"), Phase), Start.Value, 0);
    Test.TestEqual(FString::Printf(TEXT("%s: wrapper ends at the recompiled show end"), Phase), End.Value, Snapshot.ShowEnd);
    UMovieSceneCameraCutTrack* WrapperCuts = Cast<UMovieSceneCameraCutTrack>(Wrapper->GetMovieScene()->GetCameraCutTrack());
    if (!Test.TestNotNull(FString::Printf(TEXT("%s: wrapper has a Camera Cut track"), Phase), WrapperCuts))
    {
        return;
    }
    Test.TestEqual(FString::Printf(TEXT("%s: one wrapper cut per Passage"), Phase),
        WrapperCuts->GetAllSections().Num(), Snapshot.Passages.Num());
    TArray<FRetimeRange> Coverage;
    for (const UMovieSceneSection* Cut : WrapperCuts->GetAllSections())
    {
        Coverage.Add(RetimeSectionRange(*Cut));
    }
    for (const TPair<FGuid, FRetimeRange>& Scene : Snapshot.SceneSections)
    {
        Coverage.Add(Scene.Value);
    }
    Test.TestEqual(FString::Printf(TEXT("%s: Passage cuts + nested Scene intervals cover the Master [0,%d) with no gap"),
        Phase, Snapshot.ShowEnd), RetimeUncovered(Coverage, 0, Snapshot.ShowEnd), 0);
}

/** Managed Passage + Scene sections tile the Master playback range. */
void RetimeExpectManagedTiling(FAutomationTestBase& Test, const TCHAR* Phase, const FRetimeSnapshot& Snapshot)
{
    Test.TestTrue(FString::Printf(TEXT("%s: Show compiles"), Phase), Snapshot.bCompiled);
    Test.TestEqual(FString::Printf(TEXT("%s: Master playback starts at 0"), Phase), Snapshot.MasterPlayback.Start, 0);
    Test.TestEqual(FString::Printf(TEXT("%s: Master playback ends at the recompiled show end"), Phase),
        Snapshot.MasterPlayback.End, Snapshot.ShowEnd);
    TArray<FRetimeRange> Managed;
    for (const TPair<FGuid, FRetimePassageSnapshot>& Entry : Snapshot.Passages)
    {
        Managed.Add(Entry.Value.Range);
    }
    for (const TPair<FGuid, FRetimeRange>& Entry : Snapshot.SceneSections)
    {
        Managed.Add(Entry.Value);
    }
    Test.TestEqual(FString::Printf(TEXT("%s: managed Passage + Scene sections leave no gap in the Master"), Phase),
        RetimeUncovered(Managed, 0, Snapshot.ShowEnd), 0);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRetimeEverythingFollowsTest,
    "InfinityStage.Editor.RetimeEverythingFollows",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRetimeEverythingFollowsTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageRetimeEverythingFollowsTest;

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
    WorldContext.SetCurrentWorld(World);
    ON_SCOPE_EXIT
    {
        GEngine->DestroyWorldContext(World);
        World->DestroyWorld(false);
    };

    // ---------------------------------------------------------------- fixture
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const FFrameRate Tick = Show->TickResolution;
    ULevelSequence* S1Sequence = RetimeNewSequence(Tick, 48000);
    ULevelSequence* S2Sequence = RetimeNewSequence(Tick, 48000);

    const FGuid GuidA1 = RetimeAddWing(*Show, 24000);
    RetimeAddWing(*Show, 24000);
    const FGuid GuidS1 = RetimeAddScene(*Show, TEXT("Retime Fixture Scene 1"), S1Sequence, 48000);
    const FGuid GuidB1 = RetimeAddWing(*Show, 24000);
    const FGuid GuidB2 = RetimeAddWing(*Show, 24000);
    const FGuid GuidB3 = RetimeAddWing(*Show, 24000);
    const FGuid GuidS2 = RetimeAddScene(*Show, TEXT("Retime Fixture Scene 2"), S2Sequence, 48000);
    RetimeAddWing(*Show, 24000);
    const FGuid GuidC2 = RetimeAddWing(*Show, 24000);
    Show->ReconcilePassageSettings();
    if (!TestEqual(TEXT("Fixture has three Passages"), Show->PassageSettings.Num(), 3))
    {
        return false;
    }
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.TailFrames = 24000;
        Settings.TailDistanceCm = 250.0;
    }
    const FGuid GuidPA = Show->PassageSettings[0].PassageGuid;
    const FGuid GuidPB = Show->PassageSettings[1].PassageGuid;
    const FGuid GuidPC = Show->PassageSettings[2].PassageGuid;
    TestTrue(TEXT("Fixture: P_B is the Passage holding B1"), Show->PassageSettings[1].FirstCueGuid == GuidB1);

    // Choreography on the Passage after S1 and on the last Passage. 600 s each, so no
    // INFINITY_CHOREO_SHORT warning; no Camera Cut track, so the builder nests them.
    ULevelSequence* ChoreoB = RetimeNewSequence(Tick, Tick.AsFrameNumber(600.0).Value);
    ULevelSequence* ChoreoC = RetimeNewSequence(Tick, Tick.AsFrameNumber(600.0).Value);
    Show->PassageSettings[1].Choreography = ChoreoB;
    Show->PassageSettings[2].Choreography = ChoreoC;

    // One music rail, bound to P_B (Passage music) and to S2 (Scene music).
    USoundWave* Wave = NewObject<USoundWave>(GetTransientPackage());
    USoundBase* WaveBase = Wave;
    FInfinityMusicRail& Rail = Show->MusicRails.AddDefaulted_GetRef();
    Rail.RailGuid = FGuid::NewGuid();
    Rail.Label = FText::FromString(TEXT("Retime Fixture Rail"));
    Rail.Sound = WaveBase;
    Rail.SourceInFrame = 12000;
    Rail.FadeInFrames = 6000;
    Rail.FadeOutFrames = 6000;
    const FGuid RailGuid = Rail.RailGuid;
    constexpr int32 FadeIn = 6000;
    constexpr int32 FadeOut = 6000;
    Show->PassageSettings[1].Music.Mode = EInfinityMusicBindingMode::Start;
    Show->PassageSettings[1].Music.PrimaryRailGuid = RailGuid;
    Show->PassageSettings[1].Music.RailOffsetFrames = 2400;
    RetimeFindCue(*Show, GuidS2)->Scene.Music.Mode = EInfinityMusicBindingMode::Start;
    RetimeFindCue(*Show, GuidS2)->Scene.Music.PrimaryRailGuid = RailGuid;
    RetimeFindCue(*Show, GuidS2)->Scene.Music.RailOffsetFrames = 4800;
    const TMap<FGuid, int32> ExpectedStartOffsets = { { GuidPB, 12000 + 2400 }, { GuidS2, 12000 + 4800 } };

    // Passage actors + camera rigs, so handoffs can be matched and the wrapper can bind cuts.
    TArray<AInfinityStagePassageActor*> PassageActors;
    const FVector Origins[] = { FVector(0.0, 0.0, 0.0), FVector(9000.0, 12000.0, 0.0), FVector(-9000.0, 24000.0, 0.0) };
    for (int32 Index = 0; Index < 3; ++Index)
    {
        AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>(
            Origins[Index], FRotator(0.0, 90.0 * Index, 0.0));
        Passage->ShowAsset = Show;
        Passage->PassageGuid = Show->PassageSettings[Index].PassageGuid;
        PassageActors.Add(Passage);
        AInfinityStageCameraRig* Rig = World->SpawnActor<AInfinityStageCameraRig>();
        Rig->PassageActor = Passage;
    }
    const auto MaterializeAll = [this, &PassageActors](const TCHAR* Phase)
    {
        for (AInfinityStagePassageActor* Passage : PassageActors)
        {
            TestTrue(FString::Printf(TEXT("%s: Passage %s materializes"), Phase, *Passage->PassageGuid.ToString()),
                Passage->MaterializePassage());
        }
    };

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    Show->ManagedMasterSequence = Master;
    // Negative control: an UNMANAGED absolute sub-section inside S2 (Master 200000).
    // The rebuild must leave it where it was put, which proves this test can fail.
    ULevelSequence* ControlSequence = RetimeNewSequence(Tick, 24000);
    UMovieSceneSubSection* Control = Master->GetMovieScene()->AddTrack<UMovieSceneSubTrack>()
        ->AddSequence(ControlSequence, FFrameNumber(200000), 24000);
    if (!TestNotNull(TEXT("Fixture: control sub-section exists"), Control))
    {
        return false;
    }

    FString Report;
    if (!TestTrue(TEXT("First build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report)))
    {
        AddInfo(Report);
        return false;
    }

    // Author a camera / wing score and pins (section-relative frames).
    UMovieSceneInfinityPassageSection* SectionA = RetimeFindPassageSection(*Master, GuidPA);
    UMovieSceneInfinityPassageSection* SectionB = RetimeFindPassageSection(*Master, GuidPB);
    if (!TestNotNull(TEXT("P_A section built"), SectionA) || !TestNotNull(TEXT("P_B section built"), SectionB))
    {
        return false;
    }
    const FFrameNumber StartA = SectionA->GetInclusiveStartFrame();
    const FFrameNumber StartB = SectionB->GetInclusiveStartFrame();
    SectionA->HeightOffsetCm.AddCubicKey(StartA + FFrameNumber(12000), 222.0);
    SectionB->SpeedMultiplier.AddCubicKey(StartB + FFrameNumber(12000), 1.0);
    SectionB->SpeedMultiplier.AddCubicKey(StartB + FFrameNumber(54000), 1.5);      // inside the Part 2 end (60000)
    SectionB->WingPhaseBiasCycles.AddCubicKey(StartB + FFrameNumber(24000), 0.25);  // on B2's pass (B2 never moves)
    SectionB->HeightOffsetCm.AddCubicKey(StartB + FFrameNumber(48000), 150.0);      // on B3's pass (moves in Part 2)
    SectionB->HeightOffsetCm.AddCubicKey(StartB + FFrameNumber(66000), 90.0);       // in the tail (past the Part 2 end)
    SectionB->PinnedPassageFrames = { FFrameNumber(30000), FFrameNumber(66000) };
    SectionB->PinnedWingCueGuids = { GuidB3 };

    TestTrue(TEXT("Baseline rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    MaterializeAll(TEXT("Baseline"));
    TestTrue(TEXT("Baseline: handoffs match"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, {}, Report));
    const TArray<ULevelSequence*> SceneSequences = { S1Sequence, S2Sequence };
    const FRetimeSnapshot Baseline = RetimeCapture(*Show, *Master, Control);
    const TMap<FGuid, FString> Names = { { GuidPA, FString(TEXT("P_A")) }, { GuidS1, FString(TEXT("S1")) }, { GuidPB, FString(TEXT("P_B")) }, { GuidS2, FString(TEXT("S2")) }, { GuidPC, FString(TEXT("P_C")) } };

    // Fixture sanity: the expected layout, so the deltas below mean what they say.
    const FRetimeRange* BaselineB = Baseline.Segments.Find(GuidPB);
    TestTrue(TEXT("Fixture: P_B is [96000,168000)"), BaselineB && BaselineB->Start == 96000 && BaselineB->End == 168000);
    TestEqual(TEXT("Fixture: show end 264000"), Baseline.ShowEnd, 264000);
    TestEqual(TEXT("Fixture: 3 Passage sections"), Baseline.Passages.Num(), 3);
    TestEqual(TEXT("Fixture: 2 Scene sections"), Baseline.SceneSections.Num(), 2);
    TestEqual(TEXT("Fixture: 2 Choreo sections"), Baseline.ChoreoSections.Num(), 2);
    TestEqual(TEXT("Fixture: 2 music sections"), Baseline.MusicSections.Num(), 2);
    TestEqual(TEXT("Fixture: control at Master 200000"), Baseline.Control.Start, 200000);
    RetimeExpectManagedTiling(*this, TEXT("Baseline"), Baseline);
    RetimeExpectCutCoverage(*this, TEXT("Baseline"), *Show, *Master, *World, SceneSequences, GuidA1, GuidC2, Baseline);

    // Shared checks for both retimes. Delta maps are keyed by segment GUID (== BlockGuid).
    const auto ExpectEverythingFollows = [&](const TCHAR* Phase, const FRetimeSnapshot& Before, const FRetimeSnapshot& After,
        const TMap<FGuid, int32>& StartDelta, const TMap<FGuid, int32>& EndDelta)
    {
        RetimeExpectManagedTiling(*this, Phase, After);
        RetimeExpectShifted(*this, Phase, TEXT("segment"), Before.Segments, After.Segments, StartDelta, EndDelta, Names);
        RetimeExpectShifted(*this, Phase, TEXT("Passage section"), RetimePassageRanges(Before), RetimePassageRanges(After), StartDelta, EndDelta, Names);
        RetimeExpectShifted(*this, Phase, TEXT("Scene section"), Before.SceneSections, After.SceneSections, StartDelta, EndDelta, Names);
        RetimeExpectShifted(*this, Phase, TEXT("Choreo section"), Before.ChoreoSections, After.ChoreoSections, StartDelta, EndDelta, Names);
        RetimeExpectShifted(*this, Phase, TEXT("music section"), RetimeMusicRanges(Before), RetimeMusicRanges(After), StartDelta, EndDelta, Names);
        RetimeExpectMatchesCompiled(*this, Phase, TEXT("Passage"), RetimePassageRanges(After), After.Segments);
        RetimeExpectMatchesCompiled(*this, Phase, TEXT("Scene"), After.SceneSections, After.Segments);
        RetimeExpectMatchesCompiled(*this, Phase, TEXT("Choreo"), After.ChoreoSections, After.Segments);
        RetimeExpectMatchesCompiled(*this, Phase, TEXT("music"), RetimeMusicRanges(After), After.Segments);
        for (const TPair<FGuid, FRetimeMusicSnapshot>& Entry : After.MusicSections)
        {
            const FString* Name = Names.Find(Entry.Key);
            const FString Label = Name ? *Name : Entry.Key.ToString();
            const int32* Offset = ExpectedStartOffsets.Find(Entry.Key);
            TestTrue(FString::Printf(TEXT("%s: music %s start offset unchanged (rail in + binding offset)"), Phase, *Label),
                Offset && Entry.Value.StartOffset == *Offset);
            const FRetimeRange& R = Entry.Value.Range;
            const TArray<int32> Envelope = { R.Start, R.Start + FadeIn, R.End - FadeOut, R.End };
            TestTrue(FString::Printf(TEXT("%s: music %s envelope re-fit to the new section ends"), Phase, *Label),
                Entry.Value.EnvelopeTimes == Envelope);
        }
        TestEqual(FString::Printf(TEXT("%s: control (unmanaged, absolute) start did not move"), Phase), After.Control.Start, Before.Control.Start);
        TestEqual(FString::Printf(TEXT("%s: control (unmanaged, absolute) end did not move"), Phase), After.Control.End, Before.Control.End);
    };

    const auto ReportHandoffs = [&](const TCHAR* Phase)
    {
        TArray<FGuid> Stale;
        FString CheckReport;
        const bool bChecked = FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(*Show, *World, {}, Stale, CheckReport);
        TArray<FString> StaleNames;
        for (const FGuid& Guid : Stale)
        {
            const FString* Name = Names.Find(Guid);
            StaleNames.Add(Name ? *Name : Guid.ToString());
        }
        AddInfo(FString::Printf(TEXT("RETIME_HANDOFF_CHECK phase=%s checked=%d stale=[%s] report=%s"),
            Phase, bChecked ? 1 : 0, *FString::Join(StaleNames, TEXT(",")), *CheckReport));
    };

    // ------------------------------------------------- Part 1: a Scene grows
    const int32 Grow = Tick.AsFrameNumber(2.0).Value;  // audit sec. 4(1): +delta = 2 s
    TestEqual(TEXT("Part 1: delta is 2 s at 24000 ticks"), Grow, 48000);
    {
        FInfinityShowCue* Scene1 = RetimeFindCue(*Show, GuidS1);
        Scene1->Scene.DurationFrames = Scene1->Scene.DurationFrames.Value + Grow;
        // The Scene's own playback grows with it, as extend_scene_playback.py does.
        S1Sequence->GetMovieScene()->SetPlaybackRange(FFrameNumber(0), Scene1->Scene.DurationFrames.Value);
    }
    TestTrue(TEXT("Part 1: rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    MaterializeAll(TEXT("Part 1"));
    const FRetimeSnapshot AfterGrow = RetimeCapture(*Show, *Master, Control);
    ExpectEverythingFollows(TEXT("Part 1 (S1 +2 s)"), Baseline, AfterGrow,
        { { GuidPA, 0 }, { GuidS1, 0 }, { GuidPB, Grow }, { GuidS2, Grow }, { GuidPC, Grow } },
        { { GuidPA, 0 }, { GuidS1, Grow }, { GuidPB, Grow }, { GuidS2, Grow }, { GuidPC, Grow } });
    TestEqual(TEXT("Part 1: show end grew by exactly delta"), AfterGrow.ShowEnd, Baseline.ShowEnd + Grow);
    for (const FGuid& Passage : { GuidPA, GuidPB, GuidPC })
    {
        const FRetimePassageSnapshot* Before = Baseline.Passages.Find(Passage);
        const FRetimePassageSnapshot* After = AfterGrow.Passages.Find(Passage);
        if (Before && After)
        {
            const FString What = FString::Printf(TEXT("Part 1: %s"), **Names.Find(Passage));
            RetimeExpectSameKeys(*this, What, *Before, *After);
            TestTrue(What + TEXT(": relative pins unchanged"), After->PinnedPassageFrames == Before->PinnedPassageFrames);
            TestTrue(What + TEXT(": pinned wing GUIDs unchanged"), After->PinnedWingCueGuids == Before->PinnedWingCueGuids);
        }
        const TArray<int32>* PassBefore = Baseline.RelativePassFrames.Find(Passage);
        const TArray<int32>* PassAfter = AfterGrow.RelativePassFrames.Find(Passage);
        TestTrue(FString::Printf(TEXT("Part 1: %s relative wing pass frames unchanged"), **Names.Find(Passage)),
            PassBefore && PassAfter && *PassBefore == *PassAfter);
    }
    ReportHandoffs(TEXT("Part 1 before rematch"));
    TestTrue(TEXT("Part 1: handoffs rematch"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, {}, Report));
    RetimeExpectCutCoverage(*this, TEXT("Part 1"), *Show, *Master, *World, SceneSequences, GuidA1, GuidC2, AfterGrow);

    // Idempotence: a rebuild that changes nothing moves nothing.
    TestTrue(TEXT("Part 1: unchanged rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    const FRetimeSnapshot Repeat = RetimeCapture(*Show, *Master, Control);
    {
        const TMap<FGuid, int32> Zero = { { GuidPA, 0 }, { GuidS1, 0 }, { GuidPB, 0 }, { GuidS2, 0 }, { GuidPC, 0 } };
        ExpectEverythingFollows(TEXT("Part 1 idempotent"), AfterGrow, Repeat, Zero, Zero);
        for (const FGuid& Passage : { GuidPA, GuidPB, GuidPC })
        {
            const FRetimePassageSnapshot* Before = AfterGrow.Passages.Find(Passage);
            const FRetimePassageSnapshot* After = Repeat.Passages.Find(Passage);
            if (Before && After)
            {
                RetimeExpectSameKeys(*this, FString::Printf(TEXT("Part 1 idempotent: %s"), **Names.Find(Passage)), *Before, *After);
            }
        }
    }

    // --------------------------------- Part 2: a Passage's own length changes
    // B2 -> B3 shortens by 12000: P_B ends 12000 earlier, B3 passes 12000 earlier.
    const int32 Shrink = 12000;
    RetimeFindCue(*Show, GuidB2)->WingPair.IntervalToNext = 24000 - Shrink;
    TestTrue(TEXT("Part 2: rebuild succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    MaterializeAll(TEXT("Part 2"));
    const FRetimeSnapshot AfterShrink = RetimeCapture(*Show, *Master, Control);

    // What MUST follow (downstream of P_B, and P_B's own range): asserted hard.
    ExpectEverythingFollows(TEXT("Part 2 (P_B -12000)"), Repeat, AfterShrink,
        { { GuidPA, 0 }, { GuidS1, 0 }, { GuidPB, 0 }, { GuidS2, -Shrink }, { GuidPC, -Shrink } },
        { { GuidPA, 0 }, { GuidS1, 0 }, { GuidPB, -Shrink }, { GuidS2, -Shrink }, { GuidPC, -Shrink } });
    TestEqual(TEXT("Part 2: show end shrank by exactly the interval change"), AfterShrink.ShowEnd, Repeat.ShowEnd - Shrink);
    const TArray<int32>* PassBeforeB = Repeat.RelativePassFrames.Find(GuidPB);
    const TArray<int32>* PassAfterB = AfterShrink.RelativePassFrames.Find(GuidPB);
    TestTrue(TEXT("Part 2: P_B wing pass frames were {0,24000,48000}"), PassBeforeB && *PassBeforeB == TArray<int32>({ 0, 24000, 48000 }));
    TestTrue(TEXT("Part 2: P_B wing pass frames are now {0,24000,36000}"), PassAfterB && *PassAfterB == TArray<int32>({ 0, 24000, 36000 }));
    for (const FGuid& Passage : { GuidPA, GuidPC })
    {
        const FRetimePassageSnapshot* Before = Repeat.Passages.Find(Passage);
        const FRetimePassageSnapshot* After = AfterShrink.Passages.Find(Passage);
        if (Before && After)
        {
            RetimeExpectSameKeys(*this, FString::Printf(TEXT("Part 2: untouched %s"), **Names.Find(Passage)), *Before, *After);
        }
    }

    // KNOWN GAP (audit rows 4-5, Builder.cpp:286-309 at 2f6ed4b): the resized Passage's
    // own content is NOT re-fitted. Asserted as today's behaviour so the test is green,
    // and every affected key/pin is named with a RETIME_PASSAGE_KNOWN_GAP warning so it
    // is visible in every run.
    //
    // TODO(RETIME, pending Gary's decision - audit sec. 4(3) "rescale or hold?"):
    //   * STRETCH: keys/pins re-fitted through the old->new pass-frame map. Then flip the
    //     key assertions below to expect the mapped frames (B3's key 48000 -> 36000) and
    //     delete the key_off_pass warnings.
    //   * KEEP the camera score: keys stay relative (today's behaviour), but the rebuild
    //     must stop deleting pins silently. Then expect an INFINITY_PIN_DROPPED log line
    //     (AddExpectedMessagePlain) or a refusal, instead of the silent drop asserted here.
    //   Either way, keys past the new end need a decision (trim, warn, or refuse).
    const FRetimePassageSnapshot* GapBefore = Repeat.Passages.Find(GuidPB);
    const FRetimePassageSnapshot* GapAfter = AfterShrink.Passages.Find(GuidPB);
    if (TestNotNull(TEXT("Part 2: P_B section before"), GapBefore) && TestNotNull(TEXT("Part 2: P_B section after"), GapAfter)
        && PassBeforeB && PassAfterB && PassBeforeB->Num() == PassAfterB->Num())
    {
        RetimeExpectSameKeys(*this, TEXT("Part 2 KNOWN GAP: resized P_B (today: not re-fitted)"), *GapBefore, *GapAfter);
        const int32 NewDuration = GapAfter->Range.End - GapAfter->Range.Start;
        int32 OffPass = 0;
        int32 PastEnd = 0;
        for (int32 Channel = 0; Channel < GapAfter->ChannelKeys.Num(); ++Channel)
        {
            for (const FRetimeKey& Key : GapAfter->ChannelKeys[Channel])
            {
                for (int32 Wing = 0; Wing < PassBeforeB->Num(); ++Wing)
                {
                    if (Key.RelativeFrame == (*PassBeforeB)[Wing] && (*PassAfterB)[Wing] != (*PassBeforeB)[Wing])
                    {
                        ++OffPass;
                        AddWarning(FString::Printf(
                            TEXT("RETIME_PASSAGE_KNOWN_GAP kind=key_off_pass passage=P_B channel=%s key_rel=%d wing=%d pass_rel_before=%d pass_rel_after=%d"),
                            RetimeChannelName(Channel), Key.RelativeFrame, Wing, (*PassBeforeB)[Wing], (*PassAfterB)[Wing]));
                    }
                }
                if (Key.RelativeFrame >= NewDuration)
                {
                    ++PastEnd;
                    AddWarning(FString::Printf(
                        TEXT("RETIME_PASSAGE_KNOWN_GAP kind=key_past_end passage=P_B channel=%s key_rel=%d duration=%d (kept in the channel, never evaluated)"),
                        RetimeChannelName(Channel), Key.RelativeFrame, NewDuration));
                }
            }
        }
        int32 PinsDropped = 0;
        for (const int32 Pin : GapBefore->PinnedPassageFrames)
        {
            if (!GapAfter->PinnedPassageFrames.Contains(Pin))
            {
                ++PinsDropped;
                AddWarning(FString::Printf(
                    TEXT("RETIME_PASSAGE_KNOWN_GAP kind=pin_dropped passage=P_B pin_rel=%d duration=%d logged=none (deleted by the rebuild, no undo but a backup)"),
                    Pin, NewDuration));
            }
        }
        TestEqual(TEXT("Part 2 KNOWN GAP: P_B new duration"), NewDuration, 72000 - Shrink);
        TestEqual(TEXT("Part 2 KNOWN GAP: exactly one key now sits off its wing pass (HeightOffsetCm @48000, B3 now @36000)"), OffPass, 1);
        TestEqual(TEXT("Part 2 KNOWN GAP: exactly one key now lies past the section end (HeightOffsetCm @66000)"), PastEnd, 1);
        TestEqual(TEXT("Part 2 KNOWN GAP: exactly one pin was silently deleted (@66000)"), PinsDropped, 1);
        TestTrue(TEXT("Part 2 KNOWN GAP: surviving pins are {30000}"), GapAfter->PinnedPassageFrames == TArray<int32>({ 30000 }));
        TestTrue(TEXT("Part 2: GUID wing pins travel (B3 still pinned)"), GapAfter->PinnedWingCueGuids == TArray<FGuid>({ GuidB3 }));
        AddInfo(FString::Printf(TEXT("RETIME_PASSAGE_KNOWN_GAP summary passage=P_B key_off_pass=%d key_past_end=%d pin_dropped=%d decision=pending_gary"),
            OffPass, PastEnd, PinsDropped));
    }
    ReportHandoffs(TEXT("Part 2 before rematch"));
    TestTrue(TEXT("Part 2: handoffs rematch"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, {}, Report));
    RetimeExpectCutCoverage(*this, TEXT("Part 2"), *Show, *Master, *World, SceneSequences, GuidA1, GuidC2, AfterShrink);
    return true;
}

#endif
