#include "Go1RemoteReceiverComponent.h"
#include "CineCameraComponent.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageCameraRig.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * A hard cut resets the dog's look even when the dog owns the camera.
 *
 * Gary, 30 Sep, on the look at a cut inside a Scene (the hangar Scenes are free
 * look and "built on sequencers with lots of camera cuts"): "Reset at every
 * cut". Before this, only a cut into a Timeline shot dropped the look; a cut
 * between dog-owned cameras carried the offset, so the next authored shot
 * opened turned by it. Red without the fix: the offset carries onto the new
 * camera (20 degrees), and bResetLookAtCut does not exist.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1LookResetsAtEveryCutTest,
	"InfinityStage.Go1.LookResetsAtEveryCut",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1LookResetsAtEveryCutTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	ACameraActor* ShotA = World->SpawnActor<ACameraActor>(FVector(0.0, 0.0, 200.0), FRotator(0.0, 30.0, 0.0));
	ACameraActor* ShotB = World->SpawnActor<ACameraActor>(FVector(0.0, 1000.0, 200.0), FRotator(0.0, -90.0, 0.0));
	for (ACameraActor* Camera : { ShotA, ShotB })
	{
		// A bare world never runs InitializeComponents, where a real session
		// auto-activates cameras; the look goes on the active camera.
		if (Camera && Camera->GetCameraComponent() && !Camera->GetCameraComponent()->IsActive())
		{
			Camera->GetCameraComponent()->Activate(true);
		}
	}
	AActor* Host = World->SpawnActor<AActor>();
	// Never registered: registering would open the telemetry socket. No player
	// controller either, so no blend is ever in flight: every change is a hard cut.
	UGo1RemoteReceiverComponent* Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;
	if (!TestTrue(TEXT("Fixture: two active cameras and a receiver"), ShotA && ShotB && Receiver))
	{
		World->DestroyWorld(false);
		return true;
	}
	const auto ViewOf = [](const ACameraActor* Camera) { return Camera->GetCameraComponent()->GetComponentRotation(); };
	constexpr float Frame = 1.0f / 60.0f;
	Receiver->RotationMode = EGo1RotationMode::Velocity;            // Free Look, as the hangar Scenes are
	Receiver->LookHandoverSeconds = 0.6f;

	// The dog's stand-in (the mouse; no telemetry) looks 20 degrees off shot A.
	Receiver->UpdateLook(ShotA, false, false, FVector2D(5.0, 0.0), Frame);
	for (int32 Tick = 0; Tick < 60; ++Tick)
	{
		Receiver->UpdateLook(ShotA, false, false, FVector2D::ZeroVector, Frame);
	}
	TestTrue(TEXT("Fixture: looking 20 degrees off shot A"), FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, 20.0, 0.01));

	// A hard cut to shot B, the dog still owning the camera.
	Receiver->UpdateLook(ShotB, false, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("A cut between dog-owned shots drops the look at once"), Receiver->GetLookOffset().IsNearlyZero(0.001));
	TestTrue(TEXT("...so shot B opens exactly as authored"),
		ViewOf(ShotB).Equals(FRotator(0.0, -90.0, 0.0), 0.01)
		&& ShotB->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));
	TestTrue(TEXT("...and shot A is put back as driven"),
		ShotA->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));

	// The dog looks around from the authored aim afterwards.
	Receiver->UpdateLook(ShotB, false, false, FVector2D(-2.0, 0.0), Frame);
	TestTrue(TEXT("After the cut the dog looks around from shot B's authored aim"),
		FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, -8.0, 0.01)
		&& ViewOf(ShotB).Equals(FRotator(0.0, -98.0, 0.0), 0.01));

	// Off restores the earlier behaviour: the look carries across a dog-owned cut.
	Receiver->bResetLookAtCut = false;
	Receiver->UpdateLook(ShotA, false, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("With bResetLookAtCut off the look carries across the cut"),
		FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, -8.0, 0.01)
		&& ViewOf(ShotA).Equals(FRotator(0.0, 22.0, 0.0), 0.01));

	Receiver->ReleaseLook();
	World->DestroyWorld(false);
	return true;
}

