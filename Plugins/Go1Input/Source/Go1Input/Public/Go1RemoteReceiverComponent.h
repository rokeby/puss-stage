#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "HAL/CriticalSection.h"
#include "Go1RemoteReceiverComponent.generated.h"

class AInfinityStageShowRoot;
class USceneComponent;
class FSocket;
class FUdpSocketReceiver;
class FArrayReader;
struct FIPv4Endpoint;

/** Buttons on the GO1 handheld remote, matching the SDK's xKeySwitchUnion bit order. */
UENUM(BlueprintType)
enum class EGo1RemoteButton : uint8
{
	R1     = 0,
	L1     = 1,
	Start  = 2,
	Select = 3,
	R2     = 4,
	L2     = 5,
	F1     = 6,
	F2     = 7,
	A      = 8,
	B      = 9,
	X      = 10,
	Y      = 11,
	Up     = 12,
	Right  = 13,
	Down   = 14,
	Left   = 15
};

/** How the right stick maps to rotation. */
UENUM(BlueprintType)
enum class EGo1RotationMode : uint8
{
	/** Stick deflection = turn rate. Holding the stick keeps turning forever. */
	Velocity UMETA(DisplayName = "Velocity (stick = turn rate)"),

	/**
	 * Stick deflection = angle offset from the camera's driven rotation (its
	 * route or its sequence), bounded by Yaw/Pitch Range. Centring the stick
	 * returns to that rotation, wherever it has turned to meanwhile.
	 * Best when the view maps to a physical screen at a known distance.
	 */
	Absolute UMETA(DisplayName = "Absolute (stick = angle within range)")
};

/**
 * Listens for JSON telemetry packets from the GO1 bridge (go1_remote_bridge)
 * and optionally turns the live camera from the right stick.
 *
 * The turn is a look OFFSET layered on top of whatever drives the camera: it
 * is written to the camera component under the actor's root, so the root keeps
 * the rotation its route or sequence gives it and the view is driven + look.
 * Nothing is captured once and held, so the view follows a bending route and
 * never fights the sequence (the 26 Sep regression this replaced).
 *
 * Add this component to any actor (e.g. a camera actor) and press Play.
 * Staleness is measured on this machine's clock as time since the last
 * accepted packet; when stale (or the bridge reports source_lost) all axes
 * read zero and rotation stops.
 */
