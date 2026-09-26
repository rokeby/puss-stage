#pragma once

#include "CoreMinimal.h"
#include "UObject/SoftObjectPtr.h"
#include "InfinityStageEffectTypes.generated.h"

class UStaticMesh;

/**
 * Per-instance custom data on the Passage's wing ISMs.
 *
 * One layout shared by three owners: the Passage allocates the floats, the wing
 * master (Wing materiality) reads them, and Effect sources write the burn slots.
 * With no floats allocated the material's PerInstanceCustomData nodes return
 * their defaults, so either side can land first.
 */
namespace InfinityStageWingCustomData
{
    /** 0 intact, 1 consumed. Written by a Wing Burn effect in game worlds. */
    inline constexpr int32 BurnProgress = 0;
    /** Ignition point on the panel face as 0..1 UV, V down; the front spreads from it. */
    inline constexpr int32 IgnitionU = 1;
    inline constexpr int32 IgnitionV = 2;
    /** 0..1 deterministic variation seed, written by the Passage at materialize. */
    inline constexpr int32 VariationSeed = 3;
    inline constexpr int32 NumFloats = 4;
}

/**
 * The burn front, as the wing master draws it (agreed with Wing materiality).
 * Mean front radius in cm = BurnProgress * (Dmax + FrontPadCm), where Dmax is the
 * distance from the ignition point to the farthest corner of the UV square. The
 * pad — the master's IrregularityCm / 2 + 1.25 * BurnEdgeCm at its defaults —
 * is what lets progress 1 reach hole depth everywhere.
 */
namespace InfinityStageWingBurn
{
    inline constexpr float FrontPadCm = 130.0f;
}

/**
 * What an Effect attachment makes. One attachment kind, sub-typed here, so a new
 * effect never needs the shared attachment enum again — the same shape as a
 * Light attachment choosing Spot, Rect or Point.
 */
UENUM(BlueprintType)
enum class EInfinityStageEffectType : uint8
{
    /** Hand-worked smoke pot: fine, long-lived, and leaves a medium in its bay. */
    Haze,
    /** Heavier, darker, shorter-lived puffs. */
    Smoke,
    /** Kettle or boiler vent: white, fast, rising, quick to clear. */
    Steam,
    /** Contained fire in a basket or cresset. Flickers a linked light. */
    Fire,
    /** Flame consuming the wing panel the attachment is anchored to. */
    WingBurn UMETA(DisplayName = "Wing Burn"),
    /** Dust, ash and motes adrift in a bay; they read only where a beam falls. */
    Motes
};

