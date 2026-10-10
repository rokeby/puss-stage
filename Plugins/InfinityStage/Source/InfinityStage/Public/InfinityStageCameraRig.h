#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageCameraRig.generated.h"

class ACineCameraActor;
class AInfinityStagePassageActor;
class UChildActorComponent;
class UCineCameraComponent;
class USceneComponent;
class UInfinityStageShadowCatComponent;
struct FInfinityCompiledPassage;
struct FInfinityPassageCameraEvaluation;

struct FInfinityGaitBobState
{
    bool bPrimed = false;
    double LastMasterSeconds = 0.0;
    double LiftMeanCm = 0.0;
    double WalkWeight = 0.0;
};

struct FInfinityGaitBob
{
    double HeightCm = 0.0;
    double RollDeg = 0.0;
};

/**
 * One occasional appearance of the Puss shadow spot (PS, Gary 7 Oct: "a Puss
 * walking shadow spotlight which lights Puss from behind, very occasionally
 * appearing ... only for a few seconds"). Times are Passage-relative seconds
 * (0 = this rig's Passage segment start), so a cue travels with its Passage
 * and its music when a Master rebuild moves the Passage.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityShadowSpotCue
{
    GENERATED_BODY()

    /** Start of the attack, in seconds after the Passage segment start. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (Units = "s"))
    double PassageSeconds = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (ClampMin = "0.0", Units = "s"))
    double AttackSeconds = 0.5;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (ClampMin = "0.0", Units = "s"))
    double HoldSeconds = 3.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (ClampMin = "0.0", Units = "s"))
    double ReleaseSeconds = 1.0;

    /** Peak intensity, in the FollowLight component's own Intensity Units (a reference light's value copies as is). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (ClampMin = "0.0"))
    float Intensity = 15000.0f;

    /** Free text for tools (the musical moment this cue answers). Not evaluated. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot")
    FString Label;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageCameraRig : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageCameraRig();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<UCineCameraComponent> Camera;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> ShadowFigureRoot;

    /** Mesh-only AnimX cat carried by the camera-relative shadow root. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Shadow Cat")
    TObjectPtr<UInfinityStageShadowCatComponent> ShadowCat;

    /**
     * Travelling light behind the camera.
     *
     * Attached to the rig root, so it follows the route without any evaluation
     * of its own. Placed behind the shadow figure and pointing forward, it
     * throws the cat's shadow into the stage ahead of the camera.
     */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage|Follow Light")
    TObjectPtr<class USpotLightComponent> FollowLight;

    /** Off by default so existing levels light exactly as before. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light")
    bool bEnableFollowLight = false;

    /** Offset from the rig, in route space. Negative X sits behind the camera. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light", meta = (Units = "cm"))
    FVector FollowLightOffset = FVector(-600.0, 0.0, 250.0);

    /** Aim relative to the rig. Default looks slightly down the route ahead. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Follow Light")
    FRotator FollowLightRotation = FRotator(-8.0, 0.0, 0.0);

    /**
     * Puss shadow spot schedule. Empty (the default) leaves the follow light
     * exactly as before. Non-empty, the schedule owns the FollowLight
     * component: it is placed at ShadowSpotOffset/Rotation, casts shadows, and
     * is visible only while a cue's envelope is above zero (and the rig is
     * live), at envelope x Intensity; the component's units, cone, colour and
     * radii stay as set on it. A pure function of Master time,
     * so play, pause, scrub and reverse agree.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot")
    TArray<FInfinityShadowSpotCue> ShadowSpotCues;

    /** Shadow spot position relative to the rig (the camera). Low and behind the cat, for a long shadow. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot", meta = (Units = "cm"))
    FVector ShadowSpotOffset = FVector(-600.0, 0.0, 135.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Spot")
    FRotator ShadowSpotRotation = FRotator(-21.0, 0.0, 0.0);

    /** This master frame's shadow spot envelope, 0..1. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Spot")
    double CurrentShadowSpotWeight = 0.0;

    /**
     * Envelope of a cue list at a Passage-relative time: smoothstep attack,
     * hold at 1, smoothstep release; overlapping cues take the brightest.
     * OutIntensity is the brightest weighted cue intensity. Pure.
     */
    static double EvaluateShadowSpot(
        const TArray<FInfinityShadowSpotCue>& Cues,
        double PassageSeconds,
        float& OutIntensity);

    /** Whether the FollowLight component is shown. Pure; see ShadowSpotCues. */
    static bool ShouldShowFollowLight(
        bool bEnableFollowLight,
        bool bLive,
        bool bHasShadowSpotCues,
        double ShadowSpotWeight);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<AInfinityStagePassageActor> PassageActor;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage", meta = (Units = "cm"))
    FVector CameraOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage", meta = (Units = "cm"))
    FVector ShadowFigureOffset = FVector(-200.0, 0.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    bool bKeepShadowFiguresWorldUpright = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat")
    bool bEnableShadowCat = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatCastShadow = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatRenderInMainPass = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Rendering")
    bool bShadowCatVisibleInReflections = true;

    /** Extra placement controls exposed on the parent passage camera instance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (Units = "cm"))
    FVector ShadowCatPositionOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement")
    FRotator ShadowCatRotationOffset = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (ClampMin = "0.01", UIMin = "0.1", UIMax = "5.0"))
    double ShadowCatUniformScale = 1.0;

    /** Retained for existing serialized instances; use the direct placement controls for routine adjustment. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Placement", meta = (AdvancedDisplay, DisplayName = "Advanced Relative Transform"))
    FTransform ShadowCatRelativeTransform = FTransform::Identity;

    /** Keep AnimX in its walk gait even when the camera moves faster than a cat would walk. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation")
    bool bShadowCatForceWalk = true;

    /**
     * Play AnimX's authored forward-walk sequence directly. This bypasses the
     * vendor locomotion Blueprint, which can promote camera speeds to trot/run.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation")
    bool bShadowCatUseDirectWalkAnimation = true;

    /** Retained for compatibility with existing saved rig settings. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "1.0", Units = "cm/s"))
    double ShadowCatWalkBlendSpeedCmPerSecond = 120.0;

    /** Camera speed that plays the AnimX walk cycle at 1.0x. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "1.0", Units = "cm/s"))
    double ShadowCatReferenceWalkSpeedCmPerSecond = 250.0;

    /** Time constant for fading the whole gait bob with walking speed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (ClampMin = "0.05", Units = "s", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatBobFadeSeconds = 0.5;

    /** Smoothed share of the reference walk speed applied to this master frame's gait bob. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat|Camera Bob")
    double CurrentShadowCatBobWalkWeight = 0.0;

    /** Fine adjustment applied after converting camera speed to animation play rate. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0", UIMax = "2.0"))
    double ShadowCatAnimationSpeedMultiplier = 0.6;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0"))
    double ShadowCatMinPlayRate = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Animation", meta = (ClampMin = "0.0"))
    double ShadowCatMaxPlayRate = 1.25;

    /**
     * Lift the camera with the cat's gait. The vertical travel of the reference
     * bone against its rest pose, in world centimetres after the cat's scale, is
     * added to the evaluated camera height. The cat itself is counter-offset so
     * its feet stay on the floor. Zero gain disables the effect without losing
     * the settings.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob")
    bool bShadowCatCameraBob = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (ClampMin = "0.0", UIMax = "3.0", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatCameraBobGain = 1.0;

    /** Small roll coupled to the lift's deviation from its running mean. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (UIMin = "-1.0", UIMax = "1.0", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatCameraBobRollDegreesPerCm = 0.12;

    /** Time constant of the raw gait lift's running mean used to centre the roll. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (ClampMin = "0.05", UIMax = "5.0", Units = "s", EditCondition = "bShadowCatCameraBob"))
    double ShadowCatCameraBobRollMeanSeconds = 1.0;

    /**
     * Advances the master-timed gait state and returns the camera offsets for
     * this sample. The first sample, reverse, or a forward jump re-primes at the
     * raw lift with zero weight. Re-evaluating the same master time is read-only.
     */
    static FInfinityGaitBob StepGaitBob(
        FInfinityGaitBobState& State,
        double MasterSeconds,
        double RawLiftCm,
        double SpeedCmPerSecond,
        double ReferenceSpeed,
        double RollMeanSeconds,
        double FadeSeconds,
        double RollDegPerCm,
        double MaxGapSeconds = 0.5);

    /**
     * Fades a gait bob by the crossing settle weight. Height and roll scale
     * together, so a weight of 0 returns exactly no bob and 1 returns the bob
     * unchanged. Pure: the weight is a function of Master time alone.
     */
    static FInfinityGaitBob SettleGaitBob(const FInfinityGaitBob& Bob, double SettleWeight);

    /**
     * Crossing settle (Gary, 30 Sep: "in that moment between passages, we don't
     * need the cat's bob at all"). Over the last CrossingSettleSeconds of the
     * Passage the route speed eases to a stop exactly at the route-end pose the
     * Scene's Entry Handoff camera is matched to, and the gait bob and its roll
     * fade with that speed to exactly 0 there. The last span is renormalized the
     * way SpeedMultiplier already is: same arrival frame and place, slightly
     * faster earlier in the span; pins and keys stay at their absolute frames.
     * A Master-time function, so play, pause, scrub and reverse agree.
     * 0 disables it exactly.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Camera|Crossing Settle",
        meta = (ClampMin = "0.0", UIMax = "5.0", Units = "s"))
    double CrossingSettleSeconds = 3.0;

    /** This master frame's settle share: 1 outside the window, 0 at the Passage end. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Camera|Crossing Settle")
    double CurrentCrossingSettleWeight = 1.0;

    /**
     * CrossingSettleSeconds in Master ticks; 0 when disabled or unresolvable.
     * Every caller of UMovieSceneInfinityPassageSection::EvaluateCamera that
     * must agree with this rig's pose (Camera Pilot anchors, the Cue Desk
     * speed readout) passes this, because the settle renormalizes the whole
     * last span, not only its final second.
     */
    double GetCrossingSettleFrames() const;

    /** Bone whose height carries the gait. AnimX cats have no pelvis; Spine sits over the hips. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage|Shadow Cat|Camera Bob",
        meta = (EditCondition = "bShadowCatCameraBob"))
    FName ShadowCatBobReferenceBone = TEXT("Spine");

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat|Camera Bob", meta = (Units = "cm"))
    double CurrentShadowCatCameraBobCm = 0.0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat", meta = (Units = "cm/s"))
    double CurrentShadowCatCameraSpeedCmPerSecond = 0.0;

    /** Route station distance of the camera at the last evaluated master frame (camera
     * offsets included): the distance the Passage mechanisms were driven by. Read by
     * the Director's HUD for the bay number. */
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage", meta = (Units = "cm"))
    double CurrentCameraDistanceCm = 0.0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "Infinity Stage|Shadow Cat")
    double CurrentShadowCatPlayRate = 0.0;

    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool EvaluateAtMasterFrame(FFrameNumber MasterFrame);

    /**
     * True while this rig is the camera the player is actually looking through,
     * with no blend in flight. In game the shadow cat and the follow light are
     * shown only then, so a rig that is not live never puts its figure into
     * another camera's shot (the Opening's stalls cut, a transition's stalls
     * view). Always true in the editor, where the figures stay visible for
     * authoring.
     */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Shadow Cat")
    bool AreShadowFiguresLive() const { return bShadowFiguresLive; }

    /** Re-reads whether this rig is live and shows or hides its figures. Runs every game tick. */
    void UpdateShadowFigureVisibility();

    /**
     * Hides the camera's editor body (the SM_CineCam proxy) in game, whatever
     * the saved "camera mesh hidden in game" flag says. Four saved rigs had it
     * showing, which put a camera body into other cameras' shots in PIE (the
     * box in the Opening's stalls view, 29 Sep). Called at BeginPlay in game
     * worlds; the editor keeps the body for authoring.
     */
    void HideCameraBodyInGame();

    virtual void Tick(float DeltaSeconds) override;

    virtual void OnConstruction(const FTransform& Transform) override;

    /** Applies the follow-light properties to its component. */
    void ConfigureFollowLight();

    /** Samples the camera transform without changing the Actor or mechanism state. */
    bool GetCameraTransformAtMasterFrame(FFrameNumber MasterFrame, FTransform& OutWorldTransform) const;

    /** Pure endpoint sample used by Scene handoff generation, including managed lens channels. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Camera")
    bool GetCameraViewAtMasterFrame(
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        float& OutFocalLengthMm,
        float& OutFocusDistanceCm) const;

protected:
    virtual void BeginPlay() override;

private:
    FTransform BuildShadowCatRelativeTransform() const;
    void ConfigureShadowCat();
    void ApplyShadowFigureVisibility();

    /**
     * Whether the cat's BODY is drawn. Never in a game world: the camera IS the
     * cat in any passage or curtain view (Gary, 30 Sep: "we are always the cat
     * when in passage or curtain view"), so only its shadow may appear. The
     * editor keeps the body (per bShadowCatRenderInMainPass) for authoring.
     */
    bool ShouldDrawShadowCatBody() const;

    /** Places, lights and shows or hides the FollowLight for the current state. */
    void ApplyFollowLightState();
    float CurrentShadowSpotIntensity = 0.0f;

    /** See AreShadowFiguresLive. Starts true so the editor shows the figures; game worlds re-derive it. */
    bool bShadowFiguresLive = true;
    void DestroyOrphanedShadowCats();
    void UpdateShadowCatAtMasterFrame(
        FFrameNumber MasterFrame,
        const FTransform& CameraTransform,
        const FInfinityCompiledPassage& Passage);
    double CalculateCameraSpeedAtMasterFrame(
        FFrameNumber MasterFrame,
        const FTransform& CameraTransform,
        const FInfinityCompiledPassage& Passage) const;

    /** Current gait lift of the reference bone over its rest pose, in world cm, scaled by the bob gain. */
    double SampleShadowCatGaitLiftCm() const;

    bool bShadowCatBobReported = false;
    FInfinityGaitBobState ShadowCatGaitBobState;

    bool GetCameraStateAtMasterFrame(
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        FInfinityPassageCameraEvaluation& OutEvaluation) const;

    /** As GetCameraStateAtMasterFrame, against a Passage the caller has already compiled. */
    bool GetCameraStateForCompiledPassage(
        const FInfinityCompiledPassage& Passage,
        FFrameNumber MasterFrame,
        FTransform& OutWorldTransform,
        FInfinityPassageCameraEvaluation& OutEvaluation) const;
};
