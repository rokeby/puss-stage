#include "Go1RemoteReceiverComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "Common/UdpSocketBuilder.h"
#include "Common/UdpSocketReceiver.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTypes.h"
#include "Kismet/GameplayStatics.h"
#include "LevelSequenceActor.h"
#include "HAL/PlatformTime.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SocketSubsystem.h"
#include "Sockets.h"

DEFINE_LOG_CATEGORY_STATIC(LogGo1Input, Log, All);

UGo1RemoteReceiverComponent::UGo1RemoteReceiverComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// Must land before the camera POV snapshot, or the rotation is set on the
	// actor but never rendered. Overridable via RotationTickGroup.
	PrimaryComponentTick.TickGroup = TG_DuringPhysics;
	// Required for bRunInEditor; the tick itself no-ops unless that is set.
	bTickInEditor = true;
}

void UGo1RemoteReceiverComponent::StartReceiver()
{
	if (Socket != nullptr)
	{
		return;
	}

	Socket = FUdpSocketBuilder(TEXT("Go1RemoteSocket"))
		.AsNonBlocking()
		.AsReusable()
		.BoundToAddress(FIPv4Address::Any)
		.BoundToPort(ListenPort)
		.WithReceiveBufferSize(4 * 1024);

	if (Socket == nullptr)
	{
		UE_LOG(LogGo1Input, Error,
			TEXT("Could not bind UDP port %d (already in use by another PIE session or app?). "
			     "No GO1 input this session."), ListenPort);
		return;
	}

	Receiver = new FUdpSocketReceiver(Socket, FTimespan::FromMilliseconds(5), TEXT("Go1RemoteReceiver"));
	Receiver->OnDataReceived().BindUObject(this, &UGo1RemoteReceiverComponent::OnDataReceived);
	Receiver->Start();

	UE_LOG(LogGo1Input, Log, TEXT("Listening for GO1 telemetry on UDP port %d"), ListenPort);

	RecenterRotation();

	PrimaryComponentTick.TickGroup = RotationTickGroup;
	UE_LOG(LogGo1Input, Log, TEXT("Rotation tick group: %d (TG_DuringPhysics=%d)"),
		static_cast<int32>(RotationTickGroup.GetValue()), static_cast<int32>(TG_DuringPhysics));

	if (bTickAfterLevelSequences && GetWorld() != nullptr)
	{
		int32 SequenceCount = 0;
		for (TActorIterator<ALevelSequenceActor> It(GetWorld()); It; ++It)
		{
			PrimaryComponentTick.AddPrerequisite(*It, It->PrimaryActorTick);
			++SequenceCount;
		}
		UE_LOG(LogGo1Input, Log,
			TEXT("Tick prerequisites registered against %d LevelSequenceActor(s)."),
			SequenceCount);
		if (SequenceCount == 0)
		{
			UE_LOG(LogGo1Input, Warning,
				TEXT("No LevelSequenceActors found. If a sequence still drives this camera's "
				     "rotation, it is spawned later or evaluated elsewhere — mute the rotation "
				     "channels on its transform track instead."));
		}
	}
}

AActor* UGo1RemoteReceiverComponent::GetDrivenCameraActor() const
{
	// Explicit pin wins.
	if (TargetCameraActor != nullptr)
	{
		return TargetCameraActor;
	}

	// Otherwise follow whatever the player is actually looking through, which is
	// what Sequencer camera cuts change. One receiver then serves every camera.
	if (const UWorld* World = GetWorld())
	{
		if (World->WorldType != EWorldType::Editor)
		{
			if (const APlayerController* PC = UGameplayStatics::GetPlayerController(World, 0))
			{
				// A blend in flight leaves GetViewTarget() reporting the OUTGOING
				// camera until it completes, while the audience is already watching
				// the incoming one arrive. Steer, and re-centre on, the incoming
				// camera from the blend's first frame. Otherwise the re-centre lands
				// at the end of the blend, where a deflected stick steps the view
				// mid-motion instead of behind a cut. A cut leaves BlendTimeToGo at
				// zero, so cuts behave exactly as before.
				if (const APlayerCameraManager* CameraManager = PC->PlayerCameraManager)
				{
					if (CameraManager->BlendTimeToGo > 0.0f && CameraManager->PendingViewTarget.Target)
					{
						return CameraManager->PendingViewTarget.Target;
					}
				}
				if (AActor* ViewTarget = PC->GetViewTarget())
				{
					return ViewTarget;
				}
			}
		}
	}

	// Editor, or no player yet: fall back to our own actor, which keeps the
	// original "component sits on the camera" setup working.
	return GetOwner();
}

