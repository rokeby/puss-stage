#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "InfinityStageTypes.h"
#include "InfinityStageDirectorHud.generated.h"

class AInfinityStageShowRoot;
class APlayerController;
class UCanvas;
struct FInfinityGoCue;

/**
 * Director's HUD (Gary, 6 Oct: "start showing in the bottom row of the screen what
 * bay we're in so I can direct more easily"; "current cue on the bottom of screen
 * HUD"; "where we are in cues and sequences/subsequence").
 *
 * A bottom-of-screen text row in PIE: segment (cue) index and label, its kind,
 * the Passage bay, the last/next GO, Master time and time in the segment, and the
 * nested shot/sub-sequence under the playhead.
 *
 * Console: InfinityStage.DirectorHud  -1 auto (default: on in PIE, off in a
 * packaged/standalone game), 0 off, 1 on. Key H in the show viewport toggles it.
 *
 * Cost: per drawn frame it reads the transport's playhead, scans the segment
 * table and the GO list, and reads the live rig's cached camera distance. The
 * Show is compiled only when the segment under the playhead changes.
 */

/** One nested shot / sub-sequence span, in absolute Master frames. */
struct INFINITYSTAGE_API FInfinityHudShotSpan
{
    FFrameNumber StartFrame = 0;
    FFrameNumber EndFrame = 0;
    FString Name;
};

/** Everything the HUD prints, gathered without drawing (unit-testable). */
struct INFINITYSTAGE_API FInfinityDirectorHudState
{
    bool bHasShow = false;
    int32 SegmentIndex = INDEX_NONE;
    int32 SegmentCount = 0;
    FString SegmentLabel;
    EInfinityCueType SegmentType = EInfinityCueType::WingPair;
    /** 1-based nearest wing station in a Passage; 0 when unknown / not a Passage. */
    int32 Bay = 0;
    int32 BayCount = 0;
    double MasterSeconds = 0.0;
    double SegmentSeconds = 0.0;
    double SegmentLengthSeconds = 0.0;
    FString LastGo;
    FString NextGo;
    FString SequenceName;
    FString ShotName;
    bool bPlaying = false;
    bool bReversed = false;
    float PlayRate = 1.0f;
    bool bHold = false;
};

namespace InfinityStageDirectorHud
{
/** -1 auto: PIE yes, Game no. 0 never. 1 always (game worlds only). */
INFINITYSTAGE_API bool IsEnabledFor(int32 ConsoleValue, EWorldType::Type WorldType);

/** The effective switch for a world, read from the console variable. */
INFINITYSTAGE_API bool IsEnabledForWorld(const UWorld* World);

/** H cycles: off -> strip -> strip + script panel -> off (Gary, 7 Oct: "press H twice to see script"). */
INFINITYSTAGE_API void Toggle(const UWorld* World);

/** The pure cycle behind Toggle. */
INFINITYSTAGE_API void NextMode(bool bStripOn, bool bScriptOn, bool& bOutStripOn, bool& bOutScriptOn);

/** The script panel is shown (only ever with the strip). */
INFINITYSTAGE_API bool IsScriptPanelEnabledForWorld(const UWorld* World);

/** Greedy word wrap to MaxChars per line (no measuring: the panel uses a fixed-width budget). */
INFINITYSTAGE_API TArray<FString> WrapText(const FString& Text, int32 MaxChars);

/** 1-based index of the station nearest DistanceCm (ties go to the later one); 0 when empty. */
INFINITYSTAGE_API int32 NearestBay(const TArray<double>& SortedStationDistancesCm, double DistanceCm);

/** "Passage", "Scene" or "Interaction". */
INFINITYSTAGE_API const TCHAR* KindLabel(EInfinityCueType Type);

/** "m:ss.s" (negative clamps to 0). */
INFINITYSTAGE_API FString FormatClock(double Seconds);

/** The innermost-listed span containing Frame (last match wins), or empty. */
INFINITYSTAGE_API FString ShotAtFrame(const TArray<FInfinityHudShotSpan>& Spans, FFrameNumber Frame);

/** Index of the last GO at or before Frame within SegmentIndex, and the first after Frame (any segment). */
INFINITYSTAGE_API void FindGoAround(
    const TArray<FInfinityGoCue>& Cues, int32 SegmentIndex, FFrameNumber Frame, int32& OutLast, int32& OutNext);

/** The two printed lines, top then bottom. */
INFINITYSTAGE_API void FormatLines(const FInfinityDirectorHudState& State, FString& OutTop, FString& OutBottom);
}

UCLASS()
class INFINITYSTAGE_API UInfinityStageDirectorHudSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    /** Gathers this frame's state (no drawing). Public for tests and the seam diagnostic. */
    FInfinityDirectorHudState GatherState();

    /** TEST SEAM: use this root instead of searching the world. */
    void SetShowRootForTests(AInfinityStageShowRoot* Root);   // out of line: the root type is only forward-declared here

    /** TEST SEAM: how many times the per-segment cache was rebuilt. */
    int32 GetSegmentCacheBuildsForTests() const { return SegmentCacheBuilds; }

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    void Draw(UCanvas* Canvas, APlayerController* PlayerController);
    void DrawScriptPanel(UCanvas* Canvas, UFont* Font, float BottomOfPanel, const FInfinityDirectorHudState& State);
    AInfinityStageShowRoot* FindShowRoot();
    void RebuildSegmentCache(const AInfinityStageShowRoot& Root, int32 SegmentIndex);

    FDelegateHandle DrawHandle;
    TWeakObjectPtr<AInfinityStageShowRoot> CachedShowRoot;
    double LastRootSearchRealSeconds = -1000.0;

    /** Per-segment cache: rebuilt only when the segment (or the table) changes. */
    int32 CachedSegmentIndex = INDEX_NONE;
    int32 CachedSegmentCount = -1;
    FGuid CachedSegmentGuid;
    TArray<double> CachedStationDistancesCm;
    TArray<FInfinityHudShotSpan> CachedShotSpans;
    FString CachedSequenceName;
    int32 SegmentCacheBuilds = 0;
};
