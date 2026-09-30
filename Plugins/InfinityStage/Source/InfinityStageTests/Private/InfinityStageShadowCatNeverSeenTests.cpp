#include "InfinityStageCameraRig.h"
#include "InfinityStageShadowCatComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatBodyNeverSeenInGameTest,
    "InfinityStage.ShadowCat.BodyNeverSeenInGame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatBodyNeverSeenInGameTest::RunTest(const FString& Parameters)
{
    UWorld* GameWorld = UWorld::CreateWorld(EWorldType::Game, false);
    APlayerController* PlayerController = GameWorld->SpawnActor<APlayerController>();
    if (PlayerController && !PlayerController->PlayerCameraManager)
    {
        FActorSpawnParameters ManagerSpawn;
        ManagerSpawn.Owner = PlayerController;
        PlayerController->PlayerCameraManager = GameWorld->SpawnActor<APlayerCameraManager>(ManagerSpawn);
        if (PlayerController->PlayerCameraManager)
        {
            PlayerController->PlayerCameraManager->InitializeFor(PlayerController);
        }
    }
    if (PlayerController && UGameplayStatics::GetPlayerController(GameWorld, 0) != PlayerController)
    {
        GameWorld->AddController(PlayerController);
    }

    AInfinityStageCameraRig* GameRig = GameWorld->SpawnActor<AInfinityStageCameraRig>();
    const bool bGameFixture = PlayerController && PlayerController->PlayerCameraManager && GameRig;
    TestTrue(TEXT("Fixture: the game world has a controller, camera manager and rig"), bGameFixture);
    if (bGameFixture)
    {
        PlayerController->SetViewTarget(GameRig);
        GameRig->UpdateShadowFigureVisibility();
        TestTrue(TEXT("Fixture: the game rig is live"), GameRig->AreShadowFiguresLive());

        TArray<USkeletalMeshComponent*> CatMeshes;
        if (AActor* Cat = GameRig->ShadowCat ? GameRig->ShadowCat->GetChildActor() : nullptr)
        {
            Cat->GetComponents(CatMeshes);
        }
        TestTrue(TEXT("Fixture: the live shadow cat has a mesh"), CatMeshes.Num() > 0);
        for (const USkeletalMeshComponent* Mesh : CatMeshes)
        {
            // Pre-fix the ray-tracing and depth-pass assertions fail: only the main pass was disabled.
            TestFalse(TEXT("The cat body is absent from the main pass"), static_cast<bool>(Mesh->bRenderInMainPass));
            TestFalse(TEXT("The cat body is absent from ray tracing"), static_cast<bool>(Mesh->bVisibleInRayTracing));
            TestFalse(TEXT("The cat body is absent from reflection captures"), static_cast<bool>(Mesh->bVisibleInReflectionCaptures));
            TestFalse(TEXT("The cat body is absent from real-time sky captures"), static_cast<bool>(Mesh->bVisibleInRealTimeSkyCaptures));
            TestFalse(TEXT("The cat body is absent from the depth pass"), static_cast<bool>(Mesh->bRenderInDepthPass));
            TestTrue(TEXT("The cat still casts its shadow"), static_cast<bool>(Mesh->CastShadow));
            TestFalse(TEXT("The live cat is not hidden"), static_cast<bool>(Mesh->bHiddenInGame));
        }
    }
    GameWorld->DestroyWorld(false);

    UWorld* EditorWorld = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCameraRig* EditorRig = EditorWorld->SpawnActor<AInfinityStageCameraRig>();
    TArray<USkeletalMeshComponent*> EditorCatMeshes;
    if (AActor* Cat = EditorRig && EditorRig->ShadowCat ? EditorRig->ShadowCat->GetChildActor() : nullptr)
    {
        Cat->GetComponents(EditorCatMeshes);
    }
    TestTrue(TEXT("Fixture: the editor shadow cat has a mesh"), EditorCatMeshes.Num() > 0);
    for (const USkeletalMeshComponent* Mesh : EditorCatMeshes)
    {
        TestTrue(TEXT("The editor still draws the cat body for authoring"), static_cast<bool>(Mesh->bRenderInMainPass));
    }
    EditorWorld->DestroyWorld(false);
    return true;
}

#endif
