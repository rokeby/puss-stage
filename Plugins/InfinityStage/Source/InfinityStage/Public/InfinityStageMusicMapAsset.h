#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "InfinityStageMusicMapAsset.generated.h"

class USoundBase;

UENUM(BlueprintType)
enum class EInfinityMusicProposalState : uint8
{
    Suggested,
    Confirmed,
    Rejected
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityTempoCandidate
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Analysis", meta = (ClampMin = "1.0"))
    double Bpm = 120.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Analysis", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double Confidence = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    int32 Rank = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    EInfinityMusicProposalState State = EInfinityMusicProposalState::Suggested;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMusicAnalysisMarker
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid MarkerGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Analysis")
    double TimeSeconds = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Analysis", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double Strength = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Analysis")
    FText Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    EInfinityMusicProposalState State = EInfinityMusicProposalState::Suggested;
};

/**
 * A continuous expressive envelope sampled at a fixed rate.
 *
 * Markers describe instants; a build or a decay is an interval, so timing
 * movement to musical expression needs shape rather than timestamps.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityAnalysisCurve
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    FName Name;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    float RateHz = 10.0f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    TArray<float> Values;

    /** Linear sample at a time in seconds; clamps outside the sampled range. */
    float Sample(double TimeSeconds) const;
};

/** A characterised span of the track: quiet, building, intense, releasing. */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityExpressiveSection
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    double StartSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    double EndSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    double MeanIntensity = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    double Trend = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    FString Label;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UInfinityStageMusicMapAsset : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid MusicMapGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Source")
    TSoftObjectPtr<USoundBase> Sound;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Source")
    FString SourceFilename;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Source")
    FString SourceSha256;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Source")
    FString SourceMd5;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Source")
    double DurationSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Provider")
    FString ProviderName;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Provider")
    FString ProviderVersion;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Provider")
    FString GeneratedAtUtc;

    /** Min, max and RMS per review bin. This is editor review data, never a playback waveform. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    TArray<FVector3f> WaveformBins;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    TArray<FInfinityTempoCandidate> TempoCandidates;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    TArray<FInfinityMusicAnalysisMarker> OnsetProposals;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    TArray<FInfinityMusicAnalysisMarker> BeatProposals;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Review")
    TArray<FInfinityMusicAnalysisMarker> MajorChangeProposals;

    /** Continuous expressive envelopes: intensity, rhythmic density, brightness, bands, novelty. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    TArray<FInfinityAnalysisCurve> FeatureCurves;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Analysis")
    TArray<FInfinityExpressiveSection> ExpressiveSections;

    /** Named lookup for the apply-to-channel workflow. */
    const FInfinityAnalysisCurve* FindCurve(FName CurveName) const;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Safety")
    bool bCueScoreMutatedByAnalysis = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Safety")
    bool bRequiresArtistApproval = true;

    virtual FPrimaryAssetId GetPrimaryAssetId() const override;
};
