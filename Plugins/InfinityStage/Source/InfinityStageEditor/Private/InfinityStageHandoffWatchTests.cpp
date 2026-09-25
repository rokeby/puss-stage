#include "InfinityStageHandoffWatch.h"

#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "InfinityStageCameraPilotLibrary.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHandoffWatchMidPassageKeyTest,
    "InfinityStage.Editor.HandoffWatch.MidPassageKeyStalesScene",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHandoffWatchMidPassageKeyTest::RunTest(const FString& Parameters)
{
    UInfinityStageHandoffWatchSubsystem* Watch = GEditor
        ? GEditor->GetEditorSubsystem<UInfinityStageHandoffWatchSubsystem>()
        : nullptr;
    TestNotNull(TEXT("Handoff watch subsystem exists"), Watch);
    if (!Watch)
    {
        return false;
    }

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
    WorldContext.SetCurrentWorld(World);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());

    FInfinityShowCue& IncomingCue = Show->Cues.AddDefaulted_GetRef();
    IncomingCue.Type = EInfinityCueType::WingPair;
    IncomingCue.CueGuid = FGuid::NewGuid();
    IncomingCue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    FInfinityShowCue& SceneCue = Show->Cues.AddDefaulted_GetRef();
    SceneCue.Type = EInfinityCueType::Scene;
    SceneCue.CueGuid = FGuid::NewGuid();
    SceneCue.Label = FText::FromString(TEXT("Watch Test Scene"));
    SceneCue.Scene.DurationFrames = 240000;
    SceneCue.Scene.ExitHandoffHoldFrames = 24000;
    const FGuid SceneCueGuid = SceneCue.CueGuid;
    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    SceneSequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    SceneSequence->GetMovieScene()->SetPlaybackRange(0, SceneCue.Scene.DurationFrames.Value);
    SceneCue.Scene.Sequence = SceneSequence;
    FInfinityShowCue& OutgoingCue = Show->Cues.AddDefaulted_GetRef();
    OutgoingCue.Type = EInfinityCueType::WingPair;
    OutgoingCue.CueGuid = FGuid::NewGuid();
    OutgoingCue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.TailFrames = 24000;
        Settings.TailDistanceCm = 250.0;
    }
    const FGuid IncomingPassageGuid = Show->PassageSettings[0].PassageGuid;

    AInfinityStagePassageActor* IncomingPassage = World->SpawnActor<AInfinityStagePassageActor>();
    IncomingPassage->ShowAsset = Show;
    IncomingPassage->PassageGuid = IncomingPassageGuid;
    TestTrue(TEXT("Incoming Passage materializes"), IncomingPassage->MaterializePassage());
    AInfinityStageCameraRig* IncomingRig = World->SpawnActor<AInfinityStageCameraRig>();
    IncomingRig->PassageActor = IncomingPassage;
    IncomingRig->CameraOffset = FVector(0.0, 0.0, 180.0);
    IncomingRig->bEnableShadowCat = false;

    AInfinityStagePassageActor* OutgoingPassage = World->SpawnActor<AInfinityStagePassageActor>(
        FVector(5000.0, 10000.0, 0.0), FRotator(0.0, 90.0, 0.0));
    OutgoingPassage->ShowAsset = Show;
    OutgoingPassage->PassageGuid = Show->PassageSettings[1].PassageGuid;
    TestTrue(TEXT("Outgoing Passage materializes"), OutgoingPassage->MaterializePassage());
    AInfinityStageCameraRig* OutgoingRig = World->SpawnActor<AInfinityStageCameraRig>();
    OutgoingRig->PassageActor = OutgoingPassage;
    OutgoingRig->CameraOffset = FVector(0.0, 0.0, 180.0);
    OutgoingRig->bEnableShadowCat = false;

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    Show->ManagedMasterSequence = Master;
    FString Report;
    TestTrue(TEXT("Master builds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    TestTrue(TEXT("Handoffs match"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, Report));

    Watch->CaptureBaseline(*Show, *World);
    TestEqual(TEXT("Freshly matched handoffs are not raised"), Watch->CheckNow(*Show, *World, TEXT("test"), false).Num(), 0);

    // The trap: one framing key in the middle of the incoming Passage. As the
    // channel's only key it holds to both ends, so the Passage end camera the
    // Scene's Entry handoff was matched to moves with it.
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    const FInfinityCompiledPassage* Incoming = Compiled.Passages.FindByPredicate(
        [&IncomingPassageGuid](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == IncomingPassageGuid; });
    TestNotNull(TEXT("Incoming Passage compiles"), Incoming);
    if (Incoming)
    {
        const FFrameNumber MidFrame((Incoming->SegmentStartFrame.Value + Incoming->SegmentEndFrame.Value) / 2);
        const auto KeyReframe = [&](const FVector& WorldMoveCm)
        {
            FTransform View;
            float Focal = 0.0f;
            float Focus = 0.0f;
            UInfinityStageCameraPilotLibrary::GetCameraView(*IncomingRig, MidFrame, View, Focal, Focus);
            View.AddToTranslation(WorldMoveCm);
            FString KeyReport;
            return UInfinityStageCameraPilotLibrary::KeyPose(
                *World, *Show, IncomingPassageGuid, MidFrame, View, nullptr, KeyReport);
        };

        TestTrue(TEXT("Mid-Passage framing key lands"), KeyReframe(FVector(0.0, 80.0, 30.0)));
        const TArray<FGuid> NewlyStale = Watch->CheckNow(*Show, *World, TEXT("test"), false);
        TestEqual(TEXT("The mid-Passage key makes exactly one Scene handoff stale"), NewlyStale.Num(), 1);
        TestTrue(TEXT("The watch names the Scene whose Entry the key moved"), NewlyStale.Contains(SceneCueGuid));
        TestEqual(TEXT("A known stale Scene is not raised twice"), Watch->CheckNow(*Show, *World, TEXT("test"), false).Num(), 0);

        TestTrue(TEXT("Handoffs re-match"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, Report));
        TestEqual(TEXT("Matched handoffs are clean again"), Watch->CheckNow(*Show, *World, TEXT("test"), false).Num(), 0);

        TestTrue(TEXT("A later framing key lands"), KeyReframe(FVector(-50.0, 0.0, 0.0)));
        TestEqual(TEXT("Drift after a match is raised again"), Watch->CheckNow(*Show, *World, TEXT("test"), false).Num(), 1);
    }

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

#endif
