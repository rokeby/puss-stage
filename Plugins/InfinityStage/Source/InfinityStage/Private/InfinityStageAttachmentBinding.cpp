#include "InfinityStageAttachmentBinding.h"

#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageTypes.h"
#include "MovieSceneBinding.h"
#include "MovieScenePossessable.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Tracks/MovieScenePropertyTrack.h"
#include "MovieScene.h"
#include "MovieSceneBindingReferences.h"
#include "MovieSceneSequence.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "UObject/ObjectKey.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageAttachmentBinding, Log, All);

#define LOCTEXT_NAMESPACE "InfinityStageAttachmentBinding"

namespace
{
const TCHAR AttachmentTagPrefix[] = TEXT("InfinityStage.Attachment.");

struct FWorldTagCache
{
    TMap<FName, TWeakObjectPtr<AActor>> Actors;
    /** Engine frame of the last failed scan per tag, so a missing lamp costs one scan a frame at most. */
    TMap<FName, uint64> MissFrames;
    TSet<FName> WarnedMissing;
};

TMap<FObjectKey, FWorldTagCache>& Caches()
{
    static TMap<FObjectKey, FWorldTagCache> Map;
    return Map;
}

int64 GScanCount = 0;

bool ActorCarriesTag(const AActor* Actor, const FName Tag)
{
    return IsValid(Actor) && Actor->Tags.Contains(Tag);
}

AActor* ScanPassages(UWorld& World, const FName Tag)
{
    ++GScanCount;
    for (TActorIterator<AInfinityStagePassageActor> It(&World); It; ++It)
    {
        for (AActor* Candidate : It->ManagedAttachmentActors)
        {
            if (ActorCarriesTag(Candidate, Tag))
            {
                return Candidate;
            }
        }
    }
    return nullptr;
}
}

namespace InfinityStageAttachmentBinding
{
FName GetAttachmentTag(const AActor* Actor)
{
    if (!IsValid(Actor))
    {
        return NAME_None;
    }
    for (const FName& Tag : Actor->Tags)
    {
        if (Tag.ToString().StartsWith(AttachmentTagPrefix, ESearchCase::CaseSensitive))
        {
            return Tag;
        }
    }
    return NAME_None;
}

AActor* FindAttachmentActor(UWorld* World, const FName Tag)
{
    if (!World || Tag.IsNone())
    {
        return nullptr;
    }
    if (Caches().Num() > 8)
    {
        // Every PIE session makes a new world; drop the ones that have gone.
        for (auto It = Caches().CreateIterator(); It; ++It)
        {
            if (!It.Key().ResolveObjectPtr())
            {
                It.RemoveCurrent();
            }
        }
    }
    FWorldTagCache& Cache = Caches().FindOrAdd(FObjectKey(World));
    if (const TWeakObjectPtr<AActor>* Cached = Cache.Actors.Find(Tag))
    {
        AActor* Actor = Cached->Get();
        if (ActorCarriesTag(Actor, Tag))
        {
            return Actor;
        }
    }
    if (const uint64* MissFrame = Cache.MissFrames.Find(Tag); MissFrame && *MissFrame == GFrameCounter)
    {
        return nullptr;
    }

    AActor* Found = ScanPassages(*World, Tag);
    if (Found)
    {
        Cache.Actors.Add(Tag, Found);
        Cache.MissFrames.Remove(Tag);
        return Found;
    }
    Cache.Actors.Remove(Tag);
    Cache.MissFrames.Add(Tag, GFrameCounter);
    if (!Cache.WarnedMissing.Contains(Tag))
    {
        Cache.WarnedMissing.Add(Tag);
        UE_LOG(LogInfinityStageAttachmentBinding, Warning,
            TEXT("INFINITY_ATTACHMENT_BINDING_MISSING tag=%s world=%s: no materialized Passage owns this attachment; its keys do nothing until it is materialized again."),
            *Tag.ToString(), *World->GetName());
    }
    return nullptr;
}

int64 GetScanCount()
{
    return GScanCount;
}

void ResetCacheForTests()
{
    Caches().Reset();
}

bool SequenceBindsTag(const UMovieSceneSequence* Root, const FName Tag, const int32 MaxDepth)
{
    if (!Root || Tag.IsNone() || MaxDepth < 0)
    {
        return false;
    }
    if (const FMovieSceneBindingReferences* References = Root->GetBindingReferences())
    {
        for (const FMovieSceneBindingReference& Reference : References->GetAllReferences())
        {
            const UInfinityStageAttachmentBinding* Binding = Cast<UInfinityStageAttachmentBinding>(Reference.CustomBinding);
            if (Binding && Binding->AttachmentTag == Tag)
            {
                return true;
            }
        }
    }
    const UMovieScene* MovieScene = Root->GetMovieScene();
    if (!MovieScene)
    {
        return false;
    }
    for (const UMovieSceneTrack* Track : MovieScene->GetTracks())
    {
        const UMovieSceneSubTrack* SubTrack = Cast<UMovieSceneSubTrack>(Track);
        if (!SubTrack)
        {
            continue;
        }
        for (const UMovieSceneSection* Section : SubTrack->GetAllSections())
        {
            const UMovieSceneSubSection* SubSection = Cast<UMovieSceneSubSection>(Section);
            if (SubSection && SubSection->GetSequence() != Root
                && SequenceBindsTag(SubSection->GetSequence(), Tag, MaxDepth - 1))
            {
                return true;
            }
        }
    }
    return false;
}

void CollectAnimatedForBinding(
    UMovieSceneSequence* Sequence, const FGuid& BindingId, TSet<FName>& OutProperties, bool& bOutTransform)
{
    UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!MovieScene || !BindingId.IsValid())
    {
        return;
    }
    // Component tracks (Intensity, LightColor...) sit on child bindings whose parent is the actor's.
    TSet<FGuid> Owners;
    Owners.Add(BindingId);
    for (int32 Index = 0; Index < MovieScene->GetPossessableCount(); ++Index)
    {
        const FMovieScenePossessable& Possessable = MovieScene->GetPossessable(Index);
        if (Possessable.GetParent() == BindingId)
        {
            Owners.Add(Possessable.GetGuid());
        }
    }
    for (const FGuid& Owner : Owners)
    {
        const FMovieSceneBinding* SceneBinding = MovieScene->FindBinding(Owner);
        if (!SceneBinding)
        {
            continue;
        }
        for (const UMovieSceneTrack* Track : SceneBinding->GetTracks())
        {
            if (Cast<UMovieScene3DTransformTrack>(Track))
            {
                bOutTransform = true;
            }
            else if (const UMovieScenePropertyTrack* Property = Cast<UMovieScenePropertyTrack>(Track))
            {
                OutProperties.Add(Property->GetPropertyName());
            }
        }
    }
}

