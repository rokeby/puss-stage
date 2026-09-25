#pragma once

#include "CoreMinimal.h"
#include "InfinityStageTypes.h"
#include "UObject/Object.h"
#include "InfinityStageCueProxy.generated.h"

class UInfinityStageShowAsset;

DECLARE_DELEGATE(FOnInfinityStageCueProxyChanged);

UCLASS(Transient)
class INFINITYSTAGEEDITOR_API UInfinityStageCueProxy : public UObject
{
    GENERATED_BODY()

public:
    /**
     * Derived, bulk-editable pivot separation for a Wing Pair at rest. Changing
     * this preserves the current lateral centre and writes symmetrical Left/Right
     * local Y positions; it is not a second serialized source of truth.
     */
    UPROPERTY(EditAnywhere, Category = "Wing Pair Layout",
        meta = (DisplayName = "Rest Opening Width (Pivot-to-Pivot)", ClampMin = "0.0", Units = "cm", EditCondition = "bIsWingPair", EditConditionHides))
    double RestOpeningWidthCm = 0.0;

    /** Lateral offset of the opening centre from the route/pair origin. */
    UPROPERTY(EditAnywhere, Category = "Wing Pair Layout",
        meta = (DisplayName = "Opening Centre Offset", Units = "cm", EditCondition = "bIsWingPair", EditConditionHides))
    double OpeningCentreOffsetCm = 0.0;

    UPROPERTY(EditAnywhere, Category = "Selected Cue", meta = (ShowOnlyInnerProperties))
    FInfinityShowCue Cue;

    void Initialize(UInfinityStageShowAsset* InAsset, int32 InCueIndex);
    /** Owning Show, so a property customization can enumerate its Music Rails. */
    UInfinityStageShowAsset* GetShowAsset() const { return Asset.Get(); }

    FOnInfinityStageCueProxyChanged OnChanged;

    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;

private:
    UPROPERTY(Transient)
    bool bIsWingPair = false;

    TWeakObjectPtr<UInfinityStageShowAsset> Asset;
    int32 CueIndex = INDEX_NONE;
    bool bApplying = false;

    void RefreshOpeningLayoutFromCue();
    void ApplyOpeningLayoutToCue();
};
