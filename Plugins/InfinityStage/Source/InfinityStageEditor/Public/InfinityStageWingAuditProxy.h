#pragma once

#include "CoreMinimal.h"
#include "InfinityStageWingLibraryAsset.h"
#include "UObject/Object.h"
#include "InfinityStageWingAuditProxy.generated.h"

class UInfinityStageWingLibraryAsset;

DECLARE_DELEGATE(FOnInfinityStageWingAuditProxyChanged);

UCLASS(Transient)
class INFINITYSTAGEEDITOR_API UInfinityStageWingAuditProxy : public UObject
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, Category = "Selected Wing Asset", meta = (ShowOnlyInnerProperties))
    FInfinityWingAssetEntry Entry;

    void Initialize(UInfinityStageWingLibraryAsset* InLibrary, FGuid InEntryGuid);
    FOnInfinityStageWingAuditProxyChanged OnChanged;

    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
    virtual void PostEditUndo() override;

private:
    TWeakObjectPtr<UInfinityStageWingLibraryAsset> Library;
    FGuid EntryGuid;
};
