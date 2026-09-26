#pragma once

#include "CoreMinimal.h"
#include "InfinityStageEffectTypes.h"
#include "InfinityStageTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "InfinityStageEffectLibrary.generated.h"

class UInfinityStageShowAsset;
class UStaticMesh;

/**
 * Show-side authoring for Effect attachments, callable from Unreal Python and MCP
 * until the Cue Desk has buttons for it.
 *
 * Light replication copies to every bay, which is right for a rig and wrong for
 * a smoke pot. Effects are laid by selection instead: choose the bays (beam bays,
 * every Nth), then replicate onto exactly those. Replication owns only the copies
 * it made, so hand-placed sources survive every pass — the generator gives the
 * rhythm, the hand gives the accidents.
 */
UCLASS()
class INFINITYSTAGE_API UInfinityStageEffectLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** The settings a new effect of this type starts from. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Effects")
    static FInfinityStageEffectSettings MakeDefaultEffectSettings(EInfinityStageEffectType Type);

    /** Adds one hand-placed Effect attachment to a Wing Pair cue. Returns its
     * guid, or an invalid guid when the cue is missing or not a Wing Pair. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Effects")
    static FGuid AddEffectAttachment(
        UInfinityStageShowAsset* Show,
        FGuid CueGuid,
        EInfinityStageEffectType Type,
        EInfinityAttachmentAnchor Anchor,
        FTransform RelativeTransform,
        FText Label);

    /**
     * Records the burning panel's planar UV mapping on a Wing Burn attachment,
     * so its flames sit on the wing master's char line: U = UAxis.X * Y + UAxis.Y,
     * V = VAxis.X * Z + VAxis.Y in mesh-local cm. Take the values from Wing
     * materiality's probe_uv_axes_readonly.py, re-run rather than trusted stale.
     * Returns false for anything but a Wing Burn, or a degenerate mapping.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Effects")
    static bool SetWingBurnUVMapping(
        UInfinityStageShowAsset* Show,
        FGuid CueGuid,
        FGuid AttachmentGuid,
        FVector2D UAxis,
        FVector2D VAxis,
        TSoftObjectPtr<UStaticMesh> MeasuredMesh);

    /** The cues, in the given order, that carry an enabled volumetric beam
     * fixture: a light casting volumetric shadow at or above this scattering. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Effects")
    static TArray<FGuid> SelectBeamBays(
        const UInfinityStageShowAsset* Show,
        const TArray<FGuid>& CueGuids,
        float MinVolumetricScattering = 5.0f);

    /** Every Nth of the given cues, counted afresh within each Passage from Phase,
     * so a short Passage is not starved by where a long one ended. Counting is
     * among the given cues: over beam bays, Stride 3 means every third beam bay. */
    UFUNCTION(BlueprintPure, Category = "Infinity Stage|Effects")
    static TArray<FGuid> SelectEveryNthPerPassage(
        const UInfinityStageShowAsset* Show,
        const TArray<FGuid>& CueGuids,
        int32 Stride,
        int32 Phase = 0);

    /** Removes replicated effect copies from the scope cues: copies of the source
     * cue's effects, or every copy when SourceCueGuid is invalid. Hand-placed
     * effects are never removed. Returns how many were removed. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Effects")
    static int32 ClearReplicatedEffects(
        UInfinityStageShowAsset* Show,
        FGuid SourceCueGuid,
        const TArray<FGuid>& ScopeCueGuids);

    /**
     * Copies the source cue's hand-placed effects onto each target cue, after
     * clearing that source's earlier copies from the scope and the targets, so a
     * changed stride leaves nothing stale behind. Copy identities are
     * deterministic, variation is seeded per target, and a fire's linked light is
     * re-pointed to the target's light of the same ordinal. Returns copies placed.
     */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage|Effects")
    static int32 ReplicateEffectAttachments(
        UInfinityStageShowAsset* Show,
        FGuid SourceCueGuid,
        const TArray<FGuid>& ScopeCueGuids,
        const TArray<FGuid>& TargetCueGuids,
        const FInfinityEffectReplicationVariation& Variation);
};
