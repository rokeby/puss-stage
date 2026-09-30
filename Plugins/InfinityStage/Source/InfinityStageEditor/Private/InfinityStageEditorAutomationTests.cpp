#include "SInfinityStageCueDesk.h"
#include "SInfinityStageWingAudit.h"

#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageDevFixtureBuilder.h"
#include "InfinityStageMusicAnalysisImporter.h"
#include "InfinityStageMusicMapAsset.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageShadowCatComponent.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageCurtainRig.h"
#include "InfinityStageCueProxy.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageShowGameMode.h"
#include "InfinityStageTransportController.h"
#include "InfinityStageWingAssetAuditor.h"
#include "InfinityStageWingSequenceInterchange.h"
#include "InfinityStageWingLibraryAsset.h"
#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/StaticMesh.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Editor.h"
#include "FileHelpers.h"
#include "HAL/FileManager.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerInput.h"
#include "InputKeyEventArgs.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "LevelSequencePlayer.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "MovieSceneInfinitySceneTrack.h"
#include "MovieSceneInfinityAudioTrack.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "ScopedTransaction.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieSceneAudioTrack.h"
#include "Tracks/MovieSceneSubTrack.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Tests/AutomationEditorCommon.h"
#include "UObject/UnrealType.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
int32 GInfinityStageFixtureComponentsBeforePIE = INDEX_NONE;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSceneCameraHandoffTest,
    "InfinityStage.Editor.SceneCameraHandoff",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSceneCameraHandoffTest::RunTest(const FString& Parameters)
{
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
    SceneCue.Label = FText::FromString(TEXT("Handoff Test Scene"));
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
    Show->PassageSettings[0].TailFrames = 24000;
    Show->PassageSettings[0].TailDistanceCm = 250.0;
    Show->PassageSettings[1].TailFrames = 24000;
    Show->PassageSettings[1].TailDistanceCm = 250.0;

    AInfinityStagePassageActor* IncomingPassage = World->SpawnActor<AInfinityStagePassageActor>();
    IncomingPassage->ShowAsset = Show;
    IncomingPassage->PassageGuid = Show->PassageSettings[0].PassageGuid;
    TestTrue(TEXT("Incoming Passage materializes"), IncomingPassage->MaterializePassage());
    AInfinityStageCameraRig* IncomingRig = World->SpawnActor<AInfinityStageCameraRig>();
    IncomingRig->PassageActor = IncomingPassage;
    IncomingRig->CameraOffset = FVector(0.0, 0.0, 180.0);

    AInfinityStagePassageActor* OutgoingPassage = World->SpawnActor<AInfinityStagePassageActor>(
        FVector(5000.0, 10000.0, 0.0), FRotator(0.0, 90.0, 0.0));
    OutgoingPassage->ShowAsset = Show;
    OutgoingPassage->PassageGuid = Show->PassageSettings[1].PassageGuid;
    TestTrue(TEXT("Outgoing Passage materializes"), OutgoingPassage->MaterializePassage());
    AInfinityStageCameraRig* OutgoingRig = World->SpawnActor<AInfinityStageCameraRig>();
    OutgoingRig->PassageActor = OutgoingPassage;
    OutgoingRig->CameraOffset = FVector(0.0, 0.0, 180.0);

    ULevelSequence* MasterSequence = NewObject<ULevelSequence>(GetTransientPackage());
    MasterSequence->Initialize();
    Show->ManagedMasterSequence = MasterSequence;
    FString MasterReport;
    TestTrue(TEXT("Managed Master for channel-aware handoff builds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, MasterSequence, MasterReport));
    if (UMovieSceneInfinityPassageTrack* PassageTrack =
        MasterSequence->GetMovieScene()->FindTrack<UMovieSceneInfinityPassageTrack>())
    {
        for (UMovieSceneSection* BaseSection : PassageTrack->GetAllSections())
        {
            UMovieSceneInfinityPassageSection* PassageSection = CastChecked<UMovieSceneInfinityPassageSection>(BaseSection);
            if (PassageSection->PassageGuid == IncomingPassage->PassageGuid)
            {
                PassageSection->FocalLengthMm.SetDefault(52.0);
                PassageSection->FocusDistanceCm.SetDefault(1234.0);
            }
            else if (PassageSection->PassageGuid == OutgoingPassage->PassageGuid)
            {
                PassageSection->FocalLengthMm.SetDefault(44.0);
                PassageSection->FocusDistanceCm.SetDefault(2345.0);
            }
        }
    }

    FString FirstReport;
    TestTrue(TEXT("Blank Scene receives matched boundary cameras"),
        FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, FirstReport));
    UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(
        SceneSequence->GetMovieScene()->GetCameraCutTrack());
    TestNotNull(TEXT("Scene has a Camera Cut Track"), CutTrack);
    TestEqual(TEXT("Scene has Entry and Exit camera cuts"), CutTrack ? CutTrack->GetAllSections().Num() : 0, 2);

    ACineCameraActor* EntryCamera = nullptr;
    ACineCameraActor* ExitCamera = nullptr;
    int32 HandoffCameraCount = 0;
    for (TActorIterator<ACineCameraActor> It(World); It; ++It)
    {
        if (It->ActorHasTag(TEXT("InfinityStage.SceneHandoff"))) ++HandoffCameraCount;
        if (It->ActorHasTag(TEXT("InfinityStage.SceneEntry"))) EntryCamera = *It;
        if (It->ActorHasTag(TEXT("InfinityStage.SceneExit"))) ExitCamera = *It;
    }
    TestEqual(TEXT("Exactly two boundary cameras were provisioned"), HandoffCameraCount, 2);
    TestNotNull(TEXT("Entry camera resolves"), EntryCamera);
    TestNotNull(TEXT("Exit camera resolves"), ExitCamera);
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    FTransform ExpectedEntry;
    FTransform ExpectedExit;
    IncomingRig->GetCameraTransformAtMasterFrame(Compiled.Segments[0].EndFrame, ExpectedEntry);
    OutgoingRig->GetCameraTransformAtMasterFrame(Compiled.Segments[2].StartFrame, ExpectedExit);
    if (EntryCamera && ExitCamera)
    {
        TestTrue(TEXT("Entry camera exactly matches incoming endpoint"),
            EntryCamera->GetActorTransform().Equals(ExpectedEntry, 0.001));
        TestTrue(TEXT("Exit camera exactly matches outgoing start"),
            ExitCamera->GetActorTransform().Equals(ExpectedExit, 0.001));
        TestEqual(TEXT("Entry handoff copies managed focal channel"),
            EntryCamera->GetCineCameraComponent()->CurrentFocalLength, 52.0f);
        TestEqual(TEXT("Entry handoff copies managed focus channel"),
            EntryCamera->GetCineCameraComponent()->FocusSettings.ManualFocusDistance, 1234.0f);
        TestEqual(TEXT("Exit handoff copies managed focal channel"),
            ExitCamera->GetCineCameraComponent()->CurrentFocalLength, 44.0f);
        TestEqual(TEXT("Exit handoff copies managed focus channel"),
            ExitCamera->GetCineCameraComponent()->FocusSettings.ManualFocusDistance, 2345.0f);
    }

    FString SecondReport;
    TestTrue(TEXT("Handoff refresh is idempotent"),
        FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, SecondReport));
    int32 RefreshedHandoffCameraCount = 0;
    for (TActorIterator<ACineCameraActor> It(World); It; ++It)
    {
        RefreshedHandoffCameraCount += It->ActorHasTag(TEXT("InfinityStage.SceneHandoff")) ? 1 : 0;
    }
    TestEqual(TEXT("Refresh does not duplicate boundary cameras"), RefreshedHandoffCameraCount, 2);
    TestEqual(TEXT("Refresh preserves two camera cuts"), CutTrack->GetAllSections().Num(), 2);

    ACineCameraActor* InteriorCamera = World->SpawnActor<ACineCameraActor>(
        FVector(1000.0, 1000.0, 180.0), FRotator::ZeroRotator);
    const FGuid InteriorGuid = SceneSequence->GetMovieScene()->AddPossessable(
        TEXT("Interior Shot Camera"),
        ACineCameraActor::StaticClass());
    SceneSequence->BindPossessableObject(InteriorGuid, *InteriorCamera, World);
    UMovieSceneCameraCutTrack* InteriorCutTrack = Cast<UMovieSceneCameraCutTrack>(SceneSequence->GetMovieScene()->GetCameraCutTrack());
    TestNotNull(TEXT("Interior test has camera cut track"), InteriorCutTrack);
    if (InteriorCutTrack)
    {
        const FFrameNumber InteriorStart = SceneCue.Scene.DurationFrames.Value / 4;
        const FFrameNumber InteriorEnd = SceneCue.Scene.DurationFrames.Value * 3 / 4;
        UMovieSceneCameraCutSection* InteriorCut = InteriorCutTrack->AddNewCameraCut(
            FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(InteriorGuid)),
            InteriorStart);
        InteriorCut->SetEndFrame(InteriorEnd);
    }

    FString ThirdReport;
    TestTrue(TEXT("Handoff refresh keeps existing interior sections"),
        FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, { SceneCueGuid }, ThirdReport));
    TestTrue(TEXT("Interior section is preserved after refresh"),
        CutTrack->GetAllSections().Num() >= 3);
    int32 HandOffBoundaryCutCount = 0;
    for (UMovieSceneSection* Section : CutTrack->GetAllSections())
    {
        if (UMovieSceneCameraCutSection* CameraCut = Cast<UMovieSceneCameraCutSection>(Section))
        {
            ACineCameraActor* CutCamera = nullptr;
            const auto CutBinding = CameraCut->GetCameraBindingID();
            if (CutBinding.IsValid())
            {
                TArray<UObject*, TInlineAllocator<1>> BoundObjects;
                SceneSequence->LocateBoundObjects(
                    CutBinding.GetGuid(),
                    UE::UniversalObjectLocator::FResolveParams(World),
                    nullptr,
                    BoundObjects);
                for (UObject* Bound : BoundObjects)
                {
                    if (ACineCameraActor* Camera = Cast<ACineCameraActor>(Bound))
                    {
                        CutCamera = Camera;
                        break;
                    }
                    if (const UCameraComponent* Component = Cast<UCameraComponent>(Bound))
                    {
                        CutCamera = Cast<ACineCameraActor>(Component->GetOwner());
                        break;
                    }
                }
            }
            if (CutCamera && !CutCamera->ActorHasTag(TEXT("InfinityStage.SceneHandoff")))
            {
                ++HandOffBoundaryCutCount;
            }
        }
    }
    TestEqual(TEXT("Interior camera cuts remain after handoff refresh"), HandOffBoundaryCutCount, 1);

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRetainedCameraCurtainTest,
    "InfinityStage.Editor.RetainedCameraCurtainInterstitial",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRetainedCameraCurtainTest::RunTest(const FString& Parameters)
{
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
    SceneCue.Label = FText::FromString(TEXT("Retained Camera Test Scene"));
    SceneCue.Scene.DurationFrames = 240000;
    SceneCue.Scene.ExitHandoffHoldFrames = 24000;
    const FGuid SceneCueGuid = SceneCue.CueGuid;
    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    SceneSequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    SceneSequence->GetMovieScene()->SetPlaybackRange(0, SceneCue.Scene.DurationFrames.Value);
    SceneCue.Scene.Sequence = SceneSequence;

    FInfinityShowCue& InteractionCue = Show->Cues.AddDefaulted_GetRef();
    InteractionCue.Type = EInfinityCueType::Sequence;
    InteractionCue.CueGuid = FGuid::NewGuid();
    InteractionCue.Label = FText::FromString(TEXT("Post-Scene Interstitial"));
    InteractionCue.Scene.DurationFrames = 360000;
    InteractionCue.Scene.bRetainPreviousCamera = true;
    InteractionCue.Scene.CurtainMode = EInfinityCurtainCueMode::PostSceneInterstitial;
    InteractionCue.Scene.bRevealNextPassageWhenCovered = true;
    InteractionCue.Scene.CurtainEntryTransitionFrames = 48000;
    InteractionCue.Scene.CurtainHoldFrames = 240000;
    InteractionCue.Scene.CurtainExitTransitionFrames = 48000;

    FInfinityShowCue& OutgoingCue = Show->Cues.AddDefaulted_GetRef();
    OutgoingCue.Type = EInfinityCueType::WingPair;
    OutgoingCue.CueGuid = FGuid::NewGuid();
    OutgoingCue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* IncomingPassage = World->SpawnActor<AInfinityStagePassageActor>();
    IncomingPassage->ShowAsset = Show;
    IncomingPassage->PassageGuid = Show->PassageSettings[0].PassageGuid;
    TestTrue(TEXT("Retained test incoming Passage materializes"), IncomingPassage->MaterializePassage());
    AInfinityStageCameraRig* IncomingRig = World->SpawnActor<AInfinityStageCameraRig>();
    IncomingRig->PassageActor = IncomingPassage;

    AInfinityStagePassageActor* OutgoingPassage = World->SpawnActor<AInfinityStagePassageActor>(
        FVector(9000.0, 12000.0, 0.0), FRotator(0.0, 90.0, 0.0));
    OutgoingPassage->ShowAsset = Show;
    OutgoingPassage->PassageGuid = Show->PassageSettings[1].PassageGuid;
    TestTrue(TEXT("Retained test outgoing Passage materializes"), OutgoingPassage->MaterializePassage());
    AInfinityStageCameraRig* OutgoingRig = World->SpawnActor<AInfinityStageCameraRig>();
    OutgoingRig->PassageActor = OutgoingPassage;

    ACineCameraActor* ArtistCamera = World->SpawnActor<ACineCameraActor>(
        FVector(1111.0, 2222.0, 333.0),
        FRotator(-7.0, 33.0, 0.0));
    ArtistCamera->GetCineCameraComponent()->SetCurrentFocalLength(61.0f);
    FCameraFocusSettings ArtistFocus = ArtistCamera->GetCineCameraComponent()->FocusSettings;
    ArtistFocus.FocusMethod = ECameraFocusMethod::Manual;
    ArtistFocus.ManualFocusDistance = 3456.0f;
    ArtistCamera->GetCineCameraComponent()->SetFocusSettings(ArtistFocus);
    const FGuid ArtistGuid = SceneSequence->GetMovieScene()->AddPossessable(
        TEXT("Final Designed Shot"),
        ACineCameraActor::StaticClass());
    SceneSequence->BindPossessableObject(ArtistGuid, *ArtistCamera, World);
    UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(
        SceneSequence->GetMovieScene()->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
    TestNotNull(TEXT("Retained test Camera Cut Track"), CutTrack);
    if (CutTrack)
    {
        UMovieSceneCameraCutSection* ArtistCut = CutTrack->AddNewCameraCut(
            FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(ArtistGuid)),
            FFrameNumber(24000));
        ArtistCut->SetEndFrame(FFrameNumber(240000));
    }

    FString Report;
    TestTrue(TEXT("Scene followed by retained interstitial matches"),
        FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(
            *Show, *World, { SceneCueGuid }, Report));

    ACineCameraActor* ExitCamera = nullptr;
    for (TActorIterator<ACineCameraActor> It(World); It; ++It)
    {
        if (It->ActorHasTag(TEXT("InfinityStage.SceneExit")))
        {
            ExitCamera = *It;
            break;
        }
    }
    TestNotNull(TEXT("Retained Exit camera resolves"), ExitCamera);
    if (ExitCamera)
    {
        TestTrue(TEXT("Retained Exit is explicitly tagged"),
            ExitCamera->ActorHasTag(TEXT("InfinityStage.SceneRetainedHold")));
        TestTrue(TEXT("Retained Exit keeps final designed transform"),
            ExitCamera->GetActorTransform().Equals(ArtistCamera->GetActorTransform(), 0.001));
        TestEqual(TEXT("Retained Exit keeps final designed focal length"),
            ExitCamera->GetCineCameraComponent()->CurrentFocalLength, 61.0f);
        TestEqual(TEXT("Retained Exit keeps final designed focus"),
            ExitCamera->GetCineCameraComponent()->FocusSettings.ManualFocusDistance, 3456.0f);
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestEqual(TEXT("Retained fixture compiles four blocks"), Compiled.Segments.Num(), 4);
    FTransform OutgoingTransform;
    if (ExitCamera && Compiled.Segments.IsValidIndex(3)
        && OutgoingRig->GetCameraTransformAtMasterFrame(Compiled.Segments[3].StartFrame, OutgoingTransform))
    {
        TestFalse(TEXT("Retained Exit is not the next Passage camera"),
            ExitCamera->GetActorTransform().Equals(OutgoingTransform, 0.001));
    }

    AInfinityStageShowRoot* ShowRoot = World->SpawnActor<AInfinityStageShowRoot>();
    ShowRoot->ShowAsset = Show;
    if (Compiled.Segments.IsValidIndex(2))
    {
        const FFrameNumber Start = Compiled.Segments[2].StartFrame;
        float Progress = -1.0f;
        TestTrue(TEXT("Curtain activates in the interstitial"),
            ShowRoot->GetCurtainStateAtFrame(Start, Progress));
        TestEqual(TEXT("Curtain starts open"), Progress, 0.0f);
        ShowRoot->GetCurtainStateAtFrame(Start + FFrameNumber(48000), Progress);
        TestEqual(TEXT("Curtain lowers over the retained shot"), Progress, 1.0f);
        ShowRoot->GetCurtainStateAtFrame(Start + FFrameNumber(288000), Progress);
        TestEqual(TEXT("Curtain remains closed through the interaction"), Progress, 1.0f);
        ShowRoot->GetCurtainStateAtFrame(Start + FFrameNumber(312000), Progress);
        TestEqual(TEXT("Curtain lifts before the next Passage"), Progress, 0.5f);

        Show->Cues[2].Scene.bSequenceOwnsCurtain = true;
        TestFalse(TEXT("Sequence-owned curtain bypasses the legacy global evaluator"),
            ShowRoot->GetCurtainStateAtFrame(Start + FFrameNumber(48000), Progress));
    }

    AInfinityStageCurtainRig* PreviewRig = World->SpawnActor<AInfinityStageCurtainRig>();
    TestNotNull(TEXT("Sequence curtain rig can be previewed without a runtime Show Root"), PreviewRig);
    if (PreviewRig)
    {
        PreviewRig->bFollowPlayerCamera = false;
        PreviewRig->bUseAuthoredOpenClosedTransforms = true;
        PreviewRig->CurtainOpenRelativeTransform.SetLocation(FVector(0.0, 0.0, 100.0));
        PreviewRig->CurtainClosedRelativeTransform.SetLocation(FVector::ZeroVector);
        PreviewRig->SetCurtainState(0.25f, true);
        TestTrue(TEXT("Authored open and closed placements interpolate from sequence progress"),
            PreviewRig->CurtainMotionRoot
            && FMath::IsNearlyEqual(PreviewRig->CurtainMotionRoot->GetRelativeLocation().Z, 75.0));
    }

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraGustUndoMultiSelectionTest,
    "InfinityStage.Editor.CameraGustUndoRedoAndMultiSelection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraGustUndoMultiSelectionTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(
        GetTransientPackage(), NAME_None, RF_Transactional);
    TArray<FGuid> Targets;
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Targets.Add(Cue.CueGuid);
    }
    FInfinityCameraGustSettings Settings;
    {
        const FScopedTransaction Transaction(NSLOCTEXT(
            "InfinityStage", "TestCameraGustTransaction", "Test Camera Gust Multi-selection"));
        Show->Modify();
        TestEqual(TEXT("Ordered three-row multi-selection applies"),
            Show->ApplyCameraGust(Targets, Settings, false), 3);
    }
    TestEqual(TEXT("Transaction produced the Camera Gust mode"),
        Show->Cues[0].WingPair.Mechanism.PlaybackMode, EInfinityMotionPlaybackMode::CameraGust);
    GEditor->UndoTransaction();
    TestEqual(TEXT("Undo restores the previous motion mode"),
        Show->Cues[0].WingPair.Mechanism.PlaybackMode, EInfinityMotionPlaybackMode::ContinuousLoop);
    GEditor->RedoTransaction();
    TestEqual(TEXT("Redo restores the complete Camera Gust assignment"),
        Show->Cues[0].WingPair.Mechanism.PlaybackMode, EInfinityMotionPlaybackMode::CameraGust);
    TestEqual(TEXT("Redo restores ordered group metadata"),
        Show->Cues[2].WingPair.Mechanism.CameraGust.GroupOrdinal, 2);

    UInfinityStageCueProxy* FirstProxy = NewObject<UInfinityStageCueProxy>(GetTransientPackage());
    UInfinityStageCueProxy* ThirdProxy = NewObject<UInfinityStageCueProxy>(GetTransientPackage());
    FirstProxy->Initialize(Show, 0);
    ThirdProxy->Initialize(Show, 2);
    FProperty* StaggerProperty = FindFProperty<FProperty>(
        FInfinityCameraGustSettings::StaticStruct(),
        GET_MEMBER_NAME_CHECKED(FInfinityCameraGustSettings, PairStaggerSeconds));
    FPropertyChangedEvent StaggerEvent(StaggerProperty, EPropertyChangeType::ValueSet);
    FirstProxy->Cue.WingPair.Mechanism.CameraGust.PairStaggerSeconds = 0.22;
    ThirdProxy->Cue.WingPair.Mechanism.CameraGust.PairStaggerSeconds = 0.22;
    FirstProxy->PostEditChangeProperty(StaggerEvent);
    ThirdProxy->PostEditChangeProperty(StaggerEvent);
    TestEqual(TEXT("Multi-edit writes the first selected row"),
        Show->Cues[0].WingPair.Mechanism.CameraGust.PairStaggerSeconds, 0.22);
    TestEqual(TEXT("Multi-edit writes the other selected row"),
        Show->Cues[2].WingPair.Mechanism.CameraGust.PairStaggerSeconds, 0.22);
    TestEqual(TEXT("Multi-edit leaves an unselected row unchanged"),
        Show->Cues[1].WingPair.Mechanism.CameraGust.PairStaggerSeconds, 0.10);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRestOpeningControlTest,
    "InfinityStage.Editor.RestOpeningBulkControl",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRestOpeningControlTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.LocalTransform = FTransform(
        FRotator(0.0, 15.0, 0.0), FVector(12.0, -700.0, 34.0), FVector(1.2, 1.0, 0.9));
    Cue.WingPair.Right.LocalTransform = FTransform(
        FRotator(0.0, -20.0, 0.0), FVector(56.0, 500.0, 78.0), FVector(0.8, 1.1, 1.0));
    Cue.WingPair.Mechanism.InwardTravelCm = 75.0;

    UInfinityStageCueProxy* Proxy = NewObject<UInfinityStageCueProxy>(GetTransientPackage());
    Proxy->Initialize(Show, 0);
    TestEqual(TEXT("Initial pivot separation is derived"), Proxy->RestOpeningWidthCm, 1200.0);
    TestEqual(TEXT("Initial centre offset is derived"), Proxy->OpeningCentreOffsetCm, -100.0);

    Proxy->RestOpeningWidthCm = 800.0;
    FProperty* WidthProperty = FindFProperty<FProperty>(
        UInfinityStageCueProxy::StaticClass(),
        GET_MEMBER_NAME_CHECKED(UInfinityStageCueProxy, RestOpeningWidthCm));
    FPropertyChangedEvent WidthEvent(WidthProperty, EPropertyChangeType::ValueSet);
    Proxy->PostEditChangeProperty(WidthEvent);

    const FInfinityWingOccurrence& WidthResult = Show->Cues[0].WingPair;
    TestEqual(TEXT("Width edit preserves centre on Left"),
        WidthResult.Left.LocalTransform.GetTranslation().Y, -500.0);
    TestEqual(TEXT("Width edit preserves centre on Right"),
        WidthResult.Right.LocalTransform.GetTranslation().Y, 300.0);
    TestEqual(TEXT("Left X remains authored"),
        WidthResult.Left.LocalTransform.GetTranslation().X, 12.0);
    TestEqual(TEXT("Right Z remains authored"),
        WidthResult.Right.LocalTransform.GetTranslation().Z, 78.0);
    TestTrue(TEXT("Left rotation remains authored"),
        WidthResult.Left.LocalTransform.GetRotation().Equals(FQuat(FRotator(0.0, 15.0, 0.0)), 0.001));
    TestEqual(TEXT("Mechanism travel remains independent"),
        WidthResult.Mechanism.InwardTravelCm, 75.0);

    Proxy->OpeningCentreOffsetCm = 50.0;
    FProperty* CentreProperty = FindFProperty<FProperty>(
        UInfinityStageCueProxy::StaticClass(),
        GET_MEMBER_NAME_CHECKED(UInfinityStageCueProxy, OpeningCentreOffsetCm));
    FPropertyChangedEvent CentreEvent(CentreProperty, EPropertyChangeType::ValueSet);
    Proxy->PostEditChangeProperty(CentreEvent);
    TestEqual(TEXT("Centre edit translates Left symmetrically"),
        Show->Cues[0].WingPair.Left.LocalTransform.GetTranslation().Y, -350.0);
    TestEqual(TEXT("Centre edit translates Right symmetrically"),
        Show->Cues[0].WingPair.Right.LocalTransform.GetTranslation().Y, 450.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAuditWingAssetsBootstrap,
    "PussStageBootstrap.AuditWingAssets",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAuditWingAssetsBootstrap::RunTest(const FString& Parameters)
{
    UInfinityStageWingLibraryAsset* Library = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
    TestNotNull(TEXT("Default Wing Asset Library resolves"), Library);
    if (!Library)
    {
        return false;
    }
    FInfinityWingAuditSummary Summary;
    FString Error;
    TestTrue(TEXT("Wing assets audit successfully"), FInfinityStageWingAssetAuditor::Scan(*Library, Summary, Error));
    TestTrue(TEXT("Wing audit found assets"), Summary.Total > 0);
    TestTrue(TEXT("Wing audit JSON exists"), FPaths::FileExists(Summary.ReportPath));
    AddInfo(Summary.ToString());
    if (!Error.IsEmpty()) AddInfo(Error);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageApplyWingCorrectionsBootstrap,
    "PussStageBootstrap.ApplyWingAssetCorrections",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageApplyWingCorrectionsBootstrap::RunTest(const FString& Parameters)
{
    UInfinityStageWingLibraryAsset* Library = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
    TestNotNull(TEXT("Default Wing Asset Library resolves"), Library);
    if (!Library)
    {
        return false;
    }
    FInfinityWingAuditSummary Summary;
    FString Error;
    if (!FInfinityStageWingAssetAuditor::Scan(*Library, Summary, Error))
    {
        AddError(Error);
        return false;
    }
    TestTrue(TEXT("Safe Wing Asset corrections apply"),
        FInfinityStageWingAssetAuditor::ApplySafeCorrections(*Library, Summary, Error));
    AddInfo(Summary.ToString());
    if (!Error.IsEmpty()) AddInfo(Error);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCreateVerticalSliceFixture,
    "PussStageBootstrap.CreateVerticalSlice",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCreateVerticalSliceFixture::RunTest(const FString& Parameters)
{
    FString MusicRoot;
    FParse::Value(FCommandLine::Get(), TEXT("InfinityStageMusicRoot="), MusicRoot);
    FString Report;
    if (!FInfinityStageDevFixtureBuilder::Build(MusicRoot, Report))
    {
        AddError(Report);
        return false;
    }
    AddInfo(Report);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRepairCurrentWingPassages,
    "PussStageBootstrap.RepairCurrentWingPassages",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRepairCurrentWingPassages::RunTest(const FString& Parameters)
{
    FString Report;
    if (!FInfinityStageDevFixtureBuilder::RepairCurrentWingPassages(Report))
    {
        AddError(Report);
        return false;
    }
    AddInfo(Report);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMatchCurrentSceneHandoffs,
    "PussStageBootstrap.MatchSceneHandoffs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMatchCurrentSceneHandoffs::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = LoadObject<UInfinityStageShowAsset>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show"));
    TestNotNull(TEXT("Current Show resolves"), Show);
    UWorld* World = UEditorLoadingAndSavingUtils::LoadMap(
        TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"));
    TestNotNull(TEXT("Current fixture map resolves"), World);
    if (!Show || !World)
    {
        return false;
    }

    FString Report;
    if (!FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, {}, Report))
    {
        AddError(Report);
        return false;
    }
    TArray<UPackage*> SequencePackages;
    for (const FInfinityShowCue& Cue : Show->Cues)
    {
        if (Cue.Type == EInfinityCueType::Scene)
        {
            if (ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous())
            {
                SequencePackages.AddUnique(Sequence->GetOutermost());
            }
        }
    }
    TestTrue(TEXT("Matched Scene sequences save"),
        UEditorLoadingAndSavingUtils::SavePackages(SequencePackages, false));
    TestTrue(TEXT("Matched boundary cameras save in the fixture map"),
        UEditorLoadingAndSavingUtils::SaveMap(
            World,
            TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice")));
    AddInfo(Report);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageImportMusicMapsFixture,
    "PussStageBootstrap.ImportMusicMaps",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageImportMusicMapsFixture::RunTest(const FString& Parameters)
{
    FString AnalysisRoot;
    FParse::Value(FCommandLine::Get(), TEXT("InfinityStageAnalysisRoot="), AnalysisRoot);
    UInfinityStageShowAsset* Show = LoadObject<UInfinityStageShowAsset>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show"));
    TestNotNull(TEXT("Development Show exists"), Show);
    if (!Show)
    {
        return false;
    }

    TArray<FGuid> CueIdsBefore;
    for (const FInfinityShowCue& Cue : Show->Cues)
    {
        CueIdsBefore.Add(Cue.CueGuid);
    }
    FString FirstReport;
    TestTrue(TEXT("Analysis maps import"), FInfinityStageMusicAnalysisImporter::ImportDirectory(AnalysisRoot, Show, FirstReport));
    TestEqual(TEXT("Six analysis maps are linked"), Show->MusicRails.Num(), 6);
    TestEqual(TEXT("Cue count is unchanged"), Show->Cues.Num(), CueIdsBefore.Num());
    for (int32 Index = 0; Index < Show->Cues.Num(); ++Index)
    {
        TestEqual(TEXT("Cue identity is unchanged"), Show->Cues[Index].CueGuid, CueIdsBefore[Index]);
    }
    for (const FInfinityMusicRail& Rail : Show->MusicRails)
    {
        UInfinityStageMusicMapAsset* Map = Rail.AnalysisMap.LoadSynchronous();
        TestNotNull(TEXT("Music rail has a review map"), Map);
        if (Map)
        {
            TestFalse(TEXT("Analysis did not mutate cues"), Map->bCueScoreMutatedByAnalysis);
            TestTrue(TEXT("Analysis requires artist approval"), Map->bRequiresArtistApproval);
        }
    }

    FString SecondReport;
    TestTrue(TEXT("Analysis reimport is idempotent"), FInfinityStageMusicAnalysisImporter::ImportDirectory(AnalysisRoot, Show, SecondReport));
    TestEqual(TEXT("Cue count remains unchanged after reimport"), Show->Cues.Num(), CueIdsBefore.Num());
    AddInfo(FirstReport);
    AddInfo(SecondReport);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRebuildCurrentMasterFixture,
    "PussStageBootstrap.RebuildCurrentMaster",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRebuildCurrentMasterFixture::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = LoadObject<UInfinityStageShowAsset>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show"));
    ULevelSequence* Master = LoadObject<ULevelSequence>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"));
    TestNotNull(TEXT("Current Show resolves"), Show);
    TestNotNull(TEXT("Current Master resolves"), Master);
    if (!Show || !Master)
    {
        return false;
    }

    FString Report;
    TestTrue(TEXT("Current managed Master rebuilds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));
    if (!UEditorLoadingAndSavingUtils::SavePackages({ Show->GetOutermost(), Master->GetOutermost() }, false))
    {
        AddError(TEXT("The rebuilt Show/Master packages did not save."));
        return false;
    }
    AddInfo(Report);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSavedFixturePIETest,
    "PussStage.InfinityStage.Functional.SavedFixturePIE",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSavedFixturePIETest::RunTest(const FString& Parameters)
{
    GInfinityStageFixtureComponentsBeforePIE = INDEX_NONE;
    AddCommand(new FEditorLoadMap(TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice")));
    AddCommand(new FFunctionLatentCommand([this]()
    {
        UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        TestNotNull(TEXT("Saved fixture map reopens"), EditorWorld);
        if (!EditorWorld)
        {
            return true;
        }

        int32 PassageActors = 0;
        int32 FixedWingPairs = 0;
        int32 ManagedComponents = 0;
        int32 ComponentBudget = 0;
        bool bEveryPassageWithinBudget = true;
        int32 ShowRoots = 0;
        for (TActorIterator<AInfinityStagePassageActor> It(EditorWorld); It; ++It)
        {
            ++PassageActors;
            FixedWingPairs += It->MaterializedWingPairCount;
            ManagedComponents += It->ManagedComponents.Num();
            ComponentBudget += It->ComponentBudget;
            bEveryPassageWithinBudget &= It->ManagedComponents.Num() <= It->ComponentBudget;
        }
        for (TActorIterator<AInfinityStageShowRoot> It(EditorWorld); It; ++It)
        {
            ++ShowRoots;
        }
        TestEqual(TEXT("Six fixed Passage actors reopen"), PassageActors, 6);
        TestEqual(TEXT("All fixed Wing Pairs exist before PIE"), FixedWingPairs, 261);
        TestTrue(TEXT("Every authored Passage stays within its explicit component budget"), bEveryPassageWithinBudget);
        TestTrue(TEXT("The saved fixture has visible render components"), ManagedComponents > 0);
        TestTrue(TEXT("The aggregate component count stays within the aggregate budget"), ManagedComponents <= ComponentBudget);
        GInfinityStageFixtureComponentsBeforePIE = ManagedComponents;
        TestEqual(TEXT("Exactly one Show Root authority"), ShowRoots, 1);
        return true;
    }));
    AddCommand(new FStartPIECommand(false));
    AddCommand(new FDelayedFunctionLatentCommand([this]()
    {
        UWorld* PieWorld = nullptr;
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            if (Context.WorldType == EWorldType::PIE)
            {
                PieWorld = Context.World();
                break;
            }
        }
        TestNotNull(TEXT("PIE world starts"), PieWorld);
        if (!PieWorld)
        {
            return;
        }

        AInfinityStageShowRoot* ShowRoot = nullptr;
        TActorIterator<AInfinityStageShowRoot> ShowRootIt(PieWorld);
        if (ShowRootIt)
        {
            ShowRoot = *ShowRootIt;
        }
        TestNotNull(TEXT("PIE has one prepared Show Root"), ShowRoot);
        if (!ShowRoot || !ShowRoot->Transport)
        {
            return;
        }
        TestNotNull(TEXT("One Master Sequence Player is prepared"), ShowRoot->SequencePlayer.Get());
        TestEqual(TEXT("Opening, six Passages, six Scenes and six post blocks compile to transport"),
            ShowRoot->Transport->Segments.Num(), 19);
        if (ShowRoot->Transport->Segments.Num() != 19)
        {
            return;
        }
        TestEqual(TEXT("Show begins on the Opening Curtain block"),
            ShowRoot->Transport->FindSegmentAtFrame(0), 0);
        TestEqual(TEXT("Opening is a Sequence block"),
            ShowRoot->Transport->Segments[0].Type, EInfinityCueType::Sequence);
        TestEqual(TEXT("Passage 1 follows Opening"),
            ShowRoot->Transport->Segments[1].Type, EInfinityCueType::WingPair);
        TestEqual(TEXT("Scene 1 follows Passage 1"),
            ShowRoot->Transport->Segments[2].Type, EInfinityCueType::Scene);
        TestTrue(TEXT("Interaction 1 retains the Scene 1 camera before cover"),
            ShowRoot->Transport->Segments[3].bRetainPreviousCamera);
        TestTrue(TEXT("Interaction 1 reveals Passage 2 once fully covered"),
            ShowRoot->Transport->Segments[3].bRevealNextPassageWhenCovered);
        TestEqual(TEXT("Interaction 1 handoff follows its sequence-authored hidden-changeover marker"),
            ShowRoot->Transport->Segments[3].CoveredHandoffFrame,
            ShowRoot->Transport->Segments[3].StartFrame + FFrameNumber(360000));
        TestTrue(TEXT("Closing retains the Scene 6 camera"),
            ShowRoot->Transport->Segments[18].bRetainPreviousCamera);

        float OpeningCurtainProgress = -1.0f;
        TestFalse(TEXT("Opening sequence owns its curtain instead of the global evaluator"),
            ShowRoot->GetCurtainStateAtFrame(
                ShowRoot->Transport->Segments[0].StartFrame,
                OpeningCurtainProgress));
        TestNull(TEXT("Sequence-owned Show does not spawn a duplicate global curtain rig"),
            ShowRoot->CurtainRig.Get());

        APlayerController* PlayerController = PieWorld->GetFirstPlayerController();
        TestNotNull(TEXT("PIE has a Player Controller for camera ownership"), PlayerController);
        AInfinityStageCameraRig* PassageOneCamera = nullptr;
        for (TActorIterator<AInfinityStageCameraRig> It(PieWorld); It; ++It)
        {
            if (It->PassageActor
                && It->PassageActor->PassageGuid == ShowRoot->Transport->Segments[1].SegmentGuid)
            {
                PassageOneCamera = *It;
                break;
            }
        }
        TestNotNull(TEXT("Passage 1 camera resolves by Passage GUID"), PassageOneCamera);
        AInfinityStageCameraRig* PassageTwoCamera = nullptr;
        for (TActorIterator<AInfinityStageCameraRig> It(PieWorld); It; ++It)
        {
            if (It->PassageActor
                && It->PassageActor->PassageGuid == ShowRoot->Transport->Segments[4].SegmentGuid)
            {
                PassageTwoCamera = *It;
                break;
            }
        }
        TestNotNull(TEXT("Passage 2 camera resolves by Passage GUID"), PassageTwoCamera);
        TestEqual(
            TEXT("Opening evaluation lands on the first Master frame"),
            ShowRoot->Transport->JumpToCurrentStart(),
            EInfinityTransportResult::Succeeded);
        // An Opening that authors its own Camera Cut (the stalls view onto the baked drape at the stage front,
        // 29 Sep) owns the view, as the transport intends; without one, Passage 1's camera waits behind the curtain.
        bool bOpeningAuthorsCameraCut = false;
        if (ShowRoot->ShowAsset && ShowRoot->ShowAsset->Cues.IsValidIndex(ShowRoot->Transport->Segments[0].CueIndex))
        {
            const ULevelSequence* OpeningSequence =
                ShowRoot->ShowAsset->Cues[ShowRoot->Transport->Segments[0].CueIndex].Scene.Sequence.LoadSynchronous();
            const UMovieScene* OpeningScene = OpeningSequence ? OpeningSequence->GetMovieScene() : nullptr;
            const UMovieSceneTrack* OpeningCuts = OpeningScene ? OpeningScene->GetCameraCutTrack() : nullptr;
            if (OpeningCuts)
            {
                const FFrameNumber OpeningStart = OpeningScene->GetPlaybackRange().GetLowerBoundValue();
                for (const UMovieSceneSection* Section : OpeningCuts->GetAllSections())
                {
                    bOpeningAuthorsCameraCut |= Section && Section->GetRange().Contains(OpeningStart);
                }
            }
        }
        if (PlayerController && PassageOneCamera)
        {
            if (bOpeningAuthorsCameraCut)
            {
                const AActor* OpeningViewTarget = PlayerController->GetViewTarget();
                TestTrue(TEXT("Opening's authored Camera Cut owns the view before lifting"),
                    OpeningViewTarget
                    && OpeningViewTarget != PassageOneCamera
                    && OpeningViewTarget->IsA<ACameraActor>());
            }
            else
            {
                TestEqual(TEXT("Opening reveal establishes Passage 1 camera before lifting"),
                    PlayerController->GetViewTarget(), static_cast<AActor*>(PassageOneCamera));
            }
            TestTrue(TEXT("PIE controller supports viewport keyboard transport"),
                PlayerController->IsA<AInfinityStageShowPlayerController>());
            if (PlayerController->PlayerInput && PlayerController->InputComponent)
            {
                const auto PressKey = [PlayerController](const FKey Key)
                {
                    PlayerController->InputKey(FInputKeyEventArgs(nullptr,
                        FInputDeviceId::CreateFromInternalId(0), Key, IE_Pressed, FPlatformTime::Cycles64()));
                    PlayerController->PlayerTick(1.0f / 60.0f);
                    PlayerController->InputKey(FInputKeyEventArgs(nullptr,
                        FInputDeviceId::CreateFromInternalId(0), Key, IE_Released, FPlatformTime::Cycles64()));
                    PlayerController->PlayerTick(1.0f / 60.0f);
                };
                PressKey(EKeys::SpaceBar);
                TestTrue(TEXT("Viewport Space starts the held opening"), ShowRoot->Transport->IsTransportPlaying());
                PressKey(EKeys::SpaceBar);
                TestFalse(TEXT("Viewport Space holds playback"), ShowRoot->Transport->IsTransportPlaying());
                PressKey(EKeys::Right);
                TestEqual(TEXT("Viewport Right advances to Passage 1"),
                    ShowRoot->Transport->GetCurrentMasterFrame(), ShowRoot->Transport->Segments[1].StartFrame);
                PressKey(EKeys::Left);
                TestEqual(TEXT("Viewport Left returns to the opening"),
                    ShowRoot->Transport->GetCurrentMasterFrame(), ShowRoot->Transport->Segments[0].StartFrame);
                PressKey(EKeys::Right);
                PressKey(EKeys::Right);
                TestTrue(TEXT("Viewport Right starts the following Scene"), ShowRoot->Transport->IsTransportPlaying());
                TestTrue(TEXT("Playing the cued Scene preserves its entry camera"),
                    PlayerController->GetViewTarget()
                    && PlayerController->GetViewTarget()->ActorHasTag(TEXT("InfinityStage.SceneEntry")));
                const FFrameTime SceneSweepFrame = FFrameRate::TransformTime(
                    FFrameTime(ShowRoot->Transport->Segments[2].StartFrame + FFrameNumber(960)),
                    ShowRoot->ShowAsset->TickResolution, ShowRoot->ShowAsset->DisplayRate);
                ShowRoot->SequencePlayer->SetPlaybackPosition(
                    FMovieSceneSequencePlaybackParams(SceneSweepFrame, EUpdatePositionMethod::Play));
                TestTrue(TEXT("Outgoing Passage cannot reclaim the camera during the first Scene sweep"),
                    PlayerController->GetViewTarget()
                    && PlayerController->GetViewTarget()->ActorHasTag(TEXT("InfinityStage.SceneEntry")));
                const bool bWasPerformance = ShowRoot->Transport->bPerformanceMode;
                ShowRoot->Transport->bPerformanceMode = false;
                ShowRoot->Transport->ScrubToMasterFrame(ShowRoot->Transport->Segments[0].StartFrame);
                ShowRoot->Transport->bPerformanceMode = bWasPerformance;
            }
        }
        const EInfinityTransportResult OpeningJump = ShowRoot->Transport->JumpToNextSegment();
        TestEqual(TEXT("Opening hands off to Passage 1"),
            OpeningJump, EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Passage 1 starts on its exact compiled frame"),
            ShowRoot->Transport->GetCurrentMasterFrame(),
            ShowRoot->Transport->Segments[1].StartFrame);
        if (PlayerController && PassageOneCamera)
        {
            TestEqual(TEXT("PIE view target is Passage 1 camera"), PlayerController->GetViewTarget(), static_cast<AActor*>(PassageOneCamera));
        }

        const EInfinityTransportResult FirstJump = ShowRoot->Transport->JumpToNextSegment();
        AddInfo(FString::Printf(TEXT("FirstJump=%d Current=%d ExpectedScene=%d Selected=%d"),
            static_cast<int32>(FirstJump),
            ShowRoot->Transport->GetCurrentMasterFrame().Value,
            ShowRoot->Transport->Segments[2].StartFrame.Value,
            ShowRoot->Transport->SelectedSegmentIndex));
        TestEqual(TEXT("Jump Passage 1 to Scene 1"), FirstJump, EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Scene handoff lands on exact frame"), ShowRoot->Transport->GetCurrentMasterFrame(), ShowRoot->Transport->Segments[2].StartFrame);
        if (PlayerController)
        {
            AActor* SceneViewTarget = PlayerController->GetViewTarget();
            TestNotNull(TEXT("Scene handoff resolves a camera owner"), SceneViewTarget);
            TestTrue(TEXT("Scene Entry Camera owns the PIE viewport at the boundary"),
                SceneViewTarget && SceneViewTarget->ActorHasTag(TEXT("InfinityStage.SceneEntry")));
        }
        // The unsafe-jump guard only refuses in performance mode, and the saved level may be in rehearsal mode (it is
        // for Gary's walk). Force performance mode for this step instead of depending on how the level was saved:
        // on 29 Sep a rehearsal-mode level let this jump succeed, and the steps below then started one segment late.
        const bool bSavedPerformanceMode = ShowRoot->Transport->bPerformanceMode;
        AddInfo(FString::Printf(TEXT("SavedLevelPerformanceMode=%d (the fixture forces the mode each step needs)"),
            bSavedPerformanceMode ? 1 : 0));
        ShowRoot->Transport->bPerformanceMode = true;
        TestTrue(TEXT("Unsafe-jump step runs in performance mode, whatever mode the level was saved in"),
            ShowRoot->Transport->bPerformanceMode);
        const EInfinityTransportResult UnsafeJump = ShowRoot->Transport->JumpToNextSegment();
        AddInfo(FString::Printf(TEXT("UnsafeJump=%d Current=%d Selected=%d"),
            static_cast<int32>(UnsafeJump),
            ShowRoot->Transport->GetCurrentMasterFrame().Value,
            ShowRoot->Transport->SelectedSegmentIndex));
        TestEqual(TEXT("External unpausable Scene rejects an unsafe next jump"), UnsafeJump, EInfinityTransportResult::UnsafeExternalClock);

        ShowRoot->Transport->bPerformanceMode = false;
        const EInfinityTransportResult RehearsalJump = ShowRoot->Transport->AdvanceToNextSegment();
        AddInfo(FString::Printf(TEXT("RehearsalJump=%d Current=%d ExpectedInteraction=%d Selected=%d"),
            static_cast<int32>(RehearsalJump),
            ShowRoot->Transport->GetCurrentMasterFrame().Value,
            ShowRoot->Transport->Segments[3].StartFrame.Value,
            ShowRoot->Transport->SelectedSegmentIndex));
        TestEqual(TEXT("Rehearsal can enter Interaction 1"), RehearsalJump, EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Interaction 1 lands exactly"), ShowRoot->Transport->GetCurrentMasterFrame(), ShowRoot->Transport->Segments[3].StartFrame);
        TestTrue(TEXT("Advancing into Interaction 1 starts its curtain sequence automatically"),
            ShowRoot->Transport->IsTransportPlaying());
        TestEqual(TEXT("Rehearsal can hold again for deterministic curtain inspection"),
            ShowRoot->Transport->PauseTransport(),
            EInfinityTransportResult::Succeeded);
        // Transition curtain (29 Sep): once an Interaction authors its own Camera Cut, the Interaction happens ON the
        // baked drape at the next Passage's mouth, seen from Look & camera's tagged stalls camera, and the old
        // camera-following rig stays present but inactive. Until the data carries that, the legacy staging is asserted.
        bool bInteractionAuthorsCut = false;
        {
            const int32 InteractionCueIndex = ShowRoot->Transport->Segments[3].CueIndex;
            const ULevelSequence* InteractionSequence =
                ShowRoot->ShowAsset && ShowRoot->ShowAsset->Cues.IsValidIndex(InteractionCueIndex)
                    ? ShowRoot->ShowAsset->Cues[InteractionCueIndex].Scene.Sequence.LoadSynchronous()
                    : nullptr;
            const UMovieScene* InteractionScene = InteractionSequence ? InteractionSequence->GetMovieScene() : nullptr;
            const UMovieSceneTrack* InteractionCuts = InteractionScene ? InteractionScene->GetCameraCutTrack() : nullptr;
            bInteractionAuthorsCut = InteractionCuts && !InteractionCuts->GetAllSections().IsEmpty();
        }
        AddInfo(FString::Printf(TEXT("Interaction1AuthorsCameraCut=%d"), bInteractionAuthorsCut ? 1 : 0));
        const auto IsPassageTwoMouthStalls = [](const AActor* Actor)
        {
            return Actor
                && Actor->ActorHasTag(TEXT("InfinityStage.TransitionStalls"))
                && Actor->ActorHasTag(TEXT("InfinityStage.Mouth.P02"));
        };
        if (PlayerController)
        {
            AActor* InteractionViewTarget = PlayerController->GetViewTarget();
            TestNotNull(TEXT("Interaction 1 retains a camera owner"), InteractionViewTarget);
            if (bInteractionAuthorsCut)
            {
                TestTrue(TEXT("Interaction 1 happens on its curtain: the view is the stalls camera at Passage 2's mouth"),
                    IsPassageTwoMouthStalls(InteractionViewTarget));
            }
            else
            {
                TestTrue(TEXT("Interaction 1 holds the Scene 1 exit camera"),
                    InteractionViewTarget
                    && InteractionViewTarget->ActorHasTag(TEXT("InfinityStage.SceneExit"))
                    && InteractionViewTarget->ActorHasTag(TEXT("InfinityStage.SceneRetainedHold")));
            }
        }
        float InteractionCurtainProgress = -1.0f;
        TestFalse(TEXT("Interaction 1 sequence owns the visible curtain"),
            ShowRoot->GetCurtainStateAtFrame(
                ShowRoot->Transport->Segments[3].StartFrame,
                InteractionCurtainProgress));
        const FFrameNumber InteractionClosedFrame =
            ShowRoot->Transport->Segments[3].CoveredHandoffFrame;
        TestEqual(TEXT("Rehearsal can scrub to Interaction 1 curtain-down frame"),
            ShowRoot->Transport->ScrubToMasterFrame(InteractionClosedFrame),
            EInfinityTransportResult::Succeeded);
        int32 SequenceCurtainRigCount = 0;
        AInfinityStageCurtainRig* SequenceCurtainRig = nullptr;
        for (TActorIterator<AInfinityStageCurtainRig> It(PieWorld); It; ++It)
        {
            ++SequenceCurtainRigCount;
            SequenceCurtainRig = *It;
        }
        TestEqual(TEXT("Interaction sequence evaluates exactly one curtain rig"),
            SequenceCurtainRigCount, 1);
        if (SequenceCurtainRig && bInteractionAuthorsCut)
        {
            SequenceCurtainRig->Tick(0.0f);
            TestFalse(TEXT("The old camera-following rig is kept but inactive once the Interaction has its drape"),
                SequenceCurtainRig->bCurtainActive);
            TestTrue(TEXT("The old rig's fire-safety mesh is not shown"),
                !SequenceCurtainRig->CurtainMesh || !SequenceCurtainRig->CurtainMesh->IsVisible());
            int32 DrapeCount = 0;
            for (TActorIterator<AActor> It(PieWorld); It; ++It)
            {
                DrapeCount += It->GetClass()->GetName() == TEXT("GeometryCacheActor") ? 1 : 0;
            }
            TestTrue(TEXT("The Interaction spawns its baked drape"), DrapeCount >= 1);
        }
        else if (SequenceCurtainRig)
        {
            TestTrue(TEXT("Interaction curtain actor tick is enabled"),
                SequenceCurtainRig->IsActorTickEnabled());
            // ScrubToMasterFrame evaluates Sequencer synchronously inside this
            // latent command. Apply the actor's next-frame presentation tick
            // before inspecting component visibility.
            SequenceCurtainRig->Tick(0.0f);
            TestTrue(TEXT("Interaction sequence is fully lowered at its hidden-changeover marker"),
                FMath::IsNearlyEqual(SequenceCurtainRig->CurtainProgress, 1.0f));
            TestTrue(TEXT("Interaction curtain is placed beyond the near-camera placeholder distance"),
                SequenceCurtainRig->CurtainDistanceCm >= 1000.0f);
            TestTrue(TEXT("Interaction curtain closed transform supplies full-frame scale margin"),
                SequenceCurtainRig->CurtainClosedRelativeTransform.GetScale3D().GetAbsMax() >= 3.0);
            TestTrue(TEXT("Interaction curtain closed transform compensates its bottom pivot"),
                SequenceCurtainRig->CurtainClosedRelativeTransform.GetTranslation().Z <= -1500.0);
            TestTrue(TEXT("Interaction curtain keeps a safety hold after hidden changeover"),
                ShowRoot->Transport->Segments[3].CoveredHandoffFrame
                    < ShowRoot->Transport->Segments[3].StartFrame + FFrameNumber(384000));
            TestTrue(TEXT("Interaction sequence curtain is active"),
                SequenceCurtainRig->bCurtainActive);
            TestNotNull(TEXT("Interaction sequence curtain has a mesh component"),
                SequenceCurtainRig->CurtainMesh.Get());
            if (SequenceCurtainRig->CurtainMesh)
            {
                TestTrue(TEXT("Curtain mesh component is explicitly visible"),
                    SequenceCurtainRig->CurtainMesh->IsVisible());
                TestFalse(TEXT("Curtain mesh component is not hidden in game"),
                    SequenceCurtainRig->CurtainMesh->bHiddenInGame);
                TestNotNull(TEXT("Curtain mesh component resolves the production mesh"),
                    SequenceCurtainRig->CurtainMesh->GetStaticMesh().Get());
                if (const UStaticMesh* CurtainStaticMesh =
                    SequenceCurtainRig->CurtainMesh->GetStaticMesh())
                {
                    const FBoxSphereBounds CurtainBounds = CurtainStaticMesh->GetBounds();
                    TestTrue(TEXT("Curtain mesh is wide enough to cover the camera"),
                        CurtainBounds.BoxExtent.Y >= 800.0);
                    TestTrue(TEXT("Curtain mesh is tall enough to cover the camera"),
                        CurtainBounds.BoxExtent.Z >= 450.0);
                }
            }
        }
        if (PlayerController && bInteractionAuthorsCut)
        {
            TestTrue(TEXT("The authored cut keeps the drape in view through the covered frame"),
                IsPassageTwoMouthStalls(PlayerController->GetViewTarget()));
        }
        else if (PlayerController && PassageTwoCamera)
        {
            TestEqual(TEXT("Covered curtain switches the hidden world to Passage 2 start"),
                PlayerController->GetViewTarget(), static_cast<AActor*>(PassageTwoCamera));
        }

        const EInfinityTransportResult PassageTwoJump = ShowRoot->Transport->JumpToNextSegment();
        TestEqual(TEXT("Interaction 1 hands off to Passage 2"),
            PassageTwoJump, EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Passage 2 handback lands exactly"),
            ShowRoot->Transport->GetCurrentMasterFrame(),
            ShowRoot->Transport->Segments[4].StartFrame);
        if (PlayerController && PassageTwoCamera)
        {
            TestEqual(TEXT("PIE view target hands back to Passage 2 camera"), PlayerController->GetViewTarget(), static_cast<AActor*>(PassageTwoCamera));
        }
        const EInfinityTransportResult ReverseJump = ShowRoot->Transport->JumpToPreviousSegment();
        AddInfo(FString::Printf(TEXT("ReverseJump=%d Current=%d ExpectedInteraction=%d Selected=%d"),
            static_cast<int32>(ReverseJump),
            ShowRoot->Transport->GetCurrentMasterFrame().Value,
            ShowRoot->Transport->Segments[3].StartFrame.Value,
            ShowRoot->Transport->SelectedSegmentIndex));
        TestEqual(TEXT("Reverse navigation returns to Interaction 1"), ReverseJump, EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Reverse Interaction frame is exact"),
            ShowRoot->Transport->GetCurrentMasterFrame(),
            ShowRoot->Transport->Segments[3].StartFrame);
        if (PlayerController)
        {
            AActor* ReverseInteractionViewTarget = PlayerController->GetViewTarget();
            AddInfo(FString::Printf(TEXT("ReverseInteractionViewTarget=%s"),
                ReverseInteractionViewTarget ? *ReverseInteractionViewTarget->GetActorLabel() : TEXT("null")));
            // 30 Sep: reverse entry re-runs forward entry's camera arbitration, so once Interaction 1 authors its own
            // Camera Cut it is seen from the same tagged stalls camera as on the way in. The retained Scene 1 exit camera
            // is still built, and is still the fallback when no cut is authored (the legacy branch, unchanged).
            if (bInteractionAuthorsCut)
            {
                TestTrue(TEXT("Reverse navigation returns to the Interaction's authored stalls camera"),
                    IsPassageTwoMouthStalls(ReverseInteractionViewTarget));
            }
            else
            {
                TestTrue(TEXT("Reverse navigation restores the retained Scene 1 exit camera"),
                    ReverseInteractionViewTarget
                    && ReverseInteractionViewTarget->ActorHasTag(TEXT("InfinityStage.SceneExit")));
            }
        }

        float ClosingCurtainProgress = -1.0f;
        const FFrameNumber ClosingCoveredFrame(
            ShowRoot->Transport->Segments[18].StartFrame.Value + 96000);
        TestFalse(TEXT("Closing sequence owns its visible curtain"),
            ShowRoot->GetCurtainStateAtFrame(ClosingCoveredFrame, ClosingCurtainProgress));
        TestEqual(TEXT("Rehearsal can scrub into the sequence-authored closing cover"),
            ShowRoot->Transport->ScrubToMasterFrame(ClosingCoveredFrame),
            EInfinityTransportResult::Succeeded);
        int32 ClosingCurtainRigCount = 0;
        AInfinityStageCurtainRig* ClosingCurtainRig = nullptr;
        for (TActorIterator<AInfinityStageCurtainRig> It(PieWorld); It; ++It)
        {
            ++ClosingCurtainRigCount;
            ClosingCurtainRig = *It;
        }
        // Log it so a pass is visible: "passed" and "never reached" must not look the same in the log.
        AddInfo(FString::Printf(TEXT("ClosingCurtainRigCount=%d ClosingCoveredFrame=%d"),
            ClosingCurtainRigCount, ClosingCoveredFrame.Value));
        TestEqual(TEXT("Closing sequence evaluates exactly one curtain rig"),
            ClosingCurtainRigCount, 1);
        if (ClosingCurtainRig)
        {
            TestTrue(TEXT("Closing sequence keeps the curtain fully lowered"),
                FMath::IsNearlyEqual(ClosingCurtainRig->CurtainProgress, 1.0f));
        }

        int32 FixedWingPairsInPIE = 0;
        int32 ManagedComponentsInPIE = 0;
        for (TActorIterator<AInfinityStagePassageActor> It(PieWorld); It; ++It)
        {
            FixedWingPairsInPIE += It->MaterializedWingPairCount;
            ManagedComponentsInPIE += It->ManagedComponents.Num();
        }
        TestEqual(TEXT("BeginPlay did not spawn fixed Wing Pairs"), FixedWingPairsInPIE, 261);
        TestEqual(
            TEXT("BeginPlay preserved the exact editor-authored render component count"),
            ManagedComponentsInPIE,
            GInfinityStageFixtureComponentsBeforePIE);
    }, 1.0f));
    AddCommand(new FEndPlayMapCommand());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowCatPIETest,
    "PussStage.InfinityStage.Functional.ShadowCatPIE",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowCatPIETest::RunTest(const FString& Parameters)
{
    AddCommand(new FEditorLoadMap(TEXT("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice")));
    AddCommand(new FStartPIECommand(false));
    AddCommand(new FDelayedFunctionLatentCommand([this]()
    {
        UWorld* PieWorld = nullptr;
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            if (Context.WorldType == EWorldType::PIE)
            {
                PieWorld = Context.World();
                break;
            }
        }
        TestNotNull(TEXT("Shadow-cat PIE world starts"), PieWorld);
        if (!PieWorld)
        {
            return;
        }

        TArray<AInfinityStageCameraRig*> CameraRigs;
        for (TActorIterator<AInfinityStageCameraRig> It(PieWorld); It; ++It)
        {
            CameraRigs.Add(*It);
        }
        TestEqual(TEXT("PIE has six camera rigs"), CameraRigs.Num(), 6);

        TArray<AInfinityStageShadowCatActor*> Cats;
        for (TActorIterator<AInfinityStageShadowCatActor> It(PieWorld); It; ++It)
        {
            Cats.Add(*It);
        }
        TestEqual(TEXT("PIE has exactly six native shadow cats"), Cats.Num(), 6);

        const FString ExpectedMeshPath = TEXT(
            "/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R.SK_Cat_R");
        const FString ExpectedIdlePath = TEXT(
            "/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_Base.A_Cat_Idle_Base");
        const FString ExpectedWalkPath = TEXT(
            "/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Move/A_Cat_Move_Walk_F.A_Cat_Move_Walk_F");

        for (AInfinityStageShadowCatActor* Cat : Cats)
        {
            TestNotNull(TEXT("Native shadow cat has one mesh component"), Cat ? Cat->Mesh.Get() : nullptr);
            if (!Cat || !Cat->Mesh)
            {
                continue;
            }

            USkeletalMeshComponent* CatMesh = Cat->Mesh;
            TestEqual(TEXT("Shadow cat uses the consolidated realistic mesh"),
                CatMesh->GetSkeletalMeshAsset() ? CatMesh->GetSkeletalMeshAsset()->GetPathName() : FString(),
                ExpectedMeshPath);
            TestEqual(TEXT("Shadow cat bypasses the vendor AnimBP"),
                CatMesh->GetAnimationMode(),
                EAnimationMode::AnimationSingleNode);
            TestNull(TEXT("Shadow cat has no vendor animation class"), CatMesh->GetAnimClass());

            UAnimSingleNodeInstance* SingleNode = CatMesh->GetSingleNodeInstance();
            UAnimationAsset* Animation = SingleNode ? SingleNode->GetAnimationAsset() : nullptr;
            TestNotNull(TEXT("Shadow cat has a direct idle/walk animation"), Animation);
            if (Animation)
            {
                const FString AnimationPath = Animation->GetPathName();
                TestTrue(TEXT("Shadow cat animation is the direct idle or walk clip"),
                    AnimationPath == ExpectedIdlePath || AnimationPath == ExpectedWalkPath);
            }
            TestTrue(TEXT("Shadow cat direct animation is looping"), SingleNode && SingleNode->IsLooping());
            TestTrue(TEXT("Shadow cat direct animation is playing"), SingleNode && SingleNode->IsPlaying());
        }

        AInfinityStageShowRoot* ShowRoot = nullptr;
        TActorIterator<AInfinityStageShowRoot> ShowRootIt(PieWorld);
        if (ShowRootIt)
        {
            ShowRoot = *ShowRootIt;
        }

        AInfinityStageCameraRig* PassageOneCamera = nullptr;
        FFrameNumber PassageOneStartFrame(0);
        if (ShowRoot && ShowRoot->Transport && !ShowRoot->Transport->Segments.IsEmpty())
        {
            FGuid FirstPassageGuid;
            for (const FInfinityTransportSegment& Segment : ShowRoot->Transport->Segments)
            {
                if (Segment.Type == EInfinityCueType::WingPair)
                {
                    FirstPassageGuid = Segment.SegmentGuid;
                    PassageOneStartFrame = Segment.StartFrame;
                    break;
                }
            }
            for (AInfinityStageCameraRig* CameraRig : CameraRigs)
            {
                if (CameraRig && CameraRig->PassageActor
                    && CameraRig->PassageActor->PassageGuid == FirstPassageGuid)
                {
                    PassageOneCamera = CameraRig;
                    break;
                }
            }
        }
        TestNotNull(TEXT("Passage 1 camera resolves for walking-cat test"), PassageOneCamera);
        if (PassageOneCamera)
        {
            TestTrue(TEXT("Passage 1 evaluates at a moving show frame"),
                PassageOneCamera->EvaluateAtMasterFrame(
                    FFrameNumber(PassageOneStartFrame.Value + 24000)));
            AInfinityStageShadowCatActor* MovingCat = PassageOneCamera->ShadowCat
                ? Cast<AInfinityStageShadowCatActor>(PassageOneCamera->ShadowCat->GetChildActor())
                : nullptr;
            TestNotNull(TEXT("Passage 1 owns a native moving cat"), MovingCat);
            UAnimSingleNodeInstance* MovingNode = MovingCat && MovingCat->Mesh
                ? MovingCat->Mesh->GetSingleNodeInstance()
                : nullptr;
            TestEqual(TEXT("Moving camera selects the direct walk clip"),
                MovingNode && MovingNode->GetAnimationAsset()
                    ? MovingNode->GetAnimationAsset()->GetPathName()
                    : FString(),
                ExpectedWalkPath);
            TestTrue(TEXT("Moving cat has a positive direct-animation play rate"),
                MovingCat && MovingCat->Mesh && MovingCat->Mesh->GetPlayRate() > 0.0f);
        }

        int32 VendorCharacterActors = 0;
        for (TActorIterator<AActor> It(PieWorld); It; ++It)
        {
            const FString ClassPath = It->GetClass()->GetPathName();
            if (ClassPath.Contains(TEXT("CharBP_Cat_R"))
                || ClassPath.Contains(TEXT("CharBP_Base")))
            {
                ++VendorCharacterActors;
            }
        }
        TestEqual(TEXT("PIE has no vendor cat/control character actors"), VendorCharacterActors, 0);

    }, 1.0f));
    AddCommand(new FEndPlayMapCommand());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueDeskConstructionTest,
    "InfinityStage.Editor.CueDeskConstructs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueDeskConstructionTest::RunTest(const FString& Parameters)
{
    const TSharedRef<SInfinityStageCueDesk> CueDesk = SNew(SInfinityStageCueDesk);
    TestTrue(TEXT("Cue Desk constructs with a root child"), CueDesk->GetChildren()->Num() > 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMasterSequenceOpensTest,
    "InfinityStage.Editor.MasterSequenceOpens",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMasterSequenceOpensTest::RunTest(const FString& Parameters)
{
    ULevelSequence* Master = LoadObject<ULevelSequence>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"));
    TestNotNull(TEXT("Development Master Sequence exists"), Master);
    UAssetEditorSubsystem* AssetEditors = GEditor
        ? GEditor->GetEditorSubsystem<UAssetEditorSubsystem>()
        : nullptr;
    TestNotNull(TEXT("Asset Editor Subsystem exists"), AssetEditors);
    if (!Master || !AssetEditors)
    {
        return false;
    }

    TestTrue(TEXT("Master Sequence opens with registered Infinity Stage track editors"), AssetEditors->OpenEditorForAsset(Master));
    AssetEditors->CloseAllEditorsForAsset(Master);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageScenePlaybackCutWarnsTest,
    "InfinityStage.Editor.ScenePlaybackCutWarns",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// A Scene whose nested shot runs past its playback range compiles with a warning naming the cut, and a shot section
// trimmed inside the range does not warn (a trim is authoring). 29 Sep: Scene 1 played 15 s of a 210.8 s shot, silently.
bool FInfinityStageScenePlaybackCutWarnsTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    FInfinityShowCue& SceneCue = Show->Cues.AddDefaulted_GetRef();
    SceneCue.Type = EInfinityCueType::Scene;
    SceneCue.CueGuid = FGuid::NewGuid();
    SceneCue.Label = FText::FromString(TEXT("Playback Cut Test Scene"));
    SceneCue.Scene.bUseSequenceLength = true;
    const FGuid SceneGuid = SceneCue.CueGuid;
    const int32 FifteenSeconds = Show->TickResolution.AsFrameNumber(15.0).Value;

    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    UMovieScene* SceneMovie = SceneSequence->GetMovieScene();
    SceneMovie->SetTickResolutionDirectly(Show->TickResolution);
    SceneMovie->SetPlaybackRange(0, FifteenSeconds);
    ULevelSequence* Shot = NewObject<ULevelSequence>(GetTransientPackage());
    Shot->Initialize();
    Shot->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    Shot->GetMovieScene()->SetPlaybackRange(0, FifteenSeconds * 4);
    UMovieSceneSubTrack* ShotTrack = SceneMovie->AddTrack<UMovieSceneSubTrack>();
    UMovieSceneSubSection* ShotSection = ShotTrack ? ShotTrack->AddSequence(Shot, FFrameNumber(0), FifteenSeconds * 4) : nullptr;
    TestNotNull(TEXT("Fixture places a 60 s shot in a 15 s Scene"), ShotSection);
    if (!ShotSection)
    {
        return false;
    }
    SceneCue.Scene.Sequence = SceneSequence;

    const auto WarnsAboutCut = [SceneGuid](const FInfinityCompileResult& Compiled)
    {
        return Compiled.Issues.ContainsByPredicate([SceneGuid](const FInfinityCompileIssue& Issue)
        {
            return Issue.Severity == EInfinityCompileIssueSeverity::Warning
                && Issue.SubjectGuid == SceneGuid
                && Issue.Message.Contains(TEXT("is cut"));
        });
    };
    const FInfinityCompileResult Cut = FInfinityStageCompiler::Compile(*Show);
    TestTrue(TEXT("A shot running past the Scene's playback range compiles with a warning naming the cut"), WarnsAboutCut(Cut));
    TestFalse(TEXT("The cut is a warning, not an error, so a Master rebuild is not blocked"),
        Cut.Issues.ContainsByPredicate([SceneGuid](const FInfinityCompileIssue& Issue)
        {
            return Issue.Severity == EInfinityCompileIssueSeverity::Error && Issue.SubjectGuid == SceneGuid;
        }));
    if (Cut.Segments.Num() == 1)
    {
        TestEqual(TEXT("The Scene's compiled length still follows its playback range"),
            (Cut.Segments[0].EndFrame - Cut.Segments[0].StartFrame).Value, FifteenSeconds);
    }

    ShotSection->SetRange(TRange<FFrameNumber>(FFrameNumber(0), FFrameNumber(FifteenSeconds)));
    const FInfinityCompileResult Trimmed = FInfinityStageCompiler::Compile(*Show);
    TestFalse(TEXT("A shot section trimmed inside the playback range is authoring, not a cut"), WarnsAboutCut(Trimmed));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSavedMasterMatchesShowTest,
    "InfinityStage.Editor.SavedMasterMatchesShow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The saved Master must lay every Sequence cue where the Show puts it, at its sub-sequence's own length. On 29 Sep a
// Scene shortened without rebuilding the Master left every later segment 425 s off: PIE could not get past Scene 3,
// and SavedFixturePIE's Closing scrub found no curtain. Read-only: nothing is rebuilt or saved.
bool FInfinityStageSavedMasterMatchesShowTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = LoadObject<UInfinityStageShowAsset>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show.DA_InfinityStage_V1Show"));
    ULevelSequence* Master = LoadObject<ULevelSequence>(
        nullptr,
        TEXT("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"));
    TestNotNull(TEXT("Saved Show resolves"), Show);
    TestNotNull(TEXT("Saved Master resolves"), Master);
    if (!Show || !Master || !Master->GetMovieScene())
    {
        return false;
    }

    const UMovieScene* MasterScene = Master->GetMovieScene();
    const FFrameRate MasterTicks = MasterScene->GetTickResolution();
    struct FLaidSection
    {
        FString Sequence;
        double StartSeconds = 0.0;
        double EndSeconds = 0.0;
    };
    TArray<FLaidSection> Laid;
    for (const UMovieSceneTrack* Track : MasterScene->GetTracks())
    {
        if (!Track)
        {
            continue;
        }
        for (const UMovieSceneSection* Section : Track->GetAllSections())
        {
            const UMovieSceneSubSection* Sub = Cast<UMovieSceneSubSection>(Section);
            const UMovieSceneSequence* SubSequence = Sub ? Sub->GetSequence() : nullptr;
            const UMovieScene* SubScene = SubSequence ? SubSequence->GetMovieScene() : nullptr;
            if (!SubScene || !Sub->HasStartFrame() || !Sub->HasEndFrame())
            {
                continue;
            }
            const TRange<FFrameNumber> Playback = SubScene->GetPlaybackRange();
            const double AuthoredSeconds = SubScene->GetTickResolution().AsSeconds(
                FFrameTime(Playback.GetUpperBoundValue() - Playback.GetLowerBoundValue()));
            FLaidSection Row;
            Row.Sequence = SubSequence->GetName();
            Row.StartSeconds = MasterTicks.AsSeconds(FFrameTime(Sub->GetInclusiveStartFrame()));
            Row.EndSeconds = MasterTicks.AsSeconds(FFrameTime(Sub->GetExclusiveEndFrame()));
            TestTrue(FString::Printf(TEXT("The Master lays %s at its own length (%.3f s laid, %.3f s authored)"),
                *Row.Sequence, Row.EndSeconds - Row.StartSeconds, AuthoredSeconds),
                FMath::IsNearlyEqual(Row.EndSeconds - Row.StartSeconds, AuthoredSeconds, 0.05));
            Laid.Add(Row);
        }
    }
    Laid.Sort([](const FLaidSection& A, const FLaidSection& B) { return A.StartSeconds < B.StartSeconds; });

    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>();
    TestTrue(TEXT("The saved Show compiles to transport segments"), Transport->BuildSegments(Show));
    TArray<const FInfinityTransportSegment*> SequenceSegments;
    for (const FInfinityTransportSegment& Segment : Transport->Segments)
    {
        if (Segment.Type != EInfinityCueType::WingPair)
        {
            SequenceSegments.Add(&Segment);
        }
    }
    TestEqual(TEXT("The Master lays one section per Scene and Sequence cue"), Laid.Num(), SequenceSegments.Num());
    for (int32 Index = 0; Index < FMath::Min(Laid.Num(), SequenceSegments.Num()); ++Index)
    {
        const FInfinityTransportSegment& Segment = *SequenceSegments[Index];
        const double ShowStart = Show->TickResolution.AsSeconds(FFrameTime(Segment.StartFrame));
        const double ShowEnd = Show->TickResolution.AsSeconds(FFrameTime(Segment.EndFrame));
        TestTrue(FString::Printf(
            TEXT("%s: the Master lays %s at %.3f-%.3f s and the Show at %.3f-%.3f s (rebuild the Master after changing a Scene's length)"),
            *Segment.Label.ToString(), *Laid[Index].Sequence, Laid[Index].StartSeconds, Laid[Index].EndSeconds,
            ShowStart, ShowEnd),
            FMath::IsNearlyEqual(Laid[Index].StartSeconds, ShowStart, 0.05)
            && FMath::IsNearlyEqual(Laid[Index].EndSeconds, ShowEnd, 0.05));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageWingAuditConstructsTest,
    "InfinityStage.Editor.WingAuditConstructs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageWingAuditConstructsTest::RunTest(const FString& Parameters)
{
    TSharedRef<SInfinityStageWingAudit> AuditPanel = SNew(SInfinityStageWingAudit);
    TestTrue(TEXT("Wing Asset Audit constructs with a root child"), AuditPanel->GetChildren()->Num() > 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageManagedMasterIdempotenceTest,
    "InfinityStage.Editor.ManagedMasterIdempotence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageManagedMasterIdempotenceTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 24000;
        Cue.WingPair.GapToNextCm = 500.0;
    }

    ULevelSequence* ChildScene = NewObject<ULevelSequence>(GetTransientPackage());
    ChildScene->Initialize();
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 48000;
    Scene.Scene.Sequence = ChildScene;

    FInfinityShowCue& FinalWing = Show->Cues.AddDefaulted_GetRef();
    FinalWing.Type = EInfinityCueType::WingPair;
    FinalWing.CueGuid = FGuid::NewGuid();
    FinalWing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.TailFrames = 24000;
        Settings.TailDistanceCm = 250.0;
    }

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    UMovieSceneAudioTrack* UserAudioTrack = Master->GetMovieScene()->AddTrack<UMovieSceneAudioTrack>();

    FString FirstReport;
    TestTrue(TEXT("First managed build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, FirstReport));
    UMovieSceneInfinityPassageTrack* PassageTrack = Master->GetMovieScene()->FindTrack<UMovieSceneInfinityPassageTrack>();
    UMovieSceneInfinitySceneTrack* SceneTrack = Master->GetMovieScene()->FindTrack<UMovieSceneInfinitySceneTrack>();
    TestNotNull(TEXT("Managed Passage track exists"), PassageTrack);
    TestNotNull(TEXT("Managed Scene track exists"), SceneTrack);
    TestNotNull(TEXT("Managed Music track exists"), Master->GetMovieScene()->FindTrack<UMovieSceneInfinityAudioTrack>());
    TestEqual(TEXT("Two Passage sections"), PassageTrack->GetAllSections().Num(), 2);
    TestEqual(TEXT("One Scene subsection"), SceneTrack->GetAllSections().Num(), 1);

    TMap<FGuid, UMovieSceneSection*> FirstSections;
    for (UMovieSceneSection* BaseSection : PassageTrack->GetAllSections())
    {
        UMovieSceneInfinityPassageSection* Section = CastChecked<UMovieSceneInfinityPassageSection>(BaseSection);
        FirstSections.Add(Section->BlockGuid, Section);
    }
    UMovieSceneInfinityPassageSection* AuthoredSection = CastChecked<UMovieSceneInfinityPassageSection>(
        PassageTrack->GetAllSections()[0]);
    AuthoredSection->HeightOffsetCm.AddCubicKey(AuthoredSection->GetInclusiveStartFrame(), 222.0);
    AuthoredSection->PinnedWingCueGuids.Add(Show->Cues[0].CueGuid);

    FString SecondReport;
    TestTrue(TEXT("Second managed build succeeds"), UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, SecondReport));
    TestTrue(TEXT("User audio track is preserved"), Master->GetMovieScene()->ContainsTrack(*UserAudioTrack));
    TestEqual(TEXT("Idempotent Passage section count"), PassageTrack->GetAllSections().Num(), 2);
    for (UMovieSceneSection* BaseSection : PassageTrack->GetAllSections())
    {
        UMovieSceneInfinityPassageSection* Section = CastChecked<UMovieSceneInfinityPassageSection>(BaseSection);
        TestEqual(TEXT("Managed section identity is stable"), FirstSections.FindRef(Section->BlockGuid), BaseSection);
    }
    double PreservedHeight = 0.0;
    AuthoredSection->HeightOffsetCm.Evaluate(FFrameTime(AuthoredSection->GetInclusiveStartFrame()), PreservedHeight);
    TestEqual(TEXT("Managed rebuild preserves artist camera keys"), PreservedHeight, 222.0);
    TestTrue(TEXT("Managed rebuild preserves valid pinned anchors"),
        AuthoredSection->PinnedWingCueGuids.Contains(Show->Cues[0].CueGuid));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageManagedRenderSelectionTest,
    "InfinityStage.Editor.ManagedRenderSelection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageManagedRenderSelectionTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
    WorldContext.SetCurrentWorld(World);

    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Wing = Show->Cues.AddDefaulted_GetRef();
        Wing.Type = EInfinityCueType::WingPair;
        Wing.CueGuid = FGuid::NewGuid();
        Wing.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Wing.WingPair.IntervalToNext = 24000;
        Wing.WingPair.GapToNextCm = 500.0;
    }
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    const FGuid SceneCueGuid = Scene.CueGuid;
    Scene.Scene.DurationFrames = 48000;
    ULevelSequence* ChildScene = NewObject<ULevelSequence>(GetTransientPackage());
    ChildScene->Initialize();
    ChildScene->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    ChildScene->GetMovieScene()->SetPlaybackRange(0, Scene.Scene.DurationFrames.Value);
    Scene.Scene.Sequence = ChildScene;
    FInfinityShowCue& FinalWing = Show->Cues.AddDefaulted_GetRef();
    FinalWing.Type = EInfinityCueType::WingPair;
    FinalWing.CueGuid = FGuid::NewGuid();
    FinalWing.WingPair.OccurrenceGuid = FGuid::NewGuid();

    Show->ReconcilePassageSettings();
    for (FInfinityPassageSettings& Settings : Show->PassageSettings)
    {
        Settings.LeadInFrames = 12000;
        Settings.LeadInDistanceCm = 125.0;
        Settings.TailFrames = 24000;
        Settings.TailDistanceCm = 250.0;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestFalse(TEXT("Render test Show compiles"), Compiled.HasErrors());
    TestEqual(TEXT("Render test has two Passages"), Compiled.Passages.Num(), 2);

    for (const FInfinityCompiledPassage& Passage : Compiled.Passages)
    {
        AInfinityStagePassageActor* PassageActor = World->SpawnActor<AInfinityStagePassageActor>();
        PassageActor->ShowAsset = Show;
        PassageActor->PassageGuid = Passage.PassageGuid;
        AInfinityStageCameraRig* CameraRig = World->SpawnActor<AInfinityStageCameraRig>();
        CameraRig->PassageActor = PassageActor;
    }

    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    FString MasterReport;
    TestTrue(TEXT("Render test Master builds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, MasterReport));

    ULevelSequence* Wrapper = NewObject<ULevelSequence>(GetTransientPackage());
    Wrapper->Initialize();
    FFrameNumber Start;
    FFrameNumber End;
    FString Report;
    TestTrue(TEXT("Whole Passage render wrapper builds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
            Show,
            Master,
            Wrapper,
            World,
            {},
            Compiled.Passages[0].PassageGuid,
            Start,
            End,
            Report));
    TestEqual(TEXT("Passage selection includes lead-in"), Start, Compiled.Passages[0].SegmentStartFrame);
    TestEqual(TEXT("Passage selection includes tail"), End, Compiled.Passages[0].SegmentEndFrame);
    TestEqual(TEXT("Wrapper playback starts at absolute Master frame"),
        Wrapper->GetMovieScene()->GetPlaybackRange().GetLowerBoundValue(), Start);
    TestEqual(TEXT("Wrapper playback ends at exact half-open frame"),
        Wrapper->GetMovieScene()->GetPlaybackRange().GetUpperBoundValue(), End);
    UMovieSceneSubTrack* MasterSource = Wrapper->GetMovieScene()->FindTrack<UMovieSceneSubTrack>();
    TestNotNull(TEXT("Wrapper has one ordinary Master subsequence track"), MasterSource);
    TestEqual(TEXT("Wrapper has one Master subsection"),
        MasterSource ? MasterSource->GetAllSections().Num() : 0,
        1);
    UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(
        Wrapper->GetMovieScene()->GetCameraCutTrack());
    TestNotNull(TEXT("Wrapper has a standard Camera Cut Track"), CutTrack);
    TestEqual(TEXT("Whole Passage exposes one camera cut"), CutTrack ? CutTrack->GetAllSections().Num() : 0, 1);
    TestEqual(TEXT("Whole Passage exposes one possessable camera rig"),
        Wrapper->GetMovieScene()->GetPossessableCount(),
        1);

    FString RepeatReport;
    TestTrue(TEXT("Render wrapper rebuild is idempotent"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
            Show,
            Master,
            Wrapper,
            World,
            {},
            Compiled.Passages[0].PassageGuid,
            Start,
            End,
            RepeatReport));
    CutTrack = Cast<UMovieSceneCameraCutTrack>(Wrapper->GetMovieScene()->GetCameraCutTrack());
    TestEqual(TEXT("Idempotent rebuild does not duplicate camera cuts"), CutTrack->GetAllSections().Num(), 1);
    TestEqual(TEXT("Idempotent rebuild does not accumulate camera bindings"),
        Wrapper->GetMovieScene()->GetPossessableCount(),
        1);

    FString SceneReport;
    TestTrue(TEXT("Scene-only render wrapper builds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
            Show,
            Master,
            Wrapper,
            World,
            { SceneCueGuid },
            FGuid(),
            Start,
            End,
            SceneReport));
    const FInfinityCompiledSegment* SceneSegment = Compiled.Segments.FindByPredicate(
        [SceneCueGuid](const FInfinityCompiledSegment& Segment)
        {
            return Segment.SegmentGuid == SceneCueGuid;
        });
    TestNotNull(TEXT("Compiled Scene segment resolves"), SceneSegment);
    if (SceneSegment)
    {
        TestEqual(TEXT("Scene-only render starts exactly at Scene entry"), Start, SceneSegment->StartFrame);
        TestEqual(TEXT("Scene-only render ends exactly at Scene exit"), End, SceneSegment->EndFrame);
    }
    CutTrack = Cast<UMovieSceneCameraCutTrack>(Wrapper->GetMovieScene()->GetCameraCutTrack());
    TestEqual(TEXT("Scene interval leaves root Camera Cuts empty for nested Scene authority"),
        CutTrack ? CutTrack->GetAllSections().Num() : 0,
        0);
    TestEqual(TEXT("Scene-only wrapper has no stale Passage binding"),
        Wrapper->GetMovieScene()->GetPossessableCount(),
        0);

    FString SpanReport;
    TestTrue(TEXT("Cross-segment selected Cue span builds"),
        UInfinityStageSequenceBuilderLibrary::RebuildManagedRenderWrapper(
            Show,
            Master,
            Wrapper,
            World,
            { Show->Cues[0].CueGuid, FinalWing.CueGuid },
            FGuid(),
            Start,
            End,
            SpanReport));
    CutTrack = Cast<UMovieSceneCameraCutTrack>(Wrapper->GetMovieScene()->GetCameraCutTrack());
    TestEqual(TEXT("Cross-segment wrapper exposes both Passage cameras"),
        CutTrack ? CutTrack->GetAllSections().Num() : 0,
        2);

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageWingSequenceInterchangeTest,
    "InfinityStage.Editor.WingSequenceInterchange",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageWingSequenceInterchangeTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Source = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Source->DisplayRate = FFrameRate(25, 1);
    Source->TickResolution = FFrameRate(24000, 1);
    Source->EnsureStableIds();
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Source->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.Label = FText::FromString(FString::Printf(TEXT("Saved Wing %d"), Index + 1));
        Cue.Tags = { FName(TEXT("interchange-test")) };
        Cue.WingPair.Left.Mesh = TSoftObjectPtr<UStaticMesh>(
            FSoftObjectPath(TEXT("/Game/InfinityStage/Test/SM_Left.SM_Left")));
        Cue.WingPair.Right.Mesh = TSoftObjectPtr<UStaticMesh>(
            FSoftObjectPath(TEXT("/Game/InfinityStage/Test/SM_Right.SM_Right")));
        Cue.WingPair.Left.bFlipImageHorizontally = Index == 0;
        Cue.WingPair.Left.LocalTransform = FTransform(
            FRotator(0.0, 37.0, 0.0), FVector(12.0, -640.0, 25.0), FVector(1.25));
        Cue.WingPair.IntervalToNext = 48000;
        Cue.WingPair.GapToNextCm = 725.0;
        Cue.WingPair.Mechanism.PlaybackMode = EInfinityMotionPlaybackMode::CameraGust;
        Cue.WingPair.Mechanism.ExplicitOriginFrame = 12000;
        Cue.WingPair.Mechanism.InwardTravelCm = 180.0;
        Cue.WingPair.Mechanism.CameraGust.GroupAnchorCueGuid = Source->Cues[0].CueGuid;
        Cue.WingPair.Mechanism.CameraGust.GroupOrdinal = Index;
        Cue.WingPair.Mechanism.CameraGust.GroupSize = 2;
        Cue.WingPair.Mechanism.LeftNormalizedCurve.GetRichCurve()->AddKey(0.0f, 1.0f);
        Cue.WingPair.Mechanism.LeftNormalizedCurve.GetRichCurve()->AddKey(1.0f, 0.0f);
    }
    Source->ReconcilePassageSettings();
    TestEqual(TEXT("Source has one Passage"), Source->PassageSettings.Num(), 1);
    FInfinityPassageSettings& SourcePassage = Source->PassageSettings[0];
    SourcePassage.Label = FText::FromString(TEXT("Saved Passage"));
    SourcePassage.LeadInFrames = 12000;
    SourcePassage.TailFrames = 24000;
    SourcePassage.LeadInDistanceCm = 333.0;
    SourcePassage.TailDistanceCm = 444.0;
    SourcePassage.PreferredCameraSpeedCmPerSecond = 321.0;
    SourcePassage.PreferredSpacingCm = 725.0;
    SourcePassage.bUseLiveMechanismPhasePattern = true;
    SourcePassage.MechanismPhaseStepCycles = -0.125;
    SourcePassage.MechanismPhaseOffsetCycles = 0.25;

    FString Json;
    FString Report;
    TestTrue(TEXT("Full Passage exports to JSON"),
        FInfinityStageWingSequenceInterchange::ExportToJson(
            *Source, { 0, 1 }, TEXT("Saved Passage"), &SourcePassage, Json, Report));
    TestTrue(TEXT("JSON carries explicit format marker"), Json.Contains(TEXT("InfinityStageWingSequence")));
    TestTrue(TEXT("JSON carries explicit image handedness"), Json.Contains(TEXT("flipImageHorizontally"))
        || Json.Contains(TEXT("bFlipImageHorizontally")));

    FInfinityWingSequenceDocument Document;
    TestTrue(TEXT("Exported JSON imports"),
        FInfinityStageWingSequenceInterchange::ImportFromJson(Json, Document, Report));
    TestEqual(TEXT("Two Wing Pair rows round-trip"), Document.Cues.Num(), 2);
    TestTrue(TEXT("Complete Passage envelope round-trips"), Document.PassageEnvelope.IsSet());

    const FString RoundTripFile = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("Automation/Tmp/InfinityStageWingSequenceRoundTrip.infinitywings.json"));
    TestTrue(TEXT("External JSON file writes"),
        FInfinityStageWingSequenceInterchange::SaveToFile(RoundTripFile, Json, Report));
    FInfinityWingSequenceDocument FileDocument;
    TestTrue(TEXT("External JSON file reads"),
        FInfinityStageWingSequenceInterchange::LoadFromFile(RoundTripFile, FileDocument, Report));
    TestEqual(TEXT("File round-trip preserves row count"), FileDocument.Cues.Num(), 2);
    IFileManager::Get().Delete(*RoundTripFile, false, true, true);

    TArray<FInfinityShowCue> Prepared;
    TestTrue(TEXT("Imported rows prepare for a 48 kHz tick rate"),
        FInfinityStageWingSequenceInterchange::PrepareImportedCues(
            Document, FFrameRate(48000, 1), Prepared, Report));
    TestEqual(TEXT("Interval transforms exactly between tick rates"),
        Prepared[0].WingPair.IntervalToNext.Value, 96000);
    TestEqual(TEXT("Explicit origin transforms exactly between tick rates"),
        Prepared[0].WingPair.Mechanism.ExplicitOriginFrame.Value, 24000);
    TestNotEqual(TEXT("Cue identity is reminted"), Prepared[0].CueGuid, Source->Cues[0].CueGuid);
    TestNotEqual(TEXT("Occurrence identity is reminted"),
        Prepared[0].WingPair.OccurrenceGuid, Source->Cues[0].WingPair.OccurrenceGuid);
    TestEqual(TEXT("Internal gust anchor remaps to imported first cue"),
        Prepared[1].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid, Prepared[0].CueGuid);
    TestTrue(TEXT("Image handedness survives"), Prepared[0].WingPair.Left.bFlipImageHorizontally);
    TestEqual(TEXT("Mesh soft path survives"),
        Prepared[0].WingPair.Left.Mesh.ToSoftObjectPath().ToString(),
        Source->Cues[0].WingPair.Left.Mesh.ToSoftObjectPath().ToString());
    TestEqual(TEXT("Local transform survives"),
        Prepared[0].WingPair.Left.LocalTransform.GetLocation(), FVector(12.0, -640.0, 25.0));
    TestEqual(TEXT("Spacing survives"), Prepared[0].WingPair.GapToNextCm, 725.0);
    TestEqual(TEXT("Mechanism travel survives"), Prepared[0].WingPair.Mechanism.InwardTravelCm, 180.0);
    TestEqual(TEXT("Authored curve survives"),
        Prepared[0].WingPair.Mechanism.LeftNormalizedCurve.GetRichCurveConst()->GetNumKeys(), 2);

    UInfinityStageShowAsset* Target = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    Target->TickResolution = FFrameRate(48000, 1);
    FInfinityShowCue& BeforeScene = Target->Cues.AddDefaulted_GetRef();
    BeforeScene.Type = EInfinityCueType::Scene;
    BeforeScene.CueGuid = FGuid::NewGuid();
    FInfinityShowCue& OldWing = Target->Cues.AddDefaulted_GetRef();
    OldWing.Type = EInfinityCueType::WingPair;
    OldWing.CueGuid = FGuid::NewGuid();
    OldWing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    FInfinityShowCue& AfterScene = Target->Cues.AddDefaulted_GetRef();
    AfterScene.Type = EInfinityCueType::Scene;
    AfterScene.CueGuid = FGuid::NewGuid();
    Target->ReconcilePassageSettings();
    const FGuid TargetPassageGuid = Target->PassageSettings[0].PassageGuid;
    const FGuid TargetMusicGuid = FGuid::NewGuid();
    Target->PassageSettings[0].Music.PrimaryRailGuid = TargetMusicGuid;
    Target->PassageSettings[0].CelestialCycle.CycleRateMultiplier = 7.0;
    TArray<int32> Inserted;
    TestTrue(TEXT("Current Passage can be replaced from document"),
        FInfinityStageWingSequenceInterchange::ReplacePassage(
            *Target, TargetPassageGuid, Document, Inserted, Report));
    TestEqual(TEXT("Replacement inserts two rows"), Inserted.Num(), 2);
    const FInfinityPassageSettings* Replaced = Target->PassageSettings.FindByPredicate(
        [TargetPassageGuid](const FInfinityPassageSettings& Passage)
        {
            return Passage.PassageGuid == TargetPassageGuid;
        });
    TestNotNull(TEXT("Target Passage stable identity survives"), Replaced);
    if (Replaced)
    {
        TestEqual(TEXT("Target music ownership survives"), Replaced->Music.PrimaryRailGuid, TargetMusicGuid);
        TestEqual(TEXT("Target temporality survives"), Replaced->CelestialCycle.CycleRateMultiplier, 7.0);
        TestEqual(TEXT("Envelope lead frames convert to target tick rate"), Replaced->LeadInFrames.Value, 24000);
        TestEqual(TEXT("Envelope camera speed applies"), Replaced->PreferredCameraSpeedCmPerSecond, 321.0);
        TestTrue(TEXT("Envelope live movement controller applies"), Replaced->bUseLiveMechanismPhasePattern);
        TestEqual(TEXT("Envelope live phase step applies"), Replaced->MechanismPhaseStepCycles, -0.125);
        TestEqual(TEXT("Envelope live phase offset applies"), Replaced->MechanismPhaseOffsetCycles, 0.25);
    }

    UInfinityStageShowAsset* ArrangementTarget = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    ArrangementTarget->TickResolution = FFrameRate(48000, 1);
    TArray<FGuid> StableTargetCueGuids;
    TArray<FString> StableTargetLabels;
    for (int32 Index = 0; Index < 5; ++Index)
    {
        FInfinityShowCue& Cue = ArrangementTarget->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.Label = FText::FromString(FString::Printf(TEXT("Target Wing %d"), Index + 1));
        Cue.WingPair.IntervalToNext = FFrameNumber(12000 + Index);
        Cue.WingPair.GapToNextCm = 500.0 + Index;
        StableTargetCueGuids.Add(Cue.CueGuid);
        StableTargetLabels.Add(Cue.Label.ToString());
    }
    ArrangementTarget->ReconcilePassageSettings();
    FInfinityPassageSettings& ArrangementPassage = ArrangementTarget->PassageSettings[0];
    ArrangementPassage.Label = FText::FromString(TEXT("Named Target Passage"));
    const FGuid ArrangementPassageGuid = ArrangementPassage.PassageGuid;
    const FGuid ArrangementMusicGuid = FGuid::NewGuid();
    ArrangementPassage.Music.PrimaryRailGuid = ArrangementMusicGuid;

    TArray<int32> Affected;
    TestTrue(TEXT("Saved designs apply across an existing music-fitted Passage"),
        FInfinityStageWingSequenceInterchange::ApplyArrangementToPassage(
            *ArrangementTarget, ArrangementPassageGuid, Document, Affected, Report));
    TestEqual(TEXT("Arrangement application preserves target count"), Affected.Num(), 5);
    for (int32 Index = 0; Index < 5; ++Index)
    {
        const FInfinityShowCue& Cue = ArrangementTarget->Cues[Index];
        TestEqual(FString::Printf(TEXT("Target Cue identity %d survives"), Index),
            Cue.CueGuid, StableTargetCueGuids[Index]);
        TestEqual(FString::Printf(TEXT("Target row label %d survives"), Index),
            Cue.Label.ToString(), StableTargetLabels[Index]);
        TestEqual(FString::Printf(TEXT("Target timing %d survives"), Index),
            Cue.WingPair.IntervalToNext.Value, 12000 + Index);
        TestEqual(FString::Printf(TEXT("Target spacing %d survives"), Index),
            Cue.WingPair.GapToNextCm, 500.0 + Index);
        TestEqual(FString::Printf(TEXT("Saved pattern repeats at row %d"), Index),
            Cue.WingPair.Left.bFlipImageHorizontally, Index % 2 == 0);
    }
    TestEqual(TEXT("Camera-led arrangement has one continuous Passage anchor"),
        ArrangementTarget->Cues[1].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid,
        ArrangementTarget->Cues[0].CueGuid);
    TestEqual(TEXT("Later camera-led rows retain the same Passage anchor"),
        ArrangementTarget->Cues[3].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid,
        ArrangementTarget->Cues[0].CueGuid);
    TestEqual(TEXT("Camera-led arrangement reports the complete target range"),
        ArrangementTarget->Cues[4].WingPair.Mechanism.CameraGust.GroupSize, 5);
    const FInfinityPassageSettings* ArrangementSettings = ArrangementTarget->PassageSettings.FindByPredicate(
        [ArrangementPassageGuid](const FInfinityPassageSettings& Passage)
        {
            return Passage.PassageGuid == ArrangementPassageGuid;
        });
    TestNotNull(TEXT("Arrangement application preserves Passage identity"), ArrangementSettings);
    if (ArrangementSettings)
    {
        TestEqual(TEXT("Arrangement application preserves Passage name"),
            ArrangementSettings->Label.ToString(), FString(TEXT("Named Target Passage")));
        TestEqual(TEXT("Arrangement application preserves Passage music"),
            ArrangementSettings->Music.PrimaryRailGuid, ArrangementMusicGuid);
    }

    TestTrue(TEXT("Music fit can grow a Passage using its whole ordered arrangement"),
        FInfinityStageWingSequenceInterchange::ResizePassageToCountPreservingPattern(
            *ArrangementTarget,
            ArrangementPassageGuid,
            7,
            FFrameNumber(24000),
            650.0,
            Affected,
            Report));
    TestEqual(TEXT("Music fit grows to requested count"), Affected.Num(), 7);
    for (int32 Index = 0; Index < 5; ++Index)
    {
        TestEqual(FString::Printf(TEXT("Music fit keeps existing identity %d"), Index),
            ArrangementTarget->Cues[Index].CueGuid, StableTargetCueGuids[Index]);
        TestEqual(FString::Printf(TEXT("Music fit keeps existing label %d"), Index),
            ArrangementTarget->Cues[Index].Label.ToString(), StableTargetLabels[Index]);
    }
    for (int32 Index = 0; Index < 7; ++Index)
    {
        TestEqual(FString::Printf(TEXT("Music fit applies interval %d"), Index),
            ArrangementTarget->Cues[Index].WingPair.IntervalToNext.Value, 24000);
        TestEqual(FString::Printf(TEXT("Music fit applies spacing %d"), Index),
            ArrangementTarget->Cues[Index].WingPair.GapToNextCm, 650.0);
    }
    TestEqual(TEXT("Music-fit camera-led reveal remains one continuous Passage"),
        ArrangementTarget->Cues[6].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid,
        ArrangementTarget->Cues[0].CueGuid);
    TestEqual(TEXT("Music-fit camera-led reveal reports its resized range"),
        ArrangementTarget->Cues[6].WingPair.Mechanism.CameraGust.GroupSize, 7);
    ArrangementSettings = ArrangementTarget->PassageSettings.FindByPredicate(
        [ArrangementPassageGuid](const FInfinityPassageSettings& Passage)
        {
            return Passage.PassageGuid == ArrangementPassageGuid;
        });
    TestNotNull(TEXT("Music fit preserves Passage identity"), ArrangementSettings);
    if (ArrangementSettings)
    {
        TestEqual(TEXT("Music fit preserves Passage name"),
            ArrangementSettings->Label.ToString(), FString(TEXT("Named Target Passage")));
        TestEqual(TEXT("Music fit preserves Passage music"),
            ArrangementSettings->Music.PrimaryRailGuid, ArrangementMusicGuid);
    }

    FString UnsupportedJson = Json.Replace(TEXT("\"schema_version\": 1"), TEXT("\"schema_version\": 99"));
    FInfinityWingSequenceDocument Unsupported;
    TestFalse(TEXT("Unsupported future schema is rejected"),
        FInfinityStageWingSequenceInterchange::ImportFromJson(UnsupportedJson, Unsupported, Report));
    return true;
}

#endif
