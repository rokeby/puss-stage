#include "InfinityStageBeeSwarmActor.h"

#include "Components/SceneComponent.h"
#include "InfinityStageBeeSwarmComponent.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"

AInfinityStageBeeSwarmActor::AInfinityStageBeeSwarmActor()
{
    PrimaryActorTick.bCanEverTick = false;

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);

    NiagaraComponent = CreateDefaultSubobject<UNiagaraComponent>(TEXT("Niagara"));
    NiagaraComponent->SetupAttachment(Root);
    NiagaraComponent->SetAutoActivate(true);

    SwarmComponent = CreateDefaultSubobject<UInfinityStageBeeSwarmComponent>(TEXT("Swarm"));

    // A soft path, not a hard reference: the class loads without the asset, and
    // the editor-run asset script creates the system at exactly this path.
    SwarmSystem = TSoftObjectPtr<UNiagaraSystem>(
        FSoftObjectPath(TEXT("/Game/Scenes/Effects/Swarm/NS_BeeSwarm.NS_BeeSwarm")));
}

void AInfinityStageBeeSwarmActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ApplySettings();
}

void AInfinityStageBeeSwarmActor::PostInitializeComponents()
{
    Super::PostInitializeComponents();
    ApplySettings();
}

void AInfinityStageBeeSwarmActor::SetSwarmBrightness(const float Brightness)
{
    SwarmBrightness = FMath::Max(0.0f, Brightness);
    if (NiagaraComponent)
    {
        NiagaraComponent->SetVariableFloat(TEXT("User.SwarmBrightness"), SwarmBrightness);
    }
}

void AInfinityStageBeeSwarmActor::ApplySettings()
{
    if (NiagaraComponent)
    {
        UNiagaraSystem* System = SwarmSystem.LoadSynchronous();
        if (System && NiagaraComponent->GetAsset() != System)
        {
            NiagaraComponent->SetAsset(System);
        }
        NiagaraComponent->SetVariableFloat(TEXT("User.SwarmBrightness"), SwarmBrightness);
    }
    if (SwarmComponent)
    {
        SwarmComponent->SetNiagaraComponent(NiagaraComponent);
        SwarmComponent->SetParameters(Parameters);
    }
}
