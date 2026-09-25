#pragma once

#include "CoreMinimal.h"
#include "Factories/Factory.h"
#include "InfinityStageWingLibraryAssetFactory.generated.h"

UCLASS()
class INFINITYSTAGEEDITOR_API UInfinityStageWingLibraryAssetFactory : public UFactory
{
    GENERATED_BODY()

public:
    UInfinityStageWingLibraryAssetFactory();

    virtual UObject* FactoryCreateNew(
        UClass* Class,
        UObject* InParent,
        FName Name,
        EObjectFlags Flags,
        UObject* Context,
        FFeedbackContext* Warn) override;
};
