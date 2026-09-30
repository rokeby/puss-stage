#include "InfinityStageCameraPilotLibrary.h"
#include "CineCameraActor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * CheckSequenceCutBindings finds cameras that do not resolve, in the Scene and in its nested shots.
 *
 * 30 Sep: nested shot cuts outrank a Scene's root cuts, and Scene 1's LS_Animals_1 binds four cameras
 * no actor in the show level carries, so its cuts show nothing. Imported sequences will keep arriving.
 * This builds a root sequence and a nested sub-sequence, each with one camera bound in the world and one
 * possessable bound to nothing, and expects exactly the two unbound ones reported. It then binds them and
 * expects a clean pass. Spawnable and custom bindings are classified by the code but are not built here.
 * Red without the fix: the function does not exist.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCutBindingsResolveTest,
    "InfinityStage.Editor.SceneCutBindingsResolve",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCutBindingsResolveTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
    WorldContext.SetCurrentWorld(World);

    const auto MakeSequence = []()
    {
        ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage());
        Sequence->Initialize();
        Sequence->GetMovieScene()->SetPlaybackRange(0, 240000);
        UMovieSceneCameraCutTrack* Track = Cast<UMovieSceneCameraCutTrack>(
            Sequence->GetMovieScene()->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
        Track->SetIsAutoManagingSections(false);
        return Sequence;
    };
    const auto AddCut = [World](ULevelSequence* Sequence, const TCHAR* Name, ACineCameraActor* BindTo, int32 Start, int32 End)
    {
        UMovieScene* MovieScene = Sequence->GetMovieScene();
        UMovieSceneCameraCutTrack* Track = Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack());
        const FGuid Guid = MovieScene->AddPossessable(Name, ACineCameraActor::StaticClass());
        if (BindTo)
        {
            Sequence->BindPossessableObject(Guid, *BindTo, World);
        }
        UMovieSceneCameraCutSection* Cut = Track->AddNewCameraCut(
            FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(Guid)), FFrameNumber(Start));
        Cut->SetRange(TRange<FFrameNumber>(FFrameNumber(Start), FFrameNumber(End)));
        return Guid;
    };
    const auto Count = [](const TArray<FString>& Lines, const TCHAR* Needle)
    {
        int32 Found = 0;
        for (const FString& Line : Lines)
        {
            Found += Line.Contains(Needle, ESearchCase::CaseSensitive) ? 1 : 0;
        }
        return Found;
    };

    ACineCameraActor* CameraA = World->SpawnActor<ACineCameraActor>();
    ACineCameraActor* CameraB = World->SpawnActor<ACineCameraActor>();
    ACineCameraActor* CameraC = World->SpawnActor<ACineCameraActor>();
    ULevelSequence* Root = MakeSequence();
    ULevelSequence* Shot = MakeSequence();
    AddCut(Root, TEXT("Scene Camera"), CameraA, 0, 120000);
    const FGuid RootMissing = AddCut(Root, TEXT("Camera From Another Level"), nullptr, 120000, 240000);
    const FGuid ShotMissing = AddCut(Shot, TEXT("Nested Camera From Another Level"), nullptr, 0, 120000);
    AddCut(Shot, TEXT("Nested Scene Camera"), CameraB, 120000, 240000);
    UMovieSceneSubTrack* SubTrack = Root->GetMovieScene()->AddTrack<UMovieSceneSubTrack>();
    SubTrack->AddSequence(Shot, FFrameNumber(0), 240000);

    TArray<FString> Lines;
    int32 Unresolved = 0;
    TestFalse(TEXT("A Scene with unbound cameras does not pass"),
        UInfinityStageCameraPilotLibrary::CheckSequenceCutBindings(Root, World, Lines, Unresolved));
    TestEqual(TEXT("Every cut is reported, root and nested"), Lines.Num(), 4);
    TestEqual(TEXT("Exactly the two unbound cameras are unresolved"), Unresolved, 2);
    TestEqual(TEXT("Two cuts resolve to cameras in this world"), Count(Lines, TEXT("resolved: ")), 2);
    TestEqual(TEXT("Two cuts are reported UNRESOLVED"), Count(Lines, TEXT("UNRESOLVED")), 2);
    TestEqual(TEXT("The nested shot's cuts are reported under it"), Count(Lines, *(TEXT(" > ") + Shot->GetName())), 2);

    Root->BindPossessableObject(RootMissing, *CameraC, World);
    Shot->BindPossessableObject(ShotMissing, *CameraC, World);
    TestTrue(TEXT("With every camera bound here, the Scene passes"),
        UInfinityStageCameraPilotLibrary::CheckSequenceCutBindings(Root, World, Lines, Unresolved));
    TestEqual(TEXT("...with nothing unresolved"), Unresolved, 0);

    ULevelSequence* Parent = Root;
    for (int32 Depth = 1; Depth <= 6; ++Depth)
    {
        ULevelSequence* Child = MakeSequence();
        UMovieSceneSubTrack* DeepTrack = Parent->GetMovieScene()->AddTrack<UMovieSceneSubTrack>();
        DeepTrack->AddSequence(Child, FFrameNumber(0), 240000);
        Parent = Child;
    }
    AddCut(Parent, TEXT("Bound Camera Beyond Inspection Limit"), CameraA, 0, 240000);
    // Pre-fix this passes: depth > 4 returns silently, so the bound innermost cut is never inspected
    // and the gate incorrectly counts the whole six-deep branch as resolved.
    TestFalse(TEXT("A branch nested six deep fails closed when it cannot be fully inspected"),
        UInfinityStageCameraPilotLibrary::CheckSequenceCutBindings(Root, World, Lines, Unresolved));
    TestEqual(TEXT("The depth limit counts as unresolved"), Unresolved, 1);
    TestEqual(TEXT("The depth limit is reported exactly once"),
        Count(Lines, TEXT("UNCHECKED: nested deeper than 4; not inspected")), 1);

    ULevelSequence* EmptySubRoot = MakeSequence();
    UMovieSceneSubTrack* EmptySubTrack = EmptySubRoot->GetMovieScene()->AddTrack<UMovieSceneSubTrack>();
    UMovieSceneSection* EmptySubSection = EmptySubTrack->CreateNewSection();
    EmptySubTrack->AddSection(*EmptySubSection);
    TestFalse(TEXT("A sub-section with no sequence fails closed"),
        UInfinityStageCameraPilotLibrary::CheckSequenceCutBindings(EmptySubRoot, World, Lines, Unresolved));
    TestEqual(TEXT("The empty sub-section counts as unresolved"), Unresolved, 1);
    TestEqual(TEXT("The empty sub-section is reported exactly once"),
        Count(Lines, TEXT("UNCHECKED: sub-section has no sequence; not inspected")), 1);

    TestFalse(TEXT("No sequence fails closed"),
        UInfinityStageCameraPilotLibrary::CheckSequenceCutBindings(nullptr, World, Lines, Unresolved));
    TestEqual(TEXT("...and counts as unresolved"), Unresolved, 1);

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

#endif
