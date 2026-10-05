#pragma once

#include "Components/ActorComponent.h"
#include "InfinityStageBeeSwarmSimulation.h"

#include "InfinityStageBeeSwarmComponent.generated.h"

class UNiagaraComponent;

/**
 * Route-(c) bridge: deterministic CPU simulation feeds a thin Niagara renderer.
 * The component ticks after camera updates and is a prerequisite of Niagara.
 */
UCLASS(ClassGroup = (InfinityStage), meta = (BlueprintSpawnableComponent))
class INFINITYSTAGE_API UInfinityStageBeeSwarmComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UInfinityStageBeeSwarmComponent();

    virtual void OnRegister() override;
    virtual void BeginPlay() override;
    virtual void TickComponent(
        float DeltaTime,
        ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Bee Swarm")
    void SetNiagaraComponent(UNiagaraComponent* InNiagaraComponent);

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Bee Swarm")
    void NotifyCameraCut();

    /** Replaces the behaviour parameters and restarts the simulation next tick. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Bee Swarm")
    void SetParameters(const FInfinityStageBeeSwarmParameters& InParameters);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Bee Swarm")
    FInfinityStageBeeSwarmParameters GetParameters() const { return Parameters; }

    /** The simulated attractor the swarm orbits (world space). */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Bee Swarm")
    FVector GetSwarmTargetPosition() const { return Simulation.GetTargetPosition(); }

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Bee Swarm")
    int32 GetSimulatedBeeCount() const { return Simulation.GetBees().Num(); }

#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
    void ConfigureNiagaraOrdering();
    void ResetSimulation(const FVector& CameraPosition);
    bool ResolveCameraPosition(FVector& OutCameraPosition, bool& bOutCameraCut) const;
    void UploadToNiagara();

    UPROPERTY(EditAnywhere, Category = "Bee Swarm")
    FInfinityStageBeeSwarmParameters Parameters;

    UPROPERTY(EditAnywhere, Category = "Bee Swarm|Niagara")
    TObjectPtr<UNiagaraComponent> NiagaraComponent;

    UPROPERTY(EditAnywhere, Category = "Bee Swarm|Niagara")
    FName PositionArrayParameter = TEXT("User.BeePositions");

    UPROPERTY(EditAnywhere, Category = "Bee Swarm|Niagara")
    FName VelocityArrayParameter = TEXT("User.BeeVelocities");

    /** Sandbox aid: draws the swarm target as a debug sphere every tick. */
    UPROPERTY(EditAnywhere, Category = "Bee Swarm|Debug")
    bool bDrawDebugTarget = false;

    FInfinityStageBeeSwarmSimulation Simulation;
    TArray<FVector> PositionUploadBuffer;
    TArray<FVector> VelocityUploadBuffer;
    FVector LastValidCameraPosition = FVector::ZeroVector;
    bool bSimulationInitialized = false;
    bool bCameraCutPending = false;
};
