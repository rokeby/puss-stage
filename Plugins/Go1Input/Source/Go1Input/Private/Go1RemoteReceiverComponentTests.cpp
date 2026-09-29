#include "Go1RemoteReceiverComponent.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/SceneComponent.h"
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
		Receiver->TargetCameraActor = nullptr;

		// The look across a blend. The outgoing camera is still half the
		// picture until the blend lands, so it keeps its look until then;
		// putting it back at the start would step that half.
		for (ACameraActor* Camera : { Outgoing, Incoming, CutTo })
		{
			// A bare world never runs InitializeComponents, where a real session
			// auto-activates cameras; the look goes on the active camera.
			if (!Camera->GetCameraComponent()->IsActive())
			{
				Camera->GetCameraComponent()->Activate(true);
			}
		}
		PlayerController->SetViewTarget(Outgoing);
		PlayerController->PlayerCameraManager->BlendTimeToGo = 0.0f;
		const FRotator Look(0.0, 12.0, 0.0);
		Receiver->ApplyLookOffset(Outgoing, Look);
		PlayerController->SetViewTargetWithBlend(Incoming, 1.0f);
		Receiver->ApplyLookOffset(Incoming, Look);
		TestTrue(TEXT("Mid-blend the outgoing camera keeps its look"),
			Outgoing->GetCameraComponent()->GetRelativeRotation().Equals(Look, 0.01));
		TestTrue(TEXT("...while the incoming camera carries it"),
			Incoming->GetCameraComponent()->GetComponentRotation().Equals(FRotator(0.0, 102.0, 0.0), 0.01));

		PlayerController->PlayerCameraManager->BlendTimeToGo = 0.0f;
		Receiver->ApplyLookOffset(Incoming, Look);
		TestTrue(TEXT("Once the blend has landed the outgoing camera is put back as driven"),
			Outgoing->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.01));
		Receiver->ReleaseLook();
	}

	World->DestroyWorld(false);
	return true;
}

namespace Go1LookTest
{
	// A Game world with the pieces the look needs. Deliberately no player
	// controller: the look is handed its target actor directly.
	struct FFixture
	{
		UWorld* World = nullptr;
		ACameraActor* RouteCamera = nullptr;
		ACameraActor* OtherCamera = nullptr;
		AActor* RootOnly = nullptr;
		UGo1RemoteReceiverComponent* Receiver = nullptr;

		FFixture()
		{
			World = UWorld::CreateWorld(EWorldType::Game, false);
			RouteCamera = World->SpawnActor<ACameraActor>(FVector(0.0, 0.0, 200.0), FRotator(0.0, 30.0, 0.0));
			OtherCamera = World->SpawnActor<ACameraActor>(FVector(0.0, 1000.0, 200.0), FRotator(0.0, -90.0, 0.0));
			// A bare world never runs InitializeComponents, which is where a real
			// session auto-activates cameras; the view uses the active camera.
			for (ACameraActor* Camera : { RouteCamera, OtherCamera })
			{
				if (Camera && Camera->GetCameraComponent() && !Camera->GetCameraComponent()->IsActive())
				{
					Camera->GetCameraComponent()->Activate(true);
				}
			}
			RootOnly = World->SpawnActor<AActor>();
			if (RootOnly)
			{
				USceneComponent* Root = NewObject<USceneComponent>(RootOnly, TEXT("Root"));
				RootOnly->SetRootComponent(Root);
				Root->RegisterComponent();
			}
			AActor* Host = World->SpawnActor<AActor>();
			// Never registered: registering would open the telemetry socket.
			Receiver = Host ? NewObject<UGo1RemoteReceiverComponent>(Host) : nullptr;
		}

		~FFixture()
		{
			World->DestroyWorld(false);
		}

		bool IsValid() const
		{
			return RouteCamera && OtherCamera && RootOnly && RootOnly->GetRootComponent() && Receiver
				&& RouteCamera->GetCameraComponent()->IsActive() && OtherCamera->GetCameraComponent()->IsActive();
		}
	};

