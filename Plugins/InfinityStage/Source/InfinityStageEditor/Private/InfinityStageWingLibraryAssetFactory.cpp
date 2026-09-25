#include "InfinityStageWingLibraryAssetFactory.h"

#include "InfinityStageWingLibraryAsset.h"

UInfinityStageWingLibraryAssetFactory::UInfinityStageWingLibraryAssetFactory()
{
    SupportedClass = UInfinityStageWingLibraryAsset::StaticClass();
    bCreateNew = true;
    bEditAfterNew = true;
}

UObject* UInfinityStageWingLibraryAssetFactory::FactoryCreateNew(
    UClass* Class,
    UObject* InParent,
    FName Name,
    EObjectFlags Flags,
    UObject* Context,
    FFeedbackContext* Warn)
{
    return NewObject<UInfinityStageWingLibraryAsset>(
        InParent,
        Class,
        Name,
        Flags | RF_Transactional);
}
