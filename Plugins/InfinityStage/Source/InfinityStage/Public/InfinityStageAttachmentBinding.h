#pragma once

#include "CoreMinimal.h"
#include "Bindings/MovieSceneCustomBinding.h"
#include "InfinityStageAttachmentBinding.generated.h"

class AActor;
class UMovieSceneSequence;
class UWorld;
struct FInfinityStageLightSettings;

/**
 * Binds a Sequencer track to a Show attachment (a stage lamp, prop or effect)
 * by its identity tag, not by actor reference.
 *
 * Materializing a Passage destroys and re-spawns every attachment actor, so an
 * ordinary possessable binding goes dead the moment the Passage is re-fitted.
 * The identity tag survives: it is minted from the cue and attachment GUIDs at
 * spawn time (InfinityStagePassageActor.cpp, "InfinityStage.Attachment.%s|%s").
 * Keys made through this binding therefore keep driving the lamp across
 * materialize, rebuild and PIE duplication.
 *
 * Lookups are cached per world. A stale entry costs one scan of the Passage
 * actors' managed attachments (a handful of actors), never a world iteration.
 */
UCLASS(EditInlineNew, DefaultToInstanced, meta = (DisplayName = "Stage Attachment (by tag)"))
class INFINITYSTAGE_API UInfinityStageAttachmentBinding : public UMovieSceneCustomBinding
{
    GENERATED_BODY()

public:
    /** "InfinityStage.Attachment.<cue>|<attachment>", copied from the actor when bound. */
    UPROPERTY(VisibleAnywhere, Category = "Binding")
    FName AttachmentTag;

    /** The actor label at bind time, for the track name only. */
    UPROPERTY(VisibleAnywhere, Category = "Binding")
    FString DisplayLabel;

    virtual FMovieSceneBindingResolveResult ResolveBinding(
        const FMovieSceneBindingResolveParams& ResolveParams,
        int32 BindingIndex,
        TSharedRef<const UE::MovieScene::FSharedPlaybackState> SharedPlaybackState) const override;
    virtual int32 GetCustomBindingPriority() const override { return BaseCustomPriority; }
    virtual bool SupportsBindingCreationFromObject(const UObject* SourceObject) const override;
    virtual UMovieSceneCustomBinding* CreateNewCustomBinding(UObject* SourceObject, UMovieScene& OwnerMovieScene) override;
    virtual FString GetDesiredBindingName() const override { return DisplayLabel; }
    virtual UClass* GetBoundObjectClass() const override;
#if WITH_EDITOR
    // Editor-only in the base class (MovieSceneCustomBinding.h:129-172).
    virtual bool SupportsConversionFromBinding(const FMovieSceneBindingReference& BindingReference, const UObject* SourceObject) const override;
    virtual UMovieSceneCustomBinding* CreateCustomBindingFromBinding(const FMovieSceneBindingReference& BindingReference, UObject* SourceObject, UMovieScene& OwnerMovieScene) override;
    virtual FText GetBindingTypePrettyName() const override;
#endif
};

namespace InfinityStageAttachmentBinding
{
/** The actor's attachment identity tag, or NAME_None if it is not a Show attachment. */
INFINITYSTAGE_API FName GetAttachmentTag(const AActor* Actor);

/**
 * The live attachment actor carrying Tag in World, or null. Cached per world;
 * a stale or missing entry re-scans the Passage actors' managed attachments at
 * most once per engine frame per tag. A tag that cannot be found warns once
 * per world ("INFINITY_ATTACHMENT_BINDING_MISSING").
 */
INFINITYSTAGE_API AActor* FindAttachmentActor(UWorld* World, FName Tag);

/** How many scans FindAttachmentActor has run since start-up. Tests and the PIE probe read it. */
INFINITYSTAGE_API int64 GetScanCount();

/** Drops every cached entry and warning latch. Tests only. */
INFINITYSTAGE_API void ResetCacheForTests();

/**
 * True when Root, or any sequence nested beneath it through sub tracks, holds a
 * tag binding for Tag. Walks data only: nothing is evaluated or resolved.
 */
INFINITYSTAGE_API bool SequenceBindsTag(const UMovieSceneSequence* Root, FName Tag, int32 MaxDepth = 8);

/**
 * What Root (and every sequence nested in it) animates on the attachment with
 * Tag: the property names of property tracks on its tag binding and on that
 * binding's child component bindings, and whether any transform track moves it.
 * Returns true when any sequence binds the tag at all. Data only, no evaluation.
 */
INFINITYSTAGE_API void CollectAnimatedForBinding(
    UMovieSceneSequence* Sequence, const FGuid& BindingId, TSet<FName>& OutProperties, bool& bOutTransform);

INFINITYSTAGE_API bool CollectAnimatedProperties(
    UMovieSceneSequence* Root, FName Tag, TSet<FName>& OutProperties, bool& bOutTransform, int32 MaxDepth = 8);

/**
 * The capture guard's core. Captured holds every live light setting, including
 * values Sequencer is currently driving. For each animated property this puts
 * the Show's authored value back, so a hand edit of an un-keyed setting is still
 * written but a keyed value never becomes authored. Returns false, naming it,
 * when an animated property has no known mapping: the caller must then write
 * nothing rather than risk capturing a keyed value.
 */
INFINITYSTAGE_API bool RestoreAnimatedLightFields(
    FInfinityStageLightSettings& Captured,
    const FInfinityStageLightSettings& Authored,
    const TSet<FName>& AnimatedProperties,
    FString& OutUnmapped);
}
