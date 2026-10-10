#pragma once

#include "CoreMinimal.h"
#include "Curves/CurveFloat.h"
#include "Engine/EngineTypes.h"
#include "Engine/DataAsset.h"
#include "Misc/FrameRate.h"
#include "Sound/SoundBase.h"
#include "InfinityStageEffectTypes.h"
#include "InfinityStageLightDrama.h"
#include "InfinityStageBulbBody.h"
#include "InfinityStageLightMover.h"
#include "InfinityStageMechanismSound.h"
#include "InfinityStageTypes.generated.h"

class ULevelSequence;
class UAnimSequence;
class UInfinityStageMusicMapAsset;
class UMaterialInterface;
class UStaticMesh;

UENUM(BlueprintType)
enum class EInfinityShadowCatCameraMode : uint8
{
    Route,
    HeadPOV
};

UENUM(BlueprintType)
enum class EInfinityShadowCatBodyVisibility : uint8
{
    ShadowOnly,
    POVBody,
    ReflectionOnly
};
class UTexture;
class UTextureLightProfile;

UENUM(BlueprintType)
enum class EInfinityCueType : uint8
{
    WingPair,
    Scene,
    Sequence
};

UENUM(BlueprintType)
enum class EInfinityMusicBindingMode : uint8
{
    Start,
    Continue,
    Silence,
    ExplicitCrossfade
};

/**
 * Who drives the camera during a segment.
 *
 * Authored in the Show so the score records it, rather than living as a setting
 * on whichever actor happens to carry the telemetry component. The dog is not
 * always present, so Timeline must always remain a valid fallback.
 */
UENUM(BlueprintType)
enum class EInfinityCameraOwner : uint8
{
    /** Master sequence channels and the route drive the camera. */
    Timeline,
    /** Free look: stick deflection is a turn rate, so the view can keep turning
     * and circle the scene. Maps to the receiver's Velocity rotation mode. */
    DogFreeLook,
    /** Gaze-limited: stick deflection is an angle within the authored range and
     * centring returns to centre. Maps to the receiver's Absolute mode, which is
     * correct when the view maps to a physical screen at a known distance. */
    DogGazeOnly
};

/**
 * Optional show-curtain behavior for a non-Wing cue.
 *
 * These values describe the transition phase in the compiled Show. A cue can
 * either use the backwards-compatible automatic curtain or author the visible
 * rig and motion directly inside its Level Sequence.
 */
UENUM(BlueprintType)
enum class EInfinityCurtainCueMode : uint8
{
    None,
    /** Begin closed, hold, then reveal the first Passage. */
    OpeningReveal,
    /** Lower over the preceding Scene, hold for shadow play, then lift. */
    PostSceneInterstitial,
    /** Lower over the final Scene and remain closed. */
    ClosingCover
};

UENUM(BlueprintType)
enum class EInfinityExternalSoundAuthority : uint8
{
    None,
    DeclaredControllable,
    DeclaredUnpausable
};

UENUM(BlueprintType)
enum class EInfinityMotionPlaybackMode : uint8
{
    Static,
    OneShot,
    ContinuousLoop,
    BoundedLoop,
    CameraGust
};

UENUM(BlueprintType)
enum class EInfinityMotionPhaseOrigin : uint8
{
    PassageStart,
    PassFrame,
    ExplicitFrame
};

UENUM(BlueprintType)
enum class EInfinityCameraGustDirection : uint8
{
    NearestToFarthest UMETA(DisplayName = "Nearest to Farthest"),
    FarthestToNearest UMETA(DisplayName = "Farthest to Nearest")
};

/** Both policies remain open during forward Passage playback; they differ only
 * in how explicitly the author regards the Passage boundary as the reset point. */
UENUM(BlueprintType)
enum class EInfinityCameraGustHoldOpenPolicy : uint8
{
    HoldOpenThroughPassage UMETA(DisplayName = "Hold Open Through Passage"),
    HoldOpenUntilRewound UMETA(DisplayName = "Hold Open Until Rewound")
};

UENUM(BlueprintType)
enum class EInfinityCameraGustTriggerOffsetUnit : uint8
{
    Pairs UMETA(DisplayName = "Pairs Ahead of Camera"),
    Metres UMETA(DisplayName = "Metres Ahead of Camera"),
    Seconds UMETA(DisplayName = "Seconds Before Nearest Pair")
};

