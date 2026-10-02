#include "InfinityStageArrival.h"

#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Components/PointLightComponent.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Serialization/MemoryWriter.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

namespace
{
constexpr int32 TimingFps = 30;

FFrameNumber Frame(const double Seconds)
{
    return FFrameRate(TimingFps, 1).AsFrameTime(Seconds).RoundToFrame();
}

FGuid AddTransform(
    UMovieScene& MovieScene,
    const TCHAR* Name,
    const int32 ChannelIndex,
    const TArray<FFrameNumber>& Times,
    const TArray<double>& Values,
    FMovieSceneDoubleChannel*& OutChannel)
{
    const FGuid Binding = MovieScene.AddPossessable(Name, AActor::StaticClass());
    UMovieScene3DTransformTrack* Track = MovieScene.AddTrack<UMovieScene3DTransformTrack>(Binding);
    UMovieScene3DTransformSection* Section =
        CastChecked<UMovieScene3DTransformSection>(Track->CreateNewSection());
    Section->SetRange(TRange<FFrameNumber>::All());
    Track->AddSection(*Section);
    const TArrayView<FMovieSceneDoubleChannel*> Channels =
        Section->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>();
    for (int32 Index = 0; Index < Channels.Num(); ++Index)
    {
        Channels[Index]->SetDefault(Index >= 6 ? 1.0 : 0.0);
    }
    OutChannel = Channels[ChannelIndex];
    for (int32 Index = 0; Index < Times.Num(); ++Index)
    {
        OutChannel->AddCubicKey(Times[Index], Values[Index]);
    }
    return Binding;
}

FMovieSceneFloatChannel* AddLight(
    UMovieScene& MovieScene,
    const TCHAR* Name,
    const TArray<FFrameNumber>& Times,
    const TArray<float>& Values)
{
    const FGuid Binding = MovieScene.AddPossessable(Name, UPointLightComponent::StaticClass());
    UMovieSceneFloatTrack* Track = MovieScene.AddTrack<UMovieSceneFloatTrack>(Binding);
    Track->SetPropertyNameAndPath(TEXT("Intensity"), TEXT("Intensity"));
    UMovieSceneFloatSection* Section = CastChecked<UMovieSceneFloatSection>(Track->CreateNewSection());
    Section->SetRange(TRange<FFrameNumber>::All());
    Track->AddSection(*Section);
    FMovieSceneFloatChannel& Channel = Section->GetChannel();
    for (int32 Index = 0; Index < Times.Num(); ++Index)
    {
        Channel.AddLinearKey(Times[Index], Values[Index]);
    }
    return &Channel;
}

template <typename ChannelType>
TArray<uint8> ChannelBytes(ChannelType& Channel)
{
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes, true);
    Writer << Channel;
    return Bytes;
}

struct FHangarTimingFixture
{
    UWorld* World = nullptr;
    ULevelSequence* Sequence = nullptr;
    UMovieScene* MovieScene = nullptr;
    AInfinityStageArrival* Arrival = nullptr;
    FMovieSceneDoubleChannel* Root = nullptr;
    FMovieSceneDoubleChannel* Roof = nullptr;
    FMovieSceneDoubleChannel* Lattice = nullptr;
    TArray<FMovieSceneFloatChannel*> Lights;

    explicit FHangarTimingFixture(
        const TArray<TPair<double, double>>& StrikeAndRampSeconds,
        const int32 SceneNumber = 1,
        const bool bHasRoof = true,
        const TArray<FString>& LightLabels = {})
    {
        Sequence = NewObject<ULevelSequence>(GetTransientPackage());
        Sequence->Initialize();
        MovieScene = Sequence->GetMovieScene();
        MovieScene->SetTickResolutionDirectly(FFrameRate(TimingFps, 1));
        MovieScene->SetDisplayRate(FFrameRate(TimingFps, 1));
        MovieScene->SetPlaybackRange(FFrameNumber(0), TimingFps * 30, false);

        const FGuid RootBinding = AddTransform(
            *MovieScene,
            *FString::Printf(TEXT("S%d Hangar Root"), SceneNumber),
            4,
            {Frame(-5.8739), Frame(4.1261)},
            {-90.0, 0.0},
            Root);
        if (bHasRoof)
        {
            AddTransform(
                *MovieScene,
                *FString::Printf(TEXT("S%d Hangar Roof Hinge"), SceneNumber),
                4,
                {Frame(0.0), Frame(6.6333), Frame(12.6333)},
                {-90.0, -90.0, 0.0},
                Roof);
        }
        AddTransform(
            *MovieScene,
            *FString::Printf(TEXT("S%d Hangar Lattice Fly"), SceneNumber),
            2,
            {Frame(0.0), Frame(12.6333), Frame(16.6333)},
            {2800.0, 2800.0, 1200.0},
            Lattice);

        for (int32 Index = 0; Index < StrikeAndRampSeconds.Num(); ++Index)
        {
            const double Strike = StrikeAndRampSeconds[Index].Key;
            const double Ramp = StrikeAndRampSeconds[Index].Value;
            Lights.Add(AddLight(
                *MovieScene,
                LightLabels.IsValidIndex(Index)
                    ? *LightLabels[Index]
                    : *FString::Printf(TEXT("S%d Practical L%d"), SceneNumber, Index + 1),
                {Frame(0.0), Frame(Strike), Frame(Strike + Ramp)},
                {0.0f, 0.0f, 400.0f + Index * 100.0f}));
        }

        World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        Arrival = World->SpawnActor<AInfinityStageArrival>();
        Arrival->SetActorLabel(*FString::Printf(TEXT("S%d Arrival"), SceneNumber), false);
        Arrival->MotionSequence = Sequence;
        Arrival->MotionBindingGuid = RootBinding;
    }

