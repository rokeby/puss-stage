#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "InfinityStageCueSheet.generated.h"

/**
 * Puss Cue Director, CD1: the performance cue sheet (Gary, 7 Oct).
 *
 * Gary's Google Sheet "Puss_Master_cue_sheet" is the source of truth for the ORDER
 * of the show: script lines (one column per speaker), department actions (Light,
 * Sound tech, Action, Sound cue), the digital segment a row starts (Video Cue),
 * Scene beats and notes. It is exported to CSV and read here; nothing is written
 * to the Show or the level. Discrepancies with the UE stage are reported, never
 * blocking ("my UE stage and cameron's sound ... might not be fully consistent").
 */

/** One spoken line in a row: who says it, and what. */
struct INFINITYSTAGE_API FInfinityCueSheetLine
{
    FString Speaker;
    FString Text;
};

/** One sheet row, already sorted into roles. */
struct INFINITYSTAGE_API FInfinityCueSheetRow
{
    /** 1-based row in the CSV, for "see the sheet, row 37". */
    int32 SourceRow = 0;
    /** Column A: the show-wide cue number ("3", "12.5"), or empty. */
    FString Number;
    FString Light;
    FString SoundTech;
    FString Action;
    FString SoundCue;
    /** Non-empty where a digital segment starts (Opening, Passage 1, S1 Animals ...). */
    FString VideoCue;
    FString Beat;
    FString Notes;
    TArray<FInfinityCueSheetLine> Lines;
    /** The Video Cue in force at this row (carried down), and its 0-based order. -1 before the first. */
    FString Segment;
    int32 SegmentOrdinal = INDEX_NONE;

    bool IsBlank() const;
    /** Anything for a person to do or say (not just a number or a segment label). */
    bool HasContent() const;
};

struct INFINITYSTAGE_API FInfinityCueSheet
{
    TArray<FInfinityCueSheetRow> Rows;
    /** Each Video Cue label, in order; index = segment ordinal. */
    TArray<FString> SegmentLabels;
    /** First row index of each segment ordinal. */
    TArray<int32> SegmentStartRows;
    TArray<FString> Speakers;
    TArray<FString> Warnings;
    FString SourcePath;

    /** RFC-4180 CSV: quoted cells may hold commas, quotes ("") and newlines. */
    static void ParseCsv(const FString& Text, TArray<TArray<FString>>& OutTable);

    /** Finds the header row (a cell "Light"), names the speaker columns from the row below it. */
    bool LoadFromCsvText(const FString& Text);
    bool LoadFromFile(const FString& Path);

    int32 SegmentStartRow(int32 SegmentOrdinal) const;
};

/**
 * Where we are in the script. Moves forward by itself only when the stage reaches a
 * new segment; otherwise the operator (Klara) steps it. It never steps back by itself.
 */
struct INFINITYSTAGE_API FInfinityScriptCursor
{
    int32 Row = 0;
    int32 LastSyncedSegment = INDEX_NONE;

    /** Next / previous row that has content. Return false at either end. */
    bool Next(const FInfinityCueSheet& Sheet);
    bool Prev(const FInfinityCueSheet& Sheet);
    /** The stage is in this segment ordinal: move up to its first row if behind; never back. */
    void SyncToSegment(const FInfinityCueSheet& Sheet, int32 SegmentOrdinal);
};

namespace InfinityStageCueSheet
{
/** Project default: Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv (console InfinityStage.CueSheet.Path overrides). */
INFINITYSTAGE_API FString ResolvePath();

/** "KLARA: Once upon a time ..." lines of a row, one per speaker. */
INFINITYSTAGE_API TArray<FString> DescribeLines(const FInfinityCueSheetRow& Row);

/** "LX: ... | SND: ... | DO: ... | CUE: ... | NOTE: ..." for a row; empty parts left out. */
INFINITYSTAGE_API FString DescribeActions(const FInfinityCueSheetRow& Row);

/** The next row after From that is a "standby" moment: a cue number, a Video Cue or a beat. */
INFINITYSTAGE_API int32 NextStandbyRow(const FInfinityCueSheet& Sheet, int32 From);
}

/** Holds the sheet and the script cursor for one game world (PIE or the show). */
UCLASS()
class INFINITYSTAGE_API UInfinityStageCueDirectorSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;

    /** Re-reads the CSV (F5 in the show viewport): Gary exports a new sheet mid-rehearsal. */
    bool Reload();

    void StepLine(int32 Delta);
    void SyncToSegment(int32 SegmentOrdinal) { Cursor.SyncToSegment(Sheet, SegmentOrdinal); }

    const FInfinityCueSheet& GetSheet() const { return Sheet; }
    const FInfinityScriptCursor& GetCursor() const { return Cursor; }

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    FInfinityCueSheet Sheet;
    FInfinityScriptCursor Cursor;
};
