#include "Go1RemoteReceiverComponent.h"

#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
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
	ACameraActor* Outgoing = World->SpawnActor<ACameraActor>(FVector(0.0, 0.0, 200.0), FRotator::ZeroRotator);
	ACameraActor* Incoming = World->SpawnActor<ACameraActor>(FVector(1000.0, 0.0, 200.0), FRotator(0.0, 90.0, 0.0));
	ACameraActor* CutTo = World->SpawnActor<ACameraActor>(FVector(0.0, 1000.0, 200.0), FRotator(0.0, -90.0, 0.0));
	AActor* Host = World->SpawnActor<AActor>();
	// Deliberately never registered: registering would open the telemetry
	// socket. Resolving the driven camera needs only the world and controller.
	UGo1RemoteReceiverComponent* Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;

	const bool bFixture = PlayerController && PlayerController->PlayerCameraManager
		&& Outgoing && Incoming && CutTo && Receiver;
	TestTrue(TEXT("Test world has a player controller, camera manager, three cameras and a receiver"), bFixture);
	if (bFixture)
	{
		PlayerController->SetViewTarget(Outgoing);
		TestTrue(TEXT("With no blend the receiver drives the live view target"),
			Receiver->GetDrivenCameraActor() == Outgoing);

		PlayerController->SetViewTargetWithBlend(Incoming, 1.0f);
		TestTrue(TEXT("Mid-blend the engine still reports the outgoing camera"),
			PlayerController->GetViewTarget() == Outgoing);
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

#endif
