#include "InfinityStageCurtainRig.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

AInfinityStageCurtainRig::AInfinityStageCurtainRig()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    SetActorEnableCollision(false);

    CurtainRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CurtainRoot"));
    RootComponent = CurtainRoot;

    CurtainMotionRoot = CreateDefaultSubobject<USceneComponent>(TEXT("CurtainMotionRoot"));
    CurtainMotionRoot->SetupAttachment(CurtainRoot);

    CurtainMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CurtainMesh"));
    CurtainMesh->SetupAttachment(CurtainMotionRoot);
    CurtainMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CurtainMesh->SetGenerateOverlapEvents(false);
    CurtainMesh->SetCastShadow(false);
    CurtainMesh->SetRelativeRotation(FRotator::ZeroRotator);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CurtainAsset(
        TEXT("/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/SM_FireSafetyCurtain_01.SM_FireSafetyCurtain_01"));
    if (CurtainAsset.Succeeded())
    {
        CurtainMesh->SetStaticMesh(CurtainAsset.Object);
    }
    CurtainMesh->SetRelativeLocation(FVector(0.0f, 0.0f, -CurtainMeshCenterZCm));

    CurtainMesh->SetVisibility(false, true);
    CurtainMesh->SetHiddenInGame(true, true);
}

void AInfinityStageCurtainRig::BeginPlay()
{
    Super::BeginPlay();
    ApplyCurtainPresentation();
    if (bCurtainActive && bFollowPlayerCamera)
    {
        RefreshFromPlayerView();
    }
}

void AInfinityStageCurtainRig::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    ApplyCurtainPresentation();
    if (bCurtainActive && bFollowPlayerCamera)
    {
        RefreshFromPlayerView();
    }
}

void AInfinityStageCurtainRig::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ApplyCurtainPresentation();
    if (bCurtainActive && bFollowPlayerCamera)
    {
        RefreshFromPlayerView();
    }
}

bool AInfinityStageCurtainRig::ShouldTickIfViewportsOnly() const
{
    return true;
}

void AInfinityStageCurtainRig::SetCurtainState(const float InProgress, const bool bInActive)
{
    CurtainProgress = FMath::Clamp(InProgress, 0.0f, 1.0f);
    bCurtainActive = bInActive;
    ApplyCurtainPresentation();
    if (bCurtainActive && bFollowPlayerCamera)
    {
        RefreshFromPlayerView();
    }
}

void AInfinityStageCurtainRig::ApplyCurtainPresentation()
{
    CurtainProgress = FMath::Clamp(CurtainProgress, 0.0f, 1.0f);
    if (CurtainMotionRoot)
    {
        if (bUseAuthoredOpenClosedTransforms)
        {
            FTransform BlendedTransform;
            BlendedTransform.Blend(CurtainOpenRelativeTransform, CurtainClosedRelativeTransform, CurtainProgress);
            CurtainMotionRoot->SetRelativeTransform(BlendedTransform);
        }
        else
        {
            const float CentreOffset = FMath::Lerp(
                CurtainOpenCenterOffsetCm,
                CurtainClosedCenterOffsetCm,
                CurtainProgress);
            CurtainMotionRoot->SetRelativeLocation(FVector(0.0f, 0.0f, CentreOffset));
            CurtainMotionRoot->SetRelativeScale3D(FVector(CurtainUniformScale));
        }
        CurtainMotionRoot->SetVisibility(bCurtainActive, true);
    }
    if (CurtainMesh)
    {
        // Set the leaf explicitly as well as propagating from MotionRoot. This
        // makes a freshly spawned Sequencer actor render on its first frame.
        CurtainMesh->SetVisibility(bCurtainActive, true);
        CurtainMesh->SetHiddenInGame(!bCurtainActive, true);
    }
}

void AInfinityStageCurtainRig::RefreshFromPlayerView()
{
    UWorld* World = GetWorld();
    APlayerController* PlayerController = World ? World->GetFirstPlayerController() : nullptr;
    APlayerCameraManager* CameraManager = PlayerController ? PlayerController->PlayerCameraManager : nullptr;
    if (!CameraManager)
    {
        return;
    }

    const FVector CameraLocation = CameraManager->GetCameraLocation();
    const FRotator CameraRotation = CameraManager->GetCameraRotation();
    const FTransform CameraTransform(CameraRotation, CameraLocation);
    const FVector CameraLocalLocation =
        FVector(CurtainDistanceCm, 0.0f, 0.0f) + CurtainViewLocalOffsetCm;
    const FQuat CurtainRotation =
        CameraRotation.Quaternion() * CurtainViewRotationOffset.Quaternion();
    SetActorLocationAndRotation(
        CameraTransform.TransformPosition(CameraLocalLocation),
        CurtainRotation);
}