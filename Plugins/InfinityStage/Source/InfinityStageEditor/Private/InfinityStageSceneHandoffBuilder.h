#pragma once

#include "CoreMinimal.h"

class UInfinityStageShowAsset;
class UWorld;

/** Editor-only, explicit authoring tool for frame-exact Passage/Scene camera matching. */
class FInfinityStageSceneHandoffBuilder
{
public:
    /** Empty SceneCueGuids means every enabled Scene in the Show. */
    static bool MatchSceneHandoffs(
        UInfinityStageShowAsset& Show,
        UWorld& World,
        const TArray<FGuid>& SceneCueGuids,
        FString& OutReport);

    /**
     * Read-only comparison of each Scene's existing handoff cameras against the
     * current evaluated Passage endpoints.
     *
     * Handoff cameras are a snapshot taken when matching ran, so any later change
     * to a Passage's route or camera channels — a focal length key being the easy
     * one to forget — silently leaves them stale and produces a visible jump at
     * the boundary. This reports that without writing anything, so the artist can
     * decide whether the difference is a mistake or a deliberate cut.
     *
     * Returns false only on inspection failure; a stale result is a successful
     * check. OutStaleSceneGuids lists the Scenes that differ.
     */
    static bool CheckSceneHandoffs(
        UInfinityStageShowAsset& Show,
        UWorld& World,
        const TArray<FGuid>& SceneCueGuids,
        TArray<FGuid>& OutStaleSceneGuids,
        FString& OutReport);
};