bool CollectAnimatedProperties(
    UMovieSceneSequence* Root, const FName Tag, TSet<FName>& OutProperties, bool& bOutTransform, const int32 MaxDepth)
{
    if (!Root || Tag.IsNone() || MaxDepth < 0)
    {
        return false;
    }
    bool bBound = false;
    UMovieScene* MovieScene = Root->GetMovieScene();
    const FMovieSceneBindingReferences* References = Root->GetBindingReferences();
    if (MovieScene && References)
    {
        TSet<FGuid> Bound;
        for (const FMovieSceneBindingReference& Reference : References->GetAllReferences())
        {
            const UInfinityStageAttachmentBinding* Binding = Cast<UInfinityStageAttachmentBinding>(Reference.CustomBinding);
            if (Binding && Binding->AttachmentTag == Tag)
            {
                Bound.Add(Reference.ID);
            }
        }
        for (const FGuid& Id : Bound)
        {
            bBound = true;
            CollectAnimatedForBinding(Root, Id, OutProperties, bOutTransform);
        }
    }
    if (MovieScene)
    {
        for (UMovieSceneTrack* Track : MovieScene->GetTracks())
        {
            UMovieSceneSubTrack* SubTrack = Cast<UMovieSceneSubTrack>(Track);
            if (!SubTrack)
            {
                continue;
            }
            for (UMovieSceneSection* Section : SubTrack->GetAllSections())
            {
                UMovieSceneSubSection* SubSection = Cast<UMovieSceneSubSection>(Section);
                UMovieSceneSequence* Child = SubSection ? SubSection->GetSequence() : nullptr;
                if (Child && Child != Root)
                {
                    bBound |= CollectAnimatedProperties(Child, Tag, OutProperties, bOutTransform, MaxDepth - 1);
                }
            }
        }
    }
    return bBound;
}

