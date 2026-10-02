#include "InfinityStageArrival.h"

#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Components/LightComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/World.h"
#include "GeometryCacheComponent.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneGeometryCacheSection.h"
#include "MovieSceneGeometryCacheTrack.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "Tracks/MovieSceneSubTrack.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageArrival, Log, All);

namespace
{
/** The Scene sequence's sub-section that plays the motion sequence, on any sub-track.
 * Matched by sequence, not by track name: display names are editor-only data. */
const UMovieSceneSubSection* FindMotionSection(const UMovieScene& SceneMovieScene, const ULevelSequence& Motion)
{
    for (const UMovieSceneTrack* Track : SceneMovieScene.GetTracks())
    {
        const UMovieSceneSubTrack* SubTrack = Cast<UMovieSceneSubTrack>(Track);
        if (!SubTrack)
        {
            continue;
        }
        for (const UMovieSceneSection* Section : SubTrack->GetAllSections())
        {
            const UMovieSceneSubSection* SubSection = Cast<UMovieSceneSubSection>(Section);
            if (SubSection && SubSection->GetSequence() == &Motion)
            {
                return SubSection;
            }
        }
    }
    return nullptr;
}

/** The first section of a binding's track of the given class, read through the base track. */
template <typename SectionType, typename TrackType>
const SectionType* FindBindingSection(const UMovieScene& MovieScene, const FGuid& BindingGuid)
{
    const FMovieSceneBinding* Binding = MovieScene.FindBinding(BindingGuid);
    if (!Binding)
    {
        return nullptr;
    }
    for (const UMovieSceneTrack* Track : Binding->GetTracks())
    {
        if (Track && Track->IsA<TrackType>())
        {
            const TArray<UMovieSceneSection*>& Sections = Track->GetAllSections();
            return Sections.IsEmpty() ? nullptr : Cast<SectionType>(Sections[0]);
        }
    }
    return nullptr;
}

bool ResolveFirstTransform(const UMovieScene& MovieScene, const FGuid& BindingGuid, FTransform& OutTransform)
{
    const UMovieScene3DTransformSection* Section =
        FindBindingSection<UMovieScene3DTransformSection, UMovieScene3DTransformTrack>(MovieScene, BindingGuid);
    if (!Section)
    {
        return false;
    }
    // Translation XYZ, rotation XYZ (roll, pitch, yaw), scale XYZ.
    const TArrayView<FMovieSceneDoubleChannel*> Channels =
        Section->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>();
    if (Channels.Num() != 9)
    {
        return false;
    }
    double Values[9];
    for (int32 Index = 0; Index < 9; ++Index)
    {
        if (!Channels[Index])
        {
            return false;
        }
        const TArrayView<const FMovieSceneDoubleValue> Keys = Channels[Index]->GetData().GetValues();
        if (!Keys.IsEmpty())
        {
            Values[Index] = Keys[0].Value;
            continue;
        }
        const TOptional<double> Default = Channels[Index]->GetDefault();
        if (!Default.IsSet())
        {
            return false;
        }
        Values[Index] = Default.GetValue();
    }
    OutTransform = FTransform(
        FRotator(Values[4], Values[5], Values[3]),
        FVector(Values[0], Values[1], Values[2]),
        FVector(Values[6], Values[7], Values[8]));
    return true;
}

/** The float section on the named property track that owns MotionTime, or the earliest section. */
const UMovieSceneFloatSection* FindFloatBindingSection(
    const UMovieScene& MovieScene,
    const FGuid& BindingGuid,
    const FName PropertyName,
    const FFrameTime MotionTime)
{
    const FMovieSceneBinding* Binding = MovieScene.FindBinding(BindingGuid);
    if (!Binding)
    {
        return nullptr;
    }
    const UMovieSceneFloatSection* EarliestSection = nullptr;
    for (const UMovieSceneTrack* Track : Binding->GetTracks())
    {
        const UMovieSceneFloatTrack* FloatTrack = Cast<UMovieSceneFloatTrack>(Track);
        if (!FloatTrack || FloatTrack->GetPropertyName() != PropertyName)
        {
            continue;
        }
        for (const UMovieSceneSection* Candidate : FloatTrack->GetAllSections())
        {
            const UMovieSceneFloatSection* Section = Cast<UMovieSceneFloatSection>(Candidate);
            if (!Section)
            {
                continue;
            }
            if (Section->GetRange().Contains(MotionTime.FloorToFrame()))
            {
                return Section;
            }
            if (!EarliestSection
                || (!Section->HasStartFrame() && EarliestSection->HasStartFrame())
                || (Section->HasStartFrame() && EarliestSection->HasStartFrame()
                    && Section->GetInclusiveStartFrame() < EarliestSection->GetInclusiveStartFrame()))
            {
                EarliestSection = Section;
            }
        }
    }
    // Pre-cut motion time is negative by construction. If it precedes every section,
    // read the earliest section's channel outside its range on purpose, exactly as the root does.
    return EarliestSection;
}
}