/**
 * Persistent settings for a cue-anchored effect source.
 *
 * Placement is the attachment's: anchor, relative transform (whose rotation is
 * the nozzle's aim) and actor class. These are the effect's own values, pushed to
 * the apparatus's FX systems as User parameters and to its local medium.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageEffectSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Common")
    EInfinityStageEffectType Type = EInfinityStageEffectType::Haze;

    /** Spawn rate, plume or flame size. Sent to FX systems as User.Output. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Common",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float Output = 0.5f;

    /** Plume albedo, flame tint or mote colour. Sent as User.Tint; also the medium's albedo. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Common")
    FLinearColor Tint = FLinearColor::White;

    /** Plumes run only while a rendered view is this close, so a Show of dozens
     * of sources costs a handful. The apparatus and its medium always stay. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Common",
        meta = (ClampMin = "0.0", Units = "cm"))
    float ActiveRadiusCm = 6000.0f;

    /** A smoke pot is worked by hand, not run continuously. Zero pumps steadily. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Pumping",
        meta = (ClampMin = "0.0", Units = "s"))
    float PulsePeriodSeconds = 6.0f;

    /** Fraction of each cycle spent pumping. Sent as User.Pump, 0..1 with soft edges. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Pumping",
        meta = (ClampMin = "0.05", ClampMax = "1.0"))
    float PulseDuty = 0.35f;

    /**
     * Leave a Local Fog Volume downstream of the nozzle. It is voxelised into the
     * volumetric fog, so the rig's beams read here rather than everywhere. Keep it
     * modest: it works with the global medium, it does not replace it.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Medium")
    bool bFeedsLocalMedium = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Medium",
        meta = (Units = "cm", EditCondition = "bFeedsLocalMedium"))
    FVector MediumOffsetCm = FVector(250.0, 0.0, 150.0);

    /** Scale this to the corridor: P05 is 497 cm wide, P01 1244 cm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Medium",
        meta = (ClampMin = "1.0", Units = "cm", EditCondition = "bFeedsLocalMedium"))
    float MediumRadiusCm = 400.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Medium",
        meta = (ClampMin = "0.0", UIMax = "2.0", EditCondition = "bFeedsLocalMedium"))
    float MediumDensity = 0.15f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Medium",
        meta = (ClampMin = "1.0", UIMax = "5000.0", EditCondition = "bFeedsLocalMedium"))
    float MediumHeightFalloff = 1000.0f;

    /**
     * A sibling Light attachment on the same cue that this fire flickers. The
     * light belongs to the rig; an effect never creates a light of its own.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Fire")
    FGuid LinkedLightAttachmentGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Fire",
        meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float FlickerAmount = 0.25f;

    /**
     * Wing Burn: the burn starts when the show camera is this far short of the
     * wing along the route. Distance rather than time, so scrubbing and re-timing
     * the music carry the burn with them.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (Units = "cm",
            EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    float BurnStartAheadCm = 3000.0f;

    /** Camera travel over which the wing goes from intact to consumed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (ClampMin = "1.0", Units = "cm",
            EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    float BurnSpanCm = 4000.0f;

    /** Where the fire takes hold, as 0..1 UV on the panel face, V down. Bottom
     * centre by default, so it climbs. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (ClampMin = "0.0", ClampMax = "1.0",
            EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    FVector2D IgnitionUV = FVector2D(0.5, 1.0);

    /**
     * The panel mesh's planar UV mapping in mesh-local cm, X being thickness:
     * U = UAxis.X * Y + UAxis.Y and V = VAxis.X * Z + VAxis.Y. Images carry
     * transparent margins, so the mesh bounds are not the UV square and cannot
     * stand in for this. Measured per mesh by Wing materiality's
     * probe_uv_axes_readonly.py. Only the flames' placement uses it: the char is
     * drawn in UV space by the wing master and does not depend on it.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    FVector2D BurnUAxis = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    FVector2D BurnVAxis = FVector2D::ZeroVector;

    /** The mesh the mapping was measured on. A different mesh on the panel warns
     * that the flames may no longer sit on the char line. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Wing Burn",
        meta = (EditCondition = "Type == EInfinityStageEffectType::WingBurn", EditConditionHides))
    TSoftObjectPtr<UStaticMesh> BurnUVMeasuredMesh;

    /** Half-size of the drifting volume. Sent as User.Extent. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect|Motes",
        meta = (Units = "cm",
            EditCondition = "Type == EInfinityStageEffectType::Motes", EditConditionHides))
    FVector MotesExtentCm = FVector(250.0, 400.0, 500.0);

    /**
     * Set on copies made by effect replication, naming the attachment they were
     * copied from. Re-replication removes only its own copies, so hand-placed
     * sources survive every pass.
     */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Effect|Replication")
    FGuid ReplicatedFromAttachmentGuid;
};

/** Seeded per-copy variation for effect replication. The same seed always yields
 * the same corridor. */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityEffectReplicationVariation
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect Replication")
    int32 Seed = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect Replication",
        meta = (ClampMin = "0.0", ClampMax = "0.9"))
    float OutputJitterFraction = 0.15f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect Replication",
        meta = (ClampMin = "0.0", Units = "cm"))
    float PositionJitterCm = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Effect Replication",
        meta = (ClampMin = "0.0", Units = "deg"))
    float RotationJitterDegrees = 0.0f;
};
