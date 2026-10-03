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
#include "MovieScenePossessable.h"
#include "MovieSceneSpawnable.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "Tracks/MovieSceneSubTrack.h"

#if WITH_EDITOR
#include "Framework/Application/SlateApplication.h"
#include "Framework/Notifications/NotificationManager.h"
#include "ScopedTransaction.h"
#include "Widgets/Notifications/SNotificationList.h"
#endif

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

#if WITH_EDITOR
constexpr double HangarValueTolerance = 1.0e-3;

struct FHangarLightChannel
{
    FString Label;
    UMovieSceneFloatSection* Section = nullptr;
    FMovieSceneFloatChannel* Channel = nullptr;
    int32 PostLandingStrikeKeyIndex = INDEX_NONE;
};

struct FHangarTimingDiscovery
{
    int32 SceneNumber = INDEX_NONE;
    ULevelSequence* Sequence = nullptr;
    UMovieScene* MovieScene = nullptr;
    UMovieScene3DTransformSection* RootSection = nullptr;
    UMovieScene3DTransformSection* RoofSection = nullptr;
    UMovieScene3DTransformSection* LatticeSection = nullptr;
    FMovieSceneDoubleChannel* RootPitch = nullptr;
    FMovieSceneDoubleChannel* RoofPitch = nullptr;
    FMovieSceneDoubleChannel* LatticeFlyZ = nullptr;
    TArray<FHangarLightChannel> Lights;
};

FString BindingName(UMovieScene& MovieScene, const FGuid& Guid)
{
    if (const FMovieScenePossessable* Possessable = MovieScene.FindPossessable(Guid))
    {
        return Possessable->GetName();
    }
    if (const FMovieSceneSpawnable* Spawnable = MovieScene.FindSpawnable(Guid))
    {
        return Spawnable->GetName();
    }
    return FString();
}

FString ParentBindingName(UMovieScene& MovieScene, const FGuid& Guid)
{
    const FMovieScenePossessable* Possessable = MovieScene.FindPossessable(Guid);
    return Possessable && Possessable->GetParent().IsValid()
        ? BindingName(MovieScene, Possessable->GetParent())
        : FString();
}

bool ParseArrivalSceneNumber(const AInfinityStageArrival& Arrival, int32& OutSceneNumber, FString& OutReason)
{
    const FString Label = Arrival.GetActorLabel();
    FString Prefix;
    FString Suffix;
    if (!Label.Split(TEXT(" "), &Prefix, &Suffix) || Suffix != TEXT("Arrival")
        || !Prefix.StartsWith(TEXT("S")) || Prefix.Len() < 2 || !Prefix.Mid(1).IsNumeric())
    {
        OutReason = FString::Printf(TEXT("actor label '%s' is not S<N> Arrival"), *Label);
        return false;
    }
    OutSceneNumber = FCString::Atoi(*Prefix.Mid(1));
    if (OutSceneNumber <= 0)
    {
        OutReason = FString::Printf(TEXT("actor label '%s' has an invalid scene number"), *Label);
        return false;
    }
    return true;
}

bool FindUniqueBinding(UMovieScene& MovieScene, const FString& WantedName, FGuid& OutGuid, FString& OutReason)
{
    TArray<FGuid> Matches;
    for (const FMovieSceneBinding& Binding : MovieScene.GetBindings())
    {
        if (BindingName(MovieScene, Binding.GetObjectGuid()) == WantedName)
        {
            Matches.Add(Binding.GetObjectGuid());
        }
    }
    if (Matches.Num() != 1)
    {
        OutReason = FString::Printf(TEXT("expected one binding '%s', found %d"), *WantedName, Matches.Num());
        return false;
    }
    OutGuid = Matches[0];
    return true;
}

FMovieSceneDoubleChannel* TransformChannel(
    UMovieScene& MovieScene,
    const FGuid& BindingGuid,
    const int32 ChannelIndex,
    UMovieScene3DTransformSection*& OutSection)
{
    OutSection = const_cast<UMovieScene3DTransformSection*>(
        FindBindingSection<UMovieScene3DTransformSection, UMovieScene3DTransformTrack>(MovieScene, BindingGuid));
    if (!OutSection)
    {
        return nullptr;
    }
    const TArrayView<FMovieSceneDoubleChannel*> Channels =
        OutSection->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>();
    return Channels.IsValidIndex(ChannelIndex) ? Channels[ChannelIndex] : nullptr;
}

