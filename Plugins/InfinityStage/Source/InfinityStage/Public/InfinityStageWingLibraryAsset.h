#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "InfinityStageWingLibraryAsset.generated.h"

class UStaticMesh;

UENUM(BlueprintType)
enum class EInfinityWingAssetRole : uint8
{
    Unknown,
    LeftArchitectural,
    RightArchitectural,
    SideNeutral,
    Top,
    GroundOrProp,
    Excluded
};

UENUM(BlueprintType)
enum class EInfinityWingAuditStatus : uint8
{
    Unscanned,
    Ready,
    Corrected,
    ReviewRequired,
    Error
};

UENUM(BlueprintType)
enum class EInfinityWingThicknessAxis : uint8
{
    Unknown,
    X,
    Y,
    Z
};

UENUM(BlueprintType)
enum class EInfinityWingTallEdge : uint8
{
    Unknown,
    NegativeY,
    PositiveY,
    Even
};

UENUM(BlueprintType)
enum class EInfinityWingFrontAxis : uint8
{
    Unknown,
    PositiveX,
    NegativeX
};

/** Persistent audit and role record for one scenic mesh. Geometry corrections are
 * applied to the Static Mesh source description; AppliedCanonicalTransform is
 * retained so the operation can be reversed deliberately. */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityWingAssetEntry
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid EntryGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Asset")
    TSoftObjectPtr<UStaticMesh> Mesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Classification")
    EInfinityWingAssetRole Role = EInfinityWingAssetRole::Unknown;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    EInfinityWingAuditStatus Status = EInfinityWingAuditStatus::Unscanned;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    EInfinityWingThicknessAxis OriginalThicknessAxis = EInfinityWingThicknessAxis::Unknown;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    EInfinityWingTallEdge TallEdgeAfterCorrection = EInfinityWingTallEdge::Unknown;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FVector OriginalBoundsSizeCm = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FVector CanonicalBoundsSizeCm = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FVector SourceReportDimensionsCm = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FString SourceImage;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FString SourceFbx;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Correction")
    FTransform ProposedCanonicalTransform = FTransform::Identity;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Correction")
    FTransform AppliedCanonicalTransform = FTransform::Identity;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Correction")
    bool bSafeToApplyAutomatically = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Correction")
    bool bGeometryCanonical = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Correction")
    bool bMirroredForOutsideTallEdge = false;

    /** Canonical panel front after axis/pivot/scale correction. This is not a
     * Left/Right or image-mirroring instruction. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Placement")
    EInfinityWingFrontAxis FrontAxis = EInfinityWingFrontAxis::PositiveX;

    /** When enabled, subsequent audits preserve FrontAxis instead of deriving it
     * from the explicit Left/Right asset role. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Placement")
    bool bFrontAxisArtistOverride = false;

    /** Deliberate per-asset placement correction. Negative scale is rejected
     * unless bPhotographicMirrorApproved is explicitly enabled. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Placement")
    FTransform PlacementAdjustment = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Placement")
    bool bPhotographicMirrorApproved = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Placement")
    bool bAllowPassageFit = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notes", meta = (MultiLine = true))
    FString Notes;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UInfinityStageWingLibraryAsset : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid LibraryGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets")
    TArray<FInfinityWingAssetEntry> Entries;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Audit")
    FDateTime LastAuditUtc;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Version")
    int32 SchemaVersion = 1;

    UInfinityStageWingLibraryAsset();

    void EnsureStableIds();
    FInfinityWingAssetEntry* FindEntry(const FSoftObjectPath& MeshPath);
    const FInfinityWingAssetEntry* FindEntry(const FSoftObjectPath& MeshPath) const;

    virtual FPrimaryAssetId GetPrimaryAssetId() const override;
    virtual void PostLoad() override;
};