	FRotator ViewOf(const ACameraActor* Camera)
	{
		return Camera->GetCameraComponent()->GetComponentRotation();
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1LookLayersOnDrivenCameraTest,
	"InfinityStage.Go1.LookLayersOnDrivenCamera",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1LookLayersOnDrivenCameraTest::RunTest(const FString& Parameters)
{
	using namespace Go1LookTest;
	FFixture Fixture;
	TestTrue(TEXT("Fixture: two active cameras, a root-only actor and a receiver"), Fixture.IsValid());
	if (!Fixture.IsValid())
	{
		return true;
	}
	UGo1RemoteReceiverComponent* Receiver = Fixture.Receiver;
	ACameraActor* Route = Fixture.RouteCamera;
	const FRotator Look(-5.0, 20.0, 0.0);

	// The regression: the look was written over the actor's rotation from a
	// base captured once, so the view held its starting direction on a bend.
	Receiver->ApplyLookOffset(Route, Look);
	TestTrue(TEXT("The view is the driven rotation turned by the look"),
		ViewOf(Route).Equals(FRotator(-5.0, 50.0, 0.0), 0.01));
	TestTrue(TEXT("...and the root keeps the rotation its route gives it"),
		Route->GetActorRotation().Equals(FRotator(0.0, 30.0, 0.0), 0.01));

	Route->SetActorRotation(FRotator(0.0, 75.0, 0.0));
	Receiver->ApplyLookOffset(Route, Look);
	TestTrue(TEXT("When the route bends the view follows it, still turned by the look"),
		ViewOf(Route).Equals(FRotator(-5.0, 95.0, 0.0), 0.01));

	for (int32 Frame = 0; Frame < 120; ++Frame)
	{
		Receiver->ApplyLookOffset(Route, Look);
	}
	TestTrue(TEXT("A held playhead does not drift the view"),
		ViewOf(Route).Equals(FRotator(-5.0, 95.0, 0.0), 0.01));

	Receiver->ApplyLookOffset(Route, FRotator::ZeroRotator);
	TestTrue(TEXT("A zero look is exactly the driven view"),
		ViewOf(Route).Equals(Route->GetActorRotation(), 0.01)
		&& Route->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.01));

	// A camera that is its actor's root (or an actor with no camera) carries
	// the look on the root; a sequence writing the root every frame is adopted
	// as the driven rotation, not added to.
	AActor* RootOnly = Fixture.RootOnly;
	RootOnly->SetActorRotation(FRotator(0.0, 10.0, 0.0));
	const FRotator Small(0.0, 5.0, 0.0);
	Receiver->ApplyLookOffset(RootOnly, Small);
	TestTrue(TEXT("Root-carried look turns the root"),
		RootOnly->GetActorRotation().Equals(FRotator(0.0, 15.0, 0.0), 0.01));
	for (int32 Frame = 0; Frame < 60; ++Frame)
	{
		RootOnly->SetActorRotation(FRotator(0.0, 40.0, 0.0));
		Receiver->ApplyLookOffset(RootOnly, Small);
	}
	TestTrue(TEXT("A sequence writing the root each frame is adopted, not accumulated"),
		RootOnly->GetActorRotation().Equals(FRotator(0.0, 45.0, 0.0), 0.01));
	for (int32 Frame = 0; Frame < 60; ++Frame)
	{
		Receiver->ApplyLookOffset(RootOnly, Small);
	}
	TestTrue(TEXT("...and with nothing driving it the root holds"),
		RootOnly->GetActorRotation().Equals(FRotator(0.0, 45.0, 0.0), 0.01));

	// A cut: the look carries to the new camera; the one left behind goes back
	// as it was driven.
	Receiver->ApplyLookOffset(Route, Small);
	TestTrue(TEXT("After a cut the camera left behind is put back as driven"),
		RootOnly->GetActorRotation().Equals(FRotator(0.0, 40.0, 0.0), 0.01));
	TestTrue(TEXT("...and the new camera carries the same look"),
		ViewOf(Route).Equals(FRotator(0.0, 80.0, 0.0), 0.01));

	Receiver->ReleaseLook();
	TestTrue(TEXT("Releasing puts the camera back as driven"),
		Route->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.01));

