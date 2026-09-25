#pragma once

#include "CoreMinimal.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "MovieSceneInfinitySceneTrack.generated.h"

UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinitySceneSection : public UMovieSceneSubSection
{
    GENERATED_BODY()

public:
    UMovieSceneInfinitySceneSection(const FObjectInitializer& ObjectInitializer);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid BlockGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    int32 BuildVersion = 1;
};

UCLASS(BlueprintType)
class INFINITYSTAGE_API UMovieSceneInfinitySceneTrack : public UMovieSceneSubTrack
{
    GENERATED_BODY()

public:
    UMovieSceneInfinitySceneTrack(const FObjectInitializer& ObjectInitializer);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Managed Ownership")
    FGuid OwnerGuid;

    virtual UMovieSceneSection* CreateNewSection() override;

#if WITH_EDITORONLY_DATA
    virtual FText GetDisplayName() const override;
#endif
};