bool IsS3StrikeLightLabel(const FString& Label)
{
    static const TSet<FString> S3StrikeLabels = {
        TEXT("S3 Strike Key"),
        TEXT("S3 Strike Fill L"),
        TEXT("S3 Strike Fill R"),
        TEXT("S3 Strike Cyc 1"),
        TEXT("S3 Strike Cyc 2"),
        TEXT("S3 Strike Cyc 3")
    };
    return S3StrikeLabels.Contains(Label);
}

bool IsHangarLightLabel(const FString& Label, const int32 SceneNumber)
{
    const FString ScenePrefix = FString::Printf(TEXT("S%d "), SceneNumber);
    return Label.StartsWith(ScenePrefix + TEXT("Uplight "))
        || Label.StartsWith(ScenePrefix + TEXT("Practical "))
        || Label.StartsWith(ScenePrefix + TEXT("Lattice Glow "))
        || (SceneNumber == 3 && IsS3StrikeLightLabel(Label));
}

bool FindPostLandingStrikeKey(
    FHangarLightChannel& Light,
    const FFrameNumber LandFrame,
    FString& OutReason)
{
    const TMovieSceneChannelData<const FMovieSceneFloatValue> Data = Light.Channel->GetData();
    const TArrayView<const FFrameNumber> Times = Data.GetTimes();
    const TArrayView<const FMovieSceneFloatValue> Values = Data.GetValues();
    TArray<int32> Candidates;
    for (int32 Index = 0; Index + 1 < Values.Num(); ++Index)
    {
        if (FMath::Abs(Values[Index].Value) <= HangarValueTolerance
            && Values[Index + 1].Value > HangarValueTolerance
            && Times[Index] >= LandFrame)
        {
            Candidates.Add(Index);
        }
    }
    if (Candidates.Num() > 1)
    {
        OutReason = FString::Printf(TEXT("%s has %d post-landing zero-to-positive strike ramps"),
            *Light.Label, Candidates.Num());
        return false;
    }
    Light.PostLandingStrikeKeyIndex = Candidates.IsEmpty() ? INDEX_NONE : Candidates[0];
    return true;
}

