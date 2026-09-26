#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageEffectTypes.h"
#include "InfinityStageTypes.h"
#include "InfinityStageEffectSource.generated.h"

class AInfinityStageCameraRig;
class AInfinityStagePassageActor;
class UInstancedStaticMeshComponent;
class ULightComponent;
class ULocalFogVolumeComponent;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;

/**
 * A practical weather-making device in the stage machine: a smoke pot, a kettle,
 * a fire basket, a wing on fire, or motes adrift in a bay.
 *
 * Spawned and owned by the Passage from an Effect attachment, exactly as a Light
 * attachment spawns a native light. Blueprint subclasses carry the apparatus
 * mesh and the Niagara system; this class finds those systems as
 * UFXSystemComponents and pushes the Show-owned settings to them as User
 * parameters, so the runtime module needs no Niagara dependency. The native
 * class alone is a greybox that already places, feeds its medium and burns.
 *
 * Anything that drives another actor — a wing's char, a rig light's flicker —
 * runs only in game worlds (PIE and Movie Render Queue), whose packages are never
 * saved. The editor world keeps zero dirty packages at rest.
 */
UCLASS(Blueprintable, BlueprintType)
class INFINITYSTAGE_API AInfinityStageEffectSource : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageEffectSource();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Effect")
    TObjectPtr<USceneComponent> SceneRoot;

    /** Follows a panel-anchored effect's live wing through its inward travel.
     * Everything visible hangs from here. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Effect")
    TObjectPtr<USceneComponent> TrackingRoot;

    /** Greybox apparatus. Blueprint subclasses replace the mesh. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Effect")
    TObjectPtr<UStaticMeshComponent> Apparatus;

    /** The medium this source leaves in its bay. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Effect")
    TObjectPtr<ULocalFogVolumeComponent> Medium;

    /** Show-owned settings. Editing them here writes them back to the Show. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect")
    FInfinityStageEffectSettings Settings;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Effect|Identity")
    FGuid CueGuid;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Effect|Identity")
    FGuid AttachmentGuid;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Effect|Identity")
    EInfinityAttachmentAnchor Anchor = EInfinityAttachmentAnchor::Station;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Effect|State")
    bool bEffectActive = false;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Effect|State")
    float CurrentBurnProgress = 0.0f;

    /** Default apparatus class for a type: its Blueprint under /Game/Scenes/Effects
     * when that exists, otherwise this native greybox. Never null. */
    static UClass* ResolveDefaultClass(const FInfinityStageEffectSettings& InSettings);

    /**
     * Materialization hook, called after the spawned actor is parented to its
     * Passage. An effect source takes its identity and settings; any other actor
     * class still receives the settings on every FX system it carries.
     * Returns false only when the actor has nothing the settings can drive.
     */
    static bool ApplyAttachment(AActor& Spawned, const FGuid& InCueGuid, const FInfinityCueAttachment& Attachment);

    /** Pushes the Show-owned values to every FX system on the actor. */
    static int32 PushSystemParameters(AActor& Actor, const FInfinityStageEffectSettings& InSettings);

    /** 0 while the wing is at least StartAheadCm ahead of the camera, rising to 1
     * after SpanCm more camera travel. Pure, so tests and the tick agree. */
    static float ComputeBurnProgress(double WingAheadOfCameraCm, float StartAheadCm, float SpanCm);

    /** Soft-edged pump gate, 0..1. A zero period pumps steadily. */
    static float ComputePump(double TimeSeconds, float PeriodSeconds, float Duty, float InPhase01);

    /** Stable 0..1 phase from identity, so replicated pots do not pump in unison
     * and a replay pumps exactly as before. */
    static float ComputePhase(const FGuid& InCueGuid, const FGuid& InAttachmentGuid);

    /** Flame flicker in -1..1 from three incommensurate sines. */
    static float ComputeFlicker(double TimeSeconds, float InPhase01);

    /**
     * The wing master's mean burn front in panel-local cm: the ignition point on
     * the panel's mid-plane (X = 0) and the front radius at this progress, by the
     * contract in InfinityStageWingBurn. False while the UV mapping is unmeasured.
     */
    static bool ComputeBurnFront(
        const FInfinityStageEffectSettings& InSettings,
        float Progress,
        FVector& OutIgnitionLocal,
        float& OutRadiusCm);

    /** Re-applies Settings to this actor's own components and FX systems. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Effects")
    void ApplySettings();

    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override;
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& Event) override;
#endif

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    AInfinityStagePassageActor* GetOwningPassage() const;

    /** Resolves the wing panel and route position this effect is anchored to. */
    void BindAnchor();
    void BindLinkedLight();
    /** Gives a Wing Burn's FX systems the panel's geometry: bounds for its
     * thickness, and the UV square and ignition point for the front. */
    void PushBurnGeometry(const UStaticMesh& PanelMesh);
    void TrackAnchor();
    void SetEffectActive(bool bNewActive);
    bool IsWithinRenderedViewRadius() const;
    bool ResolveShowCameraRouteDistance(double& OutRouteDistanceCm) const;
    void UpdateWingBurn(bool bDriveWing);
    void UpdateLinkedLight(double TimeSeconds);
    void RestoreLinkedLight();
#if WITH_EDITOR
    void WriteSettingsToShow(const FPropertyChangedEvent& Event);
#endif

    TWeakObjectPtr<UInstancedStaticMeshComponent> PanelComponent;
    int32 PanelInstanceIndex = INDEX_NONE;
    /** The panel's rest pose at materialization, which is what the actor was
     * placed against. Tracking re-applies the actor's current offset from it to
     * the live panel, so a drag in the viewport and the wing's travel both hold. */
    FTransform PanelBaseWorld = FTransform::Identity;
    double AnchorRouteDistanceCm = 0.0;
    bool bHaveAnchorRouteDistance = false;

    TWeakObjectPtr<ULightComponent> LinkedLight;
    float LinkedLightBaseIntensity = 0.0f;
    /** The linked light has drama, which owns its intensity; stop looking for it. */
    bool bLinkedLightYieldedToDrama = false;
    double NextLinkedLightSearchSeconds = 0.0;

    mutable TWeakObjectPtr<AInfinityStageCameraRig> CachedRig;
    mutable double NextRigSearchSeconds = 0.0;

    float Phase01 = 0.0f;
    float LastWrittenBurnProgress = -1.0f;
    bool bActivityKnown = false;
    bool bWarnedNoCustomData = false;
};
