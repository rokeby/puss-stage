#include "MovieSceneInfinitySceneTrack.h"

UMovieSceneInfinitySceneSection::UMovieSceneInfinitySceneSection(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
}

UMovieSceneInfinitySceneTrack::UMovieSceneInfinitySceneTrack(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    OwnerGuid = FGuid::NewGuid();
}

UMovieSceneSection* UMovieSceneInfinitySceneTrack::CreateNewSection()
{
    return NewObject<UMovieSceneInfinitySceneSection>(this, NAME_None, RF_Transactional);
}

#if WITH_EDITORONLY_DATA
FText UMovieSceneInfinitySceneTrack::GetDisplayName() const
{
    return NSLOCTEXT("InfinityStage", "SceneTrackName", "Infinity Stage Scenes");
}
#endif
