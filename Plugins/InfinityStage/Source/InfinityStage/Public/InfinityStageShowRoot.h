#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageTypes.h"
#include "MovieSceneSequencePlaybackSettings.h"
#include "InfinityStageShowRoot.generated.h"

class ALevelSequenceActor;
class AInfinityStageCurtainRig;
class UAudioComponent;
class UInfinityStageShowAsset;
class UInfinityStageTransportController;
class ULevelSequence;
class ULevelSequencePlayer;
class UMaterialParameterCollection;
class USoundBase;

UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageShowRoot : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageShowRoot();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<UInfinityStageShowAsset> ShowAsset;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<ULevelSequence> MasterSequence;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FMovieSceneSequencePlaybackSettings PlaybackSettings;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    bool bPrepareOnBeginPlay = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<UInfinityStageTransportController> Transport;

    /**
     * Live operator override of authored camera ownership.
     *
     * Transient on purpose: a performance decision to take the camera back from
     * the dog must never silently rewrite the score. Forcing Timeline wins
     * everywhere; forcing a Dog mode does not apply inside Sequence cues (the
     * Opening, the Interactions, the Closing), which keep their authored owner.
     */
    UPROPERTY(Transient, BlueprintReadWrite, Category = "Infinity Stage|Camera")
    bool bOverrideCameraOwner = false;

    UPROPERTY(Transient, BlueprintReadWrite, Category = "Infinity Stage|Camera")
    EInfinityCameraOwner CameraOwnerOverride = EInfinityCameraOwner::Timeline;

    /**
     * Authored owner for the segment containing a Master frame, or the live
     * override when one is active.
     *
     * External input plugins should consult this rather than carrying their own
     * per-actor enable flag, so ownership stays part of the Show and one
     * telemetry receiver can serve every camera.
     */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Camera")
    EInfinityCameraOwner GetCameraOwnerAtFrame(FFrameNumber MasterFrame) const;

    /** Owner for wherever the transport currently is. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Camera")
    EInfinityCameraOwner GetCurrentCameraOwner() const;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<ULevelSequencePlayer> SequencePlayer;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<ALevelSequenceActor> SequenceActor;

    /** Optional artist subclass used only by backwards-compatible automatic curtain cues. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Curtain")
    TSubclassOf<AInfinityStageCurtainRig> CurtainRigClass;

    UPROPERTY(Transient, VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Curtain")
    TObjectPtr<AInfinityStageCurtainRig> CurtainRig;

    /** Read-only deterministic curtain evaluation used by runtime and rehearsal tests. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Curtain")
    bool GetCurtainStateAtFrame(FFrameNumber MasterFrame, float& OutProgress) const;

    /** Cameron's whole-show room tone. Runtime-owned: never follows the Master playhead. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Room Tone")
    TObjectPtr<USoundBase> RoomToneSound;

    /** Job 190's MPC; Weird optionally fades the room tone by the configured dip. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Room Tone")
    TObjectPtr<UMaterialParameterCollection> RoomToneWarpParameters;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Room Tone")
    FName RoomToneWarpParameter = TEXT("Weird");

    /** The single non-spatial runtime player, owned by the Show Root. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Transient, Category = "Infinity Stage|Room Tone")
    TObjectPtr<UAudioComponent> RoomToneAudio;

    /**
     * Pure gain rule for tests. S6DipDb is an additional negative offset:
     * -18 dB base plus the default -12 dB dip reaches -30 dB at Weird=1.
     */
    static float ComputeRoomToneGainDb(
        float BaseDb,
        float S6DipDb,
        float Weird,
        bool bEnableS6Dip);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool PrepareShow();

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void Tick(float DeltaSeconds) override;

private:
    bool ShouldUseLegacyAutomaticCurtain() const;
    void EnsureCurtainRig();
    void UpdateCurtainForCurrentFrame();
    void UpdateRoomToneMix();
};
