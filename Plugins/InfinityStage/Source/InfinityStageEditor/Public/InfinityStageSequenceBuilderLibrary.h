#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "InfinityStageSequenceBuilderLibrary.generated.h"

class UInfinityStageShowAsset;
class ULevelSequence;
class UWorld;

UCLASS()
class INFINITYSTAGEEDITOR_API UInfinityStageSequenceBuilderLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Read-only comparison of existing handoff cameras with Passage endpoints. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Sequencer")
    static bool CheckSceneHandoffs(
        UInfinityStageShowAsset* Show,
        UWorld* BindingWorld,
        TArray<FGuid>& OutStaleSceneGuids,
        FString& OutReport);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Sequencer")
    static bool RebuildManagedMaster(
        UInfinityStageShowAsset* Show,
        ULevelSequence* MasterSequence,
        FString& OutReport);

    /**
     * Rebuilds a fully plugin-managed render wrapper around the authoritative Master.
     * The wrapper preserves absolute Master-frame coordinates, exposes ordinary Camera
     * Cut bindings for Passage camera rigs, and deliberately leaves Scene intervals to
     * their nested Scene Camera Cut Tracks.
     *
     * SelectedPassageGuid renders the complete Passage (including lead-in/tail). When
     * it is not set, SelectedCueGuids define one continuous range from the earliest
     * selected cue to the interval after the latest selected cue.
     */
    static bool RebuildManagedRenderWrapper(
        UInfinityStageShowAsset* Show,
        ULevelSequence* MasterSequence,
        ULevelSequence* RenderSequence,
        UWorld* BindingWorld,
        const TArray<FGuid>& SelectedCueGuids,
        FGuid SelectedPassageGuid,
        FFrameNumber& OutStartFrame,
        FFrameNumber& OutEndFrame,
        FString& OutReport);
};