UENUM(BlueprintType)
enum class EInfinityCameraGustTimingMode : uint8
{
    CameraTravelWindow UMETA(DisplayName = "Follow Camera / Music Rail"),
    TimedCascade UMETA(DisplayName = "Advanced Timed Cascade")
};


/** What a cue-anchored attachment is for. Kind drives which fields matter and
 * how the editor presents it; placement is identical for all of them. */
UENUM(BlueprintType)
enum class EInfinityAttachmentKind : uint8
{
    Prop,
    Light,
    AnimationTrigger,
    Sound,
    Effect
};

/** Whether an attachment rides a moving panel or stays at the fixed station. */
UENUM(BlueprintType)
enum class EInfinityAttachmentAnchor : uint8
{
    /** Fixed at the pair's spline station; wings move past it. */
    Station,
    /** Rides the Left panel, including its inward travel. */
    LeftPanel,
    RightPanel,
    TopPanel,
    /** Midpoint between the Left and Right panels, so it closes in as they do. */
    PairCentre
};

/** Native Unreal light created when a Light attachment has no custom Actor Class. */
UENUM(BlueprintType)
enum class EInfinityStageLightType : uint8
{
    Spot UMETA(DisplayName = "Spot Light"),
    Rect UMETA(DisplayName = "Rect Light"),
    Point UMETA(DisplayName = "Point Light")
};

/** Serialized independently from UE's engine enum so Show assets remain explicit. */
UENUM(BlueprintType)
enum class EInfinityStageLightIntensityUnits : uint8
{
    Unitless,
    Candelas,
    Lumens,
    EV UMETA(DisplayName = "Exposure Value (EV)"),
    Nits
};

/**
 * Persistent, type-aware settings for a cue-anchored native light.
 *
 * The common controls are applied to every supported light type. Point/Spot and
 * Rect groups are retained together so an artist can change Type without losing
 * the settings they had already tuned for another fixture. A custom ActorClass
 * on the owning attachment remains an escape hatch; these settings are applied
 * to the first Light Component found on that actor.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageLightSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    EInfinityStageLightType Type = EInfinityStageLightType::Spot;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    EInfinityStageLightIntensityUnits IntensityUnits = EInfinityStageLightIntensityUnits::Lumens;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common", meta = (ClampMin = "0.0"))
    float Intensity = 5000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    FLinearColor Color = FLinearColor::White;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    bool bUseTemperature = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common",
        meta = (ClampMin = "1000.0", ClampMax = "15000.0", Units = "K", EditCondition = "bUseTemperature"))
    float TemperatureKelvin = 6500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common",
        meta = (ClampMin = "0.0", Units = "cm"))
    float AttenuationRadiusCm = 5000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common", meta = (ClampMin = "0.0"))
    float IndirectLightingIntensity = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common", meta = (ClampMin = "0.0"))
    float VolumetricScatteringIntensity = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common", meta = (ClampMin = "0.0"))
    float DiffuseScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common", meta = (ClampMin = "0.0"))
    float SpecularScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    bool bAffectTranslucentLighting = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Common")
    bool bTransmission = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bCastShadows = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bCastVolumetricShadow = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bAffectReflection = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bAffectGlobalIllumination = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float ShadowBias = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float ShadowSlopeBias = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bForceCachedShadowsForMovablePrimitives = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Shadows")
    bool bUseRayTracedDistanceFieldShadows = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Channels")
    bool bLightingChannel0 = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Channels")
    bool bLightingChannel1 = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Channels")
    bool bLightingChannel2 = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Culling",
        meta = (ClampMin = "0.0", Units = "cm"))
    float MaxDrawDistanceCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Culling",
        meta = (ClampMin = "0.0", Units = "cm"))
    float MaxDistanceFadeRangeCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot")
    bool bUseInverseSquaredFalloff = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot",
        meta = (ClampMin = "2.0", ClampMax = "16.0", EditCondition = "!bUseInverseSquaredFalloff"))
    float LightFalloffExponent = 8.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float InverseExposureBlend = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot",
        meta = (ClampMin = "0.0", Units = "cm"))
    float SourceRadiusCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot",
        meta = (ClampMin = "0.0", Units = "cm"))
    float SoftSourceRadiusCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Point and Spot",
        meta = (ClampMin = "0.0", Units = "cm"))
    float SourceLengthCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Spot",
        meta = (ClampMin = "0.0", ClampMax = "89.0", Units = "deg",
            EditCondition = "Type == EInfinityStageLightType::Spot", EditConditionHides))
    float InnerConeAngleDegrees = 18.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Spot",
        meta = (ClampMin = "1.0", ClampMax = "89.0", Units = "deg",
            EditCondition = "Type == EInfinityStageLightType::Spot", EditConditionHides))
    float OuterConeAngleDegrees = 42.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Rect",
        meta = (ClampMin = "0.1", Units = "cm",
            EditCondition = "Type == EInfinityStageLightType::Rect", EditConditionHides))
    float RectSourceWidthCm = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Rect",
        meta = (ClampMin = "0.1", Units = "cm",
            EditCondition = "Type == EInfinityStageLightType::Rect", EditConditionHides))
    float RectSourceHeightCm = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Rect",
        meta = (ClampMin = "0.0", ClampMax = "90.0", Units = "deg",
            EditCondition = "Type == EInfinityStageLightType::Rect", EditConditionHides))
    float RectBarnDoorAngleDegrees = 88.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Rect",
        meta = (ClampMin = "0.0", Units = "cm",
            EditCondition = "Type == EInfinityStageLightType::Rect", EditConditionHides))
    float RectBarnDoorLengthCm = 20.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Rect",
        meta = (EditCondition = "Type == EInfinityStageLightType::Rect", EditConditionHides))
    TSoftObjectPtr<UTexture> RectSourceTexture;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Photometric")
    TSoftObjectPtr<UTextureLightProfile> IESTexture;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Photometric")
    bool bUseIESBrightness = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Photometric",
        meta = (ClampMin = "0.0", EditCondition = "bUseIESBrightness"))
    float IESBrightnessScale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Function")
    TSoftObjectPtr<UMaterialInterface> LightFunctionMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Function")
    FVector LightFunctionScale = FVector::OneVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Function",
        meta = (ClampMin = "0.0", Units = "cm"))
    float LightFunctionFadeDistanceCm = 100000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Function", meta = (ClampMin = "0.0"))
    float LightFunctionDisabledBrightness = 0.0f;

    /** Strike on approach and slow moves. Evaluated in game worlds only; the
     * editor always shows authored values. See InfinityStageLightDrama.h. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Drama", meta = (ShowOnlyInnerProperties))
    FInfinityStageLightDrama Drama;
};

/**
 * Stage content anchored to a Wing Pair cue rather than to world space.
 *
 * Props, lights, triggers and mechanism sounds all previously had the same
 * failure: placed against world position or absolute time, they were silently
 * destroyed whenever a music change re-timed the Show or re-spaced the wings.
 * Anchoring to a stable CueGuid with a relative transform means the existing
 * materialization pass re-places them correctly for free.
 */
