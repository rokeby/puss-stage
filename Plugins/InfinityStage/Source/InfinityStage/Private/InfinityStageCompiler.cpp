#include "InfinityStageCompiler.h"

#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneSection.h"
#include "Tracks/MovieSceneSubTrack.h"

namespace
{
/**
 * A Scene's length, taken from its own Level Sequence when opted in.
 *
 * Falls back to the authored Duration Frames whenever the sequence is missing or
 * has an empty playback range, so a broken reference degrades to the previous
 * behaviour rather than collapsing the Show's timing.
 */
FFrameNumber ResolveSceneDuration(const UInfinityStageShowAsset& Show, const FInfinityShowCue& Cue)
{
    if (!Cue.Scene.bUseSequenceLength)
    {
        return Cue.Scene.DurationFrames;
    }
    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene)
    {
        return Cue.Scene.DurationFrames;
    }
    const FFrameNumber Length = MovieScene->GetPlaybackRange().Size<FFrameNumber>();
    if (Length.Value <= 0 || !MovieScene->GetTickResolution().IsValid() || !Show.TickResolution.IsValid())
    {
        return Cue.Scene.DurationFrames;
    }
    // The Scene sequence keeps its own tick resolution; the Show's compiled
    // timeline is authoritative, so convert rather than assuming they match.
    return FFrameRate::TransformTime(
        FFrameTime(Length),
        MovieScene->GetTickResolution(),
        Show.TickResolution).RoundToFrame();
}

/**
 * Nested shots or sub-sequences that run past a Scene sequence's playback end are cut, because a nested sequence is
 * evaluated only inside its parent's playback range. Lengthening the Scene here would not help: the Master would lay a
 * longer section with nothing playing in it. So report the cut and let the author extend the playback range.
 * Measure each nested SECTION's end, never the child sequence's own length. A trimmed section is an authoring decision
 * (29 Sep: Scene 3 places 60.6 s of a 119.9 s take) and is not a cut. Scene 1 played 15 s of a 210.8 s shot until
 * this was found by hand.
 */
bool FindNestedContentPastPlayback(const FInfinityShowCue& Cue, double& OutPlaybackEndSeconds, double& OutContentEndSeconds)
{
    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !MovieScene->GetTickResolution().IsValid())
    {
        return false;
    }
    const FFrameNumber PlaybackEnd = MovieScene->GetPlaybackRange().GetUpperBoundValue();
    FFrameNumber ContentEnd = PlaybackEnd;
    for (const UMovieSceneTrack* Track : MovieScene->GetTracks())
    {
        // Cinematic shot tracks are sub tracks, so both kinds of nesting are covered.
        if (!Track || !Track->IsA<UMovieSceneSubTrack>())
        {
            continue;
        }
        for (const UMovieSceneSection* Section : Track->GetAllSections())
        {
            if (Section && Section->IsActive() && Section->HasEndFrame())
            {
                ContentEnd = FMath::Max(ContentEnd, Section->GetExclusiveEndFrame());
            }
        }
    }
    const FFrameRate TickRate = MovieScene->GetTickResolution();
    OutPlaybackEndSeconds = TickRate.AsSeconds(FFrameTime(PlaybackEnd));
    OutContentEndSeconds = TickRate.AsSeconds(FFrameTime(ContentEnd));
    return ContentEnd > PlaybackEnd;
}

const FInfinityPassageSettings* FindPassageSettings(const UInfinityStageShowAsset& Show, const int32 FirstIndex, const int32 LastIndex)
{
    const FGuid FirstGuid = Show.Cues[FirstIndex].CueGuid;
    const FGuid LastGuid = Show.Cues[LastIndex].CueGuid;
    return Show.PassageSettings.FindByPredicate([FirstGuid, LastGuid](const FInfinityPassageSettings& Settings)
    {
        return Settings.FirstCueGuid == FirstGuid && Settings.LastCueGuid == LastGuid;
    });
}

void AddIssue(FInfinityCompileResult& Result, const EInfinityCompileIssueSeverity Severity, const FGuid Subject, const FString& Message)
{
    FInfinityCompileIssue& Issue = Result.Issues.AddDefaulted_GetRef();
    Issue.Severity = Severity;
    Issue.SubjectGuid = Subject;
    Issue.Message = Message;
}
}

