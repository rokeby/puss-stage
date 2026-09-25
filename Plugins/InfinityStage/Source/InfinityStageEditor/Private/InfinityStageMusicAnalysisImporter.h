#pragma once

#include "CoreMinimal.h"

class UInfinityStageShowAsset;

class FInfinityStageMusicAnalysisImporter
{
public:
    static bool ImportDirectory(const FString& AnalysisDirectory, UInfinityStageShowAsset* Show, FString& OutReport);

    /**
     * Writes a Sound's imported PCM back out as a WAV in the drop folder and runs
     * the analyzer over it.
     *
     * The analyzer reads WAV from disk, but an imported SoundWave's original file
     * may have moved or never been kept. Reconstructing the WAV from the asset
     * makes analysis depend on the project rather than on the artist's filesystem.
     *
     * Returns false with a usable OutReport when the sound cannot be decoded or
     * the analyzer cannot be launched; in the latter case the WAV is still
     * exported so the command can be run by hand.
     */
    static bool AnalyzeSound(
        class USoundBase* Sound,
        int32 PassageNumber,
        FString& OutReport);
};