AInfinityStageArrival::AInfinityStageArrival()
{
    // No clock of its own: the Master frame, delivered by the Passage track, is the only time.
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);
}

void AInfinityStageArrival::BeginPlay()
{
    Super::BeginPlay();
    ApplyInitialTransformPose();
    // A GeometryCache that is running auto-plays whenever nothing holds it in manual tick, so a
    // Show started far from this Arrival would drop the cloth on its own clock. Hold the still
    // hang (sample 0) until the Master says otherwise.
    if (AActor* Cloth = BackclothActor.Get())
    {
        if (UGeometryCacheComponent* Cache = Cloth->FindComponentByClass<UGeometryCacheComponent>())
        {
            Cache->SetManualTick(true);
            Cache->TickAtThisTime(0.0f, true, false, false);
        }
    }
}

bool AInfinityStageArrival::ApplyInitialTransformPose()
{
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld())
    {
        return false;
    }
    ULevelSequence* Motion = MotionSequence.LoadSynchronous();
    UMovieScene* MovieScene = Motion ? Motion->GetMovieScene() : nullptr;
    if (!MovieScene || !DrivenActor || !MotionBindingGuid.IsValid())
    {
        WarnOnce(TEXT("InitialPoseMissingRoot"), GetNameSafe(Motion));
        return false;
    }

    struct FResolvedInitialTransform
    {
        AActor* Target = nullptr;
        FGuid BindingGuid;
        FTransform Transform;
    };
    TArray<FResolvedInitialTransform> Resolved;
    Resolved.Reserve(1 + AdditionalInitialTransformDrives.Num());
    FResolvedInitialTransform& Root = Resolved.AddDefaulted_GetRef();
    Root.Target = DrivenActor;
    Root.BindingGuid = MotionBindingGuid;
    for (const FInfinityArrivalInitialTransformDrive& Drive : AdditionalInitialTransformDrives)
    {
        FResolvedInitialTransform& Row = Resolved.AddDefaulted_GetRef();
        Row.Target = Drive.Target;
        Row.BindingGuid = Drive.BindingGuid;
    }

    // Resolve every row before changing the first actor: a bad/missing roof or lattice binding
    // must not leave a partly initialized hangar.
    for (FResolvedInitialTransform& Row : Resolved)
    {
        if (!Row.Target || Row.Target->GetWorld() != World || !Row.BindingGuid.IsValid()
            || !ResolveFirstTransform(*MovieScene, Row.BindingGuid, Row.Transform))
        {
            WarnOnce(TEXT("InitialPoseDriveInvalid"),
                FString::Printf(TEXT("target=%s binding=%s"),
                    *GetNameSafe(Row.Target), *Row.BindingGuid.ToString()));
            return false;
        }
    }
    for (const FResolvedInitialTransform& Row : Resolved)
    {
        // Transient runtime initialization: no Modify(), no package dirtied.
        Row.Target->SetActorRelativeTransform(
            Row.Transform, false, nullptr, ETeleportType::TeleportPhysics);
    }
    UE_LOG(LogInfinityStageArrival, Display,
        TEXT("INFINITY_HANGAR_INITIAL_POSE actor='%s' motion='%s' movers=%d world=game"),
        *GetActorNameOrLabel(), *Motion->GetName(), Resolved.Num());
    return true;
}

bool AInfinityStageArrival::MapOuterToInnerTime(
    const UMovieSceneSubSection& Section,
    const FFrameRate OuterTickResolution,
    const FFrameTime OuterTime,
    FFrameTime& OutInnerTime)
{
    const UMovieSceneSequence* Inner = Section.GetSequence();
    const UMovieScene* InnerMovieScene = Inner ? Inner->GetMovieScene() : nullptr;
    if (!InnerMovieScene || !Section.HasStartFrame()
        || Section.Parameters.TimeScale.GetType() != EMovieSceneTimeWarpType::FixedPlayRate)
    {
        return false;
    }
    // The sub-section's own placement: inner start + (outer - section start) x play rate,
    // carried across the tick resolutions. It is linear, so it holds before the start too.
    const FFrameTime OuterOffset = OuterTime - FFrameTime(Section.GetInclusiveStartFrame());
    const FFrameTime Scaled = OuterOffset * Section.Parameters.TimeScale.AsFixedPlayRate();
    const FFrameTime InnerOffset = FFrameRate::TransformTime(Scaled, OuterTickResolution, InnerMovieScene->GetTickResolution());
    OutInnerTime = FFrameTime(InnerMovieScene->GetPlaybackRange().GetLowerBoundValue() + Section.Parameters.StartFrameOffset)
        + InnerOffset;
    return true;
}

