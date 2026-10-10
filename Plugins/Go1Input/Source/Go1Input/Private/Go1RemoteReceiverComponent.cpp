#include "Go1RemoteReceiverComponent.h"

#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Common/UdpSocketBuilder.h"
#include "Components/SceneComponent.h"
#include "Common/UdpSocketReceiver.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InfinityStageCameraRig.h"
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
				// During a blended handover UE 5.8 already reports the PENDING
				// (incoming) camera here, so the receiver steers and re-centres on
				// the shot the audience is watching arrive from the blend's first
				// frame. Verified by InfinityStage.Go1.ReceiverDrivesIncomingCameraDuringBlend,
				// which also asserts the engine behaviour so an upgrade that
				// changes it is caught.
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
	AccumulatedLook = FRotator::ZeroRotator;
	BeginLookHandover();
	UE_LOG(LogGo1Input, Log, TEXT("Look re-centred on the driven camera (was P=%.1f Y=%.1f)"),
		LookOffset.Pitch, LookOffset.Yaw);
}

FRotator UGo1RemoteReceiverComponent::ComposeLook(
	const FRotator& Driven,
	const FRotator& Offset,
	const float MinPitchDegrees,
	const float MaxPitchDegrees)
{
	FRotator View = Driven;
	View.Yaw = FRotator::NormalizeAxis(Driven.Yaw + Offset.Yaw);
	// Limit only what the look adds: an authored pitch beyond the limits stands.
	View.Pitch = FMath::Clamp(
		Driven.Pitch + Offset.Pitch,
		FMath::Min<double>(MinPitchDegrees, Driven.Pitch),
		FMath::Max<double>(MaxPitchDegrees, Driven.Pitch));
	return View;
}

namespace Go1Look
{
	// The component whose rotation is the view: the first active camera, as
	// AActor::CalcCamera picks it. Below the root it carries the look alone, so
	// the root keeps its route or sequence rotation and whatever else hangs on
	// the root (a rig's shadow cat, its follow light) stays on the route.
	USceneComponent* FindLookComponent(AActor* Actor)
	{
		if (!Actor)
		{
			return nullptr;
		}
		TInlineComponentArray<UCameraComponent*> Cameras(Actor);
		for (UCameraComponent* Camera : Cameras)
		{
			if (Camera && Camera->IsActive())
			{
				return Camera;
			}
		}
		return Actor->GetRootComponent();
	}

	constexpr float OwnWriteTolerance = 1.0e-3f;

	// The Show's owner and the camera cut come from the same Master frame but
	// through different systems, so the owner may land a frame or two after
	// the cut. Timeline taking over this soon after a hard cut still counts as
	// part of that cut.
	constexpr float CutGraceSeconds = 0.1f;
}

bool UGo1RemoteReceiverComponent::IsViewBlendInFlight() const
{
	const UWorld* World = GetWorld();
	const APlayerController* Controller = World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;
	return Controller && Controller->PlayerCameraManager
		&& Controller->PlayerCameraManager->BlendTimeToGo > 0.0f;
}

void UGo1RemoteReceiverComponent::RestoreIfStillOurs(
	USceneComponent* Component,
	const FRotator& DrivenRelative,
	const FRotator& WrittenRelative) const
{
	const UWorld* World = Component ? Component->GetWorld() : nullptr;
	const AActor* Owner = Component ? Component->GetOwner() : nullptr;
	if (IsValid(Component)
		&& (!World || !World->bIsTearingDown)
		&& (!Owner || !Owner->IsActorBeingDestroyed())
		&& Component->GetRelativeRotation().Equals(WrittenRelative, Go1Look::OwnWriteTolerance))
	{
		// Only while the rotation there is still ours; a newer write belongs to
		// whatever drives the camera.
		Component->SetRelativeRotation(DrivenRelative);
	}
}

void UGo1RemoteReceiverComponent::SettleLeftBehindLook(const bool bEvenMidBlend)
{
	if (!LeftBehindComponent.IsValid())
	{
		LeftBehindComponent.Reset();
		return;
	}
	if (!bEvenMidBlend && IsViewBlendInFlight())
	{
		return;
	}
	RestoreIfStillOurs(LeftBehindComponent.Get(), LeftBehindDrivenRelative, LeftBehindWrittenRelative);
	LeftBehindComponent.Reset();
}

