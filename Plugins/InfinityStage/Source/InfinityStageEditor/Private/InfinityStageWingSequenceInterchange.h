#pragma once

#include "CoreMinimal.h"
#include "InfinityStageTypes.h"

class UInfinityStageShowAsset;

/** Passage-wide values which are meaningful when a complete Passage is saved.
 * Music, temporality and stable identity deliberately remain owned by the target Show. */
struct FInfinityWingSequencePassageEnvelope
{
    FFrameNumber LeadInFrames = 0;
    FFrameNumber TailFrames = 0;
    double LeadInDistanceCm = 0.0;
    double TailDistanceCm = 0.0;
    double PreferredCameraSpeedCmPerSecond = 250.0;
    bool bUseLiveMechanismPhasePattern = false;
    double MechanismPhaseStepCycles = -0.10;
    double MechanismPhaseOffsetCycles = 0.0;
    EInfinityPassageFitMode FitMode = EInfinityPassageFitMode::MusicLockedDeriveCount;
    double PreferredSpacingCm = 500.0;
};

/** Fully parsed, side-effect-free interchange document. Source GUIDs are retained
 * only until PrepareImportedCues remints them and remaps internal references. */
struct FInfinityWingSequenceDocument
{
    FString Label;
    FString SourceShowPath;
    FGuid SourceShowGuid;
    FFrameRate SourceDisplayRate = FFrameRate(25, 1);
    FFrameRate SourceTickResolution = FFrameRate(24000, 1);
    TArray<FInfinityShowCue> Cues;
    TOptional<FInfinityWingSequencePassageEnvelope> PassageEnvelope;
};

class FInfinityStageWingSequenceInterchange
{
public:
    static constexpr int32 CurrentSchemaVersion = 1;

    static bool ExportToJson(
        const UInfinityStageShowAsset& Show,
        const TArray<int32>& OrderedCueIndices,
        const FString& SequenceLabel,
        const FInfinityPassageSettings* CompletePassage,
        FString& OutJson,
        FString& OutReport);

    static bool ImportFromJson(
        const FString& Json,
        FInfinityWingSequenceDocument& OutDocument,
        FString& OutReport);

    static bool SaveToFile(const FString& Filename, const FString& Json, FString& OutReport);
    static bool LoadFromFile(const FString& Filename, FInfinityWingSequenceDocument& OutDocument, FString& OutReport);

    /** Produces safe copies for a destination Show. Every stable row identity is
     * new; camera-gust anchors are remapped only when their anchor was exported. */
    static bool PrepareImportedCues(
        const FInfinityWingSequenceDocument& Document,
        FFrameRate TargetTickResolution,
        TArray<FInfinityShowCue>& OutCues,
        FString& OutReport);

    /** Replace only the enabled contiguous Wing rows owned by TargetPassageGuid.
     * Passage identity, label, music and temporality survive. A saved complete-
     * Passage envelope updates only layout/camera defaults. */
    static bool ReplacePassage(
        UInfinityStageShowAsset& Show,
        FGuid TargetPassageGuid,
        const FInfinityWingSequenceDocument& Document,
        TArray<int32>& OutInsertedIndices,
        FString& OutReport);

    /** Apply the saved ordered Wing designs across the rows already owned by a
     * Passage. The source pattern repeats or trims to the target row count.
     * Target row identity, labels, tags, enabled state, timing and spacing are
     * authoritative and are never replaced. Passage settings are untouched. */
    static bool ApplyArrangementToPassage(
        UInfinityStageShowAsset& Show,
        FGuid TargetPassageGuid,
        const FInfinityWingSequenceDocument& Document,
        TArray<int32>& OutAffectedIndices,
        FString& OutReport);

    /** Resize one existing Passage to a music-derived count while preserving
     * its current ordered Wing design as the repeat pattern. Existing row
     * identity and labels survive; only newly added rows receive fresh IDs and
     * generated labels. All resulting rows receive the fitted interval/gap. */
    static bool ResizePassageToCountPreservingPattern(
        UInfinityStageShowAsset& Show,
        FGuid TargetPassageGuid,
        int32 DesiredWingPairCount,
        FFrameNumber IntervalToNext,
        double GapToNextCm,
        TArray<int32>& OutAffectedIndices,
        FString& OutReport);

    /** Insert prepared rows without changing the surrounding Passage defaults. */
    static bool InsertAfter(
        UInfinityStageShowAsset& Show,
        int32 AfterCueIndex,
        const FInfinityWingSequenceDocument& Document,
        TArray<int32>& OutInsertedIndices,
        FString& OutReport);
};
