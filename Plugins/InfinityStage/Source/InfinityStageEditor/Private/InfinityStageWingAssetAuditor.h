#pragma once

#include "CoreMinimal.h"

class UInfinityStageWingLibraryAsset;

struct FInfinityWingAuditSummary
{
    int32 Total = 0;
    int32 Ready = 0;
    int32 AlreadyCanonical = 0;
    int32 Corrected = 0;
    int32 ReviewRequired = 0;
    int32 Errors = 0;
    FString ReportPath;

    FString ToString() const;
};

class FInfinityStageWingAssetAuditor
{
public:
    static UInfinityStageWingLibraryAsset* LoadOrCreateDefaultLibrary();
    static bool Scan(UInfinityStageWingLibraryAsset& Library, FInfinityWingAuditSummary& OutSummary, FString& OutError);
    static bool ApplySafeCorrections(UInfinityStageWingLibraryAsset& Library, FInfinityWingAuditSummary& OutSummary, FString& OutError);
    /** Removes only the legacy automatic negative-Y bake from right architectural
     * assets. Left and neutral assets are deliberately untouched. */
    static bool RepairLegacyRightPhotographicMirrors(UInfinityStageWingLibraryAsset& Library, int32& OutRepaired, FString& OutError);
    static bool RevertCorrections(UInfinityStageWingLibraryAsset& Library, const TSet<FGuid>& EntryGuids, FString& OutError);
    static bool SaveAuditReport(const UInfinityStageWingLibraryAsset& Library, FString& OutPath, FString& OutError);
};
