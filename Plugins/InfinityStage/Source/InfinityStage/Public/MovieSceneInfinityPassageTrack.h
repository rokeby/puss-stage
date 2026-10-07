#pragma once

#include "CoreMinimal.h"
#include "Compilation/IMovieSceneTrackTemplateProducer.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Evaluation/MovieSceneEvalTemplate.h"
#include "MovieSceneNameableTrack.h"
#include "MovieSceneSection.h"
#include "MovieSceneInfinityPassageTrack.generated.h"

struct FInfinityCompiledPassage;

/** Every keyable channel on the managed Passage section. The first ten drive the
 * Passage camera; the Wing entries modulate the authored Wing mechanisms over
 * Master time. The enum name is historical: it predates Wing modulation. */
UENUM(BlueprintType)
enum class EInfinityPassageCameraChannel : uint8
{
    SpeedMultiplier,
    LongitudinalOffsetCm,
    LateralOffsetCm,
    HeightOffsetCm,
    PitchDegrees,
    YawDegrees,
    RollDegrees,
    LookAheadDistanceCm,
    FocalLengthMm,
    FocusDistanceCm,
    /** Scales each cue's authored Inward Travel Cm. */
    WingInwardTravelScale,
    /** Scales each cue's authored Cycle Rate Hz. Integrated, never sampled. */
    WingCycleRateScale,
    /** Added to each cue's resolved mechanism phase offset. */
    WingPhaseBiasCycles
};

/** Inclusive iteration bounds so callers never hard-code an end channel. */
inline constexpr EInfinityPassageCameraChannel InfinityFirstPassageChannel =
    EInfinityPassageCameraChannel::SpeedMultiplier;
inline constexpr EInfinityPassageCameraChannel InfinityLastCameraChannel =
    EInfinityPassageCameraChannel::FocusDistanceCm;
inline constexpr EInfinityPassageCameraChannel InfinityLastPassageChannel =
    EInfinityPassageCameraChannel::WingPhaseBiasCycles;

/** Wing mechanism modulation evaluated at one absolute Master time. */
struct INFINITYSTAGE_API FInfinityPassageWingEvaluation
{
    double InwardTravelScale = 1.0;
    double PhaseBiasCycles = 0.0;
    /**
     * Integral of Wing Cycle Rate Scale from the Passage start to the evaluated
     * frame, expressed in frames. Elapsed scaled time between any two frames is
     * the difference of two such integrals, which keeps scrub, seek and reverse
     * history-independent.
     */
    double CycleRateIntegralFrames = 0.0;
};

