#include "InfinityStageBeeSwarmComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"
#include "NiagaraDataInterfaceArrayFunctionLibrary.h"
#include "NiagaraTickBehaviorEnum.h"

#if WITH_EDITOR
#include "Editor.h"
#include "LevelEditorViewport.h"
#endif

UInfinityStageBeeSwarmComponent::UInfinityStageBeeSwarmComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = true;
    PrimaryComponentTick.bTickEvenWhenPaused = true;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
    PrimaryComponentTick.EndTickGroup = TG_PostUpdateWork;
    // v3: without this the editor-viewport camera branch below never runs, and a
    // level-placed swarm is frozen outside PIE (sandbox preview, S6 authoring).
    bTickInEditor = true;
}

void UInfinityStageBeeSwarmComponent::OnRegister()
{
    Super::OnRegister();

    if (!NiagaraComponent)
    {
        if (const AActor* Owner = GetOwner())
        {
            NiagaraComponent = Owner->FindComponentByClass<UNiagaraComponent>();
        }
    }
    ConfigureNiagaraOrdering();
}

void UInfinityStageBeeSwarmComponent::BeginPlay()
{
    Super::BeginPlay();

    FVector CameraPosition = GetOwner() ? GetOwner()->GetActorLocation() : FVector::ZeroVector;
    bool bCameraCut = false;
    ResolveCameraPosition(CameraPosition, bCameraCut);
    ResetSimulation(CameraPosition);
    UploadToNiagara();
}

void UInfinityStageBeeSwarmComponent::TickComponent(
    const float DeltaTime,
    const ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    // v3: a paused world still ticks this component (bTickEvenWhenPaused, so the
    // camera bubble keeps holding) but must not advance the swarm: Niagara pauses
    // with the world, and advancing here would pop every bee on unpause.
    const UWorld* World = GetWorld();
    const float SimulationDelta = (World && World->IsPaused()) ? 0.0f : DeltaTime;

    FVector CameraPosition = LastValidCameraPosition;
    bool bGameCameraCut = false;
    ResolveCameraPosition(CameraPosition, bGameCameraCut);
    LastValidCameraPosition = CameraPosition;
    if (!bSimulationInitialized)
    {
        ResetSimulation(CameraPosition);
    }
    else
    {
        Simulation.Advance(
            SimulationDelta,
            CameraPosition,
            bCameraCutPending || bGameCameraCut);
    }
    bCameraCutPending = false;
    UploadToNiagara();

    if (bDrawDebugTarget && World)
    {
        DrawDebugSphere(World, Simulation.GetTargetPosition(), 8.0f, 8, FColor::Orange);
    }
}

void UInfinityStageBeeSwarmComponent::SetParameters(
    const FInfinityStageBeeSwarmParameters& InParameters)
{
    Parameters = InParameters;
    bSimulationInitialized = false;
}

#if WITH_EDITOR
void UInfinityStageBeeSwarmComponent::PostEditChangeProperty(
    FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    bSimulationInitialized = false;
}
#endif

void UInfinityStageBeeSwarmComponent::SetNiagaraComponent(
    UNiagaraComponent* InNiagaraComponent)
{
    if (NiagaraComponent && NiagaraComponent != InNiagaraComponent)
    {
        NiagaraComponent->RemoveTickPrerequisiteComponent(this);
    }
    NiagaraComponent = InNiagaraComponent;
    ConfigureNiagaraOrdering();
    UploadToNiagara();
}

void UInfinityStageBeeSwarmComponent::NotifyCameraCut()
{
    bCameraCutPending = true;
}

void UInfinityStageBeeSwarmComponent::ConfigureNiagaraOrdering()
{
    if (!NiagaraComponent)
    {
        return;
    }

    NiagaraComponent->SetTickBehavior(ENiagaraTickBehavior::UsePrereqs);
    NiagaraComponent->AddTickPrerequisiteComponent(this);
}

void UInfinityStageBeeSwarmComponent::ResetSimulation(const FVector& CameraPosition)
{
    const FVector Origin = GetOwner() ? GetOwner()->GetActorLocation() : FVector::ZeroVector;
    Simulation.Reset(Parameters, Origin, CameraPosition);
    const int32 BeeCount = Simulation.GetBees().Num();
    PositionUploadBuffer.SetNumUninitialized(BeeCount);
    VelocityUploadBuffer.SetNumUninitialized(BeeCount);
    LastValidCameraPosition = CameraPosition;
    bSimulationInitialized = true;
}

bool UInfinityStageBeeSwarmComponent::ResolveCameraPosition(
    FVector& OutCameraPosition,
    bool& bOutCameraCut) const
{
    bOutCameraCut = false;
    const UWorld* World = GetWorld();
    if (World && World->IsGameWorld())
    {
        if (APlayerCameraManager* CameraManager = UGameplayStatics::GetPlayerCameraManager(this, 0))
        {
            OutCameraPosition = CameraManager->GetCameraLocation();
            bOutCameraCut = CameraManager->bGameCameraCutThisFrame;
            return true;
        }
    }

#if WITH_EDITOR
    if (GCurrentLevelEditingViewportClient)
    {
        OutCameraPosition = GCurrentLevelEditingViewportClient->GetViewLocation();
        return true;
    }
#endif

    return bSimulationInitialized;
}

void UInfinityStageBeeSwarmComponent::UploadToNiagara()
{
    if (!NiagaraComponent || !bSimulationInitialized)
    {
        return;
    }

    const TConstArrayView<FInfinityStageBeeKinematics> Bees = Simulation.GetBees();
    if (PositionUploadBuffer.Num() != Bees.Num())
    {
        PositionUploadBuffer.SetNumUninitialized(Bees.Num());
        VelocityUploadBuffer.SetNumUninitialized(Bees.Num());
    }
    for (int32 BeeIndex = 0; BeeIndex < Bees.Num(); ++BeeIndex)
    {
        PositionUploadBuffer[BeeIndex] = Bees[BeeIndex].Position;
        VelocityUploadBuffer[BeeIndex] = Bees[BeeIndex].Velocity;
    }

    UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayPosition(
        NiagaraComponent,
        PositionArrayParameter,
        PositionUploadBuffer);
    UNiagaraDataInterfaceArrayFunctionLibrary::SetNiagaraArrayVector(
        NiagaraComponent,
        VelocityArrayParameter,
        VelocityUploadBuffer);
}
