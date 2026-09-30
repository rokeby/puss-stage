#include "InfinityStageArrival.h"

#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Components/SceneComponent.h"
#include "GeometryCacheComponent.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneGeometryCacheSection.h"
#include "MovieSceneGeometryCacheTrack.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieScene3DTransformTrack.h"
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
