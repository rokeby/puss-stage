#include "InfinityStageShadowCatComponent.h"

#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "UObject/ConstructorHelpers.h"

AInfinityStageShadowCatActor::AInfinityStageShadowCatActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);

    Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ShadowCatMesh"));
    SetRootComponent(Mesh);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetGenerateOverlapEvents(false);
    Mesh->SetSimulatePhysics(false);
    Mesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

    static ConstructorHelpers::FObjectFinder<USkeletalMesh> CatMeshFinder(
        TEXT("/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R.SK_Cat_R"));
    if (CatMeshFinder.Succeeded())
    {
        Mesh->SetSkeletalMeshAsset(CatMeshFinder.Object);
    }
}

void UInfinityStageShadowCatComponent::CreateChildActor(
    TFunction<void(AActor*)> CustomizerFunc)
{
    Super::CreateChildActor(
        [ExternalCustomizer = MoveTemp(CustomizerFunc)](AActor* SpawnedChildActor) mutable
        {
            PrepareShadowCat(SpawnedChildActor);
            if (ExternalCustomizer)
            {
                ExternalCustomizer(SpawnedChildActor);
            }
        });

    // Blueprint SCS components do not exist until FinishSpawning, so disable
    // the gameplay-only material and health-bar components after Super returns
    // but before the loaded world begins play.
    DisableUnusedGameplayComponents(GetChildActor());
}

void UInfinityStageShadowCatComponent::PrepareShadowCat(AActor* CatActor)
{
    if (!CatActor)
    {
        return;
    }

    // The AnimX Event Tick contains an unconditional AI-distance calculation.
    // Keep it off from the moment tick functions are first registered.
    CatActor->PrimaryActorTick.bStartWithTickEnabled = false;
    CatActor->SetActorTickEnabled(false);

}

void UInfinityStageShadowCatComponent::DisableUnusedGameplayComponents(AActor* CatActor)
{
    if (!CatActor)
    {
        return;
    }

    TInlineComponentArray<UPrimitiveComponent*> CatPrimitives(CatActor);
    for (UPrimitiveComponent* Primitive : CatPrimitives)
    {
        Primitive->SetSimulatePhysics(false);
        Primitive->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
}