bool AInfinityStageArrival::ResolveMotionTime(
    const UInfinityStageShowAsset* Show,
    const FFrameTime MasterTime,
    FFrameTime& OutMotionTime,
    const UMovieScene*& OutMotionScene) const
{
    if (!Show || !Show->TickResolution.IsValid())
    {
        return false;
    }
    const int32 CueIndex = Show->FindCueIndex(SceneCueGuid);
    if (CueIndex == INDEX_NONE || Show->Cues[CueIndex].Type != EInfinityCueType::Scene)
    {
        WarnOnce(TEXT("NoSceneSegment"), SceneCueGuid.ToString());
        return false;
    }
    const ULevelSequence* SceneSequence = Show->Cues[CueIndex].Scene.Sequence.LoadSynchronous();
    const ULevelSequence* Motion = MotionSequence.LoadSynchronous();
    const UMovieScene* SceneMovieScene = SceneSequence ? SceneSequence->GetMovieScene() : nullptr;
    const UMovieScene* MotionMovieScene = Motion ? Motion->GetMovieScene() : nullptr;
    if (!SceneMovieScene || !MotionMovieScene)
    {
        WarnOnce(TEXT("NoSequence"), MotionSequence.ToString());
        return false;
    }
    // Not nested yet is a designed state, not a fault: an Arrival can be placed ahead of its
    // hangar's nesting and stays inert until then. Checked BEFORE the compile, so a waiting
    // Arrival costs a cue lookup and a track scan per frame, not a Show compile, and it says
    // so once at Display: nothing in a test report, nothing to subtract from a Passage tick.
    const UMovieSceneSubSection* Section = FindMotionSection(*SceneMovieScene, *Motion);
    if (!Section)
    {
        bool bAlreadyNoted = false;
        WarnedReasons.Add(TEXT("NotNested"), &bAlreadyNoted);
        if (!bAlreadyNoted)
        {
            UE_LOG(LogInfinityStageArrival, Display,
                TEXT("INFINITY_STAGE_ARRIVAL_WAITING actor='%s' reason=NotNested detail='%s' (inert until %s plays %s)"),
                *GetActorNameOrLabel(), *SceneSequence->GetName(), *SceneSequence->GetName(), *Motion->GetName());
        }
        return false;
    }

    // Compiled every call and never cached: the Show is edited without Modify(), and a
    // compile costs about 0.05 ms.
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    const FInfinityCompiledSegment* Segment = Compiled.Segments.FindByPredicate(
        [this](const FInfinityCompiledSegment& Candidate)
        {
            return Candidate.SegmentGuid == SceneCueGuid && Candidate.Type == EInfinityCueType::Scene;
        });
    if (!Segment)
    {
        WarnOnce(TEXT("NoSceneSegment"), SceneCueGuid.ToString());
        return false;
    }
    // From the Scene's first frame on, Sequencer owns everything this actor drives.
    if (MasterTime >= FFrameTime(Segment->StartFrame))
    {
        return false;
    }

    // Master -> the Scene sequence's own time -> the motion sequence's time (negative here).
    const FFrameTime SceneTime = FFrameTime(SceneMovieScene->GetPlaybackRange().GetLowerBoundValue())
        + FFrameRate::TransformTime(MasterTime - FFrameTime(Segment->StartFrame), Show->TickResolution, SceneMovieScene->GetTickResolution());
    if (!MapOuterToInnerTime(*Section, SceneMovieScene->GetTickResolution(), SceneTime, OutMotionTime))
    {
        WarnOnce(TEXT("NotFixedPlayRate"), SceneSequence->GetName());
        return false;
    }
    OutMotionScene = MotionMovieScene;
    return true;
}