/** How a mechanism sound is chosen from the set for a given wing. */
UENUM(BlueprintType)
enum class EInfinityMechanismSoundPolicy : uint8
{
    /** Cycle through the set by cue ordinal. */
    RoundRobin,
    /** Pseudo-random, seeded from the cue identity so it never changes on replay. */
    StableRandom,
    /** Faster mechanisms pick later entries, so the set can be ordered by effort. */
    ByCycleRate
};

/**
 * Wheeling, squeaking and creaking for wing movement.
 *
 * Timing is never authored here: it is derived from the mechanism data that
 * already says when a pair moves and how fast, so re-timing the music re-times
 * the squeaks with it. Authoring the times separately would create exactly the
 * stale-snapshot problem the attachment system exists to avoid.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMechanismSoundSet
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    bool bEnabled = false;

    /** Bucket of movement sounds. One is chosen per wing by the policy below. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    TArray<TSoftObjectPtr<USoundBase>> Sounds;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    EInfinityMechanismSoundPolicy Policy = EInfinityMechanismSoundPolicy::StableRandom;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.0", ClampMax = "4.0"))
    float Gain = 1.0f;

    /** Only wings within this distance of the camera are voiced, so a Passage of
     * hundreds of pairs costs a handful of sounds rather than hundreds. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.0", Units = "cm"))
    double AudibleRadiusCm = 4000.0;

    /** Minimum normalized travel change that counts as the mechanism starting to
     * move, so a nearly-static wing stays silent. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound",
        meta = (ClampMin = "0.001", ClampMax = "1.0"))
    double MovementThreshold = 0.02;

    /** Silence every pair's authored phase Sound Cues (Mechanism > Sound Cues)
     * in this Passage, independently of the movement set above. Off by default. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    bool bMuteSoundCues = false;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityCueAttachment
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid AttachmentGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    FText Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    EInfinityAttachmentKind Kind = EInfinityAttachmentKind::Prop;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    bool bEnabled = true;

    /** Optional placed-actor override. Light attachments may leave this empty:
     * a native actor is then created from Lighting.Type. A custom light actor
     * receives the same persistent settings on its first Light Component. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    TSoftClassPtr<AActor> ActorClass;

    /** Simple mesh props need no Blueprint. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    TSoftObjectPtr<UStaticMesh> Mesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    EInfinityAttachmentAnchor Anchor = EInfinityAttachmentAnchor::Station;

    /** Offset from the resolved anchor. Editing in the viewport writes this
     * back, so later spacing or timing changes carry the attachment along. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Attachment")
    FTransform RelativeTransform = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Lighting",
        meta = (ShowOnlyInnerProperties,
            EditCondition = "Kind == EInfinityAttachmentKind::Light", EditConditionHides))
    FInfinityStageLightSettings Lighting;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect",
        meta = (ShowOnlyInnerProperties,
            EditCondition = "Kind == EInfinityAttachmentKind::Effect", EditConditionHides))
    FInfinityStageEffectSettings Effect;

    /** AnimationTrigger: fires when the evaluated camera is this close, in cm.
     * Distance rather than time, so retiming cannot desynchronise it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Trigger",
        meta = (ClampMin = "0.0", Units = "cm",
            EditCondition = "Kind == EInfinityAttachmentKind::AnimationTrigger", EditConditionHides))
    double TriggerDistanceCm = 800.0;

    /** A bulb's glass (a mesh prop) follows its light's evaluated brightness, with
     * an optional flicker of its own (Stable / Slight / Fail). Off by default, so
     * existing attachments are unchanged. Game worlds only. See InfinityStageBulbBody.h. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body")
    FInfinityBulbBodySettings Body;

    /** Light attachments: a club "mover" routine - seeded, rapid, jolting yaw/pitch
     * steps that start calm and turn haywire. Off by default. Game worlds only;
     * Station anchor only. See InfinityStageLightMover.h. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light|Mover",
        meta = (EditCondition = "Kind == EInfinityAttachmentKind::Light", EditConditionHides))
    FInfinityLightMoverSettings Mover;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityCameraGustSettings
{
    GENERATED_BODY()

    /** The default is spatial: music drives the camera and the camera drives the reveal. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (DisplayName = "Reveal Timing"))
    EInfinityCameraGustTimingMode TimingMode = EInfinityCameraGustTimingMode::CameraTravelWindow;

    /** Number of fully revealed pairs immediately ahead of the evaluated camera position. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "1", DisplayName = "Reveal Ahead / Fan Depth (Pairs)"))
    int32 FanDepthPairs = 6;

    /** Spatial softness of the leading edge. At constant speed, duration follows camera speed automatically. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "0.01", DisplayName = "Opening Ramp (Pair Spacing)",
            EditCondition = "TimingMode == EInfinityCameraGustTimingMode::CameraTravelWindow", EditConditionHides))
    double OpeningSpanPairs = 0.25;

    /** Legacy/advanced clock-domain fan controls. Hidden for the camera-led reveal. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "0.01", Units = "s", DisplayName = "Total Cascade Duration",
            AdvancedDisplay, EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    double CascadeDurationSeconds = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "0.01", Units = "s", DisplayName = "Individual Pair Opening Duration",
            AdvancedDisplay, EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    double PairOpeningDurationSeconds = 0.45;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "0.0", Units = "s", DisplayName = "Pair Stagger / Delay",
            AdvancedDisplay, EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    double PairStaggerSeconds = 0.10;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (AdvancedDisplay, EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    EInfinityCameraGustDirection Direction = EInfinityCameraGustDirection::NearestToFarthest;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (DisplayName = "After Opening", AdvancedDisplay))
    EInfinityCameraGustHoldOpenPolicy HoldOpenPolicy = EInfinityCameraGustHoldOpenPolicy::HoldOpenThroughPassage;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (DisplayName = "Trigger Offset Unit", AdvancedDisplay,
            EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    EInfinityCameraGustTriggerOffsetUnit TriggerOffsetUnit = EInfinityCameraGustTriggerOffsetUnit::Pairs;

    /** Positive values trigger while the camera is still behind the group's nearest pair. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ClampMin = "0.0", DisplayName = "Trigger Offset", AdvancedDisplay,
            EditCondition = "TimingMode == EInfinityCameraGustTimingMode::TimedCascade", EditConditionHides))
    double TriggerOffset = 1.0;

    /** Stable group identity: the first/nearest selected cue, never a transient gameplay token. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera Gust / Fan Reveal", meta = (AdvancedDisplay))
    FGuid GroupAnchorCueGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera Gust / Fan Reveal", meta = (AdvancedDisplay))
    int32 GroupOrdinal = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera Gust / Fan Reveal", meta = (AdvancedDisplay))
    int32 GroupSize = 1;
};

/** Asset handedness and route-side placement are deliberately separate. AutoByRole
 * rotates an explicitly RightArchitectural library asset around stage up; it never
 * applies a negative scale or mirrors the photographed image. */
