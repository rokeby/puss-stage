#pragma once

#include "CoreMinimal.h"
#include "InfinityStageCueSheet.h"
#include "InfinityStageTypes.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Views/SListView.h"

class UInfinityStageShowAsset;

/**
 * Puss Cue Director panel (opened from the Cue Desk options menu). Gary, 7 Oct:
 * "most things run on and not need pressing go ... mostly after lights out after
 * scenes". The show plays straight through (run-through); this panel picks where it
 * still stops for Klara's GO: at the end of chosen segments, and at chosen GO markers.
 *
 * It reads the Show with the pure compiler only (never writes or dirties it) and
 * writes one text file, Content/InfinityStage/CueSheet/cue_director.txt. PIE picks
 * it up at start, on F5, or with "Apply to PIE".
 */
class SInfinityStageCueDirectorPanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SInfinityStageCueDirectorPanel) {}
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs);

    struct FRow
    {
        bool bGo = false;
        FGuid SegmentGuid;
        FString Label;
        FString SheetLabel;
        EInfinityCueType Type = EInfinityCueType::WingPair;
        double StartSeconds = 0.0;
        double LengthSeconds = 0.0;
        FString GoNumber;
        /** "S3" for the third Scene; empty for other segments. */
        FString SceneKey;
        /** A fallback video for this Scene is listed in current.json. */
        bool bVideoAvailable = false;
    };

private:
    void Refresh();
    void Save();
    void ApplyToPie();
    void StopAfterEveryScene();

    TSharedRef<ITableRow> GenerateRow(TSharedPtr<FRow> Row, const TSharedRef<STableViewBase>& Owner);
    FString LabelOf(const FGuid& Guid) const;

    TWeakObjectPtr<UInfinityStageShowAsset> Show;
    FInfinityCueDirectorSettings Settings;
    FInfinityCueSheet Sheet;
    TArray<TSharedPtr<FRow>> Rows;
    TSharedPtr<SListView<TSharedPtr<FRow>>> List;
    FText Status;
    bool bDirty = false;
};
