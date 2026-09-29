#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageCelestialRig.generated.h"

class ADirectionalLight;
class AExponentialHeightFog;
class ASkyLight;
class UInfinityStageShowAsset;
class USceneComponent;
class UStaticMeshComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(
    FInfinityCelestialPhaseEvaluated,
    double, NormalizedPhase,
    float, DaylightAmount,
    float, StarsAmount);

/**
 * One show-wide, Sequencer-evaluated sun/moon/stars rig. It deliberately has no
 * private Tick clock: the Master frame and Passage cycle-rate data are the only
 * time authority, which keeps playback, reverse and scrubbing deterministic.
 */
UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageCelestialRig : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageCelestialRig();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Celestial")
    TObjectPtr<USceneComponent> SceneRoot;

    /** Built-in theatrical star field. It is hidden during daylight and rotates
     * through the night; replace its mesh/material for an art-directed sky. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Celestial")
    TObjectPtr<UStaticMeshComponent> StarsDome;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    TObjectPtr<ADirectionalLight> SunLightActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    TObjectPtr<ADirectionalLight> MoonLightActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    TObjectPtr<ASkyLight> SkyLightActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    TObjectPtr<AExponentialHeightFog> HeightFogActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    bool bAutoBindActorsByTag = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    FName SunActorTag = TEXT("InfinityStage.CelestialSun");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    FName MoonActorTag = TEXT("InfinityStage.CelestialMoon");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    FName SkyLightActorTag = TEXT("InfinityStage.CelestialSkyLight");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Bindings")
    FName HeightFogActorTag = TEXT("InfinityStage.CelestialFog");

    /** Show-start time of day. 0 midnight, 0.25 sunrise, 0.5 noon, 0.75 sunset. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Timing")
    double InitialPhaseCycles = 0.25;

    /**
     * Keeps ordinary level editing at an artist-chosen working light instead of
     * retaining the last Master frame that happened to be scrubbed. This is
     * ignored in PIE, game playback and rendering, where the Master remains the
     * sole time-of-day authority.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Editor Preview",
        meta = (DisplayName = "Use Manual Editor Lighting"))
    bool bUseManualEditorLighting = true;

    /**
     * Also apply the manual hour in PIE, game playback and rendering, so the show
     * runs at one fixed time of day and no Passage day/night cycle can move it.
     * Requires Use Manual Editor Lighting. Off (the default) keeps the Master as
     * the sole time-of-day authority in game worlds; the production Show turns
     * this on because the enclosed stage runs at one fixed night.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Editor Preview",
        meta = (DisplayName = "Manual Lighting Also In Game", EditCondition = "bUseManualEditorLighting"))
    bool bApplyManualLightingInGame = false;

    /**
     * The stage is an enclosed machine: no exterior light may reach it. Every
     * directional light, sky light, sky atmosphere, height fog, volumetric cloud
     * or sky-sphere mesh that is not one of this rig's own bound actors is
     * silenced (no world contribution, hidden in game), including inside Level
     * Instances brought in with scene content. Nothing is modified on disk.
     *
     * Event-driven, not per frame: one walk of the world at BeginPlay (and on the
     * first lighting apply in the editor), a check of each actor as it is
     * spawned (Sequencer spawnables), a walk whenever a level is added (Level
     * Instances, streamed scenes), and a throttled safety net at most every
     * ForeignLightingRecheckSeconds while the Master applies phases, which
     * re-hides only the actors already silenced (a sequence can re-show one)
     * without walking the world again. Each actor is logged once, when first
     * silenced.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting",
        meta = (DisplayName = "Suppress Foreign Environment Lighting"))
    bool bSuppressForeignEnvironmentLighting = true;

    /** The safety-net interval for re-hiding already-silenced actors during phase applies; 0 turns the safety net off. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting",
        meta = (ClampMin = "0.0", Units = "s", EditCondition = "bSuppressForeignEnvironmentLighting"))
    float ForeignLightingRecheckSeconds = 2.0f;

    /** Walk the whole world now and silence exterior lighting actors that do not belong to this rig. Returns the number of foreign actors found. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Infinity Stage|Celestial|Lighting")
    int32 SuppressForeignEnvironmentLighting();

    /** How many full-world walks the suppression has made: for measurement and tests. */
    UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Infinity Stage|Celestial|Lighting")
    int32 ForeignLightingWalkCount = 0;

    /** How many safety-net re-hides of the already-silenced actors have run: for measurement and tests. */
    UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Infinity Stage|Celestial|Lighting")
    int32 ForeignLightingReapplyCount = 0;

    /** How many distinct actors have been silenced, and so logged, once each. */
    UPROPERTY(Transient, VisibleInstanceOnly, BlueprintReadOnly, Category = "Infinity Stage|Celestial|Lighting")
    int32 ForeignLightingSuppressedCount = 0;

    /** Editor-only working time using an ordinary 24-hour clock. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Editor Preview",
        meta = (ClampMin = "0.0", ClampMax = "24.0", UIMin = "0.0", UIMax = "24.0",
            DisplayName = "Editor Preview Time (0–24 Hours)"))
    double EditorPreviewTimeHours = 12.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting", meta = (Units = "deg"))
    float SunAzimuthDegrees = 225.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting", meta = (ClampMin = "0.0", Units = "lux"))
    float MaximumSunIntensity = 5.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting", meta = (ClampMin = "0.0", Units = "lux"))
    float MaximumMoonIntensity = 0.20f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor HorizonSunColor = FLinearColor(1.0f, 0.45f, 0.16f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor NoonSunColor = FLinearColor(1.0f, 0.92f, 0.72f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor MoonColor = FLinearColor(0.34f, 0.46f, 0.72f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting", meta = (ClampMin = "0.0"))
    float DaySkyLightIntensity = 0.32f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting", meta = (ClampMin = "0.0"))
    float NightSkyLightIntensity = 0.035f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor DaySkyLightColor = FLinearColor(0.72f, 0.82f, 1.0f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor NightSkyLightColor = FLinearColor(0.055f, 0.075f, 0.16f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor DayFogColor = FLinearColor(0.26f, 0.34f, 0.48f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting")
    FLinearColor NightFogColor = FLinearColor(0.015f, 0.025f, 0.065f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Stars", meta = (ClampMin = "0.0"))
    float MaximumStarsBrightness = 2.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Stars")
    bool bShowBuiltInStars = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Celestial|Lighting",
        meta = (ClampMin = "0.001", ClampMax = "1.0"))
    float TwilightAltitudeBand = 0.12f;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Celestial|State")
    double CurrentNormalizedPhase = 0.25;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Celestial|State")
    float CurrentDaylightAmount = 0.5f;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Celestial|State")
    float CurrentStarsAmount = 0.5f;

    UPROPERTY(BlueprintAssignable, Category = "Infinity Stage|Celestial")
    FInfinityCelestialPhaseEvaluated OnCelestialPhaseEvaluated;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Celestial")
    bool EvaluateAtMasterFrame(UInfinityStageShowAsset* ShowAsset, FGuid PassageGuid, FFrameNumber MasterFrame);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Celestial")
    void ApplyCyclePhase(double NormalizedPhase);

    /** Apply the manually authored editor working light immediately. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Infinity Stage|Celestial|Editor Preview")
    void ApplyEditorPreviewLighting();

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Celestial|Editor Preview")
    void SetEditorPreviewTimeHours(double TimeHours);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Celestial|Editor Preview")
    void SetUseManualEditorLighting(bool bEnabled);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Celestial|Editor Preview")
    bool IsManualEditorLightingActive() const;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Celestial")
    void ResolveEnvironmentBindings();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void OnConstruction(const FTransform& Transform) override;

private:
    void HandleLevelAddedToWorld(ULevel* Level, UWorld* World);
    void HandleActorSpawned(AActor* Actor);
    /** Silence one actor if it carries exterior lighting and is not the rig's own. */
    bool SuppressIfForeign(AActor* Actor);
    /** The safety net: re-hide the actors already silenced, never walking the world. */
    int32 ReapplyForeignSuppression();
    FDelegateHandle LevelAddedHandle;
    FDelegateHandle ActorSpawnedHandle;
    TSet<TWeakObjectPtr<AActor>> SuppressedForeignActors;
    double LastForeignLightingWalkSeconds = -1.0;
    double LastForeignLightingCheckSeconds = -1.0;

protected:
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif
};
