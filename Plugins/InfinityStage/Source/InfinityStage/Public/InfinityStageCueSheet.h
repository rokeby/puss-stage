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
    /** Cue Book `At`, in seconds from this row's segment start. False when blank/absent/invalid. */
    bool bHasAtTime = false;
    double AtSeconds = 0.0;
    /** Cue-specific physical direction; mode/treadmill are operator directions, never telemetry. */
    FString DogAction;
    FString DogMode;
    FString Treadmill;
    /** Last stated mode/treadmill at this row. */
    FString EffectiveDogMode;
    FString EffectiveTreadmill;
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

/**
 * How the show runs in performance (Gary, 7 Oct: "most things run on and not need
 * pressing go ... mostly after lights out after scenes"). A plain text file next to
 * the CSV, written by the Cue Desk's Cue Director panel; no Show or level write.
 *
 *   run_through = true
 *   stop_after = <segment GUID>   # Scene 1 ...   (the show stops at that segment's end; GO continues)
 *   hold_go = 10                  # GO markers that still hold during run-through
 */
struct INFINITYSTAGE_API FInfinityCueDirectorSettings
{
    bool bRunThrough = false;
    /** Gary, 9 Oct: live Passage breaths remain available in performance by default. */
    bool bAllowBreathInPerformance = true;
    TArray<FGuid> StopAfterSegments;
    TArray<FString> HoldGoNumbers;
    /** Scenes ("S3") that play their pre-rendered video instead of the live Scene. */
    TArray<FString> UseVideoScenes;
    /** Who plays a video Scene's sound: "ue" (the muxed file) or "desk" (Cameron's WAV; UE silent). */
    FString VideoAudio = TEXT("ue");

    /** Unknown keys and bad GUIDs become warnings; nothing is fatal. */
    void Parse(const FString& Text, TArray<FString>& OutWarnings);
    /** LabelOf names a segment for the trailing comment (readability only). */
    FString Serialize(TFunctionRef<FString(const FGuid&)> LabelOf) const;
};

namespace InfinityStageCueSheet
{
/** Content/InfinityStage/CueSheet/cue_director.txt (console InfinityStage.CueDirector.SettingsPath overrides). */
INFINITYSTAGE_API FString ResolveSettingsPath();

/** Project default: Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv (console InfinityStage.CueSheet.Path overrides). */
INFINITYSTAGE_API FString ResolvePath();

/** "KLARA: Once upon a time ..." lines of a row, one per speaker. */
INFINITYSTAGE_API TArray<FString> DescribeLines(const FInfinityCueSheetRow& Row);

/** "LX: ... | SND: ... | DO: ... | CUE: ... | NOTE: ..." for a row; empty parts left out. */
INFINITYSTAGE_API FString DescribeActions(const FInfinityCueSheetRow& Row);

/** "DOG: trotting | Walk / trot | treadmill on", using carried mode/treadmill. */
INFINITYSTAGE_API FString DescribeDogDirection(const FInfinityCueSheetRow& Row);

/** Next row after From that directly states a dog action, mode or treadmill change. */
INFINITYSTAGE_API int32 NextDogDirectionRow(const FInfinityCueSheet& Sheet, int32 From);

/** The next row after From that is a "standby" moment: a cue number, a Video Cue or a beat. */
INFINITYSTAGE_API int32 NextStandbyRow(const FInfinityCueSheet& Sheet, int32 From);
}

/** Holds the sheet and the script cursor for one game world (PIE or the show). */
UCLASS()
class INFINITYSTAGE_API UInfinityStageCueDirectorSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;

    /** Re-reads the CSV and the settings (F5 in the show viewport), and re-applies the settings. */
    bool Reload();

    /** Pushes the run-through settings onto this world's Show transport. Returns false if there is none yet. */
    bool ApplyToTransport();

    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    /** Applies the settings once the Show transport exists (it may appear after BeginPlay). */
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UInfinityStageCueDirectorSubsystem, STATGROUP_Tickables); }

    const FInfinityCueDirectorSettings& GetSettings() const { return Settings; }

    /** B in the show viewport: the rehearsal bar along the bottom (with a mouse cursor for its buttons). */
    void ToggleRehearsalBar();
    bool IsRehearsalBarShown() const { return RehearsalBarWidget.IsValid(); }
    virtual void Deinitialize() override;

    void StepLine(int32 Delta);
    void SyncToSegment(int32 SegmentOrdinal) { Cursor.SyncToSegment(Sheet, SegmentOrdinal); }

    const FInfinityCueSheet& GetSheet() const { return Sheet; }
    const FInfinityScriptCursor& GetCursor() const { return Cursor; }

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    FInfinityCueSheet Sheet;
    FInfinityScriptCursor Cursor;
    FInfinityCueDirectorSettings Settings;
    bool bSettingsApplied = false;
    TSharedPtr<class SWidget> RehearsalBarWidget;
};
