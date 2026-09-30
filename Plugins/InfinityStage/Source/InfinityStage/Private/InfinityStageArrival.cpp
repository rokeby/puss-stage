#include "InfinityStageArrival.h"

#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Components/SceneComponent.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
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
}

AInfinityStageArrival::AInfinityStageArrival()
{
    // No clock of its own: the Master frame, delivered by the Passage track, is the only time.
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);
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

bool AInfinityStageArrival::ResolveRotationAtMasterFrame(
    const UInfinityStageShowAsset* Show,
    const FFrameTime MasterTime,
    FRotator& OutRotation) const
{
    if (!Show || !Show->TickResolution.IsValid())
    {
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
    // From the Scene's first frame on, Sequencer owns the value.
    if (MasterTime >= FFrameTime(Segment->StartFrame))
    {
        return false;
    }

    const int32 CueIndex = Show->FindCueIndex(SceneCueGuid);
    const ULevelSequence* SceneSequence = CueIndex != INDEX_NONE ? Show->Cues[CueIndex].Scene.Sequence.LoadSynchronous() : nullptr;
    const ULevelSequence* Motion = MotionSequence.LoadSynchronous();
    const UMovieScene* SceneMovieScene = SceneSequence ? SceneSequence->GetMovieScene() : nullptr;
    const UMovieScene* MotionMovieScene = Motion ? Motion->GetMovieScene() : nullptr;
    if (!SceneMovieScene || !MotionMovieScene)
    {
        WarnOnce(TEXT("NoSequence"), MotionSequence.ToString());
        return false;
    }
    const UMovieSceneSubSection* Section = FindMotionSection(*SceneMovieScene, *Motion);
    if (!Section)
    {
        WarnOnce(TEXT("NoSubSection"), SceneSequence->GetName());
        return false;
    }

    // Master -> the Scene sequence's own time -> the motion sequence's time (negative here).
    const FFrameTime SceneTime = FFrameTime(SceneMovieScene->GetPlaybackRange().GetLowerBoundValue())
        + FFrameRate::TransformTime(MasterTime - FFrameTime(Segment->StartFrame), Show->TickResolution, SceneMovieScene->GetTickResolution());
    FFrameTime MotionTime;
    if (!MapOuterToInnerTime(*Section, SceneMovieScene->GetTickResolution(), SceneTime, MotionTime))
    {
        WarnOnce(TEXT("NotFixedPlayRate"), SceneSequence->GetName());
        return false;
    }

    const FMovieSceneBinding* Binding = MotionMovieScene->FindBinding(MotionBindingGuid);
    const UMovieScene3DTransformSection* TransformSection = nullptr;
    if (Binding)
    {
        for (const UMovieSceneTrack* Track : Binding->GetTracks())
        {
            if (const UMovieScene3DTransformTrack* TransformTrack = Cast<UMovieScene3DTransformTrack>(Track))
            {
                if (!TransformTrack->GetAllSections().IsEmpty())
                {
                    TransformSection = Cast<UMovieScene3DTransformSection>(TransformTrack->GetAllSections()[0]);
                }
                break;
            }
        }
    }
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

bool AInfinityStageArrival::EvaluateAtMasterFrame(const UInfinityStageShowAsset* Show, const FFrameTime MasterTime)
{
    FRotator Rotation;
    const USceneComponent* DrivenRoot = DrivenActor ? DrivenActor->GetRootComponent() : nullptr;
    if (!DrivenRoot || !ResolveRotationAtMasterFrame(Show, MasterTime, Rotation))
    {
        return false;
    }
    // Transient evaluation, like the Passage mechanisms: no Modify(), nothing dirtied.
    if (!DrivenRoot->GetRelativeRotation().Equals(Rotation, 1.0e-4))
    {
        DrivenActor->SetActorRelativeRotation(Rotation, false, nullptr, ETeleportType::TeleportPhysics);
    }
    return true;
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