bool FInfinityCompileResult::HasErrors() const
{
    return Issues.ContainsByPredicate([](const FInfinityCompileIssue& Issue)
    {
        return Issue.Severity == EInfinityCompileIssueSeverity::Error;
    });
}

FInfinityCompileResult FInfinityStageCompiler::Compile(const UInfinityStageShowAsset& Show)
{
    FInfinityCompileResult Result;
    TSet<FGuid> CueIds;
    TSet<FGuid> OccurrenceIds;
    TSet<FGuid> PassageIds;
    TSet<FGuid> RailIds;
    FFrameNumber Cursor = 0;

    if (!Show.DisplayRate.IsValid() || !Show.TickResolution.IsValid())
    {
        AddIssue(Result, EInfinityCompileIssueSeverity::Error, FGuid(), TEXT("Display rate and tick resolution must be valid."));
    }

    for (int32 Index = 0; Index < Show.Cues.Num(); ++Index)
    {
        const FInfinityShowCue& Cue = Show.Cues[Index];
        if (!Cue.CueGuid.IsValid())
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Cue.CueGuid, FString::Printf(TEXT("Cue %d has no stable GUID."), Index));
        }
        else if (CueIds.Contains(Cue.CueGuid))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Cue.CueGuid, TEXT("Duplicate Cue GUID."));
        }
        CueIds.Add(Cue.CueGuid);

        if (Cue.Type == EInfinityCueType::WingPair)
        {
            if (!Cue.WingPair.OccurrenceGuid.IsValid())
            {
                AddIssue(Result, EInfinityCompileIssueSeverity::Error, Cue.CueGuid, TEXT("Wing occurrence has no stable GUID."));
            }
            else if (OccurrenceIds.Contains(Cue.WingPair.OccurrenceGuid))
            {
                AddIssue(Result, EInfinityCompileIssueSeverity::Error, Cue.WingPair.OccurrenceGuid, TEXT("Duplicate Wing Occurrence GUID."));
            }
            OccurrenceIds.Add(Cue.WingPair.OccurrenceGuid);
        }
    }

    for (const FInfinityPassageSettings& Settings : Show.PassageSettings)
    {
        if (!Settings.PassageGuid.IsValid())
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Passage settings have no stable GUID."));
        }
        else if (PassageIds.Contains(Settings.PassageGuid))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Duplicate Passage GUID."));
        }
        PassageIds.Add(Settings.PassageGuid);

        if (Show.FindCueIndex(Settings.FirstCueGuid) == INDEX_NONE || Show.FindCueIndex(Settings.LastCueGuid) == INDEX_NONE)
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Passage range references a missing Cue GUID."));
        }
        if (!FMath::IsFinite(Settings.CelestialCycle.CycleDurationSeconds)
            || Settings.CelestialCycle.CycleDurationSeconds <= 0.0)
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Celestial cycle duration must be positive and finite."));
        }
        if (!FMath::IsFinite(Settings.CelestialCycle.CycleRateMultiplier)
            || Settings.CelestialCycle.CycleRateMultiplier < 0.0)
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Celestial Passage cycle rate cannot be negative or non-finite."));
        }
        if (!FMath::IsFinite(Settings.CelestialCycle.EntryPhaseOffsetCycles))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Settings.PassageGuid, TEXT("Celestial entry time jump must be finite."));
        }
    }

    for (const FInfinityMusicRail& Rail : Show.MusicRails)
    {
        if (!Rail.RailGuid.IsValid())
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Rail.RailGuid, TEXT("Music rail has no stable GUID."));
        }
        else if (RailIds.Contains(Rail.RailGuid))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Rail.RailGuid, TEXT("Duplicate Music Rail GUID."));
        }
        RailIds.Add(Rail.RailGuid);
        if (Rail.SourceOutFrame.Value > 0 && Rail.SourceOutFrame <= Rail.SourceInFrame)
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Rail.RailGuid, TEXT("Music Source Out must be after Source In."));
        }
    }

    for (int32 Index = 0; Index < Show.Cues.Num();)
    {
        const FInfinityShowCue& Cue = Show.Cues[Index];

        if (!Cue.bEnabled)
        {
            ++Index;
            continue;
        }

        if (Cue.Type != EInfinityCueType::WingPair)
        {
            FInfinityCompiledSegment& Segment = Result.Segments.AddDefaulted_GetRef();
            Segment.SegmentGuid = Cue.CueGuid;
            Segment.Type = Cue.Type;
            Segment.FirstCueIndex = Index;
            Segment.LastCueIndex = Index;
            Segment.StartFrame = Cursor;
            Segment.ExternalSound = Cue.Scene.ExternalSound;
            const FFrameNumber SceneDuration = ResolveSceneDuration(Show, Cue);
            if (SceneDuration.Value <= 0)
            {
                AddIssue(Result, EInfinityCompileIssueSeverity::Error, Cue.CueGuid, TEXT("Scene/Sequence duration must be positive."));
                Segment.EndFrame = Cursor;
            }
            else
            {
                Cursor += SceneDuration;
                Segment.EndFrame = Cursor;
            }
            double PlaybackEndSeconds = 0.0;
            double ContentEndSeconds = 0.0;
            if (Cue.Scene.bUseSequenceLength && FindNestedContentPastPlayback(Cue, PlaybackEndSeconds, ContentEndSeconds))
            {
                AddIssue(Result, EInfinityCompileIssueSeverity::Warning, Cue.CueGuid, FString::Printf(
                    TEXT("%s: nested shots run to %.3f s but the sequence plays only to %.3f s, so %.3f s of placed content is cut. Extend the sequence's playback range to keep it."),
                    *Cue.Label.ToString(), ContentEndSeconds, PlaybackEndSeconds, ContentEndSeconds - PlaybackEndSeconds));
            }
            ++Index;
            continue;
        }

        const int32 FirstIndex = Index;
        int32 LastIndex = Index;
        while (LastIndex + 1 < Show.Cues.Num()
            && Show.Cues[LastIndex + 1].bEnabled
            && Show.Cues[LastIndex + 1].Type == EInfinityCueType::WingPair)
        {
            ++LastIndex;
        }

        const FInfinityPassageSettings* Settings = FindPassageSettings(Show, FirstIndex, LastIndex);
        FInfinityCompiledPassage& Passage = Result.Passages.AddDefaulted_GetRef();
        Passage.PassageGuid = Settings ? Settings->PassageGuid : Show.Cues[FirstIndex].CueGuid;
        Passage.FirstCueIndex = FirstIndex;
        Passage.LastCueIndex = LastIndex;
        Passage.SegmentStartFrame = Cursor;
        Passage.FirstPassFrame = Cursor + (Settings ? Settings->LeadInFrames : FFrameNumber(0));
        Passage.FirstPassDistanceCm = Settings ? Settings->LeadInDistanceCm : 0.0;

        FFrameNumber PassFrame = Passage.FirstPassFrame;
        double DistanceCm = Passage.FirstPassDistanceCm;
        for (int32 WingIndex = FirstIndex; WingIndex <= LastIndex; ++WingIndex)
        {
            const FInfinityShowCue& WingCue = Show.Cues[WingIndex];
            const FInfinityWingOccurrence& Wing = WingCue.WingPair;
            FInfinityCompiledWing& CompiledWing = Passage.Wings.AddDefaulted_GetRef();
            CompiledWing.CueGuid = WingCue.CueGuid;
            CompiledWing.OccurrenceGuid = Wing.OccurrenceGuid;
            CompiledWing.PassFrame = PassFrame;
            CompiledWing.DistanceCm = DistanceCm;

            if (WingIndex < LastIndex)
            {
                if (Wing.IntervalToNext.Value <= 0)
                {
                    AddIssue(Result, EInfinityCompileIssueSeverity::Error, Wing.OccurrenceGuid, TEXT("IntervalToNext must be positive."));
                }
                if (Wing.GapToNextCm <= 0.0)
                {
                    AddIssue(Result, EInfinityCompileIssueSeverity::Error, Wing.OccurrenceGuid, TEXT("GapToNextCm must be positive."));
                }
                PassFrame += Wing.IntervalToNext;
                DistanceCm += Wing.GapToNextCm;
            }
        }

        Passage.LastPassFrame = PassFrame;
        Passage.LastPassDistanceCm = DistanceCm;
        Passage.SegmentEndFrame = PassFrame + (Settings ? Settings->TailFrames : FFrameNumber(0));
        Passage.TotalDistanceCm = DistanceCm + (Settings ? Settings->TailDistanceCm : 0.0);

        if (Passage.FirstPassFrame == Passage.SegmentStartFrame && !FMath::IsNearlyEqual(Passage.FirstPassDistanceCm, 0.0))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Passage.PassageGuid, TEXT("Lead-in distance requires positive lead-in frames."));
        }
        if (Passage.SegmentEndFrame == Passage.LastPassFrame && !FMath::IsNearlyEqual(Passage.TotalDistanceCm, Passage.LastPassDistanceCm))
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Passage.PassageGuid, TEXT("Tail distance requires positive tail frames."));
        }

        FInfinityCompiledSegment& Segment = Result.Segments.AddDefaulted_GetRef();
        Segment.SegmentGuid = Passage.PassageGuid;
        Segment.Type = EInfinityCueType::WingPair;
        Segment.FirstCueIndex = FirstIndex;
        Segment.LastCueIndex = LastIndex;
        Segment.StartFrame = Passage.SegmentStartFrame;
        Segment.EndFrame = Passage.SegmentEndFrame;

        if (Passage.SegmentEndFrame < Passage.SegmentStartFrame)
        {
            AddIssue(Result, EInfinityCompileIssueSeverity::Error, Passage.PassageGuid, TEXT("Passage ends before it begins."));
        }

        Cursor = Passage.SegmentEndFrame;
        Index = LastIndex + 1;
    }

    Result.ShowEndFrame = Cursor;
    return Result;
}

