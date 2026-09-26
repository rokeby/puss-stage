#include "Go1RemoteReceiverComponent.h"

#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

// Named under InfinityStage so the standard suite run includes it; it tests the
// receiver's side of the Show's camera handovers.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1ReceiverDrivesIncomingCameraDuringBlendTest,
	"InfinityStage.Go1.ReceiverDrivesIncomingCameraDuringBlend",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1ReceiverDrivesIncomingCameraDuringBlendTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	APlayerController* PlayerController = World->SpawnActor<APlayerController>();
	// A bare world has no GameMode or local player, so the controller may come
	// up without the camera manager and controller-list entry a real session
	// gives it (the first run of this test failed exactly there). Supply both.
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
	ACameraActor* Outgoing = World->SpawnActor<ACameraActor>(FVector(0.0, 0.0, 200.0), FRotator::ZeroRotator);
	ACameraActor* Incoming = World->SpawnActor<ACameraActor>(FVector(1000.0, 0.0, 200.0), FRotator(0.0, 90.0, 0.0));
	ACameraActor* CutTo = World->SpawnActor<ACameraActor>(FVector(0.0, 1000.0, 200.0), FRotator(0.0, -90.0, 0.0));
	AActor* Host = World->SpawnActor<AActor>();
	// Deliberately never registered: registering would open the telemetry
	// socket. Resolving the driven camera needs only the world and controller.
	UGo1RemoteReceiverComponent* Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;

	TestNotNull(TEXT("Fixture: player controller"), PlayerController);
	TestTrue(TEXT("Fixture: camera manager"), PlayerController && PlayerController->PlayerCameraManager);
	TestTrue(TEXT("Fixture: controller is player 0"),
		PlayerController && UGameplayStatics::GetPlayerController(World, 0) == PlayerController);
	TestTrue(TEXT("Fixture: three cameras"), Outgoing && Incoming && CutTo);
	TestNotNull(TEXT("Fixture: receiver"), Receiver);
	const bool bFixture = PlayerController && PlayerController->PlayerCameraManager
		&& UGameplayStatics::GetPlayerController(World, 0) == PlayerController
		&& Outgoing && Incoming && CutTo && Receiver;
	if (bFixture)
	{
		PlayerController->SetViewTarget(Outgoing);
		TestTrue(TEXT("With no blend the receiver drives the live view target"),
			Receiver->GetDrivenCameraActor() == Outgoing);

		PlayerController->SetViewTargetWithBlend(Incoming, 1.0f);
		TestTrue(TEXT("Fixture: a blend is in flight"),
			PlayerController->PlayerCameraManager->BlendTimeToGo > 0.0f);
		// UE 5.8 reports the PENDING (incoming) target while a blend is in
		// flight. The receiver relies on that, so assert it: if an engine
		// upgrade changes it, this is the line that says so.
		TestTrue(TEXT("Mid-blend the engine reports the incoming camera"),
			PlayerController->GetViewTarget() == Incoming);
		TestTrue(TEXT("Mid-blend the receiver drives the incoming camera"),
			Receiver->GetDrivenCameraActor() == Incoming);

		PlayerController->SetViewTargetWithBlend(CutTo, 0.0f);
		TestTrue(TEXT("A cut drives its target at once"),
			Receiver->GetDrivenCameraActor() == CutTo);

		Receiver->TargetCameraActor = Incoming;
		TestTrue(TEXT("An explicit Target Camera Actor still wins"),
			Receiver->GetDrivenCameraActor() == Incoming);
	}

	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1ReceiverRecentreKeepsViewTest,
	"InfinityStage.Go1.RecentreKeepsViewWithStickHeld",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1ReceiverRecentreKeepsViewTest::RunTest(const FString& Parameters)
{
	// The production rig: 30.3 x 18.2 degree gaze, pitch inverted.
	constexpr float YawRange = 30.3f;
	constexpr float PitchRange = 18.2f;
	constexpr float PitchDirection = -1.0f;
	constexpr float MinPitch = -80.0f;
	constexpr float MaxPitch = 80.0f;
	const FRotator AuthoredView(-4.0f, 350.0f, 0.0f);

	for (const FVector2f Stick : { FVector2f(0.0f, 0.0f), FVector2f(0.8f, -0.5f), FVector2f(-1.0f, 1.0f) })
	{
		const FRotator Centre = UGo1RemoteReceiverComponent::CentreKeepingView(
			AuthoredView, Stick.X, Stick.Y, YawRange, PitchRange, PitchDirection);
		const FRotator Output = UGo1RemoteReceiverComponent::ComposeGazeRotation(
			Centre, Stick.X, Stick.Y, YawRange, PitchRange, PitchDirection, MinPitch, MaxPitch);
		TestTrue(
			*FString::Printf(TEXT("Re-centring with the stick at (%.1f, %.1f) leaves the view where it was"), Stick.X, Stick.Y),
			Output.Equals(AuthoredView, 0.001f));

		// Letting go of the stick then turns the view by exactly the deflection
		// that was held: the dog's centre is relative, as decided.
		const FRotator Released = UGo1RemoteReceiverComponent::ComposeGazeRotation(
			Centre, 0.0f, 0.0f, YawRange, PitchRange, PitchDirection, MinPitch, MaxPitch);
		TestTrue(TEXT("Releasing the stick turns the view by the held deflection"),
			FMath::IsNearlyEqual(
				FRotator::NormalizeAxis(Released.Yaw - AuthoredView.Yaw), -Stick.X * YawRange, 0.001f)
			&& FMath::IsNearlyEqual(Released.Pitch - AuthoredView.Pitch, -PitchDirection * Stick.Y * PitchRange, 0.001f));
	}
	return true;
}

#endif
