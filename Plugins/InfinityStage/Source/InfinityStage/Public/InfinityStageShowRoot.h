#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageTypes.h"
#include "MovieSceneSequencePlaybackSettings.h"
#include "InfinityStageShowRoot.generated.h"

class ALevelSequenceActor;
class AInfinityStageCurtainRig;
class UInfinityStageShowAsset;
class UInfinityStageTransportController;
class ULevelSequence;
class ULevelSequencePlayer;

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
     * the dog must never silently rewrite the score.
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
};