UENUM(BlueprintType)
enum class EInfinityPanelFacingPolicy : uint8
{
    AutoByRole,
    PreserveAsset,
    Rotate180AroundUp
};

UENUM(BlueprintType)
enum class EInfinityMechanismKind : uint8
{
    Slide,
    /** Applies to side panels; Top panels retain Slide behaviour. */
    Topple,
    /** Applies to side panels; Top panels retain Slide behaviour. */
    Turn,
    /** Applies to side and Top panels. */
    Trap
};

UENUM(BlueprintType)
enum class EInfinityPassageFitMode : uint8
{
    MusicLockedDeriveCount,
    MusicAndCountLockedSolveCameraSpeed,
    ManualPassage
};

UENUM(BlueprintType, meta = (Bitflags))
enum class EInfinityLocalOverride : uint8
{
    None = 0 UMETA(Hidden),
    IntervalToNext = 1 << 0,
    GapToNext = 1 << 1,
    MechanismRate = 1 << 2,
    /** Keep this row's authored phase offset when its Passage uses a live
     * ordinal-based movement pattern. */
    MechanismPhase = 1 << 3
};
ENUM_CLASS_FLAGS(EInfinityLocalOverride)

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityPanelDesign
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    TSoftObjectPtr<UStaticMesh> Mesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    TArray<TSoftObjectPtr<UMaterialInterface>> MaterialOverrides;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    FTransform LocalTransform = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    EInfinityPanelFacingPolicy FacingPolicy = EInfinityPanelFacingPolicy::AutoByRole;

    /** Mirrors the visible photograph across the panel's local horizontal axis.
     * This is an explicit artist decision and is independent of route side and
     * front/back facing. It never modifies the source mesh or texture asset. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Image Orientation",
        meta = (DisplayName = "Flip Image Horizontally"))
    bool bFlipImageHorizontally = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    bool bCastShadow = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    bool bVisibleInMainPass = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panel")
    TEnumAsByte<ECollisionEnabled::Type> Collision = ECollisionEnabled::NoCollision;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMechanismMotion
{
    GENERATED_BODY()

    /** How the normalized motion curve moves each panel. Slide preserves the legacy behaviour.
     * Top panels treat Topple and Turn as Slide; Trap still applies. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism",
        meta = (ToolTip = "How the normalized motion curve moves each panel. Top panels treat Topple and Turn as Slide; Trap still applies."))
    EInfinityMechanismKind Kind = EInfinityMechanismKind::Slide;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    EInfinityMotionPlaybackMode PlaybackMode = EInfinityMotionPlaybackMode::ContinuousLoop;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism", meta = (ClampMin = "0.0", Units = "Hz"))
    double CycleRateHz = 0.25;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    EInfinityMotionPhaseOrigin PhaseOrigin = EInfinityMotionPhaseOrigin::PassageStart;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    FFrameNumber ExplicitOriginFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    double PhaseOffsetCycles = 0.0;

    /** Slide distance along the inward axis. Trap distance along the panel's
     * base-rotation world up axis; positive rises and negative sinks. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism", meta = (Units = "cm"))
    double InwardTravelCm = 100.0;

    /** Topple or Turn angle at normalized progress 1. For Topple, positive =
     * toward the camera (downstage); negative = away from the camera. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism",
        meta = (Units = "deg", ToolTip = "Topple or Turn angle at normalized progress 1. For Topple, positive = toward the camera (downstage); negative = away from the camera."))
    double MaxAngleDeg = 90.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    FRuntimeFloatCurve LeftNormalizedCurve;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    FRuntimeFloatCurve RightNormalizedCurve;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    FRuntimeFloatCurve TopNormalizedCurve;

    /**
     * Whether the Top panel takes part in this pair's mechanism.
     *
     * On, the Top uses its own curve, falling back to the Left curve when a
     * movement preset did not author one — so a side-only preset can still drive
     * the ceiling. Off, the Top holds at its rest position whatever is authored.
     *
     * Defaults on, which leaves existing content unchanged: a preset that left
     * the Top curve flat still produces no ceiling movement.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism",
        meta = (DisplayName = "Top Follows Wing Movement"))
    bool bTopFollowsMechanism = true;

    /**
     * Sounds placed on this motion's phase (0..1 of the OneShot, or of each loop
     * cycle), e.g. a slam where a toppling wing meets the floor or its neighbour.
     * Because they ride the phase, a re-time moves them with the motion; they are
     * never Master keys. Game/PIE worlds only, forward playback only. Empty by
     * default, which leaves the pair silent. See InfinityStageMechanismSound.h.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    TArray<FInfinityMechanismSoundCue> SoundCues;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Gust / Fan Reveal",
        meta = (ShowOnlyInnerProperties, EditCondition = "PlaybackMode == EInfinityMotionPlaybackMode::CameraGust", EditConditionHides))
    FInfinityCameraGustSettings CameraGust;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityWingOccurrence
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid OccurrenceGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panels")
    FInfinityPanelDesign Left;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panels")
    FInfinityPanelDesign Right;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panels")
    bool bHasTop = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Panels", meta = (EditCondition = "bHasTop"))
    FInfinityPanelDesign Top;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "1"))
    FFrameNumber IntervalToNext = 48000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout", meta = (ClampMin = "0.01", Units = "cm"))
    double GapToNextCm = 500.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout")
    FTransform OccurrenceOffset = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism")
    FInfinityMechanismMotion Mechanism;

    /** Silence this pair's mechanism sound without disabling the Passage set. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    bool bMuteMechanismSound = false;

    /** Lights, props, triggers and sounds anchored to this pair. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Stage Content")
    TArray<FInfinityCueAttachment> Attachments;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Overrides", meta = (Bitmask, BitmaskEnum = "/Script/InfinityStage.EInfinityLocalOverride"))
    int32 LocalOverrideMask = 0;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityMusicRail
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid RailGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FText Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    TSoftObjectPtr<USoundBase> Sound;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FFrameNumber SourceInFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FFrameNumber SourceOutFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music", meta = (ClampMin = "0"))
    FFrameNumber FadeInFrames = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music", meta = (ClampMin = "0"))
    FFrameNumber FadeOutFrames = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Music")
    FString SourceFingerprint;

    /** Versioned, reviewable proposals. This reference never applies edits to the Cue Score. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music Analysis")
    TSoftObjectPtr<UInfinityStageMusicMapAsset> AnalysisMap;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinitySectionMusicBinding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    EInfinityMusicBindingMode Mode = EInfinityMusicBindingMode::Silence;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FGuid PrimaryRailGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music", meta = (EditCondition = "Mode == EInfinityMusicBindingMode::ExplicitCrossfade"))
    FGuid SecondaryRailGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FFrameNumber RailOffsetFrames = 0;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinitySceneCueData
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene")
    TSoftObjectPtr<ULevelSequence> Sequence;

    /**
     * Take the Scene's length from its own Level Sequence playback range instead
     * of the authored Duration Frames.
     *
     * A Scene is a fixed set piece with no Wing Pair structure, so its sequence
     * already defines how long it is; keeping a second hand-entered number in
     * step is the same stale-snapshot trap as the handoff cameras. Defaults off
     * so existing Shows keep their authored timing until opted in.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene",
        meta = (DisplayName = "Use Sequence Length"))
    bool bUseSequenceLength = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene", meta = (ClampMin = "1", EditCondition = "!bUseSequenceLength"))
    FFrameNumber DurationFrames = 24000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene")
    EInfinityExternalSoundAuthority ExternalSound = EInfinityExternalSoundAuthority::None;

    /** Who drives the camera during this Scene. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
    EInfinityCameraOwner CameraOwner = EInfinityCameraOwner::Timeline;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene")
    FInfinitySectionMusicBinding Music;

    /** Length of the final Scene camera shot reserved for a matched handback to the next Passage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Handoff", meta = (ClampMin = "1"))
    FFrameNumber ExitHandoffHoldFrames = 24000;

    /**
     * Keep the camera from the preceding segment for this cue.
     *
     * Post-Scene interstitials use this so the curtain lowers over the last
     * authored Scene shot instead of cutting early to the next Passage camera.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Handoff")
    bool bRetainPreviousCamera = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain")
    EInfinityCurtainCueMode CurtainMode = EInfinityCurtainCueMode::None;

    /**
     * Let this cue's Level Sequence own the visible curtain rig and motion.
     *
     * The Show Root will not create or evaluate its legacy global curtain for
     * this cue. The sequence can therefore contain one authored Curtain Rig
     * Blueprint with its own geometry, cloth, materials, light, VFX and audio.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain",
        meta = (DisplayName = "Sequence Owns Curtain"))
    bool bSequenceOwnsCurtain = false;

    /**
     * Once the entry transition is fully covered, evaluate the following
     * Passage at its first frame. Reverse and direct seeks restore the previous
     * Scene camera before this threshold. An explicit Camera Cut in this cue's
     * sequence takes precedence over the automatic handoff.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Handoff",
        meta = (DisplayName = "Reveal Next Passage When Covered",
            EditCondition = "bRetainPreviousCamera && CurtainMode == EInfinityCurtainCueMode::PostSceneInterstitial", EditConditionHides))
    bool bRevealNextPassageWhenCovered = false;

    /** Time spent moving from open to closed at cue entry. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (ClampMin = "0"))
    FFrameNumber CurtainEntryTransitionFrames = 48000;

    /** Time intended to stay fully closed for the boy/cat performance and
     * hidden scene change. Sequence-owned cues can place an
     * InfinityStage.HiddenChangeover marker inside this interval; otherwise
     * the handoff occurs at the end of entry + hold. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (ClampMin = "0"))
    FFrameNumber CurtainHoldFrames = 240000;

    /** Time spent moving from closed to open before the cue ends. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Curtain", meta = (ClampMin = "0"))
    FFrameNumber CurtainExitTransitionFrames = 48000;
};

/** Passage-level storytelling control for accelerated day/night time. The
 * celestial rig integrates these rates from absolute Master frames, so normal
 * playback, rate changes, reverse and scrubbing all resolve to the same sky. */
