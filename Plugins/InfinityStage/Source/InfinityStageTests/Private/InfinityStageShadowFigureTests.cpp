#include "InfinityStageCameraRig.h"
#include "InfinityStageShadowCatComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
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

        // The Opening case: another camera is live, so this rig's cat must not be in its shot.
        PlayerController->SetViewTarget(Stalls);
        Rig->UpdateShadowFigureVisibility();
        TestFalse(TEXT("A rig nobody is looking through is not live"), Rig->AreShadowFiguresLive());
        TestTrue(TEXT("...and its cat is hidden"), CatHidden());
        TestFalse(TEXT("...and its follow light is off"), Rig->FollowLight->IsVisible());

        PlayerController->SetViewTarget(Rig);
        Rig->UpdateShadowFigureVisibility();
        TestTrue(TEXT("The rig the player looks through is live"), Rig->AreShadowFiguresLive());
        TestFalse(TEXT("...and its cat is shown"), CatHidden());
        TestTrue(TEXT("...and its follow light is on"), Rig->FollowLight->IsVisible());

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

#endif