bool DiscoverHangarTiming(AInfinityStageArrival& Arrival, FHangarTimingDiscovery& Out, FString& OutReason)
{
    if (!ParseArrivalSceneNumber(Arrival, Out.SceneNumber, OutReason))
    {
        return false;
    }
    Out.Sequence = Arrival.MotionSequence.LoadSynchronous();
    Out.MovieScene = Out.Sequence ? Out.Sequence->GetMovieScene() : nullptr;
    if (!Out.MovieScene)
    {
        OutReason = TEXT("MotionSequence is missing or has no MovieScene");
        return false;
    }

    const FString RootLabel = FString::Printf(TEXT("S%d Hangar Root"), Out.SceneNumber);
    if (!Arrival.MotionBindingGuid.IsValid()
        || BindingName(*Out.MovieScene, Arrival.MotionBindingGuid) != RootLabel)
    {
        OutReason = FString::Printf(TEXT("MotionBindingGuid is not '%s'"), *RootLabel);
        return false;
    }
    Out.RootPitch = TransformChannel(
        *Out.MovieScene, Arrival.MotionBindingGuid, 4, Out.RootSection);
    if (!Out.RootPitch)
    {
        OutReason = TEXT("root_pitch channel is missing");
        return false;
    }
    const TArrayView<const FFrameNumber> RootTimes = Out.RootPitch->GetData().GetTimes();
    if (RootTimes.Num() == 0)
    {
        OutReason = TEXT("root_pitch channel has no landing key");
        return false;
    }
    const FFrameNumber LandFrame = RootTimes.Last();

    FGuid RoofGuid;
    const FString RoofLabel = FString::Printf(TEXT("S%d Hangar Roof Hinge"), Out.SceneNumber);
    TArray<FGuid> RoofMatches;
    for (const FMovieSceneBinding& Binding : Out.MovieScene->GetBindings())
    {
        if (BindingName(*Out.MovieScene, Binding.GetObjectGuid()) == RoofLabel)
        {
            RoofMatches.Add(Binding.GetObjectGuid());
        }
    }
    if (RoofMatches.Num() > 1)
    {
        OutReason = FString::Printf(TEXT("expected zero or one binding '%s', found %d"),
            *RoofLabel, RoofMatches.Num());
        return false;
    }
    if (RoofMatches.Num() == 1)
    {
        RoofGuid = RoofMatches[0];
        Out.RoofPitch = TransformChannel(*Out.MovieScene, RoofGuid, 4, Out.RoofSection);
        if (!Out.RoofPitch)
        {
            OutReason = TEXT("roof_pitch channel is missing");
            return false;
        }
    }

    FGuid LatticeGuid;
    if (!FindUniqueBinding(*Out.MovieScene,
        FString::Printf(TEXT("S%d Hangar Lattice Fly"), Out.SceneNumber), LatticeGuid, OutReason))
    {
        return false;
    }
    Out.LatticeFlyZ = TransformChannel(*Out.MovieScene, LatticeGuid, 2, Out.LatticeSection);
    if (!Out.LatticeFlyZ)
    {
        OutReason = TEXT("lattice_fly_z channel is missing");
        return false;
    }

    TSet<FString> LightLabels;
    for (const FMovieSceneBinding& Binding : Out.MovieScene->GetBindings())
    {
        const FString OwnName = BindingName(*Out.MovieScene, Binding.GetObjectGuid());
        const FString ParentName = ParentBindingName(*Out.MovieScene, Binding.GetObjectGuid());
        const FString Label = IsHangarLightLabel(ParentName, Out.SceneNumber)
            ? ParentName
            : (IsHangarLightLabel(OwnName, Out.SceneNumber) ? OwnName : FString());
        if (Label.IsEmpty())
        {
            continue;
        }

        TArray<TPair<UMovieSceneFloatSection*, FMovieSceneFloatChannel*>> Channels;
        for (UMovieSceneTrack* Track : Binding.GetTracks())
        {
            UMovieSceneFloatTrack* FloatTrack = Cast<UMovieSceneFloatTrack>(Track);
            if (!FloatTrack || FloatTrack->GetPropertyName() != TEXT("Intensity"))
            {
                continue;
            }
            for (UMovieSceneSection* BaseSection : FloatTrack->GetAllSections())
            {
                if (UMovieSceneFloatSection* Section = Cast<UMovieSceneFloatSection>(BaseSection))
                {
                    Channels.Emplace(Section, &Section->GetChannel());
                }
            }
        }
        if (Channels.IsEmpty())
        {
            continue;
        }
        if (Channels.Num() != 1 || LightLabels.Contains(Label))
        {
            OutReason = FString::Printf(TEXT("%s does not have exactly one unique Intensity channel"), *Label);
            return false;
        }
        LightLabels.Add(Label);
        FHangarLightChannel& Light = Out.Lights.AddDefaulted_GetRef();
        Light.Label = Label;
        Light.Section = Channels[0].Key;
        Light.Channel = Channels[0].Value;
        if (Out.SceneNumber != 6 && !FindPostLandingStrikeKey(Light, LandFrame, OutReason))
        {
            return false;
        }
    }
    if (Out.Lights.IsEmpty())
    {
        OutReason = TEXT("no uplight, practical or lattice-glow Intensity channels were found");
        return false;
    }
    if (Out.SceneNumber == 3)
    {
        int32 S3StrikeCount = 0;
        for (const FHangarLightChannel& Light : Out.Lights)
        {
            S3StrikeCount += IsS3StrikeLightLabel(Light.Label) ? 1 : 0;
        }
        if (S3StrikeCount != 6)
        {
            OutReason = FString::Printf(
                TEXT("expected all six named S3 Strike light Intensity channels, found %d"),
                S3StrikeCount);
            return false;
        }
    }
    if (Out.SceneNumber != 6)
    {
        const bool bHasPostLandingStrike = Out.Lights.ContainsByPredicate(
            [](const FHangarLightChannel& Light)
            {
                return Light.PostLandingStrikeKeyIndex != INDEX_NONE;
            });
        if (!bHasPostLandingStrike)
        {
            OutReason = TEXT("no post-landing zero-to-positive light ramp was found");
            return false;
        }
    }
    return true;
}

double FrameSeconds(const UMovieScene& MovieScene, const FFrameNumber Frame)
{
    return MovieScene.GetTickResolution().AsSeconds(FFrameTime(Frame));
}