bool AInfinityStageArrival::ResolveRotationAtMasterFrame(
    const UInfinityStageShowAsset* Show,
    const FFrameTime MasterTime,
    FRotator& OutRotation) const
{
    FFrameTime MotionTime;
    const UMovieScene* MotionMovieScene = nullptr;
    if (!ResolveMotionTime(Show, MasterTime, MotionTime, MotionMovieScene))
    {
        return false;
    }
    const UMovieScene3DTransformSection* TransformSection =
        FindBindingSection<UMovieScene3DTransformSection, UMovieScene3DTransformTrack>(*MotionMovieScene, MotionBindingGuid);
    if (!TransformSection)
    {
        WarnOnce(TEXT("NoTransformTrack"), MotionBindingGuid.ToString());
        return false;
    }
    // Translation XYZ, rotation XYZ (roll, pitch, yaw), scale XYZ, in channel-proxy order.
    const TArrayView<FMovieSceneDoubleChannel*> Channels = TransformSection->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>();
    if (Channels.Num() < 6)
    {
        WarnOnce(TEXT("TooFewChannels"), FString::FromInt(Channels.Num()));
        return false;
    }
    double Roll = 0.0;
    double Pitch = 0.0;
    double Yaw = 0.0;
    Channels[3]->Evaluate(MotionTime, Roll);
    Channels[4]->Evaluate(MotionTime, Pitch);
    Channels[5]->Evaluate(MotionTime, Yaw);
    OutRotation = FRotator(Pitch, Yaw, Roll);
    return true;
}

bool AInfinityStageArrival::ResolveBackclothTimeAtMasterFrame(
    const UInfinityStageShowAsset* Show,
    const FFrameTime MasterTime,
    const float CacheDurationSeconds,
    float& OutCacheSeconds) const
{
    FFrameTime MotionTime;
    const UMovieScene* MotionMovieScene = nullptr;
    if (!BackclothBindingGuid.IsValid() || !ResolveMotionTime(Show, MasterTime, MotionTime, MotionMovieScene))
    {
        return false;
    }
    const UMovieSceneGeometryCacheSection* Section =
        FindBindingSection<UMovieSceneGeometryCacheSection, UMovieSceneGeometryCacheTrack>(*MotionMovieScene, BackclothBindingGuid);
    if (!Section)
    {
        WarnOnce(TEXT("NoBackclothSection"), BackclothBindingGuid.ToString());
        return false;
    }
    // The engine's own mapping, exactly as Sequencer plays the same section after the boundary.
    OutCacheSeconds = Section->MapTimeToAnimation(CacheDurationSeconds, MotionTime, MotionMovieScene->GetTickResolution());
    return true;
}

bool AInfinityStageArrival::ResolveFloatDriveAtMasterFrame(
    const UInfinityStageShowAsset* Show,
    const FFrameTime MasterTime,
    const int32 DriveIndex,
    float& OutValue) const
{
    FFrameTime MotionTime;
    const UMovieScene* MotionMovieScene = nullptr;
    if (!ResolveMotionTime(Show, MasterTime, MotionTime, MotionMovieScene))
    {
        return false;
    }
    return EvaluateFloatDriveAtMotionTime(*MotionMovieScene, MotionTime, DriveIndex, OutValue);
}

bool AInfinityStageArrival::EvaluateFloatDriveAtMotionTime(
    const UMovieScene& MotionScene,
    const FFrameTime MotionTime,
    const int32 DriveIndex,
    float& OutValue) const
{
    if (!PreSceneFloatDrives.IsValidIndex(DriveIndex))
    {
        WarnOnce(TEXT("NoFloatDrive"), FString::FromInt(DriveIndex));
        return false;
    }
    const FInfinityArrivalFloatDrive& Drive = PreSceneFloatDrives[DriveIndex];
    if (!Drive.BindingGuid.IsValid() || Drive.PropertyName.IsNone())
    {
        WarnOnce(TEXT("InvalidFloatDrive"), FString::Printf(
            TEXT("index=%d binding=%s property=%s"),
            DriveIndex,
            *Drive.BindingGuid.ToString(),
            *Drive.PropertyName.ToString()));
        return false;
    }
    const UMovieSceneFloatSection* Section =
        FindFloatBindingSection(MotionScene, Drive.BindingGuid, Drive.PropertyName, MotionTime);
    if (!Section)
    {
        WarnOnce(TEXT("NoFloatTrack"), FString::Printf(
            TEXT("index=%d binding=%s property=%s"),
            DriveIndex,
            *Drive.BindingGuid.ToString(),
            *Drive.PropertyName.ToString()));
        return false;
    }
    if (!Section->GetChannel().Evaluate(MotionTime, OutValue))
    {
        WarnOnce(TEXT("NoFloatChannelValue"), FString::Printf(
            TEXT("index=%d binding=%s property=%s"),
            DriveIndex,
            *Drive.BindingGuid.ToString(),
            *Drive.PropertyName.ToString()));
        return false;
    }
    return true;
}