USTRUCT(BlueprintType, meta = (DisplayName = "Passage Temporality"))
struct INFINITYSTAGE_API FInfinityCelestialCycleSettings
{
    GENERATED_BODY()

    /** When disabled, the sun, moon and stars hold at the Passage entry phase. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Temporality",
        meta = (DisplayName = "Animate Time of Day"))
    bool bAnimate = true;

    /** Real show seconds taken by one complete sunrise-to-sunrise cycle at 1x. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Temporality",
        meta = (ClampMin = "0.01", UIMin = "1.0", Units = "s", DisplayName = "Seconds Per Day/Night Cycle"))
    double CycleDurationSeconds = 20.0;

    /** Per-Passage time-compression control. A value of 10 makes ten apparent
     * days pass in the time that normally produces one day/night cycle. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Temporality",
        meta = (ClampMin = "0.0", UIMin = "0.0", UIMax = "100.0", DisplayName = "Passage Temporality Rate"))
    double CycleRateMultiplier = 1.0;

    /** Intentional time jump applied on entry. One whole cycle preserves the
     * visible time of day; 0.5 jumps from day to night or night to day. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Temporality",
        meta = (DisplayName = "Entry Time Jump (Days)"))
    double EntryPhaseOffsetCycles = 0.0;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityShowCue
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid CueGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue")
    EInfinityCueType Type = EInfinityCueType::WingPair;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue")
    FText Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue")
    bool bEnabled = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cue")
    TArray<FName> Tags;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wing Pair", meta = (EditCondition = "Type == EInfinityCueType::WingPair", EditConditionHides))
    FInfinityWingOccurrence WingPair;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Scene", meta = (EditCondition = "Type != EInfinityCueType::WingPair", EditConditionHides))
    FInfinitySceneCueData Scene;
};

/**
 * One scripted shadow-cat action, timed relative to its owning Passage.
 * StartFrame uses the Show's tick resolution; it therefore moves with the
 * Passage when the managed Master is rebuilt or earlier material is retimed.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityShadowCatAction
{
    GENERATED_BODY()

    /** Animation on the AnimX cat skeleton. Leave empty as a slot for a not-yet-authored clip (for example Arch). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action")
    TSoftObjectPtr<UAnimSequence> Animation;

    /** Route leaves the scored Passage camera alone; HeadPOV follows the posed cat head in Master time. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action|POV")
    EInfinityShadowCatCameraMode CameraMode = EInfinityShadowCatCameraMode::Route;

    /** ShadowOnly is the legacy game view; POVBody exposes paws/body; ReflectionOnly is capture-oriented. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action|POV")
    EInfinityShadowCatBodyVisibility BodyVisibility = EInfinityShadowCatBodyVisibility::ShadowOnly;

    /** AnimX bone used as the HeadPOV origin. Binary asset strings prove Head exists. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action|POV")
    FName HeadPOVBone = TEXT("Head");

    /** Creative/rehearsal knob: camera offset in the head bone's local space. Positive X is forward. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action|POV", meta = (Units = "cm"))
    FVector HeadPOVOffsetCm = FVector(12.0, 0.0, 3.0);

    /** Start in Show ticks after this Passage's compiled segment start. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action", meta = (ClampMin = "0"))
    FFrameNumber StartFrame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action", meta = (ClampMin = "0.01", UIMax = "3.0"))
    double PlayRate = 1.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action", meta = (ClampMin = "0.0", Units = "s"))
    double BlendInSeconds = 0.25;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action", meta = (ClampMin = "0.0", Units = "s"))
    double BlendOutSeconds = 0.25;

    /** Hold the clip's last pose until the Passage ends; otherwise blend back to the gait at the clip end. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action")
    bool bHoldLastFrame = false;

    /** Rehearsal note only; not evaluated. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Action")
    FString Label;
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityPassageSettings
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Identity")
    FGuid PassageGuid;

    /** Who drives the camera through this Passage. Timeline is the safe default:
     * the dog is not always connected, and the show must run without him. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera")
    EInfinityCameraOwner CameraOwner = EInfinityCameraOwner::Timeline;

    /** Wing mechanism sound effects for this Passage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Mechanism Sound")
    FInfinityMechanismSoundSet MechanismSound;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Passage")
    FText Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Range")
    FGuid FirstCueGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Range")
    FGuid LastCueGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "0"))
    FFrameNumber LeadInFrames = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Timing", meta = (ClampMin = "0"))
    FFrameNumber TailFrames = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout", meta = (ClampMin = "0.0", Units = "cm"))
    double LeadInDistanceCm = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Layout", meta = (ClampMin = "0.0", Units = "cm"))
    double TailDistanceCm = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera", meta = (ClampMin = "0.01", Units = "cm/s"))
    double PreferredCameraSpeedCmPerSecond = 250.0;

    /** Hand-directed lights, sound and effects for this Passage. The Master rebuild
     * nests it over the Passage segment with 0:00 at the Passage start, so its keys
     * travel with the Passage on retime. Empty: nothing is nested. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Choreography")
    TSoftObjectPtr<ULevelSequence> Choreography;

    /**
     * Scripted cat poses for this Passage. Relative frames are Show authority,
     * so rehearsal may move WHEN an action happens without editing the camera
     * rig, the managed Master, or any other Passage.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shadow Cat Actions")
    TArray<FInfinityShadowCatAction> ShadowCatActions;

    /** When enabled, Continuous Loop rows derive their phase from their current
     * order in this Passage. Reordering rows therefore immediately preserves the
     * travelling wave without reapplying a preset. A row can opt out with its
     * Mechanism Phase local-override flag. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wing Movement",
        meta = (DisplayName = "Live Phase Pattern From Cue Order"))
    bool bUseLiveMechanismPhasePattern = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wing Movement",
        meta = (DisplayName = "Phase Step Per Wing Pair (Cycles)",
            EditCondition = "bUseLiveMechanismPhasePattern", EditConditionHides))
    double MechanismPhaseStepCycles = -0.10;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wing Movement",
        meta = (DisplayName = "Passage Phase Offset (Cycles)",
            EditCondition = "bUseLiveMechanismPhasePattern", EditConditionHides))
    double MechanismPhaseOffsetCycles = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fit")
    EInfinityPassageFitMode FitMode = EInfinityPassageFitMode::MusicLockedDeriveCount;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fit", meta = (ClampMin = "0.01", Units = "cm"))
    double PreferredSpacingCm = 500.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Music")
    FInfinitySectionMusicBinding Music;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Temporality",
        meta = (ShowOnlyInnerProperties, DisplayName = "Temporality"))
    FInfinityCelestialCycleSettings CelestialCycle;
};