AInfinityStageShowRoot* UGo1RemoteReceiverComponent::ResolveShowRoot()
{
	if (ShowRoot != nullptr)
	{
		return ShowRoot;
	}
	if (UWorld* World = GetWorld())
	{
		// First match only; a level is expected to have exactly one Show Root.
		TActorIterator<AInfinityStageShowRoot> It(World);
		if (It)
		{
			ShowRoot = *It;
			UE_LOG(LogGo1Input, Log, TEXT("Show Root found: %s. Camera ownership is authored by the Show."),
				*ShowRoot->GetName());
			return ShowRoot;
		}
	}
	return nullptr;
}

void UGo1RemoteReceiverComponent::RecenterRotation()
{
	if (const AActor* Target = GetDrivenCameraActor())
	{
		BaseRotation = Target->GetActorRotation();
		bBaseRotationCaptured = true;
		UE_LOG(LogGo1Input, Log, TEXT("Centre rotation captured: P=%.1f Y=%.1f"),
			BaseRotation.Pitch, BaseRotation.Yaw);
	}
}

void UGo1RemoteReceiverComponent::StopReceiver()
{
	if (Receiver != nullptr)
	{
		Receiver->Stop();
		delete Receiver;
		Receiver = nullptr;
	}
	if (Socket != nullptr)
	{
		Socket->Close();
		ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(Socket);
		Socket = nullptr;
	}

	// Editor mode: put the actor back where the level author left it.
	if (bEditorDriving)
	{
		if (AActor* Target = GetDrivenCameraActor())
		{
			Target->SetActorRotation(EditorRestoreRotation);
		}
		bEditorDriving = false;
	}
}

void UGo1RemoteReceiverComponent::BeginPlay()
{
	Super::BeginPlay();
	StartReceiver();
}

void UGo1RemoteReceiverComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopReceiver();
	Super::EndPlay(EndPlayReason);
}

void UGo1RemoteReceiverComponent::OnUnregister()
{
	// Covers editor-mode teardown: level close, component removal, recompile.
	StopReceiver();
	Super::OnUnregister();
}

void UGo1RemoteReceiverComponent::OnDataReceived(
	const TSharedPtr<FArrayReader, ESPMode::ThreadSafe>& Data, const FIPv4Endpoint& Sender)
{
	if (!Data.IsValid() || Data->Num() == 0)
	{
		return;
	}

	const FUTF8ToTCHAR Converted(reinterpret_cast<const ANSICHAR*>(Data->GetData()), Data->Num());
	const FString Text(Converted.Length(), Converted.Get());

	TSharedPtr<FJsonObject> Json;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
	{
		return;
	}

	if (static_cast<int32>(Json->GetNumberField(TEXT("v"))) != 1)
	{
		return;
	}

	const uint32 Seq = static_cast<uint32>(Json->GetNumberField(TEXT("seq")));
	const float Lx = static_cast<float>(Json->GetNumberField(TEXT("lx")));
	const float Ly = static_cast<float>(Json->GetNumberField(TEXT("ly")));
	const float Rx = static_cast<float>(Json->GetNumberField(TEXT("rx")));
	const float Ry = static_cast<float>(Json->GetNumberField(TEXT("ry")));
	const uint32 Keys = static_cast<uint32>(Json->GetNumberField(TEXT("keys")));
	bool bSourceLost = false;
	Json->TryGetBoolField(TEXT("source_lost"), bSourceLost);

	// Optional since protocol v1.0; absent from older bridge builds.
	double ModeValue = -1.0, GaitValue = -1.0;
	Json->TryGetNumberField(TEXT("mode"), ModeValue);
	Json->TryGetNumberField(TEXT("gait"), GaitValue);

	FScopeLock Lock(&StateLock);

	// Accept only strictly newer packets; drop reordered/duplicate ones.
	if (State.Seq != 0 && Seq <= State.Seq)
	{
		return;
	}
	if (State.Seq != 0 && Seq > State.Seq + 1)
	{
		State.GapCount += (Seq - State.Seq - 1);
	}

	State.Seq = Seq;
	State.Lx = FMath::Clamp(Lx, -1.0f, 1.0f);
	State.Ly = FMath::Clamp(Ly, -1.0f, 1.0f);
	State.Rx = FMath::Clamp(Rx, -1.0f, 1.0f);
	State.Ry = FMath::Clamp(Ry, -1.0f, 1.0f);
	State.Keys = Keys;
	State.DogMode = static_cast<int32>(ModeValue);
	State.DogGait = static_cast<int32>(GaitValue);
	State.bSourceLost = bSourceLost;
	State.ReceiveTimeSeconds = FPlatformTime::Seconds();
}

