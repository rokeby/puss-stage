#include "InfinityStageHandoffWatch.h"

#include "CineCameraActor.h"
#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
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

namespace
{
/** Passage -> Scene -> Passage with matched handoff cameras, in a preview world. */
struct FHandoffFixture
{
    UWorld* World = nullptr;
    UInfinityStageShowAsset* Show = nullptr;
    AInfinityStageCameraRig* IncomingRig = nullptr;
    FGuid SceneCueGuid;
    FGuid IncomingPassageGuid;

    bool Build(FAutomationTestBase& Test)
    {
        World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
        WorldContext.SetCurrentWorld(World);
        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());

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
        SceneCueGuid = SceneCue.CueGuid;
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
        IncomingPassageGuid = Show->PassageSettings[0].PassageGuid;

        AInfinityStagePassageActor* IncomingPassage = World->SpawnActor<AInfinityStagePassageActor>();
        IncomingPassage->ShowAsset = Show;
        IncomingPassage->PassageGuid = IncomingPassageGuid;
        Test.TestTrue(TEXT("Incoming Passage materializes"), IncomingPassage->MaterializePassage());
        IncomingRig = World->SpawnActor<AInfinityStageCameraRig>();
        IncomingRig->PassageActor = IncomingPassage;
        IncomingRig->CameraOffset = FVector(0.0, 0.0, 180.0);
        IncomingRig->bEnableShadowCat = false;

        AInfinityStagePassageActor* OutgoingPassage = World->SpawnActor<AInfinityStagePassageActor>(
            FVector(5000.0, 10000.0, 0.0), FRotator(0.0, 90.0, 0.0));
        OutgoingPassage->ShowAsset = Show;
        OutgoingPassage->PassageGuid = Show->PassageSettings[1].PassageGuid;
        Test.TestTrue(TEXT("Outgoing Passage materializes"), OutgoingPassage->MaterializePassage());
        AInfinityStageCameraRig* OutgoingRig = World->SpawnActor<AInfinityStageCameraRig>();
        OutgoingRig->PassageActor = OutgoingPassage;
        OutgoingRig->CameraOffset = FVector(0.0, 0.0, 180.0);
        OutgoingRig->bEnableShadowCat = false;

        ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
        Master->Initialize();
        Show->ManagedMasterSequence = Master;
        FString Report;
        const bool bMaster = UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report);
        Test.TestTrue(TEXT("Master builds"), bMaster);
        const bool bMatched = FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, Report);
        Test.TestTrue(TEXT("Handoffs match"), bMatched);
        return bMaster && bMatched;
    }

    int32 CountStale()
    {
        TArray<FGuid> Stale;
        FString Report;
        FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(*Show, *World, { SceneCueGuid }, Stale, Report);
        return Stale.Num();
    }

    ACineCameraActor* FindEntryCamera() const
    {
        for (TActorIterator<ACineCameraActor> It(World); It; ++It)
        {
            if (It->ActorHasTag(TEXT("InfinityStage.SceneEntry")))
            {
                return *It;
            }
        }
        return nullptr;
    }

    void Destroy()
    {
        if (World)
        {
            GEngine->DestroyWorldContext(World);
            World->DestroyWorld(false);
            World = nullptr;
        }
    }
};
}

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
    FHandoffFixture Fixture;
    if (!Fixture.Build(*this))
    {
        Fixture.Destroy();
        return false;
    }
    UWorld* World = Fixture.World;
    UInfinityStageShowAsset* Show = Fixture.Show;
    const FGuid SceneCueGuid = Fixture.SceneCueGuid;
    const FGuid IncomingPassageGuid = Fixture.IncomingPassageGuid;
    FString Report;

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
            UInfinityStageCameraPilotLibrary::GetCameraView(*Fixture.IncomingRig, MidFrame, View, Focal, Focus);
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

    Fixture.Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHandoffCheckReaimTest,
    "InfinityStage.Editor.HandoffCheck.ReaimWithoutMovingIsStale",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHandoffCheckReaimTest::RunTest(const FString& Parameters)
{
    FHandoffFixture Fixture;
    if (!Fixture.Build(*this))
    {
        Fixture.Destroy();
        return false;
    }
    ACineCameraActor* Entry = Fixture.FindEntryCamera();
    TestNotNull(TEXT("The matched Scene has an Entry handoff camera"), Entry);
    if (Entry)
    {
        TestEqual(TEXT("A fresh match is clean"), Fixture.CountStale(), 0);

        // The old check compared FTransforms with a 0.5 tolerance applied to
        // quaternion components as well, so a camera could be re-aimed by up to
        // about 60 degrees without moving and still count as matched.
        Entry->AddActorWorldRotation(FRotator(0.0, 0.01, 0.0));
        TestEqual(TEXT("A 0.01 degree re-aim is within tolerance"), Fixture.CountStale(), 0);
        Entry->AddActorWorldRotation(FRotator(0.0, 5.0, 0.0));
        TestEqual(TEXT("A 5 degree re-aim without moving is stale"), Fixture.CountStale(), 1);

        FString MatchReport;
        TestTrue(TEXT("Handoffs re-match"), FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(
            *Fixture.Show, *Fixture.World, { Fixture.SceneCueGuid }, MatchReport));
        Entry = Fixture.FindEntryCamera();
        TestEqual(TEXT("Re-matched handoff is clean"), Fixture.CountStale(), 0);
        if (Entry)
        {
            Entry->AddActorWorldOffset(FVector(0.0, 0.3, 0.0));
            TestEqual(TEXT("A 0.3 cm move is within tolerance"), Fixture.CountStale(), 0);
            Entry->AddActorWorldOffset(FVector(0.0, 1.0, 0.0));
            TestEqual(TEXT("A 1.3 cm move is stale"), Fixture.CountStale(), 1);
        }
    }
    Fixture.Destroy();
    return true;
}

#endif