/** The fully evaluated camera state at one absolute Master time. */
struct INFINITYSTAGE_API FInfinityPassageCameraEvaluation
{
    FFrameTime DistanceMasterFrame;
    double DistanceCm = 0.0;
    double SpeedMultiplier = 1.0;
    FVector LocalOffsetCm = FVector::ZeroVector;
    FRotator LocalRotation = FRotator::ZeroRotator;
    double LookAheadDistanceCm = 0.0;
    double FocalLengthMm = 35.0;
    double FocusDistanceCm = 100000.0;
    bool bUsedInvalidSpeedFallback = false;
    /**
     * Crossing settle share at this frame: 1 outside the settle window, easing
     * by smoothstep to exactly 0 at the Passage end. The same envelope scales
     * the route rate inside the window, so it is also the settled speed's share
     * of the walk there. 1 whenever no settle was requested.
     */
    double SettleWeight = 1.0;
    /**
     * World-space displacement the Camera.HeightOffsetCm channel added to the
     * camera position (route up axis times LocalOffsetCm.Z). Filled by the
     * camera rig; the shadow cat subtracts it so it stays on the floor
     * whatever the eye height. Zero when the channel evaluates to 0.
     */
    FVector HeightOffsetWorldCm = FVector::ZeroVector;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinityPassageSection : public UMovieSceneSection
{
    GENERATED_BODY()

public:
    UMovieSceneInfinityPassageSection(const FObjectInitializer& ObjectInitializer);

    FMovieSceneDoubleChannel* GetCameraChannel(EInfinityPassageCameraChannel Channel);
    const FMovieSceneDoubleChannel* GetCameraChannel(EInfinityPassageCameraChannel Channel) const;

    /**
     * Evaluates all channels and the pinned-anchor speed integral at absolute Master time.
     *
     * SettleFrames > 0 adds the crossing settle: inside the last
     * min(SettleFrames, last span) frames of the Passage the route rate is
     * multiplied by a smoothstep envelope that reaches 0 at the Passage end, and
     * the last span's integral is renormalized exactly as SpeedMultiplier already
     * is. The camera arrives at the same route-end distance at the same frame,
     * with zero speed, and walks slightly faster earlier in that span. Every pin
     * keeps its exact frame and no key moves; every channel other than the route
     * rate is evaluated at true Master time. SettleFrames <= 0 is the previous
     * evaluation, exactly.
     */
    bool EvaluateCamera(
        const FInfinityCompiledPassage& Passage,
        FFrameTime MasterTime,
        FInfinityPassageCameraEvaluation& OutEvaluation,
        double SettleFrames = 0.0) const;

    /**
     * The crossing settle envelope: 1 at or before WindowStart, smoothstep down
     * to exactly 0 at WindowEnd, with zero slope at both ends. A window of zero
     * or negative length returns 1.
     */
    static double CrossingSettleEnvelope(double Frame, double WindowStart, double WindowEnd);

    /**
     * True when any Wing channel carries a key or a non-neutral default. A
     * neutral section keeps the previous evaluation path exactly, so an
     * unmodulated Show pays nothing for this feature.
     */
    bool HasWingModulation() const;

    /** Evaluates Wing travel, phase bias and the rate integral at absolute Master time. */
    bool EvaluateWingModulation(
        const FInfinityCompiledPassage& Passage,
        FFrameTime MasterTime,
        FInfinityPassageWingEvaluation& OutEvaluation) const;

    /**
     * Integral of Wing Cycle Rate Scale from the Passage start to an arbitrary
     * frame. Mechanism phase origins differ per cue, so the actor differences two
     * of these rather than integrating from each origin separately.
     */
    double GetWingCycleRateIntegralFrames(
        const FInfinityCompiledPassage& Passage,
        double UntilFrame) const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FGuid PassageGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid BlockGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    int32 BuildVersion = 3;

    /** Non-negative rate shape. Its integral is normalized independently between pinned anchors. */
    UPROPERTY()
    FMovieSceneDoubleChannel SpeedMultiplier;

    UPROPERTY()
    FMovieSceneDoubleChannel LongitudinalOffsetCm;

    UPROPERTY()
    FMovieSceneDoubleChannel LateralOffsetCm;

    UPROPERTY()
    FMovieSceneDoubleChannel HeightOffsetCm;

    UPROPERTY()
    FMovieSceneDoubleChannel PitchDegrees;

    UPROPERTY()
    FMovieSceneDoubleChannel YawDegrees;

    UPROPERTY()
    FMovieSceneDoubleChannel RollDegrees;

    /** Positive distance aims the camera toward a future route point while retaining local rotation offsets. */
    UPROPERTY()
    FMovieSceneDoubleChannel LookAheadDistanceCm;

    UPROPERTY()
    FMovieSceneDoubleChannel FocalLengthMm;

    UPROPERTY()
    FMovieSceneDoubleChannel FocusDistanceCm;

    /** Multiplies each cue's authored Inward Travel Cm. Clamped non-negative. */
    UPROPERTY()
    FMovieSceneDoubleChannel WingInwardTravelScale;

    /** Multiplies each cue's authored Cycle Rate Hz. Clamped non-negative and
     * integrated, so a keyed slowdown never makes the mechanism jump on scrub. */
    UPROPERTY()
    FMovieSceneDoubleChannel WingCycleRateScale;

    /** Added to the resolved mechanism phase offset, in cycles. */
    UPROPERTY()
    FMovieSceneDoubleChannel WingPhaseBiasCycles;

    /** Start/end are always pinned. These Wing cue GUIDs add exact musical/spatial anchors. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Timing")
    TArray<FGuid> PinnedWingCueGuids;

    /** Additional music/beat anchors stored as frames relative to this Passage start. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Camera Timing")
    TArray<FFrameNumber> PinnedPassageFrames;

private:
    virtual EMovieSceneChannelProxyType CacheChannelProxy() override;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinityPassageTrack
    : public UMovieSceneNameableTrack
    , public IMovieSceneTrackTemplateProducer
{
    GENERATED_BODY()

public:
    UMovieSceneInfinityPassageTrack(const FObjectInitializer& ObjectInitializer);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    virtual UMovieSceneSection* CreateNewSection() override;
    virtual bool IsEmpty() const override;
    virtual bool SupportsType(TSubclassOf<UMovieSceneSection> SectionClass) const override;
    virtual void AddSection(UMovieSceneSection& Section) override;
    virtual const TArray<UMovieSceneSection*>& GetAllSections() const override;
    virtual bool HasSection(const UMovieSceneSection& Section) const override;
    virtual void RemoveSection(UMovieSceneSection& Section) override;
    virtual void RemoveSectionAt(int32 SectionIndex) override;
    virtual FMovieSceneEvalTemplatePtr CreateTemplateForSection(const UMovieSceneSection& InSection) const override;

#if WITH_EDITORONLY_DATA
    virtual FText GetDisplayName() const override;
#endif

private:
    UPROPERTY()
    TArray<TObjectPtr<UMovieSceneSection>> Sections;
};

USTRUCT()
struct INFINITYSTAGE_API FMovieSceneInfinityPassageSectionTemplate : public FMovieSceneEvalTemplate
{
    GENERATED_BODY()

    FMovieSceneInfinityPassageSectionTemplate() = default;
    explicit FMovieSceneInfinityPassageSectionTemplate(const UMovieSceneInfinityPassageSection& Section);

private:
    virtual UScriptStruct& GetScriptStructImpl() const override { return *StaticStruct(); }
    virtual void Evaluate(
        const FMovieSceneEvaluationOperand& Operand,
        const FMovieSceneContext& Context,
        const FPersistentEvaluationData& PersistentData,
        FMovieSceneExecutionTokens& ExecutionTokens) const override;

    UPROPERTY()
    FGuid PassageGuid;

    UPROPERTY()
    FFrameNumber EvaluationStart = MIN_int32;

    UPROPERTY()
    FFrameNumber EvaluationEnd = MAX_int32;
};
