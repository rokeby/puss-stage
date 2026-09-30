#include "InfinityStageCameraRig.h"
#include "InfinityStageShadowCatComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "CineCameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowFiguresOnlyWhenLiveTest,
    "InfinityStage.Camera.ShadowFiguresOnlyWhileRigIsLive",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowFiguresOnlyWhenLiveTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    APlayerController* PlayerController = World->SpawnActor<APlayerController>();
    // A bare world has no GameMode or local player; give the controller the
    // camera manager and controller-list entry a real session gives it.
    if (PlayerController && !PlayerController->PlayerCameraManager)
    {
        FActorSpawnParameters ManagerSpawn;
        ManagerSpawn.Owner = PlayerController;
        PlayerController->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>(ManagerSpawn);
        if (PlayerController->PlayerCameraManager)
        {
            PlayerController->PlayerCameraManager->InitializeFor(PlayerController);
        }
    }
    if (PlayerController && UGameplayStatics::GetPlayerController(World, 0) != PlayerController)
    {
        World->AddController(PlayerController);
    }
    AInfinityStageCameraRig* Rig = World->SpawnActor<AInfinityStageCameraRig>();
    ACameraActor* Stalls = World->SpawnActor<ACameraActor>(FVector(-1400.0, 0.0, 150.0), FRotator::ZeroRotator);

    const bool bFixture = PlayerController && PlayerController->PlayerCameraManager && Rig && Stalls;
    TestTrue(TEXT("Fixture: controller, camera manager, rig and a stalls camera"), bFixture);
    if (bFixture)
    {
        Rig->bEnableFollowLight = true;
        const auto CatHidden = [Rig]()
        {
            const AActor* Cat = Rig->ShadowCat ? Rig->ShadowCat->GetChildActor() : nullptr;
            return !Cat || Cat->IsHidden();
        };
        const auto CatMeshes = [Rig]()
        {
            TArray<USkeletalMeshComponent*> Meshes;
            if (AActor* Cat = Rig->ShadowCat ? Rig->ShadowCat->GetChildActor() : nullptr)
            {
                Cat->GetComponents(Meshes);
            }
            return Meshes;
        };
        TestTrue(TEXT("Fixture: the shadow cat has a mesh"), CatMeshes().Num() > 0);

        // The Opening case: another camera is live, so this rig's cat must not be in its shot.
        PlayerController->SetViewTarget(Stalls);
        Rig->UpdateShadowFigureVisibility();
        TestFalse(TEXT("A rig nobody is looking through is not live"), Rig->AreShadowFiguresLive());
        TestTrue(TEXT("...and its cat is hidden"), CatHidden());
        TestFalse(TEXT("...and its follow light is off"), Rig->FollowLight->IsVisible());

        PlayerController->SetViewTarget(Rig);
        Rig->UpdateShadowFigureVisibility();
        TestTrue(TEXT("The rig the player looks through is live"), Rig->AreShadowFiguresLive());
        TestFalse(TEXT("...and its cat is present"), CatHidden());
        TestTrue(TEXT("...and its follow light is on"), Rig->FollowLight->IsVisible());
        // Gary, 30 Sep: "we are always the cat when in passage or curtain view".
        // The camera IS the cat, so in a game world its body is never drawn;
        // only the shadow the follow light throws ahead of it appears.
        bool bBodyDrawn = false;
        bool bCastsShadow = false;
        for (const USkeletalMeshComponent* Mesh : CatMeshes())
        {
            bBodyDrawn = bBodyDrawn || Mesh->bRenderInMainPass != 0;
            bCastsShadow = bCastsShadow || (Mesh->CastShadow != 0 && !Mesh->bHiddenInGame);
        }
        TestFalse(TEXT("...but its body is never drawn in a game world"), bBodyDrawn);
        TestTrue(TEXT("...only its shadow is cast"), bCastsShadow);

        // Blending away: GetViewTarget() already reports the incoming stalls camera.
        PlayerController->SetViewTargetWithBlend(Stalls, 1.0f);
        Rig->UpdateShadowFigureVisibility();
        TestFalse(TEXT("Blending away takes the figures down at once"), Rig->AreShadowFiguresLive());

        // Blending in: the rig is the incoming target, but the view is still in flight.
        PlayerController->SetViewTarget(Stalls);
        PlayerController->SetViewTargetWithBlend(Rig, 1.0f);
        Rig->UpdateShadowFigureVisibility();
        TestTrue(TEXT("Fixture: a blend to the rig is in flight"), PlayerController->PlayerCameraManager->BlendTimeToGo > 0.0f);
        TestFalse(TEXT("Figures stay down until the blend lands"), Rig->AreShadowFiguresLive());
        TestTrue(TEXT("...so the cat is not flown past mid-blend"), CatHidden());

        PlayerController->SetViewTarget(Rig);
        PlayerController->PlayerCameraManager->BlendTimeToGo = 0.0f;
        Rig->UpdateShadowFigureVisibility();
        TestTrue(TEXT("Once the blend has landed the figures come back"), Rig->AreShadowFiguresLive());
    }

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRigCameraBodyHiddenTest,
    "InfinityStage.Camera.RigCameraBodyHiddenInGame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRigCameraBodyHiddenTest::RunTest(const FString& Parameters)
{
    // 29 Sep: the P01, P03, P04 and P06 rigs were saved with "camera mesh
    // hidden in game" off, so in PIE the P01 camera's body stood in the
    // Opening's stalls shot as a beige box.
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    AInfinityStageCameraRig* Rig = World->SpawnActor<AInfinityStageCameraRig>();
    TArray<UStaticMeshComponent*> Bodies;
    if (Rig && Rig->Camera)
    {
        TInlineComponentArray<UStaticMeshComponent*> Meshes(Rig);
        for (UStaticMeshComponent* Mesh : Meshes)
        {
            if (Mesh && Mesh->GetAttachParent() == Rig->Camera && Mesh->IsEditorOnly())
            {
                Bodies.Add(Mesh);
            }
        }
    }
    TestTrue(TEXT("Fixture: the rig's camera builds its editor body in a game world"), Bodies.Num() > 0);
    if (Bodies.Num() > 0)
    {
        // Reproduce the saved state: the flag off and the body built visible.
#if WITH_EDITORONLY_DATA
        Rig->Camera->bCameraMeshHiddenInGame = false;
#endif
        for (UStaticMeshComponent* Body : Bodies)
        {
            Body->SetHiddenInGame(false);
        }

        Rig->HideCameraBodyInGame();

        bool bAllHidden = true;
        for (const UStaticMeshComponent* Body : Bodies)
        {
            bAllHidden = bAllHidden && Body->bHiddenInGame != 0;
        }
        TestTrue(TEXT("A rig's camera body never appears in game, whatever its saved flag says"), bAllHidden);
#if WITH_EDITORONLY_DATA
        TestTrue(TEXT("...and the flag now says so too"), static_cast<bool>(Rig->Camera->bCameraMeshHiddenInGame));
#endif
    }

    World->DestroyWorld(false);
    return true;
}

#endif
