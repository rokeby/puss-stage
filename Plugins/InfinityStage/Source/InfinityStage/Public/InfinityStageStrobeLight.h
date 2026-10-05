#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageStrobeLight.generated.h"

class AInfinityStageShowRoot;
class APostProcessVolume;
class UPointLightComponent;

/**
 * A placeable, regular strobe: a hard flash, then about a third of a second of
 * ghosting (Gary, 5 Oct). Two layers: the light's own tail (Decay Seconds, so a wet
 * floor keeps glowing) and an optional camera-side ghost (Ghost Volume, below).
 *
 * In game worlds its phase comes from the Show's Master clock, so a strobe flashes
 * on the same frames on every run, scrub and rehearsal. In the editor viewport it
 * free-runs on wall-clock time as a preview only.
 *
 * Every setting is Interp: key it in a Choreography or Scene sequence to switch the
 * strobe on and off, or change its rate, at a cue.
 */
UCLASS(Blueprintable, ClassGroup = "Infinity Stage", meta = (DisplayName = "Infinity Stage Strobe"))
class INFINITYSTAGE_API AInfinityStageStrobeLight : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageStrobeLight();

    /**
     * Driven every frame (also in the editor preview), so it is TRANSIENT: never saved.
     * A level save therefore cannot persist a mid-flash value; everything authored
     * lives on the actor's own settings below.
     */
    UPROPERTY(VisibleAnywhere, Transient, BlueprintReadOnly, Category = "Strobe")
    TObjectPtr<UPointLightComponent> Light;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "1.0", Units = "cm"))
    float AttenuationRadiusCm = 1500.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe")
    bool bStrobeEnabled = true;

    /** One flash every this many seconds. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "0.05", Units = "s"))
    float PeriodSeconds = 1.0f;

    /** Full-brightness hold of each flash. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "0.0", Units = "s"))
    float FlashSeconds = 0.04f;

    /** Afterglow: an exponential fade that reaches black at this time after the flash. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "0.0", Units = "s"))
    float DecaySeconds = 0.33f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "0.0", Units = "cd"))
    float PeakIntensity = 20000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe")
    FLinearColor Color = FLinearColor::White;

    /** Offsets this strobe within the period, so two strobes can alternate. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float PhaseCycles = 0.0f;

    /** Run only inside these segments (Passage or Scene/Sequence cue GUIDs). Empty: everywhere. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Strobe")
    TArray<FGuid> ActiveSegmentGuids;

    /**
     * Optional camera-side ghost (Gary, 5 Oct: "the ghosting that happens for about a third
     * of a second after a strobe"). Point this at a Post Process Volume whose settings ARE
     * the ghost look (bloom up, exposure bias, a tint): the strobe only drives its Blend
     * Weight, full at the flash and fading over Ghost Seconds. Game worlds only, so the
     * saved level keeps the volume's authored weight. One strobe per ghost volume.
     */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Strobe|Ghost")
    TObjectPtr<APostProcessVolume> GhostVolume;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe|Ghost", meta = (ClampMin = "0.0", Units = "s"))
    float GhostSeconds = 0.33f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Interp, Category = "Strobe|Ghost", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float GhostMaxWeight = 1.0f;

    /** Free-running preview in the editor viewport (not tied to the Sequencer playhead). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Strobe")
    bool bPreviewInEditor = true;

    UPROPERTY(VisibleInstanceOnly, Transient, Category = "Strobe|Debug")
    float CurrentLevel = 0.0f;

    UPROPERTY(VisibleInstanceOnly, Transient, Category = "Strobe|Debug")
    float CurrentGhost = 0.0f;

    virtual void Tick(float DeltaSeconds) override;
    virtual void PostRegisterAllComponents() override;
    virtual bool ShouldTickIfViewportsOnly() const override { return bPreviewInEditor; }

private:
    TWeakObjectPtr<AInfinityStageShowRoot> CachedShowRoot;
    void ApplyLevel(float Level);
};

namespace InfinityStageStrobe
{
/** Pure and deterministic: brightness 0..1 at ShowSeconds. Flash = 1, then an exponential
 * tail that is cut to 0 at DecaySeconds. A non-positive period gives 0. */
INFINITYSTAGE_API float LevelAt(double ShowSeconds, float PeriodSeconds, float FlashSeconds, float DecaySeconds, float PhaseCycles);

/** Empty filter: active everywhere. Otherwise only in the listed segments. */
INFINITYSTAGE_API bool IsActiveInSegment(const TArray<FGuid>& Filter, const FGuid& SegmentGuid);
}