FString FormatDoubleKeys(
    const UMovieScene& MovieScene,
    const FMovieSceneDoubleChannel& Channel)
{
    FString Result;
    const TMovieSceneChannelData<const FMovieSceneDoubleValue> Data = Channel.GetData();
    const TArrayView<const FFrameNumber> Times = Data.GetTimes();
    const TArrayView<const FMovieSceneDoubleValue> Values = Data.GetValues();
    for (int32 Index = 0; Index < Times.Num(); ++Index)
    {
        if (!Result.IsEmpty())
        {
            Result += TEXT(",");
        }
        Result += FString::Printf(
            TEXT("%.4f:%.4f"),
            FrameSeconds(MovieScene, Times[Index]),
            Values[Index].Value);
    }
    return Result;
}

FFrameNumber SecondsFrame(const UMovieScene& MovieScene, const double Seconds)
{
    return MovieScene.GetTickResolution().AsFrameTime(Seconds).RoundToFrame();
}

bool CubicShape(
    const FMovieSceneDoubleChannel& Channel,
    const TArray<double>& ExpectedValues,
    const bool bFirstKeyAtZero)
{
    const TMovieSceneChannelData<const FMovieSceneDoubleValue> Data = Channel.GetData();
    const TArrayView<const FFrameNumber> Times = Data.GetTimes();
    const TArrayView<const FMovieSceneDoubleValue> Values = Data.GetValues();
    if (Values.Num() != ExpectedValues.Num() || Times.Num() != ExpectedValues.Num())
    {
        return false;
    }
    if (bFirstKeyAtZero && Times[0] != FFrameNumber(0))
    {
        return false;
    }
    for (int32 Index = 0; Index < Values.Num(); ++Index)
    {
        if (!FMath::IsNearlyEqual(Values[Index].Value, ExpectedValues[Index], HangarValueTolerance)
            || Values[Index].InterpMode != RCIM_Cubic)
        {
            return false;
        }
    }
    return true;
}

bool ThreeKeyCubicShapeAtZero(const FMovieSceneDoubleChannel& Channel)
{
    const TMovieSceneChannelData<const FMovieSceneDoubleValue> Data = Channel.GetData();
    const TArrayView<const FFrameNumber> Times = Data.GetTimes();
    const TArrayView<const FMovieSceneDoubleValue> Values = Data.GetValues();
    if (Times.Num() != 3 || Values.Num() != 3 || Times[0] != FFrameNumber(0))
    {
        return false;
    }
    for (const FMovieSceneDoubleValue& Value : Values)
    {
        if (Value.InterpMode != RCIM_Cubic)
        {
            return false;
        }
    }
    return true;
}

bool ValidateStandardShape(FHangarTimingDiscovery& Discovery, FString& OutReason)
{
    if (!CubicShape(*Discovery.RootPitch, {-90.0, 0.0}, false))
    {
        OutReason = TEXT("root_pitch does not match the two-key -90 to 0 cubic shape");
        return false;
    }
    const bool bS5 = Discovery.SceneNumber == 5;
    if (bS5 && !Discovery.RoofPitch)
    {
        OutReason = TEXT("S5 is missing its roof hinge channel");
        return false;
    }
    if (Discovery.RoofPitch
        && !(bS5
            ? ThreeKeyCubicShapeAtZero(*Discovery.RoofPitch)
            : CubicShape(*Discovery.RoofPitch, {-90.0, -90.0, 0.0}, true)))
    {
        OutReason = TEXT("roof_pitch does not match the standard three-key cubic shape");
        return false;
    }
    if (!(bS5
        ? ThreeKeyCubicShapeAtZero(*Discovery.LatticeFlyZ)
        : CubicShape(*Discovery.LatticeFlyZ, {2800.0, 2800.0, 1200.0}, true)))
    {
        OutReason = TEXT("lattice_fly_z does not match the standard three-key cubic shape");
        return false;
    }
    for (const FHangarLightChannel& Light : Discovery.Lights)
    {
        const TArrayView<const FMovieSceneFloatValue> Values = Light.Channel->GetData().GetValues();
        for (const FMovieSceneFloatValue& Value : Values)
        {
            if (Value.InterpMode != RCIM_Linear)
            {
                OutReason = FString::Printf(TEXT("%s Intensity keys are not linear"), *Light.Label);
                return false;
            }
        }
    }
    return true;
}