FInfinityPassageFitResult FInfinityStageCompiler::FitPassage(const FInfinityPassageFitInput& Input)
{
    FInfinityPassageFitResult Result;
    if (Input.DurationSeconds <= 0.0)
    {
        Result.Error = TEXT("Music/passage duration must be positive.");
        return Result;
    }
    if (Input.CameraSpeedCmPerSecond <= 0.0)
    {
        Result.Error = TEXT("Camera speed must be positive.");
        return Result;
    }
    if (Input.SpacingCm <= 0.0)
    {
        Result.Error = TEXT("Wing spacing must be positive.");
        return Result;
    }
    if (Input.EntryClearanceCm < 0.0 || Input.ExitClearanceCm < 0.0)
    {
        Result.Error = TEXT("Entry and exit clearances cannot be negative.");
        return Result;
    }

    Result.TravelDistanceCm = Input.DurationSeconds * Input.CameraSpeedCmPerSecond;
    const double UsableDistanceCm = Result.TravelDistanceCm - Input.EntryClearanceCm - Input.ExitClearanceCm;
    if (UsableDistanceCm < 0.0)
    {
        Result.Error = TEXT("The route is shorter than the entry and exit clearances.");
        return Result;
    }

    Result.WingPairCount = 1 + FMath::FloorToInt(UsableDistanceCm / Input.SpacingCm);
    Result.RequiredDistanceCm = Input.EntryClearanceCm
        + FMath::Max(0, Result.WingPairCount - 1) * Input.SpacingCm
        + Input.ExitClearanceCm;
    Result.ResidualDistanceCm = Result.TravelDistanceCm - Result.RequiredDistanceCm;
    Result.PassIntervalSeconds = Input.SpacingCm / Input.CameraSpeedCmPerSecond;
    Result.bValid = Result.WingPairCount > 0;
    return Result;
}

