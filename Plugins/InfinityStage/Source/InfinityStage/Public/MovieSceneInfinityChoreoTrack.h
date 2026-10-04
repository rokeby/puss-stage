#pragma once

#include "CoreMinimal.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "MovieSceneInfinityChoreoTrack.generated.h"

/**
 * One Passage's Choreography sequence, nested by the Master rebuild over the
 * Passage segment. Inner 0:00 is the Passage start (Gary, 4 Oct: things happen
 * before the song does), so hand-placed keys inside stay relative to the
 * Passage and travel with it when the Show is retimed.
 *
 * Kept apart from the Scene track on purpose: Scene sections mean "a Scene cue"
 * to the handoff, cut-binding and fit checks, and a Choreo is not one.
 */
UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinityChoreoSection : public UMovieSceneSubSection
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    /** The Passage GUID this section belongs to. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid BlockGuid;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinityChoreoTrack : public UMovieSceneSubTrack
{
    GENERATED_BODY()

public:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    virtual UMovieSceneSection* CreateNewSection() override;

#if WITH_EDITORONLY_DATA
    virtual FText GetDisplayName() const override;
#endif
};
