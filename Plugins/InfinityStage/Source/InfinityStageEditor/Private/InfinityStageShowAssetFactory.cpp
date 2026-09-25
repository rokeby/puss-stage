#include "InfinityStageShowAssetFactory.h"

#include "InfinityStageShowAsset.h"

UInfinityStageShowAssetFactory::UInfinityStageShowAssetFactory()
{
    SupportedClass = UInfinityStageShowAsset::StaticClass();
    bCreateNew = true;
    bEditAfterNew = true;
}

UObject* UInfinityStageShowAssetFactory::FactoryCreateNew(
    UClass* Class,
    UObject* InParent,
    FName Name,
    EObjectFlags Flags,
    UObject* Context,
    FFeedbackContext* Warn)
{
    UInfinityStageShowAsset* Asset = NewObject<UInfinityStageShowAsset>(InParent, Class, Name, Flags | RF_Transactional);
    Asset->EnsureStableIds();
    return Asset;
}