double FInfinityStageCompiler::SolveCameraSpeedCmPerSecond(
    const double DurationSeconds,
    const int32 WingPairCount,
    const double SpacingCm,
    const double EntryClearanceCm,
    const double ExitClearanceCm)
{
    if (DurationSeconds <= 0.0 || WingPairCount <= 0 || SpacingCm <= 0.0 || EntryClearanceCm < 0.0 || ExitClearanceCm < 0.0)
    {
        return 0.0;
    }

    const double RequiredDistanceCm = EntryClearanceCm
        + FMath::Max(0, WingPairCount - 1) * SpacingCm
        + ExitClearanceCm;
    return RequiredDistanceCm / DurationSeconds;
}

double FInfinityStageCompiler::EvaluateDistanceAtFrame(const FInfinityCompiledPassage& Passage, const FFrameTime MasterFrame)
{
    const double Frame = MasterFrame.AsDecimal();
    auto Interpolate = [Frame](const FFrameNumber AFrame, const double ADistance, const FFrameNumber BFrame, const double BDistance)
    {
        if (BFrame <= AFrame)
        {
            return BDistance;
        }
        const double Alpha = FMath::Clamp((Frame - AFrame.Value) / static_cast<double>(BFrame.Value - AFrame.Value), 0.0, 1.0);
        return FMath::Lerp(ADistance, BDistance, Alpha);
    };

    if (Passage.Wings.IsEmpty())
    {
        return 0.0;
    }
    if (Frame <= Passage.FirstPassFrame.Value)
    {
        return Interpolate(Passage.SegmentStartFrame, 0.0, Passage.FirstPassFrame, Passage.FirstPassDistanceCm);
    }
    for (int32 Index = 0; Index + 1 < Passage.Wings.Num(); ++Index)
    {
        const FInfinityCompiledWing& A = Passage.Wings[Index];
        const FInfinityCompiledWing& B = Passage.Wings[Index + 1];
        if (Frame <= B.PassFrame.Value)
        {
            return Interpolate(A.PassFrame, A.DistanceCm, B.PassFrame, B.DistanceCm);
        }
    }
    return Interpolate(Passage.LastPassFrame, Passage.LastPassDistanceCm, Passage.SegmentEndFrame, Passage.TotalDistanceCm);
}