	// Pitch limits bound what the look adds, never an authored pitch.
	const float MinPitch = -80.0f;
	const float MaxPitch = 80.0f;
	const FRotator Steep(-85.0, 0.0, 0.0);
	TestTrue(TEXT("An authored pitch past the limit stands"),
		FMath::IsNearlyEqual(UGo1RemoteReceiverComponent::ComposeLook(Steep, FRotator::ZeroRotator, MinPitch, MaxPitch).Pitch, -85.0, 0.001));
	TestTrue(TEXT("...the look cannot push it further"),
		FMath::IsNearlyEqual(UGo1RemoteReceiverComponent::ComposeLook(Steep, FRotator(-10.0, 0.0, 0.0), MinPitch, MaxPitch).Pitch, -85.0, 0.001));
	TestTrue(TEXT("...but can bring it back"),
		FMath::IsNearlyEqual(UGo1RemoteReceiverComponent::ComposeLook(Steep, FRotator(10.0, 0.0, 0.0), MinPitch, MaxPitch).Pitch, -75.0, 0.001));
	TestTrue(TEXT("A level view looks down no further than the limit"),
		FMath::IsNearlyEqual(UGo1RemoteReceiverComponent::ComposeLook(FRotator::ZeroRotator, FRotator(-100.0, 0.0, 0.0), MinPitch, MaxPitch).Pitch, -80.0, 0.001));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1MouseLookHoldsTest,
	"InfinityStage.Go1.MouseLookHoldsInGazeAndFreeLook",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1MouseLookHoldsTest::RunTest(const FString& Parameters)
{
	using namespace Go1LookTest;
	// Gary, 29 Sep: with no dog, mouse look fought the camera in every Passage
	// (Dog Gaze) and worked in the Void (Dog Free Look). The Gaze write threw
	// the mouse's turn away every frame; Free Look's write was gated on
	// telemetry. Both now move one look that nothing overwrites.
	struct FCase
	{
		EGo1RotationMode Mode;
		const TCHAR* Name;
		double ExpectedWideYaw;
	};
	for (const FCase& Case : {
		FCase{ EGo1RotationMode::Absolute, TEXT("Gaze (the Passages)"), 33.7 },
		FCase{ EGo1RotationMode::Velocity, TEXT("Free Look (the Void)"), 88.0 } })
	{
		FFixture Fixture;
		TestTrue(TEXT("Fixture"), Fixture.IsValid());
		if (!Fixture.IsValid())
		{
			return true;
		}
		UGo1RemoteReceiverComponent* Receiver = Fixture.Receiver;
		ACameraActor* Route = Fixture.RouteCamera;
		Receiver->RotationMode = Case.Mode;
		Receiver->YawRangeDeg = 33.7f;
		Receiver->MouseLookDegreesPerUnit = 4.0f;
		constexpr float Frame = 1.0f / 60.0f;

		// One flick of 2 units (8 degrees), then 120 frames of stillness while
		// the route keeps re-driving the root, as a playing Passage does.
		Receiver->UpdateLook(Route, false, false, FVector2D(2.0, 0.0), Frame);
		for (int32 Tick = 0; Tick < 120; ++Tick)
		{
			Route->SetActorRotation(FRotator(0.0, 30.0, 0.0));
			Receiver->UpdateLook(Route, false, false, FVector2D::ZeroVector, Frame);
		}
		TestTrue(*FString::Printf(TEXT("%s: the mouse's turn holds instead of springing back"), Case.Name),
			ViewOf(Route).Equals(FRotator(0.0, 38.0, 0.0), 0.01));

		// A wide sweep: Gaze stays inside the range the stick has; Free Look does not.
		Receiver->UpdateLook(Route, false, false, FVector2D(20.0, 0.0), Frame);
		TestTrue(*FString::Printf(TEXT("%s: a wide sweep lands at %.1f degrees of look"), Case.Name, Case.ExpectedWideYaw),
			FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, Case.ExpectedWideYaw, 0.01));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FGo1LookHandoverEasesTest,
	"InfinityStage.Go1.LookHandoverEasesWithoutStep",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGo1LookHandoverEasesTest::RunTest(const FString& Parameters)
{
	using namespace Go1LookTest;
	FFixture Fixture;
	TestTrue(TEXT("Fixture"), Fixture.IsValid());
	if (!Fixture.IsValid())
	{
		return true;
	}
	UGo1RemoteReceiverComponent* Receiver = Fixture.Receiver;
	ACameraActor* Route = Fixture.RouteCamera;
	Receiver->RotationMode = EGo1RotationMode::Absolute;
	Receiver->LookHandoverSeconds = 0.6f;
	constexpr float Frame = 1.0f / 60.0f;

	Receiver->UpdateLook(Route, false, false, FVector2D(5.0, 0.0), Frame);
	TestTrue(TEXT("Fixture: the dog's stand-in is looking 20 degrees off the route"),
		FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, 20.0, 0.01));

	// Gary, 26 Sep: "don't jump". The timeline taking the camera eases the look out.
	Receiver->OnLookOwnerChanged(true);
	Receiver->UpdateLook(Route, true, false, FVector2D::ZeroVector, Frame);
	const double FirstFrameYaw = Receiver->GetLookOffset().Yaw;
	TestTrue(TEXT("Handing to the timeline does not step the picture"), FirstFrameYaw > 19.8 && FirstFrameYaw < 20.0);

	bool bMonotonic = true;
	double Previous = FirstFrameYaw;
	for (int32 Tick = 0; Tick < 40; ++Tick)
	{
		Receiver->UpdateLook(Route, true, false, FVector2D::ZeroVector, Frame);
		bMonotonic &= Receiver->GetLookOffset().Yaw <= Previous + 1.0e-6;
		Previous = Receiver->GetLookOffset().Yaw;
	}
	TestTrue(TEXT("...it eases steadily back toward the route"), bMonotonic);
	TestTrue(TEXT("...and settles on it within Look Handover Seconds"),
		Receiver->GetLookOffset().IsNearlyZero(0.001));
	TestTrue(TEXT("Once settled the camera is left as the timeline drives it"),
		Route->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));