UCLASS(ClassGroup = (Input), meta = (BlueprintSpawnableComponent))
class GO1INPUT_API UGo1RemoteReceiverComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UGo1RemoteReceiverComponent();

	/** UDP port to listen on. Must match the bridge's destination port. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Network")
	int32 ListenPort = 9876;

	/** Packets older than this (ms, receiver clock) put input in the safe zero state. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Network")
	float StaleTimeoutMs = 150.0f;

	/** Stick values below this magnitude read as zero; above it, rescaled to full range. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Input", meta = (ClampMin = "0.0", ClampMax = "0.9"))
	float Deadzone = 0.08f;

	/**
	 * Low-pass smoothing on the stick axes, in milliseconds (roughly the time to
	 * cover ~63% of a step). The robot only publishes at 50Hz, so raw values
	 * arrive as a staircase; without this the camera visibly steps.
	 * ~60ms is a good starting point. 0 disables smoothing entirely.
	 * Higher = smoother but more lag.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Input", meta = (ClampMin = "0.0", ClampMax = "500.0"))
	float SmoothingTimeMs = 60.0f;

	/**
	 * Maximum rate of change of a stick axis, in axis-units per second, as if the
	 * sticks were being moved very gently however fast they are actually flicked.
	 * 0 disables the limit (default: unchanged behaviour).
	 *
	 * Unlike Smoothing Time, which softens the shape of a change, this bounds its
	 * peak speed: 0.5 means a full 0 -> 1 throw takes two seconds no matter how
	 * hard the stick is pushed. In Absolute mode the resulting camera speed is
	 * this value times Yaw/Pitch Range — e.g. 0.5 with a 30.3 degree range caps
	 * the sweep at ~15 degrees per second.
	 *
	 * The stale/lost fail-safe deliberately ignores this and snaps to zero.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Input", meta = (ClampMin = "0.0", ClampMax = "10.0"))
	float MaxAxisRatePerSec = 0.0f;

	/**
	 * Response curve exponent applied after the deadzone. 1.0 is linear;
	 * 1.5–2.0 gives finer control near centre while keeping full speed at the
	 * edges, which usually feels better for camera work.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Input", meta = (ClampMin = "1.0", ClampMax = "4.0"))
	float ResponseExponent = 1.0f;

	/** Master switch: if false this component receives telemetry but rotates nothing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bDriveOwnerRotation = true;

	/**
	 * Let the Infinity Stage Show decide who owns the camera.
	 *
	 * `AInfinityStageShowRoot::GetCurrentCameraOwner()` returns the authored
	 * owner for the current Master segment (or the operator's live override):
	 *   Timeline    -> the look eases back to zero, then this component writes
	 *                  nothing; the sequence drives.
	 *   DogGazeOnly -> Absolute mode (stick = bounded angle, springs to centre).
	 *   DogFreeLook -> Velocity mode (stick = turn rate, view holds).
	 *
	 * This is the intended arbitration mechanism: ownership belongs to the Show,
	 * not to per-actor flags, so one receiver can serve every camera. While it is
	 * governing, Follow Dog Mode and the remote mode-toggle are ignored — the
	 * Show is authoritative. If no Show Root exists (a bare test level), the
	 * component falls back to its own settings.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Show Ownership")
	bool bUseShowCameraOwnership = true;

	/** Leave empty to find the Show Root automatically. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Show Ownership")
	TObjectPtr<AInfinityStageShowRoot> ShowRoot;

	/**
	 * Which camera carries the look. Leave empty for the recommended setup: the
	 * component lives on the Show Root and rotates whichever camera is live,
	 * resolved from the player's view target, so it follows Sequencer camera
	 * cuts across Passages and Scenes without reconfiguration. During a blended
	 * handover that is the incoming camera, from the blend's first frame
	 * (the engine reports the pending view target while a blend is in flight).
	 *
	 * Set it explicitly to pin one camera, or when running in the editor, where
	 * there is no player controller to ask. Falls back to this component's own
	 * actor if neither is available.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	TObjectPtr<AActor> TargetCameraActor;

	/** The camera actor currently being driven, whatever the resolution path. */
	UFUNCTION(BlueprintPure, Category = "Go1|Camera")
	AActor* GetDrivenCameraActor() const;

	/** Velocity = stick is a turn rate; Absolute = stick is an angle within a bounded range. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	EGo1RotationMode RotationMode = EGo1RotationMode::Absolute;

	/**
	 * Absolute mode: yaw offset at full stick deflection, in degrees either side
	 * of centre. To make the swing match a physical screen, set this to half the
	 * screen's horizontal angular size from the viewer:
	 *   YawRangeDeg = degrees( atan( (ScreenWidth / 2) / ViewerDistance ) )
	 * e.g. a 4 m wide screen at 3 m => atan(2/3) = 33.7 degrees.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera", meta = (ClampMin = "1.0", ClampMax = "180.0"))
	float YawRangeDeg = 33.7f;

	/** Absolute mode: pitch offset at full stick deflection, degrees either side of centre. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera", meta = (ClampMin = "1.0", ClampMax = "89.0"))
	float PitchRangeDeg = 20.0f;

	/**
	 * Seconds the look takes to settle on its new target when its source
	 * changes: a camera-owner change (Timeline, Gaze, Free Look), telemetry
	 * arriving or lost, or a re-centre. The ease starts at the look as it
	 * stands, so none of these steps the picture (Gary, 26 Sep: "don't jump").
	 * A hard cut drops the look at once whoever owns the camera (see
	 * bResetLookAtCut), since the cut already hides the change and the shot
	 * should open as authored. A blended change eases the look to zero over
	 * this duration instead, because both cameras are then on screen.
	 * 0 = settle at once.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera", meta = (ClampMin = "0.0", UIMax = "3.0"))
	float LookHandoverSeconds = 0.6f;

	/**
	 * Reset the look whenever the view target changes, not only when the
	 * Timeline takes the camera. Gary, 30 Sep, asked what the dog's look should
	 * do at a cut inside a Scene: "Reset at every cut"; "it's not essential that
	 * dog has 'neck mobility' during cut scenes". A hard cut resets instantly;
	 * a blended transition eases to zero so neither visible camera steps. Off
	 * restores the earlier behaviour between dog-owned cameras.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bResetLookAtCut = true;


	/**
	 * Fallback only, ignored while Show ownership is governing: let a remote
	 * button switch between Absolute (gaze) and Velocity (body turn) during a
	 * session. Use when authoring the Show is impractical, e.g. a bare test map. Switching to Absolute re-centres on the current view, so there is
	 * no snap.
	 *
	 * NOTE: the dog's own controller also sees these buttons. Pick one that is
	 * inert in the dog's current mode (F1/F2 are usually safe) and verify before
	 * relying on it in performance.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bAllowRemoteModeToggle = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera",
		meta = (EditCondition = "bAllowRemoteModeToggle"))
	EGo1RemoteButton ModeToggleButton = EGo1RemoteButton::F1;

	/** Let a remote button re-capture the centre rotation (Absolute mode). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bAllowRemoteRecenter = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera",
		meta = (EditCondition = "bAllowRemoteRecenter"))
	EGo1RemoteButton RecenterButton = EGo1RemoteButton::F2;

	/** Velocity mode: yaw speed at full right-stick deflection, degrees per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	float YawDegPerSec = 120.0f;

	/** Velocity mode: pitch speed at full right-stick deflection, degrees per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	float PitchDegPerSec = 90.0f;

	/** Flip pitch direction (stick up = look down). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bInvertPitch = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera", meta = (ClampMin = "-89.0", ClampMax = "0.0"))
	float MinPitch = -80.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera", meta = (ClampMin = "0.0", ClampMax = "89.0"))
	float MaxPitch = 80.0f;

	/**
	 * Stand in for the dog with the mouse while no telemetry is arriving.
	 *
	 * This is deliberately the same path the robot drives, not a second one: it
	 * moves the same look offset, obeys the same pitch limits, recentre and
	 * Show camera ownership (in Gaze it stays inside Yaw/Pitch Range, as the
	 * stick does). So it only takes effect where the dog would — set
	 * the Cue Desk's Live Camera Owner to Force Dog (or author DogFreeLook) and
	 * the mouse looks around; under Timeline ownership it stays hands-off, as
	 * the dog does. Real telemetry always wins: one fresh packet and the mouse
	 * stops contributing.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera|Mouse Stand-In")
	bool bMouseLookWhenNoTelemetry = true;

	/** Degrees turned per unit of mouse delta. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera|Mouse Stand-In",
		meta = (ClampMin = "0.0", UIMax = "20.0", EditCondition = "bMouseLookWhenNoTelemetry"))
	float MouseLookDegreesPerUnit = 4.0f;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Go1|Camera|Mouse Stand-In")
	bool bMouseLookActive = false;

	/**
	 * Look back down the camera's driven rotation: clears what Free Look and
	 * the mouse have accumulated and eases there over Look Handover Seconds.
	 * In Gaze the stick still decides the angle; a held stick stays held.
	 */
	UFUNCTION(BlueprintCallable, Category = "Go1|Camera")
	void RecenterRotation();

	/** The look offset (pitch, yaw) currently layered on the driven camera. */
	UFUNCTION(BlueprintPure, Category = "Go1|Camera")
	FRotator GetLookOffset() const { return LookOffset; }

	/**
	 * The view the audience sees: Driven turned by the look Offset. Yaw is about
	 * world up and pitch about the camera's own right, so the horizon never
	 * rolls. The offset's pitch is limited to Min/Max Pitch, but an authored
	 * pitch beyond those limits is kept as authored.
	 */
	static FRotator ComposeLook(
		const FRotator& Driven,
		const FRotator& Offset,
		float MinPitchDegrees,
		float MaxPitchDegrees);

	/**
	 * Layer Offset on DrivenActor's view: on its camera component when it has
	 * one below the root, otherwise on its root. Whatever wrote that component
	 * since our last write (the route, a sequence) is adopted as the driven
	 * rotation first, so repeating this under a held playhead never drifts.
	 * Switching to another actor puts the previous one back as it was driven,
	 * but only once no blend is in flight: mid-blend the outgoing camera is
	 * still half the picture, and restoring it then would step that half.
	 */
	void ApplyLookOffset(AActor* DrivenActor, const FRotator& Offset);

	/** Stop layering and put every camera we turned back as it was driven. */
	void ReleaseLook();

	/** Start easing from the look as it stands (see Look Handover Seconds). */
	void BeginLookHandover();

	/** Advance the look toward Target, through any handover ease; returns the new look. */
	FRotator AdvanceLookOffset(const FRotator& Target, float DeltaSeconds);

	/**
	 * One frame of look: integrate Free Look and the mouse, aim at the target
	 * for the current mode, ease, and layer the result on TargetActor. Under
	 * Timeline ownership the look eases to zero and is then released. Called by
	 * TickComponent; public so the behaviour can be tested without a dog.
	 */
	void UpdateLook(AActor* TargetActor, bool bTimelineOwnsCamera, bool bFresh,
		const FVector2D& MouseDelta, float DeltaSeconds);

	/** A new camera owner (or mode): ease from the look as it stands. */
	void OnLookOwnerChanged(bool bTimelineOwnsCamera);

	/**
	 * When the rotation write happens in the frame.
	 *
	 * TG_DuringPhysics is the verified-working value: it lands before the camera
	 * point-of-view is cached, so the write reaches the screen the same frame.
	 * TG_PostUpdateWork runs after sequence evaluation, but that is also AFTER
	 * the camera POV snapshot — the rotation is applied to the actor but never
	 * rendered, which looks exactly like the stick doing nothing.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	TEnumAsByte<ETickingGroup> RotationTickGroup = TG_DuringPhysics;

	/**
	 * Register a tick prerequisite against every LevelSequenceActor so this
	 * component ticks after sequence evaluation. Off by default: it can push the
	 * tick past the camera POV snapshot, costing you the same frame it wins.
	 * Only useful if a sequence genuinely fights for the same rotation.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Camera")
	bool bTickAfterLevelSequences = false;

	/**
	 * Receive telemetry and drive rotation in the editor viewport WITHOUT
	 * pressing Play, so the remote can frame shots while authoring.
	 *
	 * WARNING: this rotates the camera for real, which dirties the level package
	 * exactly as if you had dragged it. The camera's own rotation is restored
	 * when this is switched off (or the component unregisters), but do not
	 * Save All while it is running.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Editor")
	bool bRunInEditor = false;

	/** Show a live on-screen readout of seq / age / axes / gaps while playing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Go1|Debug")
	bool bShowDebug = true;

	/** Left stick (lx, ly) after deadzone; zero when stale. */
	UFUNCTION(BlueprintPure, Category = "Go1")
	FVector2D GetLeftStick() const;

	/** Right stick (rx, ry) after deadzone; zero when stale. */
	UFUNCTION(BlueprintPure, Category = "Go1")
	FVector2D GetRightStick() const;

	/** True while packets are arriving, fresh, and the bridge has live source data. */
	UFUNCTION(BlueprintPure, Category = "Go1")
	bool IsFresh() const;

	/** True if the given remote button is currently held (false when stale). */
	UFUNCTION(BlueprintPure, Category = "Go1")
	bool IsButtonDown(EGo1RemoteButton Button) const;

	/** Milliseconds since the last accepted packet (receiver clock). Large when nothing received. */
	UFUNCTION(BlueprintPure, Category = "Go1")
	float GetPacketAgeMs() const;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void OnUnregister() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
	                           FActorComponentTickFunction* ThisTickFunction) override;

