#pragma once

#include "CoreMinimal.h"
#include "Components/ChildActorComponent.h"
#include "GameFramework/Actor.h"
#include "InfinityStageShadowCatComponent.generated.h"

class USkeletalMeshComponent;

/**
 * Minimal camera-carried cat used by Infinity Stage.
 *
 * This deliberately does not inherit the AnimX character stack: the stage
 * only needs the authored mesh and direct walk/idle animation, not pawn input,
 * AI, HUD, health, or the vendor locomotion Blueprint.
 */
UCLASS()
class INFINITYSTAGE_API AInfinityStageShadowCatActor : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageShadowCatActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Shadow Cat")
    TObjectPtr<USkeletalMeshComponent> Mesh;
};

/**
 * Child-actor host for the lightweight camera shadow cat.
 */
UCLASS()
class INFINITYSTAGE_API UInfinityStageShadowCatComponent : public UChildActorComponent
{
    GENERATED_BODY()

public:
    virtual void CreateChildActor(TFunction<void(AActor*)> CustomizerFunc = nullptr) override;

private:
    static void PrepareShadowCat(AActor* CatActor);
    static void DisableUnusedGameplayComponents(AActor* CatActor);
};
