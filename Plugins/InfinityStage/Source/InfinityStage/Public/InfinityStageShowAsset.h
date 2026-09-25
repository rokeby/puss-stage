#pragma once

#include "CoreMinimal.h"
#include "InfinityStageTypes.h"
#include "InfinityStageShowAsset.generated.h"

/**
 * Deliberate unevenness applied when one pair's lighting is replicated across
 * others, so a corridor of identical fixtures reads as a hand-rigged one. Each
 * target pair draws from its own seeded stream, so re-running is repeatable.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityLightReplicationVariation
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Variation", meta = (ClampMin = "0.0", Units = "cm"))
    float PositionJitterCm = 25.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Variation", meta = (ClampMin = "0.0", Units = "deg"))
    float RotationJitterDegrees = 3.0f;

    /** 0.2 means each copied light lands between 80% and 120% of the template intensity. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Variation", meta = (ClampMin = "0.0", ClampMax = "0.9"))
    float IntensityJitterFraction = 0.2f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Variation")
    int32 Seed = 0;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UInfinityStageShowAsset : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UInfinityStageShowAsset();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid ShowGuid;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Show")
    FFrameRate DisplayRate;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Show")
    FFrameRate TickResolution;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Show")
    TArray<FInfinityShowCue> Cues;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Show")
    TArray<FInfinityPassageSettings> PassageSettings;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    TArray<FInfinityMusicRail> MusicRails;

    /** Persistent artist-visible Master container. The plugin only rebuilds its managed tracks. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Show")
    TSoftObjectPtr<class ULevelSequence> ManagedMasterSequence;

    /** Shared role and canonical-geometry metadata for every wing mesh used by this Show. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Show")
    TSoftObjectPtr<class UInfinityStageWingLibraryAsset> WingLibrary;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Version")
    int32 SchemaVersion = 1;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    void EnsureStableIds();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    void ReconcilePassageSettings();

    UFUNCTION(BlueprintPure, Category = "Infinity Stage")
    int32 FindCueIndex(FGuid CueGuid) const;

    /** Applies one explicit image-flip state to every Left, Right or Top panel
     * occurrence using the same mesh. Returns the number of changed panels. */
    int32 ApplyImageFlipToAllUsesOfMesh(const FSoftObjectPath& MeshPath, bool bFlipImageHorizontally);

    /** Applies one occurrence's complete saved relative transform to every
     * Left, Right or Top panel using the same mesh. Returns the number changed. */
    int32 ApplyRelativeTransformToAllUsesOfMesh(
        const FSoftObjectPath& MeshPath,
        const FTransform& RelativeTransform);

    /** Fills the selected Wing Pair mechanisms with a closed, smooth in/out
     * gesture. Phase is derived from each cue's ordinal inside its Passage, so
     * applying the preset to a subset still aligns with the complete tunnel. */
    int32 ApplyTravelingUndulation(
        const TArray<FGuid>& CueGuids,
        double CycleRateHz,
        double InwardTravelCm,
        double PhaseStepCycles,
        bool bUseLivePassagePattern = false);

    /** Applies a camera-relative reveal to an ordered selection. Advanced timed
     * cascades may partition a complete Passage into deterministic groups; the
     * normal camera/music-rail mode remains one continuous Passage window. */
    int32 ApplyCameraGust(
        const TArray<FGuid>& OrderedCueGuids,
        const FInfinityCameraGustSettings& Settings,
        bool bPartitionIntoFanDepthGroups);

    /** Holds the selected mechanisms at their authored phase without changing
     * their curves, travel or rate, so the movement can be restored later. */
    int32 SetMechanismsStatic(const TArray<FGuid>& CueGuids);

    /** Replaces only Light attachments on each target Wing Pair with copies from
     * the source cue. An empty source light set clears target lights. Props,
     * sounds and triggers are preserved. Destination identities remain stable
     * when the light ordinal already exists. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Lighting")
    int32 ReplicateLightAttachments(FGuid SourceCueGuid, const TArray<FGuid>& TargetCueGuids);

    /** As ReplicateLightAttachments, then jitters each copy's offset, aim and intensity per target with a seeded stream. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Stage Lighting")
    int32 ReplicateLightAttachmentsWithVariation(
        FGuid SourceCueGuid,
        const TArray<FGuid>& TargetCueGuids,
        const FInfinityLightReplicationVariation& Variation);

    /** Every Wing Pair cue in Show order, for whole-show lighting operations. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Stage Lighting")
    TArray<FGuid> GetAllWingPairCueGuids() const;

    /** The Passage whose cue range contains the cue, or an invalid guid when none does. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage")
    FGuid FindPassageGuidForCue(FGuid CueGuid) const;

    /** Every Wing Pair cue inside one Passage's range, in Show order. Empty for an unknown Passage. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Stage Lighting")
    TArray<FGuid> GetWingPairCueGuidsInPassage(FGuid PassageGuid) const;

    virtual FPrimaryAssetId GetPrimaryAssetId() const override;
    virtual void Serialize(FArchive& Ar) override;
    virtual void PostLoad() override;
};