bool RestoreAnimatedLightFields(
    FInfinityStageLightSettings& Captured,
    const FInfinityStageLightSettings& Authored,
    const TSet<FName>& AnimatedProperties,
    FString& OutUnmapped)
{
    OutUnmapped.Reset();
    for (const FName& Property : AnimatedProperties)
    {
        const FString Name = Property.ToString();
        if (Name == TEXT("Intensity")) { Captured.Intensity = Authored.Intensity; }
        else if (Name == TEXT("LightColor")) { Captured.Color = Authored.Color; }
        else if (Name == TEXT("Temperature")) { Captured.TemperatureKelvin = Authored.TemperatureKelvin; }
        else if (Name == TEXT("bUseTemperature")) { Captured.bUseTemperature = Authored.bUseTemperature; }
        else if (Name == TEXT("IndirectLightingIntensity")) { Captured.IndirectLightingIntensity = Authored.IndirectLightingIntensity; }
        else if (Name == TEXT("VolumetricScatteringIntensity")) { Captured.VolumetricScatteringIntensity = Authored.VolumetricScatteringIntensity; }
        else if (Name == TEXT("DiffuseScale")) { Captured.DiffuseScale = Authored.DiffuseScale; }
        else if (Name == TEXT("SpecularScale")) { Captured.SpecularScale = Authored.SpecularScale; }
        else if (Name == TEXT("AttenuationRadius")) { Captured.AttenuationRadiusCm = Authored.AttenuationRadiusCm; }
        else if (Name == TEXT("InnerConeAngle")) { Captured.InnerConeAngleDegrees = Authored.InnerConeAngleDegrees; }
        else if (Name == TEXT("OuterConeAngle")) { Captured.OuterConeAngleDegrees = Authored.OuterConeAngleDegrees; }
        else if (Name == TEXT("SourceRadius")) { Captured.SourceRadiusCm = Authored.SourceRadiusCm; }
        else if (Name == TEXT("LightFunctionScale")) { Captured.LightFunctionScale = Authored.LightFunctionScale; }
        // Visibility is not a captured setting, so keying it can never leak into the Show.
        else if (Name == TEXT("bVisible") || Name == TEXT("bHiddenInGame")) {}
        else
        {
            OutUnmapped += OutUnmapped.IsEmpty() ? Name : FString(TEXT(",")) + Name;
        }
    }
    return OutUnmapped.IsEmpty();
}
}

FMovieSceneBindingResolveResult UInfinityStageAttachmentBinding::ResolveBinding(
    const FMovieSceneBindingResolveParams& ResolveParams,
    int32 BindingIndex,
    TSharedRef<const UE::MovieScene::FSharedPlaybackState> SharedPlaybackState) const
{
    FMovieSceneBindingResolveResult Result;
    UObject* Context = ResolveParams.Context;
    UWorld* World = Context ? Context->GetWorld() : nullptr;
    if (AActor* Actor = InfinityStageAttachmentBinding::FindAttachmentActor(World, AttachmentTag))
    {
        Result.Objects.Add(Actor);
    }
    return Result;
}

bool UInfinityStageAttachmentBinding::SupportsBindingCreationFromObject(const UObject* SourceObject) const
{
    return !InfinityStageAttachmentBinding::GetAttachmentTag(Cast<AActor>(SourceObject)).IsNone();
}

UMovieSceneCustomBinding* UInfinityStageAttachmentBinding::CreateNewCustomBinding(UObject* SourceObject, UMovieScene& OwnerMovieScene)
{
    const AActor* Actor = Cast<AActor>(SourceObject);
    const FName Tag = InfinityStageAttachmentBinding::GetAttachmentTag(Actor);
    if (Tag.IsNone())
    {
        return nullptr;
    }
    UInfinityStageAttachmentBinding* Binding =
        NewObject<UInfinityStageAttachmentBinding>(&OwnerMovieScene, NAME_None, RF_Transactional);
    Binding->AttachmentTag = Tag;
#if WITH_EDITOR
    Binding->DisplayLabel = Actor->GetActorLabel();
#else
    Binding->DisplayLabel = Actor->GetName();
#endif
    return Binding;
}

UClass* UInfinityStageAttachmentBinding::GetBoundObjectClass() const
{
    return AActor::StaticClass();
}

#if WITH_EDITOR
bool UInfinityStageAttachmentBinding::SupportsConversionFromBinding(
    const FMovieSceneBindingReference& BindingReference,
    const UObject* SourceObject) const
{
    return SupportsBindingCreationFromObject(SourceObject);
}

UMovieSceneCustomBinding* UInfinityStageAttachmentBinding::CreateCustomBindingFromBinding(
    const FMovieSceneBindingReference& BindingReference,
    UObject* SourceObject,
    UMovieScene& OwnerMovieScene)
{
    return CreateNewCustomBinding(SourceObject, OwnerMovieScene);
}

FText UInfinityStageAttachmentBinding::GetBindingTypePrettyName() const
{
    return LOCTEXT("PrettyName", "Stage Attachment (by tag)");
}
#endif

#undef LOCTEXT_NAMESPACE
