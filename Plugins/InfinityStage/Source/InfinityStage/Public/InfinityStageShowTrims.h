#pragma once

#include "CoreMinimal.h"
#include "Engine/Scene.h"
#include "GameFramework/Actor.h"
#include "InfinityStageShowTrims.generated.h"

class UPostProcessComponent;
class USoundClass;
class USoundMix;

/** The trim values, separated from the actor so the mapping is unit-testable. Neutral = no effect. */
struct INFINITYSTAGE_API FInfinityShowTrimValues
{
    float MasterGainDb = 0.0f;
    float MusicGainDb = 0.0f;
    float AmbienceGainDb = 0.0f;
    float ExposureEv = 0.0f;
    float Saturation = 1.0f;
    float Contrast = 1.0f;
    float WhiteTemp = 6500.0f;
    float WhiteTint = 0.0f;
};

namespace InfinityStageShowTrims
{
/** Writes only the non-neutral picture trims as overrides; everything neutral stays un-overridden,
 * so a section with no trims leaves the show's own look exactly as it is. Returns how many overrides. */
INFINITYSTAGE_API int32 BuildPostProcess(const FInfinityShowTrimValues& Values, FPostProcessSettings& OutSettings);

/** dB to linear gain, clamped to a safe range (-80 dB is silence). */
INFINITYSTAGE_API float DbToGain(float Db);
}

/**
 * Show Trims (Gary, 8 Oct): per-section sound and picture correction, "too loud or too dark",
 * keyed over time in each Choreography / Scene / Interaction sequence with the normal curve
 * editor. Place ONE in the show level and add it to those sequences; set the keyed sections to
 * Restore State so each section returns to neutral when it ends (cuts are matched by hand).
 *
 * Picture: a high-priority unbound post-process on this actor. Exposure is applied as a colour
 * grading gain (2^EV), so it stacks with the show's exposure. Saturation, Contrast and White
 * Temp/Tint REPLACE the show's value while they are away from neutral (post-process blending
 * is a replace, not a multiply).
 * Sound (game worlds only): master gain on the audio device; Music / Ambience gains through a
 * transient Sound Mix on the Sound Classes named below (assign your music to its class first).
 */
UCLASS(ClassGroup = "Infinity Stage", meta = (DisplayName = "Infinity Stage Show Trims"))
class INFINITYSTAGE_API AInfinityStageShowTrims : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageShowTrims();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Sound", meta = (ClampMin = "-80.0", ClampMax = "12.0", Units = "dB"))
    float MasterGainDb = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Sound", meta = (ClampMin = "-80.0", ClampMax = "12.0", Units = "dB"))
    float MusicGainDb = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Sound", meta = (ClampMin = "-80.0", ClampMax = "12.0", Units = "dB"))
    float AmbienceGainDb = 0.0f;

    /** Brightness in stops (applied as colour-grading gain, stacks with the show's exposure). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Picture", meta = (ClampMin = "-6.0", ClampMax = "6.0"))
    float ExposureEv = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Picture", meta = (ClampMin = "0.0", ClampMax = "2.0"))
    float Saturation = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Picture", meta = (ClampMin = "0.0", ClampMax = "2.0"))
    float Contrast = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Picture", meta = (ClampMin = "1500.0", ClampMax = "15000.0"))
    float WhiteTemp = 6500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Trims|Picture", meta = (ClampMin = "-1.0", ClampMax = "1.0"))
    float WhiteTint = 0.0f;

    /** Sound Class the music rails play through (needed for Music Gain). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Trims|Sound")
    TObjectPtr<USoundClass> MusicSoundClass;

    /** Sound Class for scene / Choreography sound (needed for Ambience Gain). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Trims|Sound")
    TObjectPtr<USoundClass> AmbienceSoundClass;

    /** Above the show's look volumes, so a trim always wins while it is away from neutral. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Trims|Picture")
    float PostProcessPriority = 1000.0f;

    /** Driven every frame, so TRANSIENT (never saved): a level save cannot keep a keyed value. */
    UPROPERTY(VisibleAnywhere, Transient, Category = "Trims")
    TObjectPtr<UPostProcessComponent> PostProcess;

    FInfinityShowTrimValues GetValues() const;

    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override { return true; }
    virtual void PostRegisterAllComponents() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    void ApplySound(const FInfinityShowTrimValues& Values);

    UPROPERTY(Transient)
    TObjectPtr<USoundMix> SoundMix;

    float AppliedMasterGain = 1.0f;
    float AppliedMusicGain = 1.0f;
    float AppliedAmbienceGain = 1.0f;
    bool bMixPushed = false;
};
