#pragma once

#include "GameFramework/Actor.h"
#include "InfinityStageBeeSwarmSimulation.h"

#include "InfinityStageBeeSwarmActor.generated.h"

class UInfinityStageBeeSwarmComponent;
class UNiagaraComponent;
class UNiagaraSystem;

/**
 * Placeable S6 bee/firefly swarm: deterministic simulation component + the thin
 * Niagara renderer it feeds. Usable as a Show Prop attachment's ActorClass
 * (/Script/InfinityStage.InfinityStageBeeSwarmActor) with no Blueprint, because
 * every tunable lives on the actor and defaults to the S6 values.
 *
 * The actor's location is the behaviour-box centre. For S6 it sits 150 cm above
 * the floor so the default 140 cm Z half-extent keeps bees 10 cm off the floor.
 */
UCLASS(ClassGroup = (InfinityStage), meta = (DisplayName = "Infinity Stage Bee Swarm"))
class INFINITYSTAGE_API AInfinityStageBeeSwarmActor : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageBeeSwarmActor();

    virtual void OnConstruction(const FTransform& Transform) override;
    virtual void PostInitializeComponents() override;

    /** Scales User.SwarmBrightness (glint, wing rim, body) for the S6 release dim. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Bee Swarm")
    void SetSwarmBrightness(float Brightness);

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Bee Swarm")
    UInfinityStageBeeSwarmComponent* GetSwarmComponent() const { return SwarmComponent; }

    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Bee Swarm")
    UNiagaraComponent* GetNiagaraComponent() const { return NiagaraComponent; }

    /** Behaviour. Pushed to the swarm component on construction and on edit. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bee Swarm")
    FInfinityStageBeeSwarmParameters Parameters;

    /** The render-only Niagara system (array-indexed mesh particles). */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bee Swarm")
    TSoftObjectPtr<UNiagaraSystem> SwarmSystem;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bee Swarm", meta = (ClampMin = "0.0", UIMax = "4.0"))
    float SwarmBrightness = 1.0f;

private:
    void ApplySettings();

    UPROPERTY(VisibleAnywhere, Category = "Bee Swarm")
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(VisibleAnywhere, Category = "Bee Swarm")
    TObjectPtr<UNiagaraComponent> NiagaraComponent;

    UPROPERTY(VisibleAnywhere, Category = "Bee Swarm")
    TObjectPtr<UInfinityStageBeeSwarmComponent> SwarmComponent;
};