void NotifyHangarTiming(const FString& Message, const bool bSuccess)
{
    if (!FSlateApplication::IsInitialized())
    {
        return;
    }
    FNotificationInfo Info(FText::FromString(Message));
    Info.ExpireDuration = bSuccess ? 3.0f : 6.0f;
    if (TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info))
    {
        Item->SetCompletionState(bSuccess
            ? SNotificationItem::CS_Success
            : SNotificationItem::CS_Fail);
    }
}

bool RefuseHangarTiming(AInfinityStageArrival& Arrival, const FString& Reason)
{
    UE_LOG(LogInfinityStageArrival, Warning,
        TEXT("INFINITY_HANGAR_TIMING_REFUSED|actor=%s|reason=%s"),
        *Arrival.GetActorNameOrLabel(), *Reason);
    NotifyHangarTiming(FString::Printf(TEXT("Hangar timing refused: %s"), *Reason), false);
    return false;
}
#endif
}

AInfinityStageArrival::AInfinityStageArrival()
{
    // No clock of its own: the Master frame, delivered by the Passage track, is the only time.
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);
}

#if WITH_EDITOR
void AInfinityStageArrival::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    HangarTiming.LightStrikeSeconds =
        HangarTiming.LandSeconds + HangarTiming.StrikeAfterLandSeconds;
}
#endif

bool AInfinityStageArrival::ReadHangarTiming()
{
#if WITH_EDITOR
    FHangarTimingDiscovery Discovery;
    FString Reason;
    if (!DiscoverHangarTiming(*this, Discovery, Reason))
    {
        return RefuseHangarTiming(*this, FString::Printf(TEXT("read: %s"), *Reason));
    }

    const TArrayView<const FFrameNumber> RootTimes = Discovery.RootPitch->GetData().GetTimes();
    const TArrayView<const FFrameNumber> LatticeTimes = Discovery.LatticeFlyZ->GetData().GetTimes();
    if (RootTimes.Num() != 2 || LatticeTimes.Num() != 3)
    {
        return RefuseHangarTiming(*this, TEXT("read: root or lattice key count is non-standard"));
    }

    HangarTiming.bHasRoofHinge = Discovery.RoofPitch != nullptr;
    HangarTiming.LandSeconds = FrameSeconds(*Discovery.MovieScene, RootTimes.Last());
    if (Discovery.RoofPitch)
    {
        const TArrayView<const FFrameNumber> RoofTimes = Discovery.RoofPitch->GetData().GetTimes();
        if (RoofTimes.Num() != 3)
        {
            return RefuseHangarTiming(*this, TEXT("read: roof key count is non-standard"));
        }
        HangarTiming.RoofCloseStartSeconds = FrameSeconds(*Discovery.MovieScene, RoofTimes[1]);
        HangarTiming.RoofCloseEndSeconds = FrameSeconds(*Discovery.MovieScene, RoofTimes[2]);
    }
    HangarTiming.LatticeStartSeconds = FrameSeconds(*Discovery.MovieScene, LatticeTimes[1]);
    HangarTiming.LatticeEndSeconds = FrameSeconds(*Discovery.MovieScene, LatticeTimes[2]);

    HangarTiming.bDimInsteadOfStrike = Discovery.SceneNumber == 6;
    if (!HangarTiming.bDimInsteadOfStrike)
    {
        double EarliestStrike = TNumericLimits<double>::Max();
        for (const FHangarLightChannel& Light : Discovery.Lights)
        {
            if (Light.PostLandingStrikeKeyIndex == INDEX_NONE)
            {
                continue;
            }
            const TArrayView<const FFrameNumber> Times = Light.Channel->GetData().GetTimes();
            EarliestStrike = FMath::Min(
                EarliestStrike,
                FrameSeconds(*Discovery.MovieScene, Times[Light.PostLandingStrikeKeyIndex]));
        }
        HangarTiming.LightStrikeSeconds = EarliestStrike;
        HangarTiming.StrikeAfterLandSeconds = EarliestStrike - HangarTiming.LandSeconds;
    }

    UE_LOG(LogInfinityStageArrival, Display,
        TEXT("INFINITY_HANGAR_TIMING_READ|actor=%s|roof=%.4f..%.4f|lattice=%.4f..%.4f|mode=%s|strike_after_land=%.4f|strike=%.4f|dim=%.4f|lights=%d"),
        *GetActorNameOrLabel(),
        HangarTiming.RoofCloseStartSeconds,
        HangarTiming.RoofCloseEndSeconds,
        HangarTiming.LatticeStartSeconds,
        HangarTiming.LatticeEndSeconds,
        HangarTiming.bDimInsteadOfStrike ? TEXT("dim") : TEXT("strike"),
        HangarTiming.StrikeAfterLandSeconds,
        HangarTiming.LightStrikeSeconds,
        HangarTiming.DimSeconds,
        Discovery.Lights.Num());
    NotifyHangarTiming(TEXT("Hangar timing read from the rise sequence."), true);
    return true;
#else
    return false;
#endif
}