UGo1RemoteReceiverComponent::FPacketState UGo1RemoteReceiverComponent::GetStateCopy() const
{
	FScopeLock Lock(&StateLock);
	return State;
}

float UGo1RemoteReceiverComponent::ApplyDeadzone(float Value) const
{
	const float Magnitude = FMath::Abs(Value);
	if (Magnitude < Deadzone)
	{
		return 0.0f;
	}
	const float Rescaled = (Magnitude - Deadzone) / (1.0f - Deadzone);
	return FMath::Sign(Value) * FMath::Min(Rescaled, 1.0f);
}

float UGo1RemoteReceiverComponent::ShapeAxis(float Value) const
{
	const float Deadzoned = ApplyDeadzone(Value);
	if (ResponseExponent <= 1.0f || Deadzoned == 0.0f)
	{
		return Deadzoned;
	}
	// Preserve sign and full-scale range; only reshape the middle.
	return FMath::Sign(Deadzoned) * FMath::Pow(FMath::Abs(Deadzoned), ResponseExponent);
}

bool UGo1RemoteReceiverComponent::IsFresh() const
{
	const FPacketState Copy = GetStateCopy();
	const double AgeMs = (FPlatformTime::Seconds() - Copy.ReceiveTimeSeconds) * 1000.0;
	return !Copy.bSourceLost && AgeMs <= StaleTimeoutMs;
}

FVector2D UGo1RemoteReceiverComponent::GetLeftStick() const
{
	// Smoothed values are maintained in TickComponent and already zeroed when stale.
	return FVector2D(SmoothedLx, SmoothedLy);
}

FVector2D UGo1RemoteReceiverComponent::GetRightStick() const
{
	return FVector2D(SmoothedRx, SmoothedRy);
}

bool UGo1RemoteReceiverComponent::IsButtonDown(EGo1RemoteButton Button) const
{
	if (!IsFresh())
	{
		return false;
	}
	const FPacketState Copy = GetStateCopy();
	return (Copy.Keys & (1u << static_cast<uint32>(Button))) != 0;
}

float UGo1RemoteReceiverComponent::GetPacketAgeMs() const
{
	const FPacketState Copy = GetStateCopy();
	return static_cast<float>((FPlatformTime::Seconds() - Copy.ReceiveTimeSeconds) * 1000.0);
}

