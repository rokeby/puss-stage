#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraOwnerLockTest,
    "InfinityStage.Camera.DogOverrideLockedOutOfSequences",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraOwnerLockTest::RunTest(const FString& Parameters)
{
    // Opening (Sequence) -> Passage -> Void (Scene, dog-owned) -> Interaction (Sequence).
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const auto AddSceneLike = [Show](const EInfinityCueType Type, const EInfinityCameraOwner Owner)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = Type;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Scene.DurationFrames = 2000;
        Cue.Scene.CameraOwner = Owner;
    };
    AddSceneLike(EInfinityCueType::Sequence, EInfinityCameraOwner::Timeline);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Wing = Show->Cues.AddDefaulted_GetRef();
        Wing.Type = EInfinityCueType::WingPair;
        Wing.CueGuid = FGuid::NewGuid();
        Wing.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Wing.WingPair.IntervalToNext = 1000;
    }
    AddSceneLike(EInfinityCueType::Scene, EInfinityCameraOwner::DogFreeLook);
    AddSceneLike(EInfinityCueType::Sequence, EInfinityCameraOwner::Timeline);
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].CameraOwner = EInfinityCameraOwner::DogGazeOnly;

    AInfinityStageShowRoot* Root = World->SpawnActor<AInfinityStageShowRoot>();
    Root->ShowAsset = Show;

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestEqual(TEXT("Fixture compiles to four segments"), Compiled.Segments.Num(), 4);
    if (Compiled.Segments.Num() != 4)
    {
        World->DestroyWorld(false);
        return false;
    }
    const auto Middle = [&Compiled](const int32 Index)
    {
        return FFrameNumber((Compiled.Segments[Index].StartFrame.Value + Compiled.Segments[Index].EndFrame.Value) / 2);
    };
    const FFrameNumber Opening = Middle(0);
    const FFrameNumber Passage = Middle(1);
    const FFrameNumber Void = Middle(2);
    const FFrameNumber Interaction = Middle(3);

    // Force Dog: steers the Passage and the Void, never a Sequence cue.
    Root->bOverrideCameraOwner = true;
    Root->CameraOwnerOverride = EInfinityCameraOwner::DogFreeLook;
    TestEqual(TEXT("Force Dog takes the Passage"), Root->GetCameraOwnerAtFrame(Passage), EInfinityCameraOwner::DogFreeLook);
    TestEqual(TEXT("Force Dog takes the Void"), Root->GetCameraOwnerAtFrame(Void), EInfinityCameraOwner::DogFreeLook);
    TestEqual(TEXT("Force Dog cannot take the Opening"), Root->GetCameraOwnerAtFrame(Opening), EInfinityCameraOwner::Timeline);
    TestEqual(TEXT("Force Dog cannot take an Interaction"), Root->GetCameraOwnerAtFrame(Interaction), EInfinityCameraOwner::Timeline);

    // Force Timeline: the dog-failure drill wins everywhere, the dog-owned Void included.
    Root->CameraOwnerOverride = EInfinityCameraOwner::Timeline;
    TestEqual(TEXT("Force Timeline takes the Void"), Root->GetCameraOwnerAtFrame(Void), EInfinityCameraOwner::Timeline);
    TestEqual(TEXT("Force Timeline takes the Passage"), Root->GetCameraOwnerAtFrame(Passage), EInfinityCameraOwner::Timeline);

    // No override: the authored owners stand.
    Root->bOverrideCameraOwner = false;
    TestEqual(TEXT("Authored Passage owner"), Root->GetCameraOwnerAtFrame(Passage), EInfinityCameraOwner::DogGazeOnly);
    TestEqual(TEXT("Authored Void owner"), Root->GetCameraOwnerAtFrame(Void), EInfinityCameraOwner::DogFreeLook);
    TestEqual(TEXT("Authored Interaction owner"), Root->GetCameraOwnerAtFrame(Interaction), EInfinityCameraOwner::Timeline);

    World->DestroyWorld(false);
    return true;
}

#endif