bool FInfinityStageCompiler::EvaluateCelestialPhase(
    const UInfinityStageShowAsset& Show,
    const FGuid PassageGuid,
    const FFrameTime MasterFrame,
    const double InitialPhaseCycles,
    double& OutNormalizedPhase)
{
    OutNormalizedPhase = 0.0;
    const double TickRate = Show.TickResolution.AsDecimal();
    if (!PassageGuid.IsValid() || TickRate <= 0.0 || !FMath::IsFinite(InitialPhaseCycles))
    {
        return false;
    }

    const FInfinityCompileResult Compiled = Compile(Show);
    if (Compiled.HasErrors())
    {
        return false;
    }

    double IntegratedPhase = InitialPhaseCycles;
    bool bFoundPassage = false;
    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        const FInfinityPassageSettings* Settings = Show.PassageSettings.FindByPredicate(
            [&Passage](const FInfinityPassageSettings& Candidate)
            {
                return Candidate.PassageGuid == Passage.PassageGuid;
            });
        const FInfinityCelestialCycleSettings Defaults;
        const FInfinityCelestialCycleSettings& Cycle = Settings
            ? Settings->CelestialCycle
            : Defaults;
        const double DurationSeconds = FMath::Max(Cycle.CycleDurationSeconds, UE_KINDA_SMALL_NUMBER);
        const double Rate = Cycle.bAnimate ? FMath::Max(0.0, Cycle.CycleRateMultiplier) : 0.0;

        IntegratedPhase += Cycle.EntryPhaseOffsetCycles;
        if (Passage.PassageGuid == PassageGuid)
        {
            const double ElapsedFrames = FMath::Clamp(
                MasterFrame.AsDecimal() - Passage.SegmentStartFrame.Value,
                0.0,
                static_cast<double>(Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value));
            IntegratedPhase += (ElapsedFrames / TickRate) * Rate / DurationSeconds;
            bFoundPassage = true;
            break;
        }

        const double PassageFrames = FMath::Max(
            0,
            Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value);
        IntegratedPhase += (PassageFrames / TickRate) * Rate / DurationSeconds;
    }

    if (!bFoundPassage || !FMath::IsFinite(IntegratedPhase))
    {
        return false;
    }
    OutNormalizedPhase = IntegratedPhase - FMath::FloorToDouble(IntegratedPhase);
    return true;
}