bool AInfinityStageArrival::EvaluateAtMasterFrame(const UInfinityStageShowAsset* Show, const FFrameTime MasterTime)
{
    bool bDrove = false;
    FRotator Rotation;
    const USceneComponent* DrivenRoot = DrivenActor ? DrivenActor->GetRootComponent() : nullptr;
    if (DrivenRoot && ResolveRotationAtMasterFrame(Show, MasterTime, Rotation))
    {
        // Transient evaluation, like the Passage mechanisms: no Modify(), nothing dirtied.
        if (!DrivenRoot->GetRelativeRotation().Equals(Rotation, 1.0e-4))
        {
            DrivenActor->SetActorRelativeRotation(Rotation, false, nullptr, ETeleportType::TeleportPhysics);
        }
        bDrove = true;
    }

    AActor* Cloth = BackclothActor.Get();
    UGeometryCacheComponent* Cache = Cloth ? Cloth->FindComponentByClass<UGeometryCacheComponent>() : nullptr;
    float CacheSeconds = 0.0f;
    if (Cache && ResolveBackclothTimeAtMasterFrame(Show, MasterTime, Cache->GetDuration(), CacheSeconds))
    {
        // Every evaluation, not once: a running cache left out of manual tick plays on its own clock.
        Cache->SetManualTick(true);
        Cache->TickAtThisTime(CacheSeconds, true, false, false);
        bDrove = true;
        if (!bLoggedBackcloth)
        {
            bLoggedBackcloth = true;
            UE_LOG(LogInfinityStageArrival, Display, TEXT("ArrivalBackcloth|actor=%s|duration=%.3f|cache_time=%.3f|master_frame=%d"),
                *Cloth->GetActorNameOrLabel(), Cache->GetDuration(), CacheSeconds, MasterTime.FloorToFrame().Value);
        }
    }

    // Sequencer also calls Arrivals while evaluating editor worlds. Unlike the existing
    // root/backcloth behaviour, component property writes can be saved into the level later,
    // so pre-Scene light/exposure drives are deliberately game-world-only.
    const UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld())
    {
        return bDrove;
    }

    FFrameTime MotionTime;
    const UMovieScene* MotionMovieScene = nullptr;
    if (PreSceneFloatDrives.IsEmpty()
        || !ResolveMotionTime(Show, MasterTime, MotionTime, MotionMovieScene))
    {
        return bDrove;
    }
    for (int32 DriveIndex = 0; DriveIndex < PreSceneFloatDrives.Num(); ++DriveIndex)
    {
        float Value = 0.0f;
        if (!EvaluateFloatDriveAtMotionTime(*MotionMovieScene, MotionTime, DriveIndex, Value))
        {
            continue;
        }

        const FInfinityArrivalFloatDrive& Drive = PreSceneFloatDrives[DriveIndex];
        UObject* Target = Drive.Target.Get();
        if (!Target)
        {
            WarnOnce(TEXT("NoFloatTarget"), FString::Printf(TEXT("index=%d target=%s"), DriveIndex, *Drive.Target.ToString()));
            continue;
        }
        if (Target->GetWorld() != GetWorld())
        {
            WarnOnce(TEXT("ForeignWorldTarget"), FString::Printf(
                TEXT("index=%d target=%s"), DriveIndex, *Target->GetPathName()));
            continue;
        }
        if (ULightComponent* Light = Cast<ULightComponent>(Target))
        {
            if (!FMath::IsNearlyEqual(Light->Intensity, Value, 1.0e-3f))
            {
                Light->SetIntensity(Value);
            }
            bDrove = true;
        }
        else if (APostProcessVolume* Volume = Cast<APostProcessVolume>(Target))
        {
            if (!FMath::IsNearlyEqual(Volume->BlendWeight, Value, 1.0e-4f))
            {
                Volume->BlendWeight = Value;
            }
            bDrove = true;
        }
        else
        {
            WarnOnce(TEXT("UnsupportedFloatTarget"), FString::Printf(
                TEXT("index=%d target=%s class=%s"),
                DriveIndex,
                *Target->GetPathName(),
                *Target->GetClass()->GetName()));
        }
    }
    return bDrove;
}

void AInfinityStageArrival::WarnOnce(const TCHAR* Reason, const FString& Detail) const
{
    bool bAlreadyWarned = false;
    WarnedReasons.Add(Reason, &bAlreadyWarned);
    if (!bAlreadyWarned)
    {
        UE_LOG(LogInfinityStageArrival, Warning, TEXT("INFINITY_STAGE_ARRIVAL_SKIPPED actor='%s' reason=%s detail='%s'"),
            *GetActorNameOrLabel(), Reason, *Detail);
    }
}
