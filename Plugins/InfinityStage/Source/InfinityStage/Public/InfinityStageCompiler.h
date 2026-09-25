#pragma once

#include "CoreMinimal.h"
#include "InfinityStageShowAsset.h"

enum class EInfinityCompileIssueSeverity : uint8
{
    Warning,
    Error
};

struct INFINITYSTAGE_API FInfinityCompileIssue
{
    EInfinityCompileIssueSeverity Severity = EInfinityCompileIssueSeverity::Error;
    FGuid SubjectGuid;
    FString Message;
};

struct INFINITYSTAGE_API FInfinityCompiledWing
{
    FGuid CueGuid;
    FGuid OccurrenceGuid;
    FFrameNumber PassFrame = 0;
    double DistanceCm = 0.0;
};

struct INFINITYSTAGE_API FInfinityCompiledPassage
{
    FGuid PassageGuid;
    int32 FirstCueIndex = INDEX_NONE;
    int32 LastCueIndex = INDEX_NONE;
    FFrameNumber SegmentStartFrame = 0;
    FFrameNumber FirstPassFrame = 0;
    FFrameNumber LastPassFrame = 0;
    FFrameNumber SegmentEndFrame = 0;
    double FirstPassDistanceCm = 0.0;
    double LastPassDistanceCm = 0.0;
    double TotalDistanceCm = 0.0;
    TArray<FInfinityCompiledWing> Wings;
};

struct INFINITYSTAGE_API FInfinityCompiledSegment
{
    FGuid SegmentGuid;
    EInfinityCueType Type = EInfinityCueType::WingPair;
    int32 FirstCueIndex = INDEX_NONE;
    int32 LastCueIndex = INDEX_NONE;
    FFrameNumber StartFrame = 0;
    FFrameNumber EndFrame = 0;
    EInfinityExternalSoundAuthority ExternalSound = EInfinityExternalSoundAuthority::None;
};

struct INFINITYSTAGE_API FInfinityCompileResult
{
    TArray<FInfinityCompiledPassage> Passages;
    TArray<FInfinityCompiledSegment> Segments;
    TArray<FInfinityCompileIssue> Issues;
    FFrameNumber ShowEndFrame = 0;

    bool HasErrors() const;
};

struct INFINITYSTAGE_API FInfinityPassageFitInput
{
    double DurationSeconds = 0.0;
    double CameraSpeedCmPerSecond = 250.0;
    double SpacingCm = 500.0;
    double EntryClearanceCm = 250.0;
    double ExitClearanceCm = 250.0;
};

struct INFINITYSTAGE_API FInfinityPassageFitResult
{
    bool bValid = false;
    int32 WingPairCount = 0;
    double TravelDistanceCm = 0.0;
    double RequiredDistanceCm = 0.0;
    double ResidualDistanceCm = 0.0;
    double PassIntervalSeconds = 0.0;
    FString Error;
};

class INFINITYSTAGE_API FInfinityStageCompiler
{
public:
    static FInfinityCompileResult Compile(const UInfinityStageShowAsset& Show);
    static FInfinityPassageFitResult FitPassage(const FInfinityPassageFitInput& Input);
    static double SolveCameraSpeedCmPerSecond(double DurationSeconds, int32 WingPairCount, double SpacingCm, double EntryClearanceCm, double ExitClearanceCm);
    static double EvaluateDistanceAtFrame(const FInfinityCompiledPassage& Passage, FFrameTime MasterFrame);

    /** Resolves the integrated, normalized day/night phase for one Passage.
     * Phase zero is midnight, 0.25 sunrise, 0.5 noon and 0.75 sunset. Previous
     * Passage rates are accumulated so direct seeks never depend on history. */
    static bool EvaluateCelestialPhase(
        const UInfinityStageShowAsset& Show,
        FGuid PassageGuid,
        FFrameTime MasterFrame,
        double InitialPhaseCycles,
        double& OutNormalizedPhase);
};
