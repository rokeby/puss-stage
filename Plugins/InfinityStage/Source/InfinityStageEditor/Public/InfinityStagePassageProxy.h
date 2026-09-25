#pragma once

#include "CoreMinimal.h"
#include "InfinityStageTypes.h"
#include "UObject/Object.h"
#include "InfinityStagePassageProxy.generated.h"

class UInfinityStageShowAsset;

DECLARE_DELEGATE(FOnInfinityStagePassageProxyChanged);

/** Contextual editor object for the selected Passage. It prevents the Music
 * inspector from exposing the entire Show/MusicRails array at once. */
UCLASS(Transient)
class INFINITYSTAGEEDITOR_API UInfinityStagePassageProxy : public UObject
{
    GENERATED_BODY()

public:
    /** Owning Show, so a property customization can enumerate its Music Rails. */
    UInfinityStageShowAsset* GetShowAsset() const { return Asset.Get(); }

    UPROPERTY(EditAnywhere, Category = "Passage", meta = (ShowOnlyInnerProperties))
    FInfinityPassageSettings Passage;

    UPROPERTY(EditAnywhere, Category = "Defining Music", meta = (ShowOnlyInnerProperties))
    FInfinityMusicRail MusicRail;

    UPROPERTY(VisibleAnywhere, Category = "Fit")
    double UsedMusicSeconds = 0.0;

    UPROPERTY(VisibleAnywhere, Category = "Fit")
    int32 CurrentWingPairCount = 0;

    UPROPERTY(VisibleAnywhere, Category = "Fit", meta = (Units = "cm"))
    double CurrentRouteDistanceCm = 0.0;

    /** Number of apparent day/night cycles produced across this Passage at its
     * current duration and temporality rate. */
    UPROPERTY(VisibleAnywhere, Category = "Temporality", meta = (DisplayName = "Apparent Days Across Passage"))
    double ApparentCelestialCycles = 0.0;

    void Initialize(UInfinityStageShowAsset* InAsset, FGuid InPassageGuid);
    FOnInfinityStagePassageProxyChanged OnChanged;

    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;

private:
    TWeakObjectPtr<UInfinityStageShowAsset> Asset;
    FGuid PassageGuid;
    FGuid RailGuid;
    bool bApplying = false;

    void RefreshDerived();
};
