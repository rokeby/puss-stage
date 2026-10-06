#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "UObject/ObjectKey.h"
#include "InfinityStageLightEvents.generated.h"

class AActor;
class AInfinityStageShowRoot;
class ULocalLightComponent;

/**
 * Light tuning aid (Gary, 5 Oct: "an extremely useful small update for tuning
 * lights is if screen text printed the light that was currently coming on").
 *
 * Console: InfinityStage.ShowLightEvents  0 off (default), 1 screen + log, 2 log only.
 *
 * Lights come on by many paths: Light Drama strikes, Sequencer Intensity keys on
 * level lights (Opening FOH, hangar rises, Choreos), the Strobe and the Sweep Light,
 * Effect-source flicker, and visibility toggles. Rather than hook each one, a
 * per-world tracker polls every local light in the game world once a frame and
 * reports an OFF->ON crossing of its effective intensity, with hysteresis. Polling
 * sees every path the same way, including Sequencer keys.
 */

/** What one poll of one light produced. */
enum class EInfinityLightEdge : uint8
{
    None,
    /** A fresh OFF->ON crossing: printed. */
    On,
    /** An OFF->ON crossing inside the repeat window of the previous one: counted, not printed anew. */
    Repeat,
    /** An ON->OFF crossing. */
    Off
};

struct INFINITYSTAGE_API FInfinityLightEdgeThresholds
{
    /** The light counts as ON once its effective intensity reaches this (in its own units). */
    double OnLevel = 1.0;
    /** ...and as OFF again only below this. Between the two nothing changes (hysteresis). */
    double OffLevel = 0.25;
    /** An ON within this many seconds of the light's previous ON is a repeat (strobe, flicker). */
    double RepeatWindowSeconds = 8.0;
};

struct INFINITYSTAGE_API FInfinityLightEdgeState
{
    bool bOn = false;
    /** ON crossings in the current run, the first included. 0 before the first. */
    int32 RunCount = 0;
    double LastOnSeconds = 0.0;
};

namespace InfinityStageLightEvents
{
/** Pure: advances one light's state by one sample and says what crossed. */
INFINITYSTAGE_API EInfinityLightEdge StepEdge(
    FInfinityLightEdgeState& State,
    double EffectiveLevel,
    double NowSeconds,
    const FInfinityLightEdgeThresholds& Thresholds);

/** Seeds a state silently from the current level (the first scan: no burst of prints at PIE start). */
INFINITYSTAGE_API void SeedEdge(FInfinityLightEdgeState& State, double EffectiveLevel, const FInfinityLightEdgeThresholds& Thresholds);

/** Intensity as the viewer gets it: 0 unless registered, visible, not hidden in game and affecting the world. */
INFINITYSTAGE_API double EffectiveLevel(const ULocalLightComponent& Light);

/** "cd", "lm", "nits", "EV" or "" (unitless). */
INFINITYSTAGE_API const TCHAR* UnitsLabel(const ULocalLightComponent& Light);

/**
 * The name a person tuning lights knows this light by: the Show attachment label
 * for a materialised Show lamp (resolved through its identity tag, so it is the
 * Show's label even where the actor label differs), else the actor label. When
 * the actor carries several local lights, the component name is appended.
 */
INFINITYSTAGE_API FString ResolveLabel(const ULocalLightComponent& Light);

/** The console level, 0..2. */
INFINITYSTAGE_API int32 GetLevel();
}

/**
 * Polls the game world's local lights and reports lights coming on. Exists only in
 * Game and PIE worlds, never in the editor world or a preview world, and does no
 * work at all while InfinityStage.ShowLightEvents is 0.
 */
UCLASS()
class INFINITYSTAGE_API UInfinityStageLightEventSubsystem : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    virtual void Tick(float DeltaTime) override;
    virtual bool IsTickable() const override;
    virtual TStatId GetStatId() const override;

    /** True for the world types the tracker runs in (Game, PIE). */
    static bool SupportsWorldType(EWorldType::Type WorldType);

    /** TEST SEAM: one tick at an explicit real-time clock, through the same cvar gate as Tick. */
    void TickAtForTests(double RealSeconds) { TickAt(RealSeconds); }

    /** TEST SEAM: receives every emitted line; bScreen says whether it went to the screen. */
    TFunction<void(const FString& Line, bool bScreen)> LineSinkForTests;

    /** TEST SEAM: how many polls ran and how many lights they sampled. */
    int64 GetPollCountForTests() const { return PollCount; }
    int64 GetLightsSampledForTests() const { return LightsSampled; }
    int32 GetTrackedLightCountForTests() const { return Tracked.Num(); }

    /** TEST SEAM: overrides the thresholds (the cvar values otherwise). */
    TOptional<FInfinityLightEdgeThresholds> ThresholdsForTests;

protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
    struct FTrackedLight
    {
        TWeakObjectPtr<ULocalLightComponent> Light;
        FString Label;
        FInfinityLightEdgeState Edge;
        /** Rolling on-screen slot this light last wrote, or INDEX_NONE. */
        int32 ScreenSlot = INDEX_NONE;
        /** The ON line is logged once the rise has settled, with the level it rose to. */
        bool bLogPending = false;
        double PendingUntilSeconds = 0.0;
        double PeakLevel = 0.0;
        float PeakIntensity = 0.0f;
        double OnMasterSeconds = 0.0;
        FString OnSegment;
        double LastRepeatLogSeconds = 0.0;
    };

    void TickAt(double RealSeconds);
    void Poll(double RealSeconds, int32 Level);
    void StartSweep(bool bBaseline);
    void ContinueSweep(int32 ActorBudget, const FInfinityLightEdgeThresholds& Thresholds);
    void AddLight(ULocalLightComponent& Light, bool bBaseline, const FInfinityLightEdgeThresholds& Thresholds);
    void HandleActorSpawned(AActor* Actor);
    FInfinityLightEdgeThresholds GetThresholds() const;
    AInfinityStageShowRoot* FindShowRoot();
    void ReadClock(double& OutMasterSeconds, bool& bOutMasterClock, int32& OutSegmentIndex, FString& OutSegment);
    void EmitScreen(FTrackedLight& Entry, const FString& Line, bool bAllowScreen);
    void EmitLog(const FString& Line);

    TArray<FTrackedLight> Tracked;
    TMap<FObjectKey, int32> TrackedIndex;
    /** Which light owns each rolling on-screen line. */
    TArray<FObjectKey> SlotOwners;
    TWeakObjectPtr<AInfinityStageShowRoot> CachedShowRoot;
    FDelegateHandle SpawnHandle;
    bool bScanned = false;
    bool bSweepActive = false;
    bool bSweepBaseline = false;
    int32 SweepLevelIndex = 0;
    int32 SweepActorIndex = 0;
    double LastRescanSeconds = 0.0;
    uint64 LastPollFrame = 0;
    int32 LastSegmentIndex = INDEX_NONE;
    int32 NextScreenSlot = 0;
    int32 PollCursor = 0;
    int64 PollCount = 0;
    int64 LightsSampled = 0;
};