	// The timeline now moves the camera; nothing from the receiver follows it.
	Route->SetActorRotation(FRotator(10.0, 120.0, 0.0));
	Receiver->UpdateLook(Route, true, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("Under the timeline the receiver writes nothing"),
		ViewOf(Route).Equals(FRotator(10.0, 120.0, 0.0), 0.01)
		&& Route->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));

	// The dog taking it back with no deflection: the picture stays put.
	Receiver->OnLookOwnerChanged(false);
	Receiver->UpdateLook(Route, false, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("Handing back to the dog does not step the picture either"),
		ViewOf(Route).Equals(FRotator(10.0, 120.0, 0.0), 0.01));

	// A hard cut into a Timeline shot: the cut already hides the change, so
	// the shot opens exactly as authored instead of easing the look out over it.
	Receiver->UpdateLook(Route, false, false, FVector2D(5.0, 0.0), Frame);
	for (int32 Tick = 0; Tick < 60; ++Tick)
	{
		Receiver->UpdateLook(Route, false, false, FVector2D::ZeroVector, Frame);
	}
	TestTrue(TEXT("Fixture: looking 20 degrees off the route again"),
		FMath::IsNearlyEqual(Receiver->GetLookOffset().Yaw, 20.0, 0.01));
	ACameraActor* Authored = Fixture.OtherCamera;
	Receiver->OnLookOwnerChanged(true);
	Receiver->UpdateLook(Authored, true, false, FVector2D::ZeroVector, Frame);
	TestTrue(TEXT("A hard cut into a timeline shot drops the look at once"),
		Receiver->GetLookOffset().IsNearlyZero(0.001));
	TestTrue(TEXT("...so the shot opens exactly as authored"),
		ViewOf(Authored).Equals(FRotator(0.0, -90.0, 0.0), 0.01)
		&& Authored->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));
	TestTrue(TEXT("...and the camera cut away from is put back as driven"),
		Route->GetCameraComponent()->GetRelativeRotation().IsNearlyZero(0.001));
	return true;
}

#endif
