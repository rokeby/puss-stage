#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "InfinityStagePassageResizeLibrary.generated.h"

class UInfinityStageShowAsset;
class ULevelSequence;
class UWorld;

UENUM(BlueprintType)
enum class EInfinityPassageResizePolicy : uint8
{
    PreserveSpeedAndSpacing
};

USTRUCT(BlueprintType)
struct INFINITYSTAGEEDITOR_API FInfinityPassageCueIndexShift
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FGuid CueGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    int32 OldIndex = INDEX_NONE;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    int32 NewIndex = INDEX_NONE;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGEEDITOR_API FInfinityPassageManagedSectionMove
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FString Kind;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FGuid BlockGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber OldStartFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber NewStartFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber OldEndFrame = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber NewEndFrame = 0;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGEEDITOR_API FInfinityPassageResizePlan
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    bool bCanApply = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    bool bApplied = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FGuid PassageGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double TargetSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    int32 OldWingPairCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    int32 NewWingPairCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    int32 PairsAppended = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double OldDurationSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double NewDurationSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double OldRouteLengthCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double NewRouteLengthCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double RouteSplineLengthCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    bool bRouteIsShaped = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double ResidualDistanceAbsorbedCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber NewTailFrames = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    double NewTailDistanceCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FVector OldWorldExtentMin = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FVector OldWorldExtentMax = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FVector NewWorldExtentMin = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FVector NewWorldExtentMax = FVector::ZeroVector;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FFrameNumber MasterPlaybackRangeDelta = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FGuid> LocalOverrideCueGuids;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FString> LocalOverrideRows;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FInfinityPassageCueIndexShift> LaterCueIndexShifts;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FInfinityPassageManagedSectionMove> ManagedSectionsMoving;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FString> ArtistOwnedMasterContentNotRippled;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FString> OverlapActors;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FString> RefusalReasons;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    TArray<FString> Warnings;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Passage Resize")
    FString Report;
};

/** Narrow editor-only data operation. It never saves, materializes, rebuilds the
 * Master, rematches a handoff, or edits the route. Those remain explicit guarded
 * orchestration steps after a successful APPLY and backup. */
UCLASS()
class INFINITYSTAGEEDITOR_API UInfinityStagePassageResizeLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Passage Resize",
        meta = (AdvancedDisplay = "bAcceptOverrideLoss"))
    static FInfinityPassageResizePlan ResizePassageToDuration(
        UInfinityStageShowAsset* Show,
        UWorld* BindingWorld,
        ULevelSequence* MasterSequence,
        FGuid PassageGuid,
        double TargetSeconds,
        EInfinityPassageResizePolicy Policy = EInfinityPassageResizePolicy::PreserveSpeedAndSpacing,
        bool bDryRun = true,
        bool bAcceptOverrideLoss = false);
};
