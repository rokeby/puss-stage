#include "MovieSceneInfinityAudioTrack.h"

bool UMovieSceneInfinityAudioTrack::SupportsType(const TSubclassOf<UMovieSceneSection> SectionClass) const
{
    return SectionClass == UMovieSceneInfinityAudioSection::StaticClass();
}

UMovieSceneSection* UMovieSceneInfinityAudioTrack::CreateNewSection()
{
    return NewObject<UMovieSceneInfinityAudioSection>(this, NAME_None, RF_Transactional);
}
