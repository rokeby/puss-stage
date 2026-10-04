#include "MovieSceneInfinityChoreoTrack.h"

UMovieSceneSection* UMovieSceneInfinityChoreoTrack::CreateNewSection()
{
    return NewObject<UMovieSceneInfinityChoreoSection>(this, NAME_None, RF_Transactional);
}

#if WITH_EDITORONLY_DATA
FText UMovieSceneInfinityChoreoTrack::GetDisplayName() const
{
    return NSLOCTEXT("InfinityStage", "ChoreoTrackName", "Infinity Stage Choreography");
}
#endif