private:
	struct FPacketState
	{
		float Lx = 0.0f;
		float Ly = 0.0f;
		float Rx = 0.0f;
		float Ry = 0.0f;
		uint32 Keys = 0;
		uint32 Seq = 0;
		int32 DogMode = -1;   // HighState.mode as reported by the dog
		int32 DogGait = -1;
		bool bSourceLost = true;
		double ReceiveTimeSeconds = -1.0e9;
		uint64 GapCount = 0;
	};

	// Called on the receiver's own thread — must only touch State under the lock.
	void OnDataReceived(const TSharedPtr<FArrayReader, ESPMode::ThreadSafe>& Data, const FIPv4Endpoint& Sender);

	FPacketState GetStateCopy() const;
	float ApplyDeadzone(float Value) const;
	float ShapeAxis(float Value) const;  // deadzone + response curve

	// Game-thread only: smoothed axis values, updated in TickComponent.
	float SmoothedLx = 0.0f;
	float SmoothedLy = 0.0f;
	float SmoothedRx = 0.0f;
	float SmoothedRy = 0.0f;

	// The look layered on the driven camera, and what Free Look (stick rate) and
	// the mouse have integrated into it. In Gaze only the mouse accumulates.
	FRotator LookOffset = FRotator::ZeroRotator;
	FRotator AccumulatedLook = FRotator::ZeroRotator;

	// Handover ease: from the look as it stood toward the live target.
	FRotator HandoverFrom = FRotator::ZeroRotator;
	float HandoverAlpha = 1.0f;

	// The component carrying the look, its rotation as driven (relative), and
	// what we last wrote there, to tell our own write from the route's.
	TWeakObjectPtr<USceneComponent> LookComponent;
	FRotator LookDrivenRelative = FRotator::ZeroRotator;
	FRotator LookWrittenRelative = FRotator::ZeroRotator;
	bool bLookWritten = false;
	float LastDrivenPitch = 0.0f;

	// Telemetry freshness last tick: a change is a look-source handover.
	bool bWasFresh = false;

	// A camera cut away from keeps its look until the blend away from it has
	// landed (see ApplyLookOffset).
	TWeakObjectPtr<USceneComponent> LeftBehindComponent;
	FRotator LeftBehindDrivenRelative = FRotator::ZeroRotator;
	FRotator LeftBehindWrittenRelative = FRotator::ZeroRotator;

	// Transition detection: a view-target change, hard or blended.
	TWeakObjectPtr<AActor> LastViewTarget;
	float SecondsSinceHardCut = 1.0e6f;

	bool IsViewBlendInFlight() const;
	void SettleLeftBehindLook(bool bEvenMidBlend);
	void ReleaseCurrentLook();
	void SettleLookAtOnce();
	void RestoreIfStillOurs(USceneComponent* Component, const FRotator& DrivenRelative,
		const FRotator& WrittenRelative) const;

	// For rising-edge detection on remote buttons.
	uint32 PrevKeys = 0;

	// One log line the first time the mouse stands in, not one per frame.
	bool bMouseLookReported = false;

	void StartReceiver();
	void StopReceiver();

	AInfinityStageShowRoot* ResolveShowRoot();

	// -1 until an owner has been seen; stores EInfinityCameraOwner as an int so
	// this header need not depend on the InfinityStage module.
	int32 LastCameraOwner = -1;

	FSocket* Socket = nullptr;
	FUdpSocketReceiver* Receiver = nullptr;

	mutable FCriticalSection StateLock;
	FPacketState State;
};
