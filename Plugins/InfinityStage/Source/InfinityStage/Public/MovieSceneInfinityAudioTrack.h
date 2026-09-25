#pragma once

#include "CoreMinimal.h"
#include "Sections/MovieSceneAudioSection.h"
#include "Tracks/MovieSceneAudioTrack.h"
#include "MovieSceneInfinityAudioTrack.generated.h"

/** A generated music section whose identity survives managed Master rebuilds. */
UCLASS()
class INFINITYSTAGE_API UMovieSceneInfinityAudioSection : public UMovieSceneAudioSection
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage")
    FGuid OwnerGuid;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage")
    FGuid BlockGuid;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage")
    FGuid RailGuid;

    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage")
    int32 BuildVersion = 1;
};

/** Master-owned passage music. User audio remains on ordinary Audio tracks. */
UCLASS()
class INFINITYSTAGE_API UMovieSceneInfinityAudioTrack : public UMovieSceneAudioTrack
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, Category = "Infinity Stage")
    FGuid OwnerGuid;

    virtual bool SupportsType(TSubclassOf<UMovieSceneSection> SectionClass) const override;
    virtual UMovieSceneSection* CreateNewSection() override;
};
