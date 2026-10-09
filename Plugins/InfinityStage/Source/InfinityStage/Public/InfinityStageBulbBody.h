#pragma once

#include "CoreMinimal.h"
#include "InfinityStageBulbBody.generated.h"

/**
 * Bulb glass that follows its light (Gary, 6 Oct: "It would be great to have a
 * flickering and dying bulb, not all bulbs! some should flicker only slightly and
 * others be stable").
 *
 * A bulb's visible glass is a mesh prop attachment (a static mesh actor) with an
 * emissive material (M_UP_TubeEmissive or an MI of it, scalar "Intensity"). Until
 * now it glowed steadily whatever its light did. With bFollowLight the glass's
 * emissive scalar is driven each game frame from the light's EVALUATED drama
 * brightness (strike on approach, unstruck level, after-pass decay / extinguish),
 * times a cheap CPU flicker of the glass's own (a light-function flicker such as
 * MI_LF_Flicker_Hum runs on the GPU and cannot be read back).
 *
 * Game worlds only: the editor keeps the authored look, and the level is never
 * dirtied (the dynamic material is created at first evaluation in the game world).
 */
UENUM(BlueprintType)
enum class EInfinityBulbBodyFlicker : uint8
{
    /** Steady: the glass is exactly the light's drama level. */
    Stable,
    /** A gentle, irregular shimmer down to (1 - SlightDepth). */
    Slight,
    /** Flickers harder as the camera approaches, then dies at FailAtCm past the lamp. */
    Fail
};

USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityBulbBodySettings
{
    GENERATED_BODY()

    /** Off (default): the glass glows as authored, exactly as before. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body")
    bool bFollowLight = false;

    /** The Light attachment ON THE SAME CUE whose drama drives this glass. Unset: the
     * first enabled Light attachment on the cue. No light: flicker alone. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    FGuid LightAttachmentGuid;

    /** The scalar parameter on the glass material (M_UP_TubeEmissive: "Intensity"). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    FName IntensityParameter = TEXT("Intensity");

    /** The parameter's value at full brightness. 0 or less: read from the glass's
     * material when the dynamic instance is made (its authored value). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    float FullIntensity = -1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    EInfinityBulbBodyFlicker Flicker = EInfinityBulbBodyFlicker::Stable;

    /** Mixed with the attachment's identity: re-rolls this bulb's flicker. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    int32 Seed = 0;

    /** Slight: the deepest dip, as a fraction of the level. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body",
        meta = (ClampMin = "0.0", ClampMax = "1.0", EditCondition = "bFollowLight"))
    float SlightDepth = 0.12f;

    /** Slight and Fail: flicker steps per second of Master time. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body",
        meta = (ClampMin = "1.0", UIMax = "60.0", EditCondition = "bFollowLight"))
    float FlickerRateHz = 14.0f;

    /** Fail: route distance before the death point over which the flicker worsens. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body",
        meta = (ClampMin = "1.0", Units = "cm", EditCondition = "bFollowLight"))
    double FailWindowCm = 1500.0;

    /** Fail: where it dies, measured from the lamp along the route (0: as the camera
     * passes it; negative: before). Distance, not time, so a replay dies identically. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body",
        meta = (Units = "cm", EditCondition = "bFollowLight"))
    double FailAtCm = 0.0;

    /** Also apply the glass flicker to the light itself (authored x drama x flicker;
     * switched off at 0). Off: only the glass flickers. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body", meta = (EditCondition = "bFollowLight"))
    bool bFlickerAlsoDrivesLight = false;

    /** Add a transient point light to the bulb actor in game worlds. This gives a
     * bare bulb a small specular/reflection contribution without authoring a Light
     * attachment (and therefore without asking the Structure for a lantern). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical", meta = (EditCondition = "bFollowLight"))
    bool bEmitPointLight = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical",
        meta = (ClampMin = "0.0", EditCondition = "bEmitPointLight"))
    float PointLightLumens = 24.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical",
        meta = (ClampMin = "0.0", Units = "cm", EditCondition = "bEmitPointLight"))
    float PointLightAttenuationRadiusCm = 450.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical",
        meta = (ClampMin = "0.0", Units = "cm", EditCondition = "bEmitPointLight"))
    float PointLightSourceRadiusCm = 8.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical",
        meta = (ClampMin = "0.0", Units = "cm", EditCondition = "bEmitPointLight"))
    float PointLightSoftSourceRadiusCm = 18.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Practical",
        meta = (ClampMin = "1000.0", ClampMax = "20000.0", Units = "K", EditCondition = "bEmitPointLight"))
    float PointLightTemperatureKelvin = 2200.0f;

    /** Rotate this bulb and its linked cord around the cord mesh's top in game
     * worlds. The phase is a stable hash of attachment GUID + SwaySeed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway")
    bool bSwingOnCord = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway", meta = (EditCondition = "bSwingOnCord"))
    FGuid CordAttachmentGuid;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway",
        meta = (ClampMin = "0.0", ClampMax = "20.0", Units = "deg", EditCondition = "bSwingOnCord"))
    float SwingYawAmplitudeDegrees = 2.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway",
        meta = (ClampMin = "0.0", ClampMax = "20.0", Units = "deg", EditCondition = "bSwingOnCord"))
    float SwingPitchAmplitudeDegrees = 1.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway",
        meta = (ClampMin = "0.25", Units = "s", EditCondition = "bSwingOnCord"))
    float SwingPeriodSeconds = 7.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bulb Body|Cord Sway", meta = (EditCondition = "bSwingOnCord"))
    int32 SwaySeed = 0;
};

namespace InfinityStageBulbBody
{
/**
 * Pure and deterministic: the glass's own flicker multiplier, 0..1.
 *
 * @param Identity           The body attachment's GUID (mixed with Settings.Seed).
 * @param ShowSeconds        The Master clock (scrubs replay the same flicker).
 * @param CameraPastLampCm   Camera route distance minus the lamp's (positive once passed).
 */
INFINITYSTAGE_API float FlickerScale(
    const FInfinityBulbBodySettings& Settings,
    const FGuid& Identity,
    double ShowSeconds,
    double CameraPastLampCm);

/** The emissive parameter value: Full x drama level x flicker, never negative. */
INFINITYSTAGE_API float BodyIntensity(float FullIntensity, float DramaScale, float FlickerScale);

/** Continuous deterministic sine sway. Yaw and pitch share a GUID-derived phase,
 * with pitch one quarter-cycle ahead so rows of bulbs never move in lock-step. */
INFINITYSTAGE_API FRotator CordSwingRotation(
    const FInfinityBulbBodySettings& Settings,
    const FGuid& Identity,
    double ShowSeconds);
}
