#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageSweepLight.generated.h"

class AInfinityStageShowRoot;
class ULocalLightComponent;
class UMaterialInterface;
class URectLightComponent;
class USpotLightComponent;

UENUM(BlueprintType)
enum class EInfinityStageSweepShape : uint8
{
    Spot,
    Rect
};

/**
 * "Window car light" (Gary, 5 Oct): a shadow-casting lamp outside the wing line that
 * travels along a path, so the light through the wing gaps slides, stretches, skews and
 * is cut by wing edges. All of that comes from the lamp's movement; nothing else moves.
 *
 * Copies the Strobe's model: in game worlds the time comes from the Show's Master clock
 * (so a pause or a scrub holds or moves the car exactly), and in the editor viewport it
 * free-runs on wall-clock time as a preview only. The light components are TRANSIENT and
 * driven with runtime setters, so a level save never stores a mid-pass light and the
 * preview never dirties the level.
 *
 * The path is in actor-local space: place and rotate the actor, then tune Start/End.
 */
UCLASS(Blueprintable, ClassGroup = "Infinity Stage", meta = (DisplayName = "Infinity Stage Sweep Light"))
class INFINITYSTAGE_API AInfinityStageSweepLight : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageSweepLight();

    /** Driven every frame (also in the editor preview), so TRANSIENT: never saved. */
    UPROPERTY(VisibleAnywhere, Transient, BlueprintReadOnly, Category = "Sweep")
    TObjectPtr<USpotLightComponent> SpotLight;

    /** Used instead of the spot when Shape is Rect. Also TRANSIENT. */
    UPROPERTY(VisibleAnywhere, Transient, BlueprintReadOnly, Category = "Sweep")
    TObjectPtr<URectLightComponent> RectLight;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep")
    bool bSweepEnabled = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep")
    EInfinityStageSweepShape Shape = EInfinityStageSweepShape::Spot;

    // ---- Path (actor-local) ------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Path", meta = (MakeEditWidget = true))
    FVector StartOffset = FVector(0.0, -800.0, 0.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Path", meta = (MakeEditWidget = true))
    FVector EndOffset = FVector(0.0, 800.0, 0.0);

    /** Off: a straight line. On: a quadratic Bezier through ArcControlOffset's pull ("curving off"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Path")
    bool bCurvedPath = false;

    /** Bezier control point. The curve does not pass through it: at mid-pass the lamp is at
     * 0.25 Start + 0.5 Control + 0.25 End. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Path", meta = (MakeEditWidget = true, EditCondition = "bCurvedPath"))
    FVector ArcControlOffset = FVector(400.0, 0.0, 0.0);

    /** Off: the lamp keeps the actor's rotation (aims along actor +X). On: it looks at AimTargetLocal. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Path")
    bool bAimAtTarget = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Path", meta = (MakeEditWidget = true, EditCondition = "bAimAtTarget"))
    FVector AimTargetLocal = FVector(1000.0, 0.0, 0.0);

    // ---- Timing --------------------------------------------------------------------

    /** Time from the time origin to the first pass. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing", meta = (ClampMin = "0.0", Units = "s"))
    float StartDelaySeconds = 0.0f;

    /** One pass, Start to End. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing", meta = (ClampMin = "0.05", Units = "s"))
    float TravelSeconds = 4.0f;

    /** A new pass starts this long after the last one started (never sooner than TravelSeconds,
     * so passes never overlap). Zero or less: a single pass. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing", meta = (Units = "s"))
    float RepeatEverySeconds = 9.0f;

    /** Each gap gets an extra 0..Jitter seconds, from a stream seeded by RandomSeed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing", meta = (ClampMin = "0.0", Units = "s"))
    float RepeatJitterSeconds = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing")
    int32 RandomSeed = 1;

    /** On: every other pass runs End to Start (traffic both ways). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing")
    bool bPingPong = false;

    /** On (default): time counts from the start of the current Show segment, so StartDelay is
     * "seconds into this Passage". Off: absolute Master seconds. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing")
    bool bTimeFromSegmentStart = true;

    /** Run only inside these segments (Passage or Scene/Sequence cue GUIDs). Empty: everywhere. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Timing")
    TArray<FGuid> ActiveSegmentGuids;

    // ---- Envelope and look -----------------------------------------------------------

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light", meta = (ClampMin = "0.0", Units = "s"))
    float FadeInSeconds = 0.8f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light", meta = (ClampMin = "0.0", Units = "s"))
    float FadeOutSeconds = 0.8f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Light", meta = (ClampMin = "0.0", Units = "cd"))
    float PeakIntensity = 8000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Light")
    FLinearColor Color = FLinearColor::White;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light")
    bool bUseTemperature = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Light", meta = (ClampMin = "1700.0", ClampMax = "12000.0", Units = "K", EditCondition = "bUseTemperature"))
    float TemperatureKelvin = 4200.0f;

    /** Short by default: just reaching the wall keeps each moving shadow cheap. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Sweep|Light", meta = (ClampMin = "1.0", Units = "cm"))
    float AttenuationRadiusCm = 1200.0f;

    /** Must stay on for the effect: the wing edges cut the beam only through its shadow. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light")
    bool bCastShadows = true;

    /** Haze-beam shadows: expensive on a moving light, so off by default. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light")
    bool bCastVolumetricShadow = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light|Spot", meta = (ClampMin = "0.0", ClampMax = "80.0", Units = "deg"))
    float InnerConeDegrees = 12.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light|Spot", meta = (ClampMin = "1.0", ClampMax = "80.0", Units = "deg"))
    float OuterConeDegrees = 28.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light|Rect", meta = (ClampMin = "1.0", Units = "cm"))
    float RectWidthCm = 60.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light|Rect", meta = (ClampMin = "1.0", Units = "cm"))
    float RectHeightCm = 20.0f;

    /** Optional mask, e.g. a soft headlight pair (light-pattern series 72-75 style). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep|Light")
    TObjectPtr<UMaterialInterface> LightFunctionMaterial;

    /** Free-running preview in the editor viewport (not tied to the Sequencer playhead). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sweep")
    bool bPreviewInEditor = true;

    UPROPERTY(VisibleInstanceOnly, Transient, Category = "Sweep|Debug")
    float CurrentAlpha = 0.0f;

    UPROPERTY(VisibleInstanceOnly, Transient, Category = "Sweep|Debug")
    int32 CurrentPass = INDEX_NONE;

    /** Poses the light as it is at this many seconds after the time origin (stills, tests).
     * Runtime setters only: never dirties the level. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Sweep")
    void ApplyAtSeconds(double Seconds);

    virtual void Tick(float DeltaSeconds) override;
    virtual void PostRegisterAllComponents() override;
    virtual bool ShouldTickIfViewportsOnly() const override { return bPreviewInEditor; }
#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

    ULocalLightComponent* GetActiveLight() const;

private:
    TWeakObjectPtr<AInfinityStageShowRoot> CachedShowRoot;
    double PreviewOriginSeconds = -1.0;
    void ApplyComponentSettings(ULocalLightComponent* Light) const;
};

namespace InfinityStageSweep
{
/** Plain inputs of the pure evaluator (built from the actor's properties). */
struct FParams
{
    FVector Start = FVector::ZeroVector;
    FVector End = FVector::ZeroVector;
    bool bCurved = false;
    FVector Control = FVector::ZeroVector;
    bool bAimAtTarget = false;
    FVector AimTarget = FVector::ZeroVector;
    float StartDelaySeconds = 0.0f;
    float TravelSeconds = 1.0f;
    float RepeatEverySeconds = 0.0f;
    float RepeatJitterSeconds = 0.0f;
    int32 Seed = 0;
    bool bPingPong = false;
    float FadeInSeconds = 0.0f;
    float FadeOutSeconds = 0.0f;
    float PeakIntensity = 1.0f;
};

struct FSample
{
    /** Actor-local lamp position. */
    FVector Position = FVector::ZeroVector;
    /** Actor-local lamp rotation (zero unless aiming at the target). */
    FRotator Rotation = FRotator::ZeroRotator;
    /** Envelope 0..1. */
    float Alpha = 0.0f;
    /** PeakIntensity * Alpha (candela). */
    float Intensity = 0.0f;
    /** Which pass is running, or INDEX_NONE between passes. */
    int32 PassIndex = INDEX_NONE;
    /** 0..1 along the path (already reversed on ping-pong return passes). */
    float PathParam = 0.0f;
};

/** Upper bound on passes walked per evaluation; later times are dark. */
constexpr int32 MaxPasses = 100000;

/** Point on the path at U in 0..1: a line, or the quadratic Bezier Start-Control-End. */
INFINITYSTAGE_API FVector PathPoint(const FVector& Start, const FVector& End, bool bCurved, const FVector& Control, float U);

/** Fade envelope 0..1 at LocalSeconds into a pass of TravelSeconds; 0 outside the pass. */
INFINITYSTAGE_API float Envelope(double LocalSeconds, float TravelSeconds, float FadeInSeconds, float FadeOutSeconds);

/** Start time of pass PassIndex (0-based). Deterministic per Seed: gaps are
 * max(RepeatEvery, Travel) + Jitter * U, one stream draw per pass, in pass order. */
INFINITYSTAGE_API double PassStartSeconds(const FParams& Params, int32 PassIndex);

/** Pure and deterministic: the lamp at Seconds after the time origin. No world needed. */
INFINITYSTAGE_API FSample Evaluate(const FParams& Params, double Seconds);

/** Empty filter: active everywhere. Otherwise only in the listed segments. */
INFINITYSTAGE_API bool IsActiveInSegment(const TArray<FGuid>& Filter, const FGuid& SegmentGuid);
}
