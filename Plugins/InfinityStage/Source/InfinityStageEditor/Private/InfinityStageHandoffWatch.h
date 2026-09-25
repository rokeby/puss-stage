#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "EditorSubsystem.h"
#include "InfinityStageHandoffWatch.generated.h"

class UInfinityStageShowAsset;
class UWorld;

/**
 * Says when an edit makes a Scene camera handoff stale, and which edit did it.
 *
 * Scene handoff cameras are snapshots of the neighbouring Passage endpoints.
 * Anything that moves an endpoint silently leaves them behind: a Passage camera
 * key (from the pilot, the Cue Desk curve editor or Sequencer), a route or rig
 * edit, or a Show timing change. A key in the middle of a Passage is enough
 * when it is a channel's only key, because the curve then holds that value to
 * both ends. Nobody connects the framing tweak to the jump at a boundary two
 * segments away, so this does.
 *
 * The first relevant Modify() of a burst records which Scenes are already stale
 * (Modify runs before the change). Once edits have been quiet for a moment the
 * read-only Check All Scenes runs again, and only Scenes that became stale are
 * reported, with a Match button. Scenes already stale, or kept on purpose, are
 * not raised again. Writes nothing unless the artist presses Match.
 *
 * Console: InfinityStage.HandoffWatch 0 disables it.
 */
UCLASS()
class UInfinityStageHandoffWatchSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** Records the Scenes that are stale right now as already known. */
    void CaptureBaseline(UInfinityStageShowAsset& Show, UWorld& World);

    /**
     * Runs the read-only Scene handoff check and returns the Scenes that became
     * stale since the last baseline or check. The known set becomes the current
     * stale set, so a Scene that is matched and later drifts is raised again.
     */
    TArray<FGuid> CheckNow(UInfinityStageShowAsset& Show, UWorld& World, const FString& Trigger, bool bNotify);

private:
    struct FShowWatchState
    {
        TSet<FGuid> KnownStale;
        bool bHasBaseline = false;
        bool bPending = false;
        FString Trigger;
    };

    void HandleObjectModified(UObject* Object);
    void HandleUndoRedo();
    bool Tick(float DeltaTime);
    void NotifyNewlyStale(UInfinityStageShowAsset& Show, const TArray<FGuid>& NewlyStale, const FString& Trigger);
    FShowWatchState& GetState(UInfinityStageShowAsset& Show);

    TMap<TWeakObjectPtr<UInfinityStageShowAsset>, FShowWatchState> States;
    double LastRelevantChangeSeconds = 0.0;
    bool bChecking = false;
    FDelegateHandle ObjectModifiedHandle;
    FDelegateHandle UndoRedoHandle;
    FTSTicker::FDelegateHandle TickHandle;
};