/** A blended view-target change eases the reset while both cameras are visible. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1LookResetEasesAcrossBlendTest,
	"InfinityStage.Go1.LookResetEasesAcrossBlend",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1LookResetEasesAcrossBlendTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	APlayerController* PlayerController = World->SpawnActor<APlayerController>();
	// A bare world has no GameMode or local player, so supply the camera manager
	// and controller-list entry that make IsViewBlendInFlight observable.
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
	ACameraActor* ShotA = World->SpawnActor<ACameraActor>(FVector(0.0, 0.0, 200.0), FRotator(0.0, 30.0, 0.0));
	ACameraActor* ShotB = World->SpawnActor<ACameraActor>(FVector(0.0, 1000.0, 200.0), FRotator(0.0, -90.0, 0.0));
	for (ACameraActor* Camera : { ShotA, ShotB })
	{
		if (Camera && Camera->GetCameraComponent() && !Camera->GetCameraComponent()->IsActive())
		{
			Camera->GetCameraComponent()->Activate(true);
		}
	}
	AActor* Host = World->SpawnActor<AActor>();
	// Never registered: registering would open the telemetry socket.
	UGo1RemoteReceiverComponent* Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;

	TestNotNull(TEXT("Fixture: player controller"), PlayerController);
	TestTrue(TEXT("Fixture: camera manager"), PlayerController && PlayerController->PlayerCameraManager);
	TestTrue(TEXT("Fixture: controller is player 0"),
		PlayerController && UGameplayStatics::GetPlayerController(World, 0) == PlayerController);
	TestTrue(TEXT("Fixture: two active cameras and a receiver"), ShotA && ShotB && Receiver);
	const bool bFixture = PlayerController && PlayerController->PlayerCameraManager
		&& UGameplayStatics::GetPlayerController(World, 0) == PlayerController
		&& ShotA && ShotB && Receiver;
	if (!bFixture)
	{
		World->DestroyWorld(false);
		return true;
	}

	constexpr float Frame = 1.0f / 60.0f;
	Receiver->RotationMode = EGo1RotationMode::Velocity;
	Receiver->LookHandoverSeconds = 0.6f;
	PlayerController->SetViewTarget(ShotA);
	PlayerController->PlayerCameraManager->BlendTimeToGo = 0.0f;

	// Free Look is 20 degrees off the authored aim on shot A.
	Receiver->UpdateLook(ShotA, false, false, FVector2D(5.0, 0.0), Frame);
	for (int32 Tick = 0; Tick < 60; ++Tick)
	{
		Receiver->UpdateLook(ShotA, false, false, FVector2D::ZeroVector, Frame);
	}
	TestTrue(TEXT("Fixture: looking 20 degrees off shot A"),
		FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, 20.0, 0.01));

	PlayerController->SetViewTargetWithBlend(ShotB, 1.0f);
	TestTrue(TEXT("Fixture: a blend to shot B is in flight"),
		PlayerController->PlayerCameraManager->BlendTimeToGo > 0.0f
		&& PlayerController->GetViewTarget() == ShotB);

	const int32 EaseTicks = FMath::CeilToInt(Receiver->LookHandoverSeconds / Frame);
	const double MaxEaseStep = 20.0 * 1.5 * Frame / Receiver->LookHandoverSeconds + 0.01;
	double PreviousYaw = Receiver->GetLookOffset().Yaw;
	bool bMonotonic = true;
	bool bNoVisibleStep = true;
	for (int32 Tick = 0; Tick < EaseTicks; ++Tick)
	{
		Receiver->UpdateLook(ShotB, false, false, FVector2D::ZeroVector, Frame);
		const double CurrentYaw = Receiver->GetLookOffset().Yaw;
		bMonotonic &= CurrentYaw >= -1.0e-6 && CurrentYaw <= PreviousYaw + 1.0e-6;
		// SmoothStep's maximum slope is 1.5, so this is the largest legitimate
		// one-frame move for a 20-degree ease over LookHandoverSeconds.
		bNoVisibleStep &= PreviousYaw - CurrentYaw <= MaxEaseStep;
		PreviousYaw = CurrentYaw;
	}
	TestTrue(TEXT("During the blend the look eases monotonically toward zero"), bMonotonic);
	TestTrue(TEXT("...without a step larger than the per-tick ease"), bNoVisibleStep);
	TestTrue(TEXT("...and reaches authored aim within LookHandoverSeconds"),
		Receiver->GetLookOffset().IsNearlyZero(0.001));

	// Before the fix, LastViewTarget changed on the first blended tick but no
	// reset began, so every assertion below saw the original 20-degree look.
	PlayerController->PlayerCameraManager->BlendTimeToGo = 0.0f;
	for (int32 Tick = 0; Tick < 10; ++Tick)
	{
		Receiver->UpdateLook(ShotB, false, false, FVector2D::ZeroVector, Frame);
	}
	TestTrue(TEXT("After the blend lands the look stays at authored aim"),
		Receiver->GetLookOffset().IsNearlyZero(0.001));
	TestTrue(TEXT("...and the left-behind camera is restored only after landing"),
		ShotA->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));

	Receiver->ReleaseLook();
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1FreeLookReturnsDuringPassageSettleTest,
	"InfinityStage.Go1.FreeLookReturnsDuringPassageSettle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1FreeLookReturnsDuringPassageSettleTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	AInfinityStageCameraRig* Rig = World->SpawnActor<AInfinityStageCameraRig>();
	AActor* Host = World->SpawnActor<AActor>();
	UGo1RemoteReceiverComponent* Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;
	if (!TestTrue(TEXT("Fixture: Passage rig and receiver"), Rig && Receiver))
	{
		World->DestroyWorld(false);
		return true;
	}
	if (!Rig->Camera->IsActive())
	{
		Rig->Camera->Activate(true);
	}
	Receiver->RotationMode = EGo1RotationMode::Velocity;
	Receiver->LookHandoverSeconds = 0.0f;
	constexpr float Frame = 1.0f / 60.0f;

	Rig->CurrentCrossingSettleWeight = 1.0;
	Receiver->UpdateLook(Rig, false, false, FVector2D(5.0, -2.5), Frame);
	const FRotator Full = Receiver->GetLookOffset();
	TestTrue(TEXT("Control: Free Look is non-zero before the settle"),
		FMath::IsNearlyEqual(Full.Yaw, 20.0, 0.01) && FMath::IsNearlyEqual(Full.Pitch, -10.0, 0.01));

	Rig->CurrentCrossingSettleWeight = 0.5;
	Receiver->UpdateLook(Rig, false, false, FVector2D::ZeroVector, Frame);
	const FRotator Half = Receiver->GetLookOffset();
	TestTrue(TEXT("Halfway through the settle, Free Look is halfway home"),
		FMath::IsNearlyEqual(Half.Yaw, 10.0, 0.01) && FMath::IsNearlyEqual(Half.Pitch, -5.0, 0.01));

	Rig->CurrentCrossingSettleWeight = 0.0;
	Receiver->UpdateLook(Rig, false, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("At the Passage boundary, Free Look is exactly authored default"),
		Receiver->GetLookOffset().IsNearlyZero(0.001));

	Receiver->ReleaseLook();
	World->DestroyWorld(false);
	return true;
}

#endif