void UGo1RemoteReceiverComponent::ReleaseCurrentLook()
{
	if (bLookWritten)
	{
		RestoreIfStillOurs(LookComponent.Get(), LookDrivenRelative, LookWrittenRelative);
	}
	LookComponent.Reset();
	bLookWritten = false;
}

void UGo1RemoteReceiverComponent::SettleLookAtOnce()
{
	LookOffset = FRotator::ZeroRotator;
	AccumulatedLook = FRotator::ZeroRotator;
	HandoverAlpha = 1.0f;
}

void UGo1RemoteReceiverComponent::ApplyLookOffset(AActor* DrivenActor, const FRotator& Offset)
{
	SettleLeftBehindLook(false);

	USceneComponent* Component = Go1Look::FindLookComponent(DrivenActor);
	if (Component != LookComponent.Get())
	{
		// A cut or a blend: the look carries over to the new camera unchanged,
		// and the camera being left waits to be put back as driven until no
		// blend is in flight.
		USceneComponent* Leaving = LookComponent.Get();
		const bool bLeavingWritten = Leaving && bLookWritten;
		const FRotator LeavingDriven = LookDrivenRelative;
		const FRotator LeavingWritten = LookWrittenRelative;

		if (Component && Component == LeftBehindComponent.Get())
		{
			// Cut back before the blend away had landed: carry on where we were.
			LookDrivenRelative = LeftBehindDrivenRelative;
			LookWrittenRelative = LeftBehindWrittenRelative;
			bLookWritten = true;
			LeftBehindComponent.Reset();
		}
		else
		{
			// Only one camera waits; an older one goes back now.
			SettleLeftBehindLook(true);
			bLookWritten = false;
		}
		if (bLeavingWritten)
		{
			LeftBehindComponent = Leaving;
			LeftBehindDrivenRelative = LeavingDriven;
			LeftBehindWrittenRelative = LeavingWritten;
		}
		LookComponent = Component;
		SettleLeftBehindLook(false);
	}
	if (!Component)
	{
		return;
	}

	const FRotator Current = Component->GetRelativeRotation();
	if (!bLookWritten || !Current.Equals(LookWrittenRelative, Go1Look::OwnWriteTolerance))
	{
		// Not our write: the route, a sequence or an operator put it there, so
		// that is the driven rotation now. This is what stops a held playhead
		// from accumulating the look frame on frame.
		LookDrivenRelative = Current;
	}

	const USceneComponent* Parent = Component->GetAttachParent();
	const FQuat ParentWorld = (Parent && !Component->IsUsingAbsoluteRotation())
		? Parent->GetSocketQuaternion(Component->GetAttachSocketName())
		: FQuat::Identity;
	const FRotator Driven = (ParentWorld * LookDrivenRelative.Quaternion()).Rotator();
	LastDrivenPitch = static_cast<float>(Driven.Pitch);

	Component->SetWorldRotation(ComposeLook(Driven, Offset, MinPitch, MaxPitch));
	LookWrittenRelative = Component->GetRelativeRotation();
	bLookWritten = true;
}

void UGo1RemoteReceiverComponent::ReleaseLook()
{
	ReleaseCurrentLook();
	SettleLeftBehindLook(true);
}

void UGo1RemoteReceiverComponent::BeginLookHandover()
{
	HandoverFrom = LookOffset;
	HandoverAlpha = (LookHandoverSeconds > 0.0f) ? 0.0f : 1.0f;
}

FRotator UGo1RemoteReceiverComponent::AdvanceLookOffset(const FRotator& Target, const float DeltaSeconds)
{
	if (HandoverAlpha < 1.0f)
	{
		HandoverAlpha = (LookHandoverSeconds > 0.0f)
			? FMath::Min(1.0f, HandoverAlpha + DeltaSeconds / LookHandoverSeconds)
			: 1.0f;
		const double Blend = FMath::SmoothStep(0.0, 1.0, static_cast<double>(HandoverAlpha));
		LookOffset.Pitch = FMath::Lerp(HandoverFrom.Pitch, Target.Pitch, Blend);
		// The short way round, so a Free Look that has spun a full turn eases
		// back by the angle that shows, not by the turns it made.
		LookOffset.Yaw = HandoverFrom.Yaw + FRotator::NormalizeAxis(Target.Yaw - HandoverFrom.Yaw) * Blend;
	}
	else
	{
		LookOffset.Pitch = Target.Pitch;
		LookOffset.Yaw = Target.Yaw;
	}
	LookOffset.Roll = 0.0;
	return LookOffset;
}

