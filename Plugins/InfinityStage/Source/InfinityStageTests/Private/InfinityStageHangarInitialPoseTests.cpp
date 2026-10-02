#include "InfinityStageArrival.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Tracks/MovieScene3DTransformTrack.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
FGuid AddMover(
    UMovieScene& MovieScene,
    const TCHAR* Name,
    const FVector& LandedLocation,
    const int32 MovingChannel,
    const double FirstValue,
    const double LastValue)
{
    const FGuid Binding = MovieScene.AddPossessable(Name, AStaticMeshActor::StaticClass());
    UMovieScene3DTransformTrack* Track = MovieScene.AddTrack<UMovieScene3DTransformTrack>(Binding);
    UMovieScene3DTransformSection* Section =
        CastChecked<UMovieScene3DTransformSection>(Track->CreateNewSection());
    Section->SetRange(TRange<FFrameNumber>::All());
    Track->AddSection(*Section);
    const TArrayView<FMovieSceneDoubleChannel*> Channels =
        Section->GetChannelProxy().GetChannels<FMovieSceneDoubleChannel>();
    const double Defaults[9] = {
        LandedLocation.X, LandedLocation.Y, LandedLocation.Z,
        0.0, 0.0, 0.0,
        1.0, 1.0, 1.0
    };
    for (int32 Index = 0; Index < 9; ++Index)
    {
        Channels[Index]->SetDefault(Defaults[Index]);
    }
    Channels[MovingChannel]->AddCubicKey(FFrameNumber(-30), FirstValue);
    Channels[MovingChannel]->AddCubicKey(FFrameNumber(60), LastValue);
    return Binding;
}

AStaticMeshActor* SpawnMovable(UWorld& World)
{
    AStaticMeshActor* Actor = World.SpawnActor<AStaticMeshActor>();
    Actor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
    return Actor;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHangarInitialPoseTest,
    "InfinityStage.Arrival.GameWorldStartsAtFirstHangarKeys",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHangarInitialPoseTest::RunTest(const FString& Parameters)
{
    ULevelSequence* Motion = NewObject<ULevelSequence>(GetTransientPackage());
    Motion->Initialize();
    UMovieScene* MovieScene = Motion->GetMovieScene();
    const FGuid RootBinding = AddMover(*MovieScene, TEXT("Root"), FVector(100.0, 200.0, 300.0), 4, -90.0, 0.0);
    const FGuid RoofBinding = AddMover(*MovieScene, TEXT("Roof"), FVector(6000.0, 0.0, 3000.0), 4, -90.0, 0.0);
    const FGuid LatticeBinding = AddMover(*MovieScene, TEXT("Lattice"), FVector(3000.0, 0.0, 1200.0), 2, 2800.0, 1200.0);

    UWorld* GameWorld = UWorld::CreateWorld(EWorldType::Game, false);
    FWorldContext& GameContext = GEngine->CreateNewWorldContext(EWorldType::Game);
    GameContext.SetCurrentWorld(GameWorld);
    AStaticMeshActor* Root = SpawnMovable(*GameWorld);
    AStaticMeshActor* Roof = SpawnMovable(*GameWorld);
    AStaticMeshActor* Lattice = SpawnMovable(*GameWorld);
    Root->SetActorRelativeTransform(FTransform(FRotator::ZeroRotator, FVector(100.0, 200.0, 300.0)));
    Roof->SetActorRelativeTransform(FTransform(FRotator::ZeroRotator, FVector(6000.0, 0.0, 3000.0)));
    Lattice->SetActorRelativeTransform(FTransform(FRotator::ZeroRotator, FVector(3000.0, 0.0, 1200.0)));
    AInfinityStageArrival* GameArrival = GameWorld->SpawnActor<AInfinityStageArrival>();
    GameArrival->MotionSequence = Motion;
    GameArrival->DrivenActor = Root;
    GameArrival->MotionBindingGuid = RootBinding;
    FInfinityArrivalInitialTransformDrive& RoofDrive =
        GameArrival->AdditionalInitialTransformDrives.AddDefaulted_GetRef();
    RoofDrive.Target = Roof;
    RoofDrive.BindingGuid = RoofBinding;
    FInfinityArrivalInitialTransformDrive& LatticeDrive =
        GameArrival->AdditionalInitialTransformDrives.AddDefaulted_GetRef();
    LatticeDrive.Target = Lattice;
    LatticeDrive.BindingGuid = LatticeBinding;

    GameArrival->DispatchBeginPlay();
    TestTrue(TEXT("Game world is recognized as game"), GameWorld->IsGameWorld());
    TestTrue(TEXT("Root starts at the sequence's first pitch key"),
        FMath::IsNearlyEqual(Root->GetRootComponent()->GetRelativeRotation().Pitch, -90.0, 1.0e-3));
    TestTrue(TEXT("Roof starts at the sequence's first pitch key"),
        FMath::IsNearlyEqual(Roof->GetRootComponent()->GetRelativeRotation().Pitch, -90.0, 1.0e-3));
    TestTrue(TEXT("Lattice starts at the sequence's first Z key"),
        FMath::IsNearlyEqual(Lattice->GetRootComponent()->GetRelativeLocation().Z, 2800.0, 1.0e-3));

    UWorld* EditorWorld = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AStaticMeshActor* EditorRoot = SpawnMovable(*EditorWorld);
    EditorRoot->SetActorRelativeRotation(FRotator::ZeroRotator);
    AInfinityStageArrival* EditorArrival = EditorWorld->SpawnActor<AInfinityStageArrival>();
    EditorArrival->MotionSequence = Motion;
    EditorArrival->DrivenActor = EditorRoot;
    EditorArrival->MotionBindingGuid = RootBinding;
    EditorArrival->DispatchBeginPlay();
    TestFalse(TEXT("Editor preview is not a game world"), EditorWorld->IsGameWorld());
    TestTrue(TEXT("Editor world keeps its saved landed pose"),
        EditorRoot->GetRootComponent()->GetRelativeRotation().IsNearlyZero(1.0e-6));

    EditorWorld->DestroyWorld(false);
    GEngine->DestroyWorldContext(GameWorld);
    GameWorld->DestroyWorld(false);
    return true;
}

#endif
