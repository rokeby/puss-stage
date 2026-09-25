#pragma once

#include "CoreMinimal.h"
#include "Factories/Factory.h"
#include "InfinityStageShowAssetFactory.generated.h"

UCLASS()
class INFINITYSTAGEEDITOR_API UInfinityStageShowAssetFactory : public UFactory
{
    GENERATED_BODY()

public:
    UInfinityStageShowAssetFactory();

    virtual UObject* FactoryCreateNew(
        UClass* Class,
        UObject* InParent,
        FName Name,
        EObjectFlags Flags,
        UObject* Context,
        FFeedbackContext* Warn) override;
};