void UGo1RemoteReceiverComponent::TickComponent(
	float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// --- Editor-mode start/stop (no BeginPlay runs outside PIE) -------------
	const UWorld* World = GetWorld();
	const bool bIsEditorWorld = (World != nullptr && World->WorldType == EWorldType::Editor);
	if (bIsEditorWorld)
	{
		if (bRunInEditor && Socket == nullptr)
		{
			if (const AActor* Target = GetDrivenCameraActor())
			{
				EditorRestoreRotation = Target->GetActorRotation();
			}
			bEditorDriving = true;
			StartReceiver();
		}
		else if (!bRunInEditor && Socket != nullptr)
		{
			StopReceiver();
			return;
		}

		if (!bRunInEditor)
		{
			return;
		}
	}

	const FPacketState Copy = GetStateCopy();
	const double AgeMs = (FPlatformTime::Seconds() - Copy.ReceiveTimeSeconds) * 1000.0;
	const bool bFresh = !Copy.bSourceLost && AgeMs <= StaleTimeoutMs;

	// --- Update smoothed axes (game thread only) ----------------------------
	if (bFresh)
	{
		// Frame-rate independent exponential smoothing: alpha = 1 - e^(-dt/tau).
		const float Alpha = (SmoothingTimeMs <= 0.0f)
			? 1.0f
			: 1.0f - FMath::Exp(-(DeltaTime * 1000.0f) / SmoothingTimeMs);

		// Optional slew limit: bounds how fast an axis may change, which reads as
		// a gentle hand on the sticks regardless of how hard they are pushed.
		const float MaxStep = (MaxAxisRatePerSec > 0.0f)
			? MaxAxisRatePerSec * DeltaTime
			: TNumericLimits<float>::Max();

		auto Advance = [Alpha, MaxStep](float Current, float Target)
		{
			const float Next = FMath::Lerp(Current, Target, Alpha);
			return FMath::Clamp(Next, Current - MaxStep, Current + MaxStep);
		};

		SmoothedLx = Advance(SmoothedLx, ShapeAxis(Copy.Lx));
		SmoothedLy = Advance(SmoothedLy, ShapeAxis(Copy.Ly));
		SmoothedRx = Advance(SmoothedRx, ShapeAxis(Copy.Rx));
		SmoothedRy = Advance(SmoothedRy, ShapeAxis(Copy.Ry));
	}
	else
	{
		// Fail-safe must be immediate, not smoothed.
		SmoothedLx = SmoothedLy = SmoothedRx = SmoothedRy = 0.0f;
	}

	// --- Which camera are we driving? ----------------------------------------
	// The view target changes on Sequencer camera cuts, so re-centre when it does
	// or the new camera inherits the previous one's centre.
	AActor* TargetActor = GetDrivenCameraActor();
	if (TargetActor != LastDrivenActor.Get())
	{
		LastDrivenActor = TargetActor;
		RecenterRotation();
	}

	// --- Camera ownership: the Show is authoritative when one exists ---------
	bool bOwnershipGoverning = false;
	bool bTimelineOwnsCamera = false;
	if (bUseShowCameraOwnership)
	{
		if (AInfinityStageShowRoot* Root = ResolveShowRoot())
		{
			const EInfinityCameraOwner Owner = Root->GetCurrentCameraOwner();
			bOwnershipGoverning = true;

			switch (Owner)
			{
			case EInfinityCameraOwner::DogGazeOnly:
				RotationMode = EGo1RotationMode::Absolute;
				break;
			case EInfinityCameraOwner::DogFreeLook:
				RotationMode = EGo1RotationMode::Velocity;
				break;
			case EInfinityCameraOwner::Timeline:
			default:
				bTimelineOwnsCamera = true;
				break;
			}

			const int32 OwnerValue = static_cast<int32>(Owner);
			if (OwnerValue != LastCameraOwner)
			{
				// Taking the camera back from the timeline must not snap: adopt
				// wherever the sequence left it as the new centre.
				if (!bTimelineOwnsCamera)
				{
					RecenterRotation();
				}
				UE_LOG(LogGo1Input, Log, TEXT("Camera owner -> %s"),
					bTimelineOwnsCamera ? TEXT("Timeline (input released)")
					: (RotationMode == EGo1RotationMode::Absolute ? TEXT("DogGazeOnly (Absolute)")
					                                              : TEXT("DogFreeLook (Velocity)")));
				LastCameraOwner = OwnerValue;
			}
		}
	}

	// Mode selection is the Show's job: EInfinityCameraOwner on the Passage or
	// Scene decides gaze vs free look, authored in the Cue Desk and correct even
	// when the dog is absent. Mirroring HighState.mode was tried and removed —
	// measured on hardware, standing and move mode both report mode 0 and the
	// expected turn value 2 never appears, so the field cannot distinguish them.

	// --- Remote button edges (mode toggle / recentre) -----------------------
	if (bFresh)
	{
		const uint32 Pressed = Copy.Keys & ~PrevKeys;  // rising edges only

		if (!bOwnershipGoverning && bAllowRemoteModeToggle &&
			(Pressed & (1u << static_cast<uint32>(ModeToggleButton))) != 0)
		{
			if (RotationMode == EGo1RotationMode::Absolute)
			{
				RotationMode = EGo1RotationMode::Velocity;
			}
			else
			{
				RotationMode = EGo1RotationMode::Absolute;
				// Adopt the current view as centre so the switch doesn't snap.
				RecenterRotation();
			}
			UE_LOG(LogGo1Input, Log, TEXT("Rotation mode -> %s"),
				RotationMode == EGo1RotationMode::Absolute ? TEXT("Absolute") : TEXT("Velocity"));
		}

		if (bAllowRemoteRecenter &&
			(Pressed & (1u << static_cast<uint32>(RecenterButton))) != 0)
		{
			RecenterRotation();
		}

		PrevKeys = Copy.Keys;
	}

	// Timeline ownership means hands off entirely — the sequence drives, and any
	// write from here would fight it.
	if (bDriveOwnerRotation && !bTimelineOwnsCamera)
	{
		if (AActor* Owner = TargetActor)
		{
			const float PitchDir = bInvertPitch ? -1.0f : 1.0f;

			if (RotationMode == EGo1RotationMode::Absolute)
			{
				if (!bBaseRotationCaptured)
				{
					RecenterRotation();
				}

				// Stick position IS the angle, so there is no limit to run into
				// and nothing to integrate. Applied even when stale, because the
				// zeroed axes then return the view smoothly to centre.
				FRotator Rotation = BaseRotation;
				Rotation.Yaw += SmoothedRx * YawRangeDeg;
				Rotation.Pitch = FMath::Clamp(
					BaseRotation.Pitch + PitchDir * SmoothedRy * PitchRangeDeg,
					MinPitch, MaxPitch);
				Rotation.Roll = BaseRotation.Roll;
				Owner->SetActorRotation(Rotation);
			}
			else if (bFresh)
			{
				FRotator Rotation = Owner->GetActorRotation();
				Rotation.Yaw += SmoothedRx * YawDegPerSec * DeltaTime;
				Rotation.Pitch = FMath::Clamp(
					Rotation.Pitch + PitchDir * SmoothedRy * PitchDegPerSec * DeltaTime,
					MinPitch, MaxPitch);
				Rotation.Roll = 0.0f;
				Owner->SetActorRotation(Rotation);
			}

			// No dog: the mouse stands in on the same rotation, so a look pass can
			// be judged before the robot is on site. A mouse delta is a movement,
			// not a held deflection, so it is applied directly rather than
			// integrated as a rate.
			const bool bMouseEligible = bMouseLookWhenNoTelemetry && !bFresh;
			bMouseLookActive = false;
			if (bMouseEligible)
			{
				if (APlayerController* Controller = UGameplayStatics::GetPlayerController(this, 0))
				{
					float MouseDeltaX = 0.0f;
					float MouseDeltaY = 0.0f;
					Controller->GetInputMouseDelta(MouseDeltaX, MouseDeltaY);
					if (!FMath::IsNearlyZero(MouseDeltaX) || !FMath::IsNearlyZero(MouseDeltaY))
					{
						FRotator Rotation = Owner->GetActorRotation();
						Rotation.Yaw += MouseDeltaX * MouseLookDegreesPerUnit;
						Rotation.Pitch = FMath::Clamp(
							Rotation.Pitch + PitchDir * MouseDeltaY * MouseLookDegreesPerUnit,
							MinPitch, MaxPitch);
						Rotation.Roll = 0.0f;
						Owner->SetActorRotation(Rotation);
						bMouseLookActive = true;
						if (!bMouseLookReported)
						{
							bMouseLookReported = true;
							UE_LOG(
								LogGo1Input,
								Display,
								TEXT("GO1_MOUSE_LOOK_ACTIVE|target=%s|deg_per_unit=%.2f|mode=%s"),
								*Owner->GetName(),
								MouseLookDegreesPerUnit,
								RotationMode == EGo1RotationMode::Absolute ? TEXT("Absolute") : TEXT("Velocity"));
						}
					}
				}
			}
		}
	}

	if (bShowDebug && GEngine != nullptr)
	{
		// Distinguish "nothing has ever arrived" (check bridge/network) from
		// "the robot's feed died" (check the dog) — they need different fixes.
		const bool bEverReceived = (Copy.Seq != 0);
		FString Status;
		if (!bEverReceived)
		{
			Status = FString::Printf(TEXT("NO DATA - nothing received on port %d"), ListenPort);
		}
		else if (Copy.bSourceLost)
		{
			Status = TEXT("SOURCE LOST - bridge running, robot feed stopped");
		}
		else if (!bFresh)
		{
			Status = TEXT("STALE");
		}
		else
		{
			Status = TEXT("LIVE");
		}

		// FPS is included because uneven frame time looks exactly like input
		// jitter; if age is ~10-20ms and fps is unstable, the frame rate is the
		// problem, not the telemetry.
		const float Fps = (DeltaTime > KINDA_SMALL_NUMBER) ? (1.0f / DeltaTime) : 0.0f;

		const TCHAR* ModeName =
			bTimelineOwnsCamera ? TEXT("TIMELINE") :
			(RotationMode == EGo1RotationMode::Absolute) ? TEXT("GAZE") : TEXT("TURN");

		// Where the mode came from: the Show, or this component's own settings.
		const TCHAR* OwnerSource = bOwnershipGoverning ? TEXT("show") : TEXT("local");

		const FString Msg = bEverReceived
			? FString::Printf(
				TEXT("GO1 %s [%s/%s] | seq %u | age %.0f ms | gaps %llu | %.0f fps | dog mode %d gait %d | R(%.2f, %.2f) -> yaw %+.1f pitch %+.1f | keys 0x%04x"),
				*Status, ModeName, OwnerSource, Copy.Seq, AgeMs, Copy.GapCount, Fps,
				Copy.DogMode, Copy.DogGait,
				SmoothedRx, SmoothedRy,
				SmoothedRx * YawRangeDeg, SmoothedRy * PitchRangeDeg, Copy.Keys)
			: FString::Printf(TEXT("GO1 %s"), *Status);

		GEngine->AddOnScreenDebugMessage(
			/*Key=*/0x601601, /*TimeToDisplay=*/0.5f,
			bFresh ? FColor::Green : FColor::Red, Msg);
	}
}