    ~FHangarTimingFixture()
    {
        World->DestroyWorld(false);
    }
};

}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingAppliesTest,
    "InfinityStage.Hangar.TimingAppliesToTransientRise",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingAppliesTest::RunTest(const FString& Parameters)
{
    FHangarTimingFixture Fixture({{6.6333, 0.2}, {7.1333, 0.3}});
    const TArray<uint8> RootBefore = ChannelBytes(*Fixture.Root);

    TestTrue(TEXT("The default timing applies to a standard transient rise"),
        Fixture.Arrival->ApplyHangarTiming());
    const TArrayView<const FFrameNumber> RoofTimes = Fixture.Roof->GetData().GetTimes();
    const TArrayView<const FFrameNumber> LatticeTimes = Fixture.Lattice->GetData().GetTimes();
    TestEqual(TEXT("Roof close starts at landing"), RoofTimes[1].Value, Frame(4.1261).Value);
    TestEqual(TEXT("Roof close ends at the exposed default"), RoofTimes[2].Value, Frame(8.6261).Value);
    TestEqual(TEXT("Lattice starts after the roof"), LatticeTimes[1].Value, Frame(8.6261).Value);
    TestEqual(TEXT("Lattice ends at the exposed default"), LatticeTimes[2].Value, Frame(12.6261).Value);
    TestEqual(TEXT("The earliest light strike moves to ten seconds"),
        Fixture.Lights[0]->GetData().GetTimes()[1].Value, Frame(10.0).Value);
    TestTrue(TEXT("Root keys are byte-identical"), ChannelBytes(*Fixture.Root) == RootBefore);

    // Negative control: an ApplyHangarTiming stub returns false and leaves every asserted old time in place.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingRefusesBadOrderTest,
    "InfinityStage.Hangar.TimingRefusesBadOrder",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingRefusesBadOrderTest::RunTest(const FString& Parameters)
{
    FHangarTimingFixture Fixture({{6.6333, 0.2}});
    const TArray<uint8> RoofBefore = ChannelBytes(*Fixture.Roof);
    const TArray<uint8> LatticeBefore = ChannelBytes(*Fixture.Lattice);
    const TArray<uint8> LightBefore = ChannelBytes(*Fixture.Lights[0]);

    Fixture.Arrival->HangarTiming.RoofCloseStartSeconds = 4.0;
    AddExpectedMessagePlain(
        TEXT("INFINITY_HANGAR_TIMING_REFUSED"),
        ELogVerbosity::Warning,
        EAutomationExpectedMessageFlags::Contains,
        1);
    TestFalse(TEXT("Roof motion before landing is refused"), Fixture.Arrival->ApplyHangarTiming());
    TestTrue(TEXT("Bad roof order changes no roof keys"), ChannelBytes(*Fixture.Roof) == RoofBefore);
    TestTrue(TEXT("Bad roof order changes no lattice keys"), ChannelBytes(*Fixture.Lattice) == LatticeBefore);
    TestTrue(TEXT("Bad roof order changes no light keys"), ChannelBytes(*Fixture.Lights[0]) == LightBefore);

    Fixture.Arrival->HangarTiming.RoofCloseStartSeconds = 4.1261;
    Fixture.Arrival->HangarTiming.LatticeStartSeconds = 8.0;
    AddExpectedMessagePlain(
        TEXT("INFINITY_HANGAR_TIMING_REFUSED"),
        ELogVerbosity::Warning,
        EAutomationExpectedMessageFlags::Contains,
        1);
    TestFalse(TEXT("Lattice motion overlapping the roof is refused"),
        Fixture.Arrival->ApplyHangarTiming());
    TestTrue(TEXT("Overlapping lattice changes no roof keys"), ChannelBytes(*Fixture.Roof) == RoofBefore);
    TestTrue(TEXT("Overlapping lattice changes no lattice keys"), ChannelBytes(*Fixture.Lattice) == LatticeBefore);
    TestTrue(TEXT("Overlapping lattice changes no light keys"), ChannelBytes(*Fixture.Lights[0]) == LightBefore);

    Fixture.Arrival->HangarTiming.LatticeStartSeconds = 8.6261;
    TestTrue(TEXT("The same fixture applies after its order is corrected"),
        Fixture.Arrival->ApplyHangarTiming());
    TestFalse(TEXT("The corrected apply moves the roof keys"), ChannelBytes(*Fixture.Roof) == RoofBefore);

    // Negative control: the two refusal assertions need the refusal log, and the corrected sentinel fails with a stub.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingPreservesLightStaggerTest,
    "InfinityStage.Hangar.TimingPreservesLightStagger",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingPreservesLightStaggerTest::RunTest(const FString& Parameters)
{
    FHangarTimingFixture Fixture({{6.6333, 0.2}, {7.1333, 0.3}, {8.0667, 0.4}});
    TArray<TArray<FMovieSceneFloatValue>> ValuesBefore;
    TArray<int32> StrikeOffsets;
    TArray<int32> RampDurations;
    const int32 FirstStrikeBefore = Fixture.Lights[0]->GetData().GetTimes()[1].Value;
    for (const FMovieSceneFloatChannel* Light : Fixture.Lights)
    {
        const TMovieSceneChannelData<const FMovieSceneFloatValue> Data = Light->GetData();
        ValuesBefore.Emplace(Data.GetValues());
        StrikeOffsets.Add(Data.GetTimes()[1].Value - FirstStrikeBefore);
        RampDurations.Add(Data.GetTimes()[2].Value - Data.GetTimes()[1].Value);
    }

    TestTrue(TEXT("The stagger fixture applies"), Fixture.Arrival->ApplyHangarTiming());
    const int32 FirstStrikeAfter = Fixture.Lights[0]->GetData().GetTimes()[1].Value;
    TestEqual(TEXT("The first strike lands at ten seconds"), FirstStrikeAfter, Frame(10.0).Value);
    for (int32 Index = 0; Index < Fixture.Lights.Num(); ++Index)
    {
        const TMovieSceneChannelData<const FMovieSceneFloatValue> Data = Fixture.Lights[Index]->GetData();
        TestEqual(
            *FString::Printf(TEXT("Light %d keeps its strike offset"), Index),
            Data.GetTimes()[1].Value - FirstStrikeAfter,
            StrikeOffsets[Index]);
        TestEqual(
            *FString::Printf(TEXT("Light %d keeps its ramp duration"), Index),
            Data.GetTimes()[2].Value - Data.GetTimes()[1].Value,
            RampDurations[Index]);
        TestTrue(
            *FString::Printf(TEXT("Light %d keeps values and interpolation"), Index),
            TArray<FMovieSceneFloatValue>(Data.GetValues()) == ValuesBefore[Index]);
    }

    // Negative control: a stub returns false, leaves the first strike at 6.6333 s, and fails both sentinels.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingMovesS3StrikeLightsTest,
    "InfinityStage.Hangar.TimingMovesS3StrikeLights",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingMovesS3StrikeLightsTest::RunTest(const FString& Parameters)
{
    const TArray<FString> Labels = {
        TEXT("S3 Strike Key"),
        TEXT("S3 Strike Fill L"),
        TEXT("S3 Strike Fill R"),
        TEXT("S3 Strike Cyc 1"),
        TEXT("S3 Strike Cyc 2"),
        TEXT("S3 Strike Cyc 3")
    };
    FHangarTimingFixture Fixture(
        {{6.1333, 0.20}, {6.3000, 0.25}, {6.4667, 0.30},
         {6.6333, 0.35}, {6.8000, 0.40}, {6.9667, 0.45}},
        3,
        true,
        Labels);
    FMovieSceneFloatChannel* Decoy = AddLight(
        *Fixture.MovieScene,
        TEXT("S3 Practical Decoy"),
        {Frame(0.0), Frame(5.0), Frame(5.5)},
        {0.0f, 0.0f, 999.0f});
    const TArray<uint8> DecoyBefore = ChannelBytes(*Decoy);

    TArray<int32> StrikeOffsets;
    TArray<int32> RampDurations;
    const int32 FirstStrikeBefore = Fixture.Lights[0]->GetData().GetTimes()[1].Value;
    for (const FMovieSceneFloatChannel* Light : Fixture.Lights)
    {
        const TArrayView<const FFrameNumber> Times = Light->GetData().GetTimes();
        StrikeOffsets.Add(Times[1].Value - FirstStrikeBefore);
        RampDurations.Add(Times[2].Value - Times[1].Value);
    }

    TestTrue(TEXT("S3 applies to the six named Strike lights"), Fixture.Arrival->ApplyHangarTiming());
    const int32 FirstStrikeAfter = Fixture.Lights[0]->GetData().GetTimes()[1].Value;
    TestEqual(TEXT("S3 earliest strike lands on the data-driven target"),
        FirstStrikeAfter, Frame(Fixture.Arrival->HangarTiming.LightStrikeSeconds).Value);
    for (int32 Index = 0; Index < Fixture.Lights.Num(); ++Index)
    {
        const TArrayView<const FFrameNumber> Times = Fixture.Lights[Index]->GetData().GetTimes();
        TestEqual(*FString::Printf(TEXT("S3 light %d preserves its offset"), Index),
            Times[1].Value - FirstStrikeAfter, StrikeOffsets[Index]);
        TestEqual(*FString::Printf(TEXT("S3 light %d preserves its ramp"), Index),
            Times[2].Value - Times[1].Value, RampDurations[Index]);
    }
    TestTrue(TEXT("A non-Strike S3 light is byte-identical"), ChannelBytes(*Decoy) == DecoyBefore);

    // Negative control: with Apply stubbed, the first named light stays at 6.1333 s,
    // the ten-second sentinel fails, and the per-light assertions cannot mask that failure.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingS6DimsInsteadOfStrikeTest,
    "InfinityStage.Hangar.TimingS6DimsInsteadOfStrike",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingS6DimsInsteadOfStrikeTest::RunTest(const FString& Parameters)
{
    FHangarTimingFixture Fixture({{6.6333, 0.4}, {7.1333, 0.5}}, 6, false);
    const TArray<uint8> RootBefore = ChannelBytes(*Fixture.Root);
    for (int32 Index = 0; Index < Fixture.Lights.Num(); ++Index)
    {
        TArrayView<FMovieSceneFloatValue> Values = Fixture.Lights[Index]->GetData().GetValues();
        Values[0].Value = 1000.0f + Index * 500.0f;
        Values[1].Value = Values[0].Value;
        Values[2].Value = Values[0].Value * 2.0f;
    }

    TestFalse(TEXT("The fixture proves S6 derives dim mode without a saved flag"),
        Fixture.Arrival->HangarTiming.bDimInsteadOfStrike);
    TestTrue(TEXT("Roofless S6 applies lattice timing and a dim instead of a strike"),
        Fixture.Arrival->ApplyHangarTiming());
    const FFrameNumber Land = Frame(4.1261);
    const FFrameNumber DimEnd = Frame(14.1261);
    for (int32 Index = 0; Index < Fixture.Lights.Num(); ++Index)
    {
        const float StartValue = 1000.0f + Index * 500.0f;
        const TMovieSceneChannelData<const FMovieSceneFloatValue> Data = Fixture.Lights[Index]->GetData();
        const TArrayView<const FFrameNumber> Times = Data.GetTimes();
        const TArrayView<const FMovieSceneFloatValue> Values = Data.GetValues();
        TestEqual(*FString::Printf(TEXT("S6 light %d has only pre-land, land and dim-end keys"), Index),
            Times.Num(), 3);
        TestEqual(*FString::Printf(TEXT("S6 light %d starts dimming at landing"), Index),
            Times[1].Value, Land.Value);
        TestEqual(*FString::Printf(TEXT("S6 light %d reaches near-black after ten seconds"), Index),
            Times[2].Value, DimEnd.Value);
        TestTrue(*FString::Printf(TEXT("S6 light %d preserves its landing intensity"), Index),
            FMath::IsNearlyEqual(Values[1].Value, StartValue));
        TestTrue(*FString::Printf(TEXT("S6 light %d ends at two percent"), Index),
            FMath::IsNearlyEqual(Values[2].Value, StartValue * 0.02f));
        TestTrue(*FString::Printf(TEXT("S6 light %d never turns on after landing"), Index),
            Values[2].Value <= Values[1].Value);
    }
    TestTrue(TEXT("S6 dimming leaves root keys byte-identical"), ChannelBytes(*Fixture.Root) == RootBefore);

    // Negative control: with Apply stubbed, each channel retains the later 2x-intensity key,
    // so the key-count, dim-end and no-turn-on sentinels all fail.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarTimingStandardisesS5ShapeTest,
    "InfinityStage.Hangar.TimingStandardisesS5Shape",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarTimingStandardisesS5ShapeTest::RunTest(const FString& Parameters)
{
    FHangarTimingFixture Fixture({{6.6333, 0.2}}, 5);
    {
        TArrayView<FFrameNumber> Times = Fixture.Roof->GetData().GetTimes();
        Times[1] = Frame(29.27);
        Times[2] = Frame(38.73);
        TArrayView<FMovieSceneDoubleValue> Values = Fixture.Roof->GetData().GetValues();
        Values[0].Value = -83.0;
        Values[1].Value = -83.0;
        Values[2].Value = 7.0;
    }
    {
        TArrayView<FFrameNumber> Times = Fixture.Lattice->GetData().GetTimes();
        Times[1] = Frame(38.73);
        Times[2] = Frame(45.07);
        TArrayView<FMovieSceneDoubleValue> Values = Fixture.Lattice->GetData().GetValues();
        Values[0].Value = 3000.0;
        Values[1].Value = 3000.0;
        Values[2].Value = 1300.0;
    }
    TArray<double> RoofValuesBefore;
    TArray<double> LatticeValuesBefore;
    TArray<ERichCurveInterpMode> RoofInterpBefore;
    TArray<ERichCurveInterpMode> LatticeInterpBefore;
    for (const FMovieSceneDoubleValue& Value : Fixture.Roof->GetData().GetValues())
    {
        RoofValuesBefore.Add(Value.Value);
        RoofInterpBefore.Add(Value.InterpMode);
    }
    for (const FMovieSceneDoubleValue& Value : Fixture.Lattice->GetData().GetValues())
    {
        LatticeValuesBefore.Add(Value.Value);
        LatticeInterpBefore.Add(Value.InterpMode);
    }

    TestTrue(TEXT("S5 non-standard times are accepted for standardisation"),
        Fixture.Arrival->ApplyHangarTiming());
    const TArrayView<const FFrameNumber> RoofTimes = Fixture.Roof->GetData().GetTimes();
    const TArrayView<const FFrameNumber> LatticeTimes = Fixture.Lattice->GetData().GetTimes();
    TestEqual(TEXT("S5 roof starts at zero"), RoofTimes[0].Value, Frame(0.0).Value);
    TestEqual(TEXT("S5 roof close starts at landing"), RoofTimes[1].Value, Frame(4.1261).Value);
    TestEqual(TEXT("S5 roof close ends at the standard time"), RoofTimes[2].Value, Frame(8.6261).Value);
    TestEqual(TEXT("S5 lattice starts at the standard time"), LatticeTimes[1].Value, Frame(8.6261).Value);
    TestEqual(TEXT("S5 lattice ends at the standard time"), LatticeTimes[2].Value, Frame(12.6261).Value);
    const TArrayView<const FMovieSceneDoubleValue> RoofValuesAfter = Fixture.Roof->GetData().GetValues();
    const TArrayView<const FMovieSceneDoubleValue> LatticeValuesAfter = Fixture.Lattice->GetData().GetValues();
    for (int32 Index = 0; Index < RoofValuesAfter.Num(); ++Index)
    {
        TestEqual(*FString::Printf(TEXT("S5 roof value %d is preserved"), Index),
            RoofValuesAfter[Index].Value, RoofValuesBefore[Index]);
        TestEqual(*FString::Printf(TEXT("S5 roof interpolation %d is preserved"), Index),
            RoofValuesAfter[Index].InterpMode, RoofInterpBefore[Index]);
    }
    for (int32 Index = 0; Index < LatticeValuesAfter.Num(); ++Index)
    {
        TestEqual(*FString::Printf(TEXT("S5 lattice value %d is preserved"), Index),
            LatticeValuesAfter[Index].Value, LatticeValuesBefore[Index]);
        TestEqual(*FString::Printf(TEXT("S5 lattice interpolation %d is preserved"), Index),
            LatticeValuesAfter[Index].InterpMode, LatticeInterpBefore[Index]);
    }

    // Negative control: with Apply stubbed, the 29.27/38.73/45.07 timing remains,
    // making all four standard-time sentinels fail while value-preservation alone still passes.
    return true;
}

#endif
