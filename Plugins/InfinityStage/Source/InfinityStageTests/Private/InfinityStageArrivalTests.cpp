#include "InfinityStageArrival.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Channels/MovieSceneFloatChannel.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneGeometryCacheSection.h"
#include "MovieSceneGeometryCacheTrack.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Sections/MovieSceneFloatSection.h"
#include "Sections/MovieSceneSubSection.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Tracks/MovieSceneFloatTrack.h"
#include "Tracks/MovieSceneSubTrack.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageArrivalTest,
    "InfinityStage.Arrival.OneCurveAcrossTheSceneBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

/**
 * The Arrival reads the SAME channel Sequencer plays from the Scene's first frame, at
 * negative motion time before it: rest long before, the channel itself mid-way, the
 * channel's value at motion time 0 one tick before the boundary, nothing at or after
 * the boundary, the speed dial honoured, and the same answer in any evaluation order.
 */
bool FInfinityStageArrivalTest::RunTest(const FString& Parameters)
{
    // The motion: a possessable whose pitch rises -90 -> 0 from motion time -3 s to +2 s.
    ULevelSequence* Motion = NewObject<ULevelSequence>(GetTransientPackage());
    Motion->Initialize();
    UMovieScene* MotionScene = Motion->GetMovieScene();
    const FFrameRate MotionRate = MotionScene->GetTickResolution();
    MotionScene->SetPlaybackRange(0, MotionRate.AsFrameTime(5.0).FloorToFrame().Value);
    const FGuid Binding = MotionScene->AddPossessable(TEXT("Root"), AStaticMeshActor::StaticClass());
    UMovieScene3DTransformTrack* TransformTrack = MotionScene->AddTrack<UMovieScene3DTransformTrack>(Binding);
    UMovieScene3DTransformSection* TransformSection =
        CastChecked<UMovieScene3DTransformSection>(TransformTrack->CreateNewSection());
    TransformSection->SetRange(TRange<FFrameNumber>::All());
    TransformTrack->AddSection(*TransformSection);
    FMovieSceneDoubleChannel* Pitch = TransformSection->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>()[4];
    Pitch->AddCubicKey(MotionRate.AsFrameTime(-3.0).FloorToFrame(), -90.0);
    Pitch->AddCubicKey(MotionRate.AsFrameTime(2.0).FloorToFrame(), 0.0);
    const auto PitchAt = [Pitch, MotionRate](const double Seconds)
    {
        double Value = 0.0;
        Pitch->Evaluate(MotionRate.AsFrameTime(Seconds), Value);
        return Value;
    };

    // The Scene plays the motion as a sub-section from its first frame.
    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    UMovieScene* SceneScene = SceneSequence->GetMovieScene();
    const FFrameRate SceneRate = SceneScene->GetTickResolution();
    const int32 SceneLength = SceneRate.AsFrameTime(5.0).FloorToFrame().Value;
    SceneScene->SetPlaybackRange(0, SceneLength);
    UMovieSceneSubSection* SubSection =
        SceneScene->AddTrack<UMovieSceneSubTrack>()->AddSequence(Motion, FFrameNumber(0), SceneLength);

    // A Passage of two wing pairs, then the Scene.
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = Show->TickResolution.AsFrameTime(4.0).FloorToFrame();
        Cue.WingPair.GapToNextCm = 500.0;
    }
    FInfinityShowCue& SceneCue = Show->Cues.AddDefaulted_GetRef();
    SceneCue.Type = EInfinityCueType::Scene;
    SceneCue.CueGuid = FGuid::NewGuid();
    SceneCue.Scene.Sequence = SceneSequence;
    SceneCue.Scene.DurationFrames = Show->TickResolution.AsFrameTime(5.0).FloorToFrame();
    FInfinityPassageSettings& Settings = Show->PassageSettings.AddDefaulted_GetRef();
    Settings.PassageGuid = FGuid::NewGuid();
    Settings.FirstCueGuid = Show->Cues[0].CueGuid;
    Settings.LastCueGuid = Show->Cues[1].CueGuid;
    Settings.TailFrames = Show->TickResolution.AsFrameTime(4.0).FloorToFrame();
    Settings.TailDistanceCm = 400.0;

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    const FInfinityCompiledSegment* Segment = Compiled.Segments.FindByPredicate(
        [&SceneCue](const FInfinityCompiledSegment& Candidate) { return Candidate.SegmentGuid == SceneCue.CueGuid; });
    if (Compiled.HasErrors() || !Segment)
    {
        AddError(TEXT("Expected a Passage followed by a compiled Scene segment."));
        return false;
    }
    const FFrameTime SceneStart(Segment->StartFrame);
    const FFrameRate MasterRate = Show->TickResolution;
    const auto Master = [&SceneStart, MasterRate](const double SecondsBeforeScene)
    {
        return SceneStart - MasterRate.AsFrameTime(SecondsBeforeScene);
    };

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AStaticMeshActor* Driven = World->SpawnActor<AStaticMeshActor>();
    Driven->GetRootComponent()->SetMobility(EComponentMobility::Movable);
    AInfinityStageArrival* Arrival = World->SpawnActor<AInfinityStageArrival>();
    Arrival->SceneCueGuid = SceneCue.CueGuid;
    Arrival->MotionSequence = Motion;
    Arrival->MotionBindingGuid = Binding;
    Arrival->DrivenActor = Driven;

    FRotator Rotation;
    TestTrue(TEXT("Long before the Scene the Arrival resolves"), Arrival->ResolveRotationAtMasterFrame(Show, Master(3.5), Rotation));
    TestTrue(TEXT("Long before the Scene it holds the rest pose"), FMath::IsNearlyEqual(Rotation.Pitch, -90.0, 1.0e-3));
    TestTrue(TEXT("Mid-way it is the channel itself"),
        Arrival->EvaluateAtMasterFrame(Show, Master(1.5))
        && FMath::IsNearlyEqual(Driven->GetActorRotation().Pitch, PitchAt(-1.5), 1.0e-3));
    TestTrue(TEXT("One Master tick before the Scene it meets the channel at motion time 0"),
        Arrival->ResolveRotationAtMasterFrame(Show, SceneStart - FFrameTime(1), Rotation)
        && FMath::IsNearlyEqual(Rotation.Pitch, PitchAt(0.0), 1.0e-2));
    const FRotator Before = Driven->GetActorRotation();
    TestFalse(TEXT("At the Scene's first frame Sequencer owns it"), Arrival->ResolveRotationAtMasterFrame(Show, SceneStart, Rotation));
    TestFalse(TEXT("After the Scene starts the Arrival does nothing"), Arrival->EvaluateAtMasterFrame(Show, SceneStart + MasterRate.AsFrameTime(1.0)));
    TestTrue(TEXT("...and leaves the actor where it was"), Driven->GetActorRotation().Equals(Before, 1.0e-6));

    // The same frames in two orders give the same answers: a pure function of Master time.
    const TArray<double> Seconds = { 3.2, 2.4, 1.9, 1.1, 0.4, 0.05 };
    TArray<double> Forward;
    TArray<double> Reverse;
    for (const double S : Seconds)
    {
        Arrival->ResolveRotationAtMasterFrame(Show, Master(S), Rotation);
        Forward.Add(Rotation.Pitch);
    }
    for (int32 Index = Seconds.Num() - 1; Index >= 0; --Index)
    {
        Arrival->ResolveRotationAtMasterFrame(Show, Master(Seconds[Index]), Rotation);
        Reverse.Insert(Rotation.Pitch, 0);
    }
    TestTrue(TEXT("Evaluation order does not matter"), Forward == Reverse);

    // Inside the section the mapping agrees with the sub-section's own transform.
    for (const double S : { 0.5, 2.0, 4.5 })
    {
        const FFrameTime Outer = SceneRate.AsFrameTime(S);
        FFrameTime Mapped;
        const bool bMapped = AInfinityStageArrival::MapOuterToInnerTime(*SubSection, SceneRate, Outer, Mapped);
        const FFrameTime Engine = SubSection->OuterToInnerTransform().TransformTime(Outer);
        TestTrue(FString::Printf(TEXT("Mapping matches OuterToInnerTransform at %.1f s"), S),
            bMapped && FMath::Abs((Mapped - Engine).AsDecimal()) <= 1.0);
    }

    // Gary's speed dial: at 0.8 the motion runs slower, so 1.5 Master seconds early is 1.2 motion seconds early.
    SubSection->Parameters.TimeScale = FMovieSceneTimeWarpVariant(0.8);
    TestTrue(TEXT("The speed dial scales the pre-roll too"),
        Arrival->ResolveRotationAtMasterFrame(Show, Master(1.5), Rotation)
        && FMath::IsNearlyEqual(Rotation.Pitch, PitchAt(-1.2), 1.0e-3));

    // The backcloth: a GeometryCache section in the same motion sequence, starting at negative
    // time. No cache asset is needed to test the mapping: the duration is passed in, as the
    // component's own would be. These are Soft goods' rules, asserted one by one.
    SubSection->Parameters.TimeScale = FMovieSceneTimeWarpVariant(1.0);
    const FGuid Cloth = MotionScene->AddPossessable(TEXT("Cloth"), AStaticMeshActor::StaticClass());
    UMovieSceneTrack* ClothTrack = MotionScene->AddTrack<UMovieSceneGeometryCacheTrack>(Cloth);
    UMovieSceneGeometryCacheSection* ClothSection = CastChecked<UMovieSceneGeometryCacheSection>(ClothTrack->CreateNewSection());
    constexpr float CacheSeconds = 11.0f;
    ClothSection->SetRange(TRange<FFrameNumber>(
        MotionRate.AsFrameTime(-2.5).FloorToFrame(), MotionRate.AsFrameTime(-2.5 + CacheSeconds).FloorToFrame()));
    ClothTrack->AddSection(*ClothSection);
    Arrival->BackclothBindingGuid = Cloth;
    float ClothTime = -1.0f;
    TestTrue(TEXT("Before its section the cloth holds sample 0 exactly (the still hang)"),
        Arrival->ResolveBackclothTimeAtMasterFrame(Show, Master(3.5), CacheSeconds, ClothTime) && ClothTime == 0.0f);
    TestTrue(TEXT("Inside its section the cloth runs on the section's clock"),
        Arrival->ResolveBackclothTimeAtMasterFrame(Show, Master(1.5), CacheSeconds, ClothTime) && FMath::IsNearlyEqual(ClothTime, 1.0f, 1.0e-3f));
    TestTrue(TEXT("One Master tick before the Scene the cloth is where Sequencer takes it up"),
        Arrival->ResolveBackclothTimeAtMasterFrame(Show, SceneStart - FFrameTime(1), CacheSeconds, ClothTime)
        && FMath::IsNearlyEqual(ClothTime, 2.5f, 1.0e-2f));
    TestFalse(TEXT("At the Scene's first frame Sequencer plays the cloth"),
        Arrival->ResolveBackclothTimeAtMasterFrame(Show, SceneStart, CacheSeconds, ClothTime));
    TestTrue(TEXT("Past its section the cloth holds its last sample (the pile), it does not loop"),
        ClothSection->MapTimeToAnimation(CacheSeconds, MotionRate.AsFrameTime(20.0), MotionRate) > CacheSeconds - 0.1f);

    // A practical's Intensity uses the same negative-time mapping and the same channel
    // Sequencer takes over at the cut: 0 -> 400 from motion time -2 s to +2 s.
    const FGuid LightBinding = MotionScene->AddPossessable(TEXT("Practical"), UPointLightComponent::StaticClass());
    UMovieSceneFloatTrack* IntensityTrack = MotionScene->AddTrack<UMovieSceneFloatTrack>(LightBinding);
    IntensityTrack->SetPropertyNameAndPath(TEXT("Intensity"), TEXT("Intensity"));
    UMovieSceneFloatSection* IntensitySection = CastChecked<UMovieSceneFloatSection>(IntensityTrack->CreateNewSection());
    IntensitySection->SetRange(TRange<FFrameNumber>(FFrameNumber(0), MotionRate.AsFrameTime(5.0).FloorToFrame()));
    IntensityTrack->AddSection(*IntensitySection);
    FMovieSceneFloatChannel* IntensityChannel = &IntensitySection->GetChannel();
    IntensityChannel->AddLinearKey(MotionRate.AsFrameTime(-2.0).FloorToFrame(), 0.0f);
    IntensityChannel->AddLinearKey(MotionRate.AsFrameTime(2.0).FloorToFrame(), 400.0f);
    const auto IntensityAt = [IntensityChannel, MotionRate](const double Seconds)
    {
        float Value = 0.0f;
        IntensityChannel->Evaluate(MotionRate.AsFrameTime(Seconds), Value);
        return Value;
    };

    UPointLightComponent* Practical = NewObject<UPointLightComponent>(Arrival);
    Practical->SetIntensity(777.0f);
    FInfinityArrivalFloatDrive& FloatDrive = Arrival->PreSceneFloatDrives.AddDefaulted_GetRef();
    FloatDrive.Target = Practical;
    FloatDrive.BindingGuid = LightBinding;
    FloatDrive.PropertyName = TEXT("Intensity");
    float Intensity = -1.0f;
    TestTrue(TEXT("At motion -1 s the pre-Scene float drive resolves to 100"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, Master(1.0), 0, Intensity)
        && FMath::IsNearlyEqual(Intensity, 100.0f, 1.0f));
    TestTrue(TEXT("One tick before the cut the float drive meets Sequencer's value at motion 0"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, SceneStart - FFrameTime(1), 0, Intensity)
        && FMath::IsNearlyEqual(Intensity, IntensityAt(0.0), 1.0e-2f));
    TestFalse(TEXT("At the Scene's first frame Sequencer owns the float drive"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, SceneStart, 0, Intensity));

    FloatDrive.PropertyName = TEXT("NotIntensity");
    AddExpectedMessagePlain(TEXT("reason=NoFloatTrack"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
    TestFalse(TEXT("A wrong float property name does not resolve"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, Master(1.0), 0, Intensity));
    TestFalse(TEXT("A repeated wrong float property name still does not resolve"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, Master(0.5), 0, Intensity));
    FloatDrive.PropertyName = TEXT("Intensity");

    // This fixture is deliberately an editor world: resolution remains available for
    // editor tests, but evaluation must not leave a saveable preview intensity behind.
    TestTrue(TEXT("Fixture is a non-game editor world"), !World->IsGameWorld());
    Arrival->EvaluateAtMasterFrame(Show, Master(1.0));
    TestTrue(TEXT("Editor evaluation leaves the practical's intensity untouched"),
        FMath::IsNearlyEqual(Practical->Intensity, 777.0f, 1.0e-6f));

    // When sections are split, prefer the one containing the motion time. If none
    // contains it, use the earliest section and deliberately evaluate outside its range.
    UMovieSceneFloatSection* ContainedIntensitySection =
        CastChecked<UMovieSceneFloatSection>(IntensityTrack->CreateNewSection());
    ContainedIntensitySection->SetRange(TRange<FFrameNumber>(
        MotionRate.AsFrameTime(-1.5).FloorToFrame(), MotionRate.AsFrameTime(-0.5).FloorToFrame()));
    IntensityTrack->AddSection(*ContainedIntensitySection);
    FMovieSceneFloatChannel* ContainedIntensityChannel = &ContainedIntensitySection->GetChannel();
    ContainedIntensityChannel->AddLinearKey(MotionRate.AsFrameTime(-1.5).FloorToFrame(), 250.0f);
    ContainedIntensityChannel->AddLinearKey(MotionRate.AsFrameTime(-0.5).FloorToFrame(), 250.0f);
    TestTrue(TEXT("A float section containing motion time is preferred"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, Master(1.0), 0, Intensity)
        && FMath::IsNearlyEqual(Intensity, 250.0f, 1.0e-3f));
    TestTrue(TEXT("With no containing section the earliest section evaluates out of range"),
        Arrival->ResolveFloatDriveAtMasterFrame(Show, Master(3.0), 0, Intensity)
        && FMath::IsNearlyEqual(Intensity, 250.0f, 1.0e-3f));

    const FGuid ExposureBinding = MotionScene->AddPossessable(TEXT("Exposure"), APostProcessVolume::StaticClass());
    UMovieSceneFloatTrack* BlendWeightTrack = MotionScene->AddTrack<UMovieSceneFloatTrack>(ExposureBinding);
    BlendWeightTrack->SetPropertyNameAndPath(TEXT("BlendWeight"), TEXT("BlendWeight"));
    UMovieSceneFloatSection* BlendWeightSection =
        CastChecked<UMovieSceneFloatSection>(BlendWeightTrack->CreateNewSection());
    BlendWeightSection->SetRange(TRange<FFrameNumber>(FFrameNumber(0), MotionRate.AsFrameTime(5.0).FloorToFrame()));
    BlendWeightTrack->AddSection(*BlendWeightSection);
    FMovieSceneFloatChannel* BlendWeightChannel = &BlendWeightSection->GetChannel();
    BlendWeightChannel->AddLinearKey(MotionRate.AsFrameTime(-2.0).FloorToFrame(), 0.0f);
    BlendWeightChannel->AddLinearKey(MotionRate.AsFrameTime(2.0).FloorToFrame(), 1.0f);

    UWorld* GameWorld = UWorld::CreateWorld(EWorldType::Game, false);
    FWorldContext& GameWorldContext = GEngine->CreateNewWorldContext(EWorldType::Game);
    GameWorldContext.SetCurrentWorld(GameWorld);
    AInfinityStageArrival* GameArrival = GameWorld->SpawnActor<AInfinityStageArrival>();
    GameArrival->SceneCueGuid = SceneCue.CueGuid;
    GameArrival->MotionSequence = Motion;

    AActor* LightOwner = GameWorld->SpawnActor<AActor>();
    UPointLightComponent* GamePractical = NewObject<UPointLightComponent>(LightOwner, TEXT("ArrivalPractical"));
    LightOwner->AddInstanceComponent(GamePractical);
    GamePractical->RegisterComponent();
    GamePractical->SetIntensity(777.0f);
    APostProcessVolume* Exposure = GameWorld->SpawnActor<APostProcessVolume>();
    Exposure->BlendWeight = 0.9f;

    FInfinityArrivalFloatDrive& GameLightDrive = GameArrival->PreSceneFloatDrives.AddDefaulted_GetRef();
    GameLightDrive.Target = GamePractical;
    GameLightDrive.BindingGuid = LightBinding;
    GameLightDrive.PropertyName = TEXT("Intensity");
    FInfinityArrivalFloatDrive& GameExposureDrive = GameArrival->PreSceneFloatDrives.AddDefaulted_GetRef();
    GameExposureDrive.Target = Exposure;
    GameExposureDrive.BindingGuid = ExposureBinding;
    GameExposureDrive.PropertyName = TEXT("BlendWeight");
    FInfinityArrivalFloatDrive& ForeignWorldDrive = GameArrival->PreSceneFloatDrives.AddDefaulted_GetRef();
    ForeignWorldDrive.Target = Practical;
    ForeignWorldDrive.BindingGuid = LightBinding;
    ForeignWorldDrive.PropertyName = TEXT("Intensity");

    TestTrue(TEXT("Fixture is a game world"), GameWorld->IsGameWorld());
    AddExpectedMessagePlain(TEXT("reason=ForeignWorldTarget"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
    TestTrue(TEXT("Game-world evaluation writes supported float targets"),
        GameArrival->EvaluateAtMasterFrame(Show, Master(1.0)));
    TestTrue(TEXT("Game-world evaluation writes the practical intensity from the containing section"),
        FMath::IsNearlyEqual(GamePractical->Intensity, 250.0f, 1.0e-3f));
    TestTrue(TEXT("Game-world evaluation writes the exposure BlendWeight from the channel"),
        FMath::IsNearlyEqual(Exposure->BlendWeight, 0.25f, 1.0e-3f));
    TestTrue(TEXT("A target in another world is not written"),
        FMath::IsNearlyEqual(Practical->Intensity, 777.0f, 1.0e-6f));

    GamePractical->SetIntensity(901.0f);
    Exposure->BlendWeight = 0.83f;
    TestFalse(TEXT("At the Scene's first frame the game-world Arrival writes nothing"),
        GameArrival->EvaluateAtMasterFrame(Show, SceneStart));
    TestTrue(TEXT("At the Scene's first frame the practical intensity is unchanged"),
        FMath::IsNearlyEqual(GamePractical->Intensity, 901.0f, 1.0e-6f));
    TestTrue(TEXT("At the Scene's first frame the exposure BlendWeight is unchanged"),
        FMath::IsNearlyEqual(Exposure->BlendWeight, 0.83f, 1.0e-6f));

    GamePractical->SetIntensity(902.0f);
    Exposure->BlendWeight = 0.84f;
    TestFalse(TEXT("After the Scene starts the game-world Arrival writes nothing"),
        GameArrival->EvaluateAtMasterFrame(Show, SceneStart + MasterRate.AsFrameTime(1.0)));
    TestTrue(TEXT("After the Scene starts the practical intensity is unchanged"),
        FMath::IsNearlyEqual(GamePractical->Intensity, 902.0f, 1.0e-6f));
    TestTrue(TEXT("After the Scene starts the exposure BlendWeight is unchanged"),
        FMath::IsNearlyEqual(Exposure->BlendWeight, 0.84f, 1.0e-6f));

    GEngine->DestroyWorldContext(GameWorld);
    GameWorld->DestroyWorld(false);

    // Placed ahead of its nesting (Scenes 1, 2, 3, 5, 6 on 30 Sep): an Arrival whose motion the
    // Scene does not play declines, leaves its actor alone, and says so exactly once at Display
    // (not the old per-session warning), however many frames ask.
    ULevelSequence* Unnested = NewObject<ULevelSequence>(GetTransientPackage());
    Unnested->Initialize();
    AInfinityStageArrival* Waiting = World->SpawnActor<AInfinityStageArrival>();
    Waiting->SceneCueGuid = SceneCue.CueGuid;
    Waiting->MotionSequence = Unnested;
    Waiting->MotionBindingGuid = Binding;
    Waiting->DrivenActor = Driven;
    AddExpectedMessagePlain(TEXT("INFINITY_STAGE_ARRIVAL_WAITING"), ELogVerbosity::Display, EAutomationExpectedMessageFlags::Contains, 1);
    const FRotator Resting = Driven->GetActorRotation();
    TestFalse(TEXT("Unnested, the Arrival declines"), Waiting->ResolveRotationAtMasterFrame(Show, Master(1.5), Rotation));
    TestFalse(TEXT("Unnested, it drives nothing"), Waiting->EvaluateAtMasterFrame(Show, Master(1.0)));
    TestTrue(TEXT("...and leaves its actor alone"), Driven->GetActorRotation().Equals(Resting, 1.0e-6));

    World->DestroyWorld(false);
    return true;
}

#endif
