#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "InfinityStageSurtitles.generated.h"

struct FCompositeFont;
struct FInfinityTransportSegment;
struct FSlateBrush;
class AInfinityStageShowRoot;
class STextBlock;
class SWidget;
class UWorld;

/**
 * Surtitles (Gary, 8 Oct: "text at centre top of screen, visible serifed font,
 * timecoded"; "should integrate as part of cue system"). First use: what the S5
 * mountains say to each other in rumbles.
 *
 * The text is a sheet, read like the Cue Director's cue sheet: a CSV exported
 * from Gary's Google Sheet (a "Surtitles" tab), one row per line:
 *
 *   Segment, In, Out, Speaker, Text, Notes
 *   S5,      1:14.0, 1:25.0, West, "We have been here a while.",
 *
 * - Segment names the digital segment the line belongs to: S<n> (n-th Scene),
 *   P<n> (n-th Passage), I<n> (n-th Interaction), counted in show order the same
 *   way as the Cue Director's use_video = S<n>; or a Show cue label ("Opening").
 *   Blank carries down from the row above.
 * - In / Out are times from the START of that segment, so lines move with any
 *   retime or reorder. Seconds ("74.5"), m:ss.s, h:mm:ss.s, or hh:mm:ss:ff
 *   (frames at 25 fps). Blank Out holds the line until the next line in the same
 *   segment, or the segment's end.
 * - Text may hold line breaks (a quoted multi-line cell).
 *
 * Nothing is written to the Show or the level. The file is re-read when it
 * changes on disk (and on F5 with the cue sheet), so text can be fixed mid-rehearsal.
 *
 * What is shown is a pure function of the Master playhead: seeks, reverse, holds
 * and the Scene video fallbacks (which follow the same playhead) all agree. It is
 * a viewport overlay in game worlds (PIE and the show), not rendered into MRQ
 * output, so editing a word never means re-rendering a video.
 *
 * Console: InfinityStage.Surtitles 1 show / 0 blackout (key T in the show viewport);
 * .Path, .Font, .Size, .Top, .BarOpacity, .Fade, .Speakers for rehearsal tuning;
 * InfinityStage.Surtitles.Dump logs every line at its absolute Master time for proofing.
 */
struct INFINITYSTAGE_API FInfinitySurtitleLine
{
    /** 1-based row in the CSV, for "see the sheet, row 12". */
    int32 SourceRow = 0;
    /** As written (after carry-down): "S5", "P2", "I1" or a cue label. */
    FString Segment;
    double InSeconds = 0.0;
    /** Negative: hold until the next line in the segment, or the segment end. */
    double OutSeconds = -1.0;
    FString Speaker;
    FString Text;
};

struct INFINITYSTAGE_API FInfinitySurtitleScript
{
    /** In sheet order. */
    TArray<FInfinitySurtitleLine> Lines;
    TArray<FString> Warnings;
    FString SourcePath;

    /** Finds the header row (a cell "Segment"); columns are found by name. */
    bool LoadFromCsvText(const FString& Text);
    bool LoadFromFile(const FString& Path);
};

/** The line to show this frame (LineIndex INDEX_NONE: nothing). */
struct INFINITYSTAGE_API FInfinitySurtitleShown
{
    int32 LineIndex = INDEX_NONE;
    int32 SegmentIndex = INDEX_NONE;
    float Opacity = 0.0f;
};

namespace InfinityStageSurtitles
{
/** Seconds, m:ss.s, h:mm:ss.s, or hh:mm:ss:ff (four fields: last is frames at Fps). */
INFINITYSTAGE_API bool ParseTime(const FString& Text, double Fps, double& OutSeconds);

/** "m:ss.ss". */
INFINITYSTAGE_API FString FormatTime(double Seconds);

/** "S3" / "P2" / "I1" for a segment: its kind letter and 1-based ordinal among that kind. */
INFINITYSTAGE_API FString SegmentCode(const TArray<FInfinityTransportSegment>& Segments, int32 SegmentIndex);

/** True when a line's Segment names this segment (code or cue label, case-insensitive). */
INFINITYSTAGE_API bool LineMatchesSegment(const FInfinitySurtitleLine& Line, const TArray<FInfinityTransportSegment>& Segments, int32 SegmentIndex);

/** First segment a key names, or INDEX_NONE. */
INFINITYSTAGE_API int32 ResolveSegment(const FString& Key, const TArray<FInfinityTransportSegment>& Segments);

/** The segment's length in seconds. */
INFINITYSTAGE_API double SegmentSeconds(const FInfinityTransportSegment& Segment, double TicksPerSecond);

/** A line's effective out time in its segment (blank Out resolved), in segment seconds. */
INFINITYSTAGE_API double EffectiveOut(const FInfinitySurtitleScript& Script, int32 LineIndex, const TArray<FInfinityTransportSegment>& Segments, int32 SegmentIndex, double TicksPerSecond);

/**
 * What to show at a Master frame. Of the lines in the segment under the playhead
 * that have started, the latest-starting one wins while it is before its out.
 * Opacity ramps over FadeSeconds at both ends (0: hard cuts).
 */
INFINITYSTAGE_API FInfinitySurtitleShown Evaluate(
    const FInfinitySurtitleScript& Script,
    const TArray<FInfinityTransportSegment>& Segments,
    int64 MasterFrame,
    double TicksPerSecond,
    double FadeSeconds);

/** Content/InfinityStage/CueSheet/Puss_Surtitles.csv (console InfinityStage.Surtitles.Path overrides). */
INFINITYSTAGE_API FString ResolvePath();

/** Operator blackout: flips InfinityStage.Surtitles. */
INFINITYSTAGE_API void ToggleBlackout();
}

/** Loads the surtitle sheet and draws the current line over the show, per game world. */
UCLASS()
class INFINITYSTAGE_API UInfinityStageSurtitleSubsystem final : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UInfinityStageSurtitleSubsystem, STATGROUP_Tickables); }

    /** Re-reads the sheet. */
    bool Reload();

    /** Logs every line with its absolute Master time (INFINITY_SURTITLE rows) for proofing. */
    void Dump();

    const FInfinitySurtitleScript& GetScript() const { return Script; }

private:
    void EnsureOverlay();
    void ApplyStyle();
    AInfinityStageShowRoot* FindRoot();

    FInfinitySurtitleScript Script;
    FDateTime LoadedStamp;
    double NextStampCheck = 0.0;

    TWeakObjectPtr<AInfinityStageShowRoot> Root;
    TSharedPtr<SWidget> Overlay;
    TSharedPtr<SWidget> Bar;
    TSharedPtr<STextBlock> TextBlock;
    TSharedPtr<STextBlock> SpeakerBlock;
    TSharedPtr<const FCompositeFont> Font;
    TSharedPtr<FSlateBrush> BarBrush;
    FString StyleKey;
    int32 ShownLine = INDEX_NONE;
    bool bOverlayAdded = false;
};