bool AInfinityStageArrival::ApplyHangarTiming()
{
#if WITH_EDITOR
    FHangarTimingDiscovery Discovery;
    FString Reason;
    if (!DiscoverHangarTiming(*this, Discovery, Reason))
    {
        return RefuseHangarTiming(*this, Reason);
    }
    if (!ValidateStandardShape(Discovery, Reason))
    {
        return RefuseHangarTiming(*this, Reason);
    }

    const TArrayView<const FFrameNumber> RootTimes = Discovery.RootPitch->GetData().GetTimes();
    const double LandSeconds = FrameSeconds(*Discovery.MovieScene, RootTimes.Last());
    const bool bHasRoof = Discovery.RoofPitch != nullptr;
    const bool bDimInsteadOfStrike = HangarTiming.bDimInsteadOfStrike || Discovery.SceneNumber == 6;
    const FFrameNumber RoofStart = SecondsFrame(*Discovery.MovieScene, HangarTiming.RoofCloseStartSeconds);
    const FFrameNumber RoofEnd = SecondsFrame(*Discovery.MovieScene, HangarTiming.RoofCloseEndSeconds);
    const FFrameNumber LatticeStart = SecondsFrame(*Discovery.MovieScene, HangarTiming.LatticeStartSeconds);
    const FFrameNumber LatticeEnd = SecondsFrame(*Discovery.MovieScene, HangarTiming.LatticeEndSeconds);
    const double LightStrikeSeconds = LandSeconds + HangarTiming.StrikeAfterLandSeconds;
    const FFrameNumber StrikeTarget = SecondsFrame(*Discovery.MovieScene, LightStrikeSeconds);
    const FFrameNumber DimStart = RootTimes.Last();
    const FFrameNumber DimEnd = SecondsFrame(
        *Discovery.MovieScene,
        LandSeconds + HangarTiming.DimSeconds);
    if (bHasRoof && RoofStart < RootTimes.Last())
    {
        return RefuseHangarTiming(*this, FString::Printf(
            TEXT("roof start %.4f is before landing %.4f"),
            HangarTiming.RoofCloseStartSeconds, LandSeconds));
    }
    if (bHasRoof && RoofEnd <= RoofStart)
    {
        return RefuseHangarTiming(*this, TEXT("roof end must be after roof start"));
    }
    if (bHasRoof && LatticeStart < RoofEnd)
    {
        return RefuseHangarTiming(*this, TEXT("lattice start must not overlap the roof close"));
    }
    if (!bHasRoof && LatticeStart < RootTimes.Last())
    {
        return RefuseHangarTiming(*this, TEXT("roofless lattice start must not be before landing"));
    }
    if (LatticeEnd <= LatticeStart)
    {
        return RefuseHangarTiming(*this, TEXT("lattice end must be after lattice start"));
    }

    const TRange<FFrameNumber> PlaybackRange = Discovery.MovieScene->GetPlaybackRange();
    if (!PlaybackRange.HasLowerBound() || !PlaybackRange.HasUpperBound())
    {
        return RefuseHangarTiming(*this, TEXT("sequence playback range is unbounded"));
    }
    const FFrameNumber PlaybackStart = PlaybackRange.GetLowerBoundValue();
    const FFrameNumber PlaybackEnd = PlaybackRange.GetUpperBoundValue();
    if ((bHasRoof && (RoofStart < PlaybackStart || RoofEnd >= PlaybackEnd))
        || LatticeStart < PlaybackStart || LatticeEnd >= PlaybackEnd)
    {
        return RefuseHangarTiming(*this, TEXT("requested mechanism timing is outside the playback range"));
    }
    if (!bDimInsteadOfStrike && (HangarTiming.StrikeAfterLandSeconds < 0.0
        || StrikeTarget < RootTimes.Last() || StrikeTarget < PlaybackStart || StrikeTarget >= PlaybackEnd))
    {
        return RefuseHangarTiming(*this,
            TEXT("light strike offset is negative or its absolute time is beyond the playback range"));
    }
    if (bDimInsteadOfStrike && (HangarTiming.DimSeconds <= 0.0
        || DimStart < PlaybackStart || DimEnd <= DimStart || DimEnd >= PlaybackEnd))
    {
        return RefuseHangarTiming(*this, TEXT("light dim duration is non-positive or beyond the playback range"));
    }

    FFrameNumber EarliestStrike = FFrameNumber(TNumericLimits<int32>::Max());
    FFrameNumber LightShift(0);
    TArray<float> DimStartValues;
    if (bDimInsteadOfStrike)
    {
        DimStartValues.Reserve(Discovery.Lights.Num());
        for (const FHangarLightChannel& Light : Discovery.Lights)
        {
            float StartValue = 0.0f;
            if (!Light.Channel->Evaluate(FFrameTime(DimStart), StartValue)
                || !FMath::IsFinite(StartValue) || StartValue < 0.0f)
            {
                return RefuseHangarTiming(*this, FString::Printf(
                    TEXT("%s has no finite non-negative Intensity value at landing"),
                    *Light.Label));
            }
            DimStartValues.Add(StartValue);
        }
    }
    else
    {
        for (const FHangarLightChannel& Light : Discovery.Lights)
        {
            if (Light.PostLandingStrikeKeyIndex == INDEX_NONE)
            {
                continue;
            }
            const TArrayView<const FFrameNumber> Times = Light.Channel->GetData().GetTimes();
            EarliestStrike = FMath::Min(EarliestStrike, Times[Light.PostLandingStrikeKeyIndex]);
        }
        LightShift = StrikeTarget - EarliestStrike;
        for (const FHangarLightChannel& Light : Discovery.Lights)
        {
            if (Light.PostLandingStrikeKeyIndex == INDEX_NONE)
            {
                continue;
            }
            const TArrayView<const FFrameNumber> Times = Light.Channel->GetData().GetTimes();
            for (int32 Index = Light.PostLandingStrikeKeyIndex; Index < Times.Num(); ++Index)
            {
                const FFrameNumber Shifted = Times[Index] + LightShift;
                const FFrameNumber Previous = Index > Light.PostLandingStrikeKeyIndex
                    ? Times[Index - 1] + LightShift
                    : (Index > 0 ? Times[Index - 1] : FFrameNumber(TNumericLimits<int32>::Min()));
                if (Shifted < PlaybackStart || Shifted >= PlaybackEnd
                    || Shifted <= Previous)
                {
                    return RefuseHangarTiming(*this, FString::Printf(
                        TEXT("shifting %s would move or reorder keys outside the playback range"),
                        *Light.Label));
                }
            }
        }
    }

    FString S5RoofBefore;
    FString S5LatticeBefore;
    if (Discovery.SceneNumber == 5)
    {
        S5RoofBefore = FormatDoubleKeys(*Discovery.MovieScene, *Discovery.RoofPitch);
        S5LatticeBefore = FormatDoubleKeys(*Discovery.MovieScene, *Discovery.LatticeFlyZ);
    }

    const FScopedTransaction Transaction(
        TEXT("InfinityStageHangarTiming"),
        NSLOCTEXT("InfinityStage", "ApplyHangarTiming", "Apply Hangar Timing"),
        Discovery.Sequence);
    Discovery.Sequence->Modify();
    Discovery.MovieScene->Modify();
    if (bHasRoof)
    {
        Discovery.RoofSection->Modify();
        TArrayView<FFrameNumber> Times = Discovery.RoofPitch->GetData().GetTimes();
        Times[1] = RoofStart;
        Times[2] = RoofEnd;
        Discovery.RoofPitch->AutoSetTangents();
    }
    Discovery.LatticeSection->Modify();
    {
        TArrayView<FFrameNumber> Times = Discovery.LatticeFlyZ->GetData().GetTimes();
        Times[1] = LatticeStart;
        Times[2] = LatticeEnd;
        Discovery.LatticeFlyZ->AutoSetTangents();
    }
    for (int32 LightIndex = 0; LightIndex < Discovery.Lights.Num(); ++LightIndex)
    {
        FHangarLightChannel& Light = Discovery.Lights[LightIndex];
        if (bDimInsteadOfStrike)
        {
            Light.Section->Modify();
            TMovieSceneChannelData<FMovieSceneFloatValue> Data = Light.Channel->GetData();
            for (int32 KeyIndex = Data.GetTimes().Num() - 1; KeyIndex >= 0; --KeyIndex)
            {
                if (Data.GetTimes()[KeyIndex] >= DimStart)
                {
                    Data.RemoveKey(KeyIndex);
                }
            }
            Light.Channel->AddLinearKey(DimStart, DimStartValues[LightIndex]);
            Light.Channel->AddLinearKey(DimEnd, DimStartValues[LightIndex] * 0.02f);
        }
        else if (Light.PostLandingStrikeKeyIndex != INDEX_NONE && LightShift.Value != 0)
        {
            Light.Section->Modify();
            TArrayView<FFrameNumber> Times = Light.Channel->GetData().GetTimes();
            const FFrameNumber StrikeBefore = Times[Light.PostLandingStrikeKeyIndex];
            for (int32 Index = Light.PostLandingStrikeKeyIndex; Index < Times.Num(); ++Index)
            {
                Times[Index] += LightShift;
            }
            UE_LOG(LogInfinityStageArrival, Display,
                TEXT("INFINITY_HANGAR_TIMING_LIGHT|actor=%s|light=%s|action=moved|strike_before=%.4f|strike_after=%.4f|shift=%.4f"),
                *GetActorNameOrLabel(),
                *Light.Label,
                FrameSeconds(*Discovery.MovieScene, StrikeBefore),
                FrameSeconds(*Discovery.MovieScene, Times[Light.PostLandingStrikeKeyIndex]),
                FrameSeconds(*Discovery.MovieScene, LightShift));
        }
        else if (Light.PostLandingStrikeKeyIndex != INDEX_NONE)
        {
            UE_LOG(LogInfinityStageArrival, Display,
                TEXT("INFINITY_HANGAR_TIMING_LIGHT|actor=%s|light=%s|action=kept|reason=already_at_target"),
                *GetActorNameOrLabel(), *Light.Label);
        }
        else
        {
            UE_LOG(LogInfinityStageArrival, Display,
                TEXT("INFINITY_HANGAR_TIMING_LIGHT|actor=%s|light=%s|action=kept|reason=no_post_landing_ramp"),
                *GetActorNameOrLabel(), *Light.Label);
        }
    }
    HangarTiming.LandSeconds = LandSeconds;
    HangarTiming.LightStrikeSeconds = LightStrikeSeconds;
    Discovery.Sequence->MarkPackageDirty();

    if (Discovery.SceneNumber == 5)
    {
        UE_LOG(LogInfinityStageArrival, Display,
            TEXT("INFINITY_HANGAR_TIMING_S5_KEYS|actor=%s|roof_before=%s|roof_after=%s|lattice_before=%s|lattice_after=%s"),
            *GetActorNameOrLabel(),
            *S5RoofBefore,
            *FormatDoubleKeys(*Discovery.MovieScene, *Discovery.RoofPitch),
            *S5LatticeBefore,
            *FormatDoubleKeys(*Discovery.MovieScene, *Discovery.LatticeFlyZ));
    }

    UE_LOG(LogInfinityStageArrival, Display,
        TEXT("INFINITY_HANGAR_TIMING_APPLIED|actor=%s|roof=%.4f..%.4f|lattice=%.4f..%.4f|mode=%s|strike_after_land=%.4f|strike=%.4f|dim=%.4f|lights=%d"),
        *GetActorNameOrLabel(),
        HangarTiming.RoofCloseStartSeconds,
        HangarTiming.RoofCloseEndSeconds,
        HangarTiming.LatticeStartSeconds,
        HangarTiming.LatticeEndSeconds,
        bDimInsteadOfStrike ? TEXT("dim") : TEXT("strike"),
        HangarTiming.StrikeAfterLandSeconds,
        HangarTiming.LightStrikeSeconds,
        HangarTiming.DimSeconds,
        Discovery.Lights.Num());
    NotifyHangarTiming(TEXT("Hangar timing applied. Save the rise sequence when ready."), true);
    return true;
#else
    return false;
#endif
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