void UGo1RemoteReceiverComponent::OnLookOwnerChanged(const bool bTimelineOwnsCamera)
{
	// Free Look holds the view where the handover finds it; Gaze and the
	// Timeline aim back at the driven camera (Gaze then adds the stick).
	AccumulatedLook = (!bTimelineOwnsCamera && RotationMode == EGo1RotationMode::Velocity)
		? LookOffset
		: FRotator::ZeroRotator;
	if (bTimelineOwnsCamera && SecondsSinceHardCut < Go1Look::CutGraceSeconds)
	{
		SettleLookAtOnce();
		return;
	}
	BeginLookHandover();
}

void UGo1RemoteReceiverComponent::UpdateLook(
	AActor* TargetActor,
	const bool bTimelineOwnsCamera,
	const bool bFresh,
	const FVector2D& MouseDelta,
	const float DeltaSeconds)
{
	const bool bGaze = RotationMode == EGo1RotationMode::Absolute;
	const float PitchDir = bInvertPitch ? -1.0f : 1.0f;

	SettleLeftBehindLook(false);

	// A view-target change (the first camera seen is not a transition). A hard
	// cut drops the look at once because the cut hides it. During a blend both
	// cameras are visible, so ease the same reset instead of stepping it.
	SecondsSinceHardCut += DeltaSeconds;
	if (TargetActor != LastViewTarget.Get())
	{
		if (LastViewTarget.IsValid())
		{
			const bool bBlendInFlight = IsViewBlendInFlight();
			if (!bBlendInFlight)
			{
				SecondsSinceHardCut = 0.0f;
				if (bTimelineOwnsCamera || bResetLookAtCut)
				{
					SettleLookAtOnce();
				}
			}
			else if (bTimelineOwnsCamera || bResetLookAtCut)
			{
				AccumulatedLook = FRotator::ZeroRotator;
				BeginLookHandover();
			}
		}
		LastViewTarget = TargetActor;
	}

	if (bFresh != bWasFresh)
	{
		// The dog arriving or dropping out changes who is looking. In Gaze the
		// mouse's look ends (or starts from the driven view); Free Look keeps
		// the view where it is. Either way the change eases, never steps.
		if (bGaze)
		{
			AccumulatedLook = FRotator::ZeroRotator;
		}
		BeginLookHandover();
		bWasFresh = bFresh;
	}

	bMouseLookActive = false;
	FRotator Target = FRotator::ZeroRotator;
	if (!bTimelineOwnsCamera)
	{
		if (!bGaze && bFresh)
		{
			// Free Look: the stick is a turn rate, integrated into the look.
			AccumulatedLook.Yaw += SmoothedRx * YawDegPerSec * DeltaSeconds;
			AccumulatedLook.Pitch += PitchDir * SmoothedRy * PitchDegPerSec * DeltaSeconds;
		}

		// No dog: the mouse stands in on the same look. A mouse delta is a
		// movement, not a held deflection, so it is added rather than
		// integrated as a rate. It persists because nothing overwrites it: the
		// look is an offset on the driven camera, not a captured rotation.
		if (bMouseLookWhenNoTelemetry && !bFresh && !MouseDelta.IsNearlyZero())
		{
			AccumulatedLook.Yaw += MouseDelta.X * MouseLookDegreesPerUnit;
			AccumulatedLook.Pitch += PitchDir * MouseDelta.Y * MouseLookDegreesPerUnit;
			bMouseLookActive = true;
			if (!bMouseLookReported)
			{
				bMouseLookReported = true;
				UE_LOG(
					LogGo1Input,
					Display,
					TEXT("GO1_MOUSE_LOOK_ACTIVE|target=%s|deg_per_unit=%.2f|mode=%s"),
					*GetNameSafe(TargetActor),
					MouseLookDegreesPerUnit,
					bGaze ? TEXT("Absolute") : TEXT("Velocity"));
			}
		}

		AccumulatedLook.Yaw = FRotator::NormalizeAxis(AccumulatedLook.Yaw);
		// Keep the integral inside the pitch the view can reach, so it never
		// winds up past a limit and has to be unwound before it moves again.
		AccumulatedLook.Pitch = FMath::Clamp(
			AccumulatedLook.Pitch,
			FMath::Min(MinPitch, LastDrivenPitch) - LastDrivenPitch,
			FMath::Max(MaxPitch, LastDrivenPitch) - LastDrivenPitch);
		AccumulatedLook.Roll = 0.0;

		Target = AccumulatedLook;
		// A Passage rig's Master-time crossing envelope is already the authored
		// ease to its Scene Entry pose. Free Look uses that same envelope, so a
		// dog/mouse look returns to the route aim BEFORE the cut rather than
		// disappearing on it. Gaze remains live, and non-Passage cameras keep
		// their existing behavior. At the boundary the weight is exactly zero.
		if (!bGaze)
		{
			if (const AInfinityStageCameraRig* PassageRig = Cast<AInfinityStageCameraRig>(TargetActor))
			{
				const double Weight = FMath::Clamp(PassageRig->CurrentCrossingSettleWeight, 0.0, 1.0);
				Target.Pitch *= Weight;
				Target.Yaw *= Weight;
			}
		}
		if (bGaze)
		{
			// Stick position IS the angle, so there is nothing to integrate; the
			// mouse stands in within the same range the stick has.
			Target.Yaw = FMath::Clamp(Target.Yaw + SmoothedRx * YawRangeDeg, -YawRangeDeg, YawRangeDeg);
			Target.Pitch = FMath::Clamp(Target.Pitch + PitchDir * SmoothedRy * PitchRangeDeg, -PitchRangeDeg, PitchRangeDeg);
			AccumulatedLook.Yaw = FMath::Clamp(AccumulatedLook.Yaw, -YawRangeDeg, YawRangeDeg);
			AccumulatedLook.Pitch = FMath::Clamp(AccumulatedLook.Pitch, -PitchRangeDeg, PitchRangeDeg);
		}
	}

	AdvanceLookOffset(Target, DeltaSeconds);

	if (bTimelineOwnsCamera && HandoverAlpha >= 1.0f && LookOffset.IsNearlyZero(Go1Look::OwnWriteTolerance))
	{
		// Timeline ownership is hands off once the look has settled: the
		// sequence drives, and any write from here would fight it.
		ReleaseCurrentLook();
		return;
	}
	ApplyLookOffset(TargetActor, LookOffset);
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

	// Put the camera back as it is driven (in the editor: as the level author
	// left it).
	ReleaseLook();
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
	// The view target, so Sequencer cuts change it. The look carries across a
	// cut unchanged; ApplyLookOffset puts the camera being left back as driven.
	AActor* TargetActor = GetDrivenCameraActor();

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
				// A new owner eases from the look as it stands, so taking the
				// camera from the timeline or giving it back never snaps.
				OnLookOwnerChanged(bTimelineOwnsCamera);
				UE_LOG(LogGo1Input, Log, TEXT("Camera owner -> %s"),
					bTimelineOwnsCamera ? TEXT("Timeline (look eases out, then input released)")
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
			RotationMode = (RotationMode == EGo1RotationMode::Absolute)
				? EGo1RotationMode::Velocity
				: EGo1RotationMode::Absolute;
			OnLookOwnerChanged(false);
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

	// --- The look: an offset layered on whatever drives the camera ----------
	if (bDriveOwnerRotation && TargetActor != nullptr)
	{
		FVector2D MouseDelta = FVector2D::ZeroVector;
		if (bMouseLookWhenNoTelemetry && !bFresh && !bTimelineOwnsCamera)
		{
			if (APlayerController* Controller = UGameplayStatics::GetPlayerController(this, 0))
			{
				float MouseDeltaX = 0.0f;
				float MouseDeltaY = 0.0f;
				Controller->GetInputMouseDelta(MouseDeltaX, MouseDeltaY);
				MouseDelta = FVector2D(MouseDeltaX, MouseDeltaY);
			}
		}
		UpdateLook(TargetActor, bTimelineOwnsCamera, bFresh, MouseDelta, DeltaTime);
	}
	else
	{
		ReleaseLook();
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
				LookOffset.Yaw, LookOffset.Pitch, Copy.Keys)
			: FString::Printf(TEXT("GO1 %s"), *Status);

		GEngine->AddOnScreenDebugMessage(
			/*Key=*/0x601601, /*TimeToDisplay=*/0.5f,
			bFresh ? FColor::Green : FColor::Red, Msg);
	}
}
