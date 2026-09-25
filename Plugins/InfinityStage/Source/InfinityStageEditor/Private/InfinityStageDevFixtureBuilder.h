#pragma once

#include "CoreMinimal.h"

class FInfinityStageDevFixtureBuilder
{
public:
    /** Creates a clearly named development fixture; never edits legacy Stage Wing assets. */
    static bool Build(const FString& MusicSourceDirectory, FString& OutReport);

    /** Preserves authored cues, replaces only excluded panel assets, raises editing
     * headroom, and atomically rematerializes the current Infinity Stage fixture. */
    static bool RepairCurrentWingPassages(FString& OutReport);
};
