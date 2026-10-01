#include "InfinityStageCompiler.h"
#include "InfinityStageMusicMapAsset.h"
#include "InfinityStageCelestialRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "InfinityStageWingEditProxy.h"
#include "InfinityStageWingLibraryAsset.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/SplineComponent.h"
#include "Engine/Engine.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** Builds the managed Master a Show needs before Wing modulation can resolve. */
UMovieSceneInfinityPassageSection* AttachManagedPassageSection(
    UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid)
{
    ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
    Master->Initialize();
    UMovieSceneInfinityPassageTrack* Track =
        Master->GetMovieScene()->AddTrack<UMovieSceneInfinityPassageTrack>();
    UMovieSceneInfinityPassageSection* Section =
        CastChecked<UMovieSceneInfinityPassageSection>(Track->CreateNewSection());
    Section->PassageGuid = PassageGuid;
    Section->BlockGuid = PassageGuid;
    Track->AddSection(*Section);
    Show.ManagedMasterSequence = Master;
    return Section;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStagePassageCameraChannelsTest,
    "InfinityStage.Camera.PinnedSpeedAndFramingChannels",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStagePassageCameraChannelsTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 100;
        Cue.WingPair.GapToNextCm = 100.0;
    }
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestEqual(TEXT("Fixture compiles one Passage"), Compiled.Passages.Num(), 1);
    if (Compiled.Passages.Num() != 1)
    {
        return false;
    }
    const FInfinityCompiledPassage& Passage = Compiled.Passages[0];
    UMovieSceneInfinityPassageSection* Section = NewObject<UMovieSceneInfinityPassageSection>();
    Section->PassageGuid = Passage.PassageGuid;
    Section->PinnedWingCueGuids.Add(Passage.Wings[1].CueGuid);

    FMovieSceneDoubleChannel* Speed = Section->GetCameraChannel(EInfinityPassageCameraChannel::SpeedMultiplier);
    Speed->Reset();
    Speed->AddLinearKey(0, 0.2);
    Speed->AddLinearKey(100, 2.0);
    Speed->AddLinearKey(200, 0.5);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::HeightOffsetCm)->SetDefault(180.0);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::PitchDegrees)->SetDefault(-7.5);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::LookAheadDistanceCm)->SetDefault(750.0);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::FocalLengthMm)->SetDefault(50.0);

    FInfinityPassageCameraEvaluation AtPin;
    TestTrue(TEXT("Pinned frame evaluates"), Section->EvaluateCamera(Passage, FFrameTime(100), AtPin));
    TestTrue(TEXT("Pinned Wing keeps exact baseline distance-frame"),
        FMath::IsNearlyEqual(AtPin.DistanceMasterFrame.AsDecimal(), 100.0, 0.001));
    TestEqual(TEXT("Height channel evaluates"), AtPin.LocalOffsetCm.Z, 180.0);
    TestEqual(TEXT("Pitch channel evaluates"), AtPin.LocalRotation.Pitch, -7.5);
    TestEqual(TEXT("Focal channel evaluates"), AtPin.FocalLengthMm, 50.0);
    TestEqual(TEXT("Look-ahead channel evaluates"), AtPin.LookAheadDistanceCm, 750.0);

    double PreviousWarpedFrame = -1.0;
    for (int32 Frame = 0; Frame <= 200; Frame += 10)
    {
        FInfinityPassageCameraEvaluation Sample;
        TestTrue(TEXT("Speed sample evaluates"), Section->EvaluateCamera(Passage, FFrameTime(Frame), Sample));
        TestTrue(TEXT("Integrated non-negative speed never reverses"),
            Sample.DistanceMasterFrame.AsDecimal() + 0.001 >= PreviousWarpedFrame);
        PreviousWarpedFrame = Sample.DistanceMasterFrame.AsDecimal();
    }
    FInfinityPassageCameraEvaluation AtEnd;
    Section->EvaluateCamera(Passage, FFrameTime(200), AtEnd);
    TestTrue(TEXT("Passage endpoint remains exact"),
        FMath::IsNearlyEqual(AtEnd.DistanceMasterFrame.AsDecimal(), 200.0, 0.001));

    Speed->Reset();
    Speed->SetDefault(0.0);
    FInfinityPassageCameraEvaluation ZeroRate;
    Section->EvaluateCamera(Passage, FFrameTime(50), ZeroRate);
    TestTrue(TEXT("All-zero constraint span reports fallback"), ZeroRate.bUsedInvalidSpeedFallback);
    TestTrue(TEXT("Invalid span still evaluates deterministically"),
        FMath::IsNearlyEqual(ZeroRate.DistanceMasterFrame.AsDecimal(), 50.0, 0.001));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageExactMusicFitTest,
    "InfinityStage.Compiler.ExactMusicFit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageExactMusicFitTest::RunTest(const FString& Parameters)
{
    FInfinityPassageFitInput Input;
    Input.DurationSeconds = 240.0;
    Input.CameraSpeedCmPerSecond = 250.0;
    Input.SpacingCm = 500.0;
    Input.EntryClearanceCm = 250.0;
    Input.ExitClearanceCm = 250.0;

    const FInfinityPassageFitResult Result = FInfinityStageCompiler::FitPassage(Input);
    TestTrue(TEXT("Fit is valid"), Result.bValid);
    TestEqual(TEXT("Derived pair count"), Result.WingPairCount, 120);
    TestEqual(TEXT("Travel distance"), Result.TravelDistanceCm, 60000.0);
    TestEqual(TEXT("Required distance"), Result.RequiredDistanceCm, 60000.0);
    TestEqual(TEXT("Residual"), Result.ResidualDistanceCm, 0.0);
    TestEqual(TEXT("Pass interval"), Result.PassIntervalSeconds, 2.0);
    TestEqual(TEXT("Inverse speed"), FInfinityStageCompiler::SolveCameraSpeedCmPerSecond(240.0, 120, 500.0, 250.0, 250.0), 250.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStagePassageCompileTest,
    "InfinityStage.Compiler.PassageScenePassage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStagePassageCompileTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 48000;
        Cue.WingPair.GapToNextCm = 500.0;
    }

    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 72000;

    FInfinityShowCue& FinalWing = Show->Cues.AddDefaulted_GetRef();
    FinalWing.Type = EInfinityCueType::WingPair;
    FinalWing.CueGuid = FGuid::NewGuid();
    FinalWing.WingPair.OccurrenceGuid = FGuid::NewGuid();

    FInfinityPassageSettings& FirstSettings = Show->PassageSettings.AddDefaulted_GetRef();
    FirstSettings.PassageGuid = FGuid::NewGuid();
    FirstSettings.FirstCueGuid = Show->Cues[0].CueGuid;
    FirstSettings.LastCueGuid = Show->Cues[1].CueGuid;
    FirstSettings.LeadInFrames = 12000;
    FirstSettings.TailFrames = 24000;
    FirstSettings.LeadInDistanceCm = 250.0;
    FirstSettings.TailDistanceCm = 250.0;

    const FInfinityCompileResult Result = FInfinityStageCompiler::Compile(*Show);
    TestFalse(TEXT("Compilation has no errors"), Result.HasErrors());
    TestEqual(TEXT("Two passages"), Result.Passages.Num(), 2);
    TestEqual(TEXT("Passage, Scene, Passage transport segments"), Result.Segments.Num(), 3);
    TestEqual(TEXT("First passage wing count"), Result.Passages[0].Wings.Num(), 2);
    TestEqual(TEXT("First pass includes lead-in"), Result.Passages[0].FirstPassFrame.Value, 12000);
    TestEqual(TEXT("Second pass is frame exact"), Result.Passages[0].LastPassFrame.Value, 60000);
    TestEqual(TEXT("First passage end includes tail"), Result.Passages[0].SegmentEndFrame.Value, 84000);
    TestEqual(TEXT("Scene advances show cursor"), Result.Passages[1].SegmentStartFrame.Value, 156000);
    TestEqual(TEXT("Total show duration"), Result.ShowEndFrame.Value, 156000);
    TestEqual(TEXT("Distance starts at segment origin"), FInfinityStageCompiler::EvaluateDistanceAtFrame(Result.Passages[0], 0), 0.0);
    TestEqual(TEXT("Distance reaches lead-in anchor"), FInfinityStageCompiler::EvaluateDistanceAtFrame(Result.Passages[0], 12000), 250.0);
    TestEqual(TEXT("Distance interpolates between wing anchors"), FInfinityStageCompiler::EvaluateDistanceAtFrame(Result.Passages[0], 36000), 500.0);
    TestEqual(TEXT("Distance reaches tail anchor"), FInfinityStageCompiler::EvaluateDistanceAtFrame(Result.Passages[0], 84000), 1000.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialCycleTest,
    "InfinityStage.Celestial.IntegratedPassageRateIsDeterministic",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialCycleTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    const int32 TickRate = Show->TickResolution.Numerator;

    FInfinityShowCue& FirstWing = Show->Cues.AddDefaulted_GetRef();
    FirstWing.Type = EInfinityCueType::WingPair;
    FirstWing.CueGuid = FGuid::NewGuid();
    FirstWing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 5 * TickRate;
    FInfinityShowCue& SecondWing = Show->Cues.AddDefaulted_GetRef();
    SecondWing.Type = EInfinityCueType::WingPair;
    SecondWing.CueGuid = FGuid::NewGuid();
    SecondWing.WingPair.OccurrenceGuid = FGuid::NewGuid();

    FInfinityPassageSettings& First = Show->PassageSettings.AddDefaulted_GetRef();
    First.PassageGuid = FGuid::NewGuid();
    First.FirstCueGuid = FirstWing.CueGuid;
    First.LastCueGuid = FirstWing.CueGuid;
    First.TailFrames = 20 * TickRate;
    FInfinityPassageSettings& Second = Show->PassageSettings.AddDefaulted_GetRef();
    Second.PassageGuid = FGuid::NewGuid();
    Second.FirstCueGuid = SecondWing.CueGuid;
    Second.LastCueGuid = SecondWing.CueGuid;
    Second.TailFrames = 10 * TickRate;
    Second.CelestialCycle.CycleRateMultiplier = 5.0;

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestFalse(TEXT("Celestial fixture compiles"), Compiled.HasErrors());
    TestEqual(TEXT("Two Celestial Passages compile"), Compiled.Passages.Num(), 2);
    if (Compiled.Passages.Num() != 2)
    {
        return false;
    }

    double Phase = 0.0;
    TestTrue(TEXT("First Passage midpoint phase resolves"),
        FInfinityStageCompiler::EvaluateCelestialPhase(
            *Show, First.PassageGuid, 10 * TickRate, 0.25, Phase));
    TestTrue(TEXT("Ten seconds advances half a default cycle"), FMath::IsNearlyEqual(Phase, 0.75));

    const FFrameNumber SecondStart = Compiled.Passages[1].SegmentStartFrame;
    TestTrue(TEXT("Direct seek to the second Passage resolves"),
        FInfinityStageCompiler::EvaluateCelestialPhase(
            *Show, Second.PassageGuid, SecondStart, 0.25, Phase));
    TestTrue(TEXT("Scene time holds the sky and the completed first cycle wraps"),
        FMath::IsNearlyEqual(Phase, 0.25));

    TestTrue(TEXT("Accelerated Passage phase resolves"),
        FInfinityStageCompiler::EvaluateCelestialPhase(
            *Show, Second.PassageGuid, SecondStart + 2 * TickRate, 0.25, Phase));
    TestTrue(TEXT("Two seconds at 5x advances half a day/night cycle"),
        FMath::IsNearlyEqual(Phase, 0.75));

    Second.CelestialCycle.bAnimate = false;
    TestTrue(TEXT("A held Passage still evaluates deterministically"),
        FInfinityStageCompiler::EvaluateCelestialPhase(
            *Show, Second.PassageGuid, SecondStart + 9 * TickRate, 0.25, Phase));
    TestTrue(TEXT("Disabled animation holds at Passage entry"), FMath::IsNearlyEqual(Phase, 0.25));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialLightingTest,
    "InfinityStage.Celestial.SunMoonStarsAndLightingFollowPhase",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialLightingTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>();
    ADirectionalLight* Moon = World->SpawnActor<ADirectionalLight>();
    ASkyLight* Sky = World->SpawnActor<ASkyLight>();
    AExponentialHeightFog* Fog = World->SpawnActor<AExponentialHeightFog>();
    AInfinityStageCelestialRig* Rig = World->SpawnActor<AInfinityStageCelestialRig>();
    Rig->SunLightActor = Sun;
    Rig->MoonLightActor = Moon;
    Rig->SkyLightActor = Sky;
    Rig->HeightFogActor = Fog;

    Rig->ApplyCyclePhase(0.5);
    TestTrue(TEXT("Noon has full daylight"), FMath::IsNearlyEqual(Rig->CurrentDaylightAmount, 1.0f));
    TestTrue(TEXT("Noon hides the stars"), !Rig->StarsDome->IsVisible());
    TestTrue(TEXT("Noon sun reaches its authored maximum"),
        FMath::IsNearlyEqual(Sun->GetLightComponent()->Intensity, Rig->MaximumSunIntensity));
    TestTrue(TEXT("Noon moon is dark"), FMath::IsNearlyZero(Moon->GetLightComponent()->Intensity));

    Rig->ApplyCyclePhase(0.0);
    TestTrue(TEXT("Midnight has no daylight"), FMath::IsNearlyZero(Rig->CurrentDaylightAmount));
    TestTrue(TEXT("Midnight reveals the stars"), Rig->StarsDome->IsVisible());
    TestTrue(TEXT("Midnight moon reaches its authored maximum"),
        FMath::IsNearlyEqual(Moon->GetLightComponent()->Intensity, Rig->MaximumMoonIntensity));
    TestTrue(TEXT("Midnight sun is dark"), FMath::IsNearlyZero(Sun->GetLightComponent()->Intensity));
    TestTrue(TEXT("Skylight reaches the night level"),
        FMath::IsNearlyEqual(Sky->GetLightComponent()->Intensity, Rig->NightSkyLightIntensity));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEditorLightingOverrideTest,
    "InfinityStage.Celestial.EditorWorkingLightIsSeparateFromPlayback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEditorLightingOverrideTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    FInfinityShowCue& Wing = Show->Cues.AddDefaulted_GetRef();
    Wing.Type = EInfinityCueType::WingPair;
    Wing.CueGuid = FGuid::NewGuid();
    Wing.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    TestFalse(TEXT("Editor-lighting fixture compiles"), Compiled.HasErrors());
    TestEqual(TEXT("Editor-lighting fixture has one Passage"), Compiled.Passages.Num(), 1);
    if (Compiled.Passages.IsEmpty())
    {
        return false;
    }

    UWorld* EditorWorld = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCelestialRig* EditorRig = EditorWorld->SpawnActor<AInfinityStageCelestialRig>();
    EditorRig->InitialPhaseCycles = 0.0;
    EditorRig->bUseManualEditorLighting = true;
    EditorRig->EditorPreviewTimeHours = 12.0;
    TestTrue(TEXT("Manual editor working light evaluates"),
        EditorRig->EvaluateAtMasterFrame(
            Show,
            Compiled.Passages[0].PassageGuid,
            Compiled.Passages[0].SegmentStartFrame));
    TestTrue(TEXT("Editor Master evaluation is protected at authored noon"),
        FMath::IsNearlyEqual(EditorRig->CurrentNormalizedPhase, 0.5));

    EditorRig->SetUseManualEditorLighting(false);
    TestTrue(TEXT("Editor can deliberately follow the Master"),
        EditorRig->EvaluateAtMasterFrame(
            Show,
            Compiled.Passages[0].PassageGuid,
            Compiled.Passages[0].SegmentStartFrame));
    TestTrue(TEXT("Follow-Master editor mode restores the Master phase"),
        FMath::IsNearlyZero(EditorRig->CurrentNormalizedPhase));
    EditorWorld->DestroyWorld(false);

    UWorld* GameWorld = UWorld::CreateWorld(EWorldType::Game, false);
    AInfinityStageCelestialRig* GameRig = GameWorld->SpawnActor<AInfinityStageCelestialRig>();
    GameRig->InitialPhaseCycles = 0.0;
    GameRig->bUseManualEditorLighting = true;
    GameRig->EditorPreviewTimeHours = 12.0;
    TestTrue(TEXT("Game-world Master lighting evaluates"),
        GameRig->EvaluateAtMasterFrame(
            Show,
            Compiled.Passages[0].PassageGuid,
            Compiled.Passages[0].SegmentStartFrame));
    TestTrue(TEXT("PIE/game ignores the manual editor working light"),
        FMath::IsNearlyZero(GameRig->CurrentNormalizedPhase));
    GameWorld->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDuplicateIdentityTest,
    "InfinityStage.Compiler.RejectsDuplicateIdentity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDuplicateIdentityTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    const FGuid DuplicateCueGuid = FGuid::NewGuid();
    const FGuid DuplicateOccurrenceGuid = FGuid::NewGuid();
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = DuplicateCueGuid;
        Cue.WingPair.OccurrenceGuid = DuplicateOccurrenceGuid;
    }

    const FInfinityCompileResult Result = FInfinityStageCompiler::Compile(*Show);
    TestTrue(TEXT("Duplicate identities are compile errors"), Result.HasErrors());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSegmentBoundaryTest,
    "InfinityStage.Transport.SegmentBoundaries",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSegmentBoundaryTest::RunTest(const FString& Parameters)
{
    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>();
    FInfinityTransportSegment& First = Transport->Segments.AddDefaulted_GetRef();
    First.StartFrame = 0;
    First.EndFrame = 100;
    FInfinityTransportSegment& Second = Transport->Segments.AddDefaulted_GetRef();
    Second.StartFrame = 100;
    Second.EndFrame = 200;

    TestEqual(TEXT("Start is inclusive"), Transport->FindSegmentAtFrame(0), 0);
    TestEqual(TEXT("End is exclusive and next start wins"), Transport->FindSegmentAtFrame(100), 1);
    TestEqual(TEXT("Final show end resolves to final segment"), Transport->FindSegmentAtFrame(200), 1);
    TestEqual(TEXT("Outside show has no segment"), Transport->FindSegmentAtFrame(201), INDEX_NONE);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStagePersistentMaterializationTest,
    "InfinityStage.Materialization.PersistentEditorComponents",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStagePersistentMaterializationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);

    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    UFunction* MaterializeButton = Actor->FindFunction(
        GET_FUNCTION_NAME_CHECKED(AInfinityStagePassageActor, MaterializePassageInEditor));
    TestNotNull(TEXT("Materialize Passage editor-button wrapper is reflected"), MaterializeButton);
    TestTrue(TEXT("Materialize Passage wrapper is exposed as Call In Editor"),
        MaterializeButton && MaterializeButton->HasMetaData(TEXT("CallInEditor")));
    const bool bMaterialized = Actor->MaterializePassage();
    TestTrue(TEXT("Materialization succeeds in an editor world"), bMaterialized);
    TestEqual(TEXT("One repeated render key creates one ISM component"), Actor->ManagedComponents.Num(), 1);
    TestEqual(TEXT("Two pairs create four materialized panel references"), Actor->MaterializedPanels.Num(), 4);
    TestEqual(TEXT("Materialized pair count"), Actor->MaterializedWingPairCount, 2);
    TestTrue(TEXT("Straight route fits compiled passage"), Actor->Route->GetSplineLength() >= 500.0);

    UInstancedStaticMeshComponent* PreviousComponent = Actor->ManagedComponents[0];
    const int32 PreviousPanelCount = Actor->MaterializedPanels.Num();
    Actor->ComponentBudget = 1;
    Show->Cues[0].WingPair.Left.Mesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    AddExpectedError(
        TEXT("Passage needs 2 render components but its budget is 1"),
        EAutomationExpectedErrorFlags::Contains,
        1);
    TestFalse(TEXT("A replacement that exceeds the budget is rejected"), Actor->MaterializePassage());
    TestEqual(TEXT("Failed replacement keeps the existing component"), Actor->ManagedComponents[0].Get(), PreviousComponent);
    TestEqual(TEXT("Failed replacement keeps every visible panel reference"), Actor->MaterializedPanels.Num(), PreviousPanelCount);
    TestEqual(TEXT("Failed replacement keeps the visible pair count"), Actor->MaterializedWingPairCount, 2);

    Actor->ComponentBudget = 4;
    TestTrue(TEXT("Replacement succeeds after authoring headroom is available"), Actor->MaterializePassage());
    TestEqual(TEXT("The replacement creates the second render component"), Actor->ManagedComponents.Num(), 2);

    Actor->ClearMaterializedPassage();
    TestEqual(TEXT("Clear removes only managed components"), Actor->ManagedComponents.Num(), 0);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageOrphanedManagedComponentRecoveryTest,
    "InfinityStage.Materialization.RecoversOrphanedTaggedComponents",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageOrphanedManagedComponentRecoveryTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Cube;
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Initial materialization succeeds"), Actor->MaterializePassage());
    TestEqual(TEXT("Initial render component count"), Actor->ManagedComponents.Num(), 1);
    UInstancedStaticMeshComponent* OrphanedComponent = Actor->ManagedComponents[0];

    // Reproduce the saved Passage 1 failure: the generated component remains
    // owned and tagged on the Actor, but the serialized tracking arrays have
    // lost it. A normal re-materialize must recover it instead of doubling.
    Actor->ManagedComponents.Reset();
    Actor->MaterializedPanels.Reset();
    Actor->MaterializedWingPairCount = 0;

    TestTrue(TEXT("Re-materialization recovers the orphan"), Actor->MaterializePassage());
    TInlineComponentArray<UInstancedStaticMeshComponent*> RemainingComponents(Actor);
    TestEqual(TEXT("Only the replacement render component remains"), RemainingComponents.Num(), 1);
    TestFalse(TEXT("The orphaned component was destroyed"), RemainingComponents.Contains(OrphanedComponent));
    TestEqual(TEXT("Recovered materialization tracks one component"), Actor->ManagedComponents.Num(), 1);
    TestEqual(TEXT("Recovered materialization tracks both panels"), Actor->MaterializedPanels.Num(), 2);
    TestEqual(TEXT("Recovered materialization tracks one pair"), Actor->MaterializedWingPairCount, 1);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRoleAwareFacingTest,
    "InfinityStage.Materialization.RoleAwareFacingDoesNotMirror",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRoleAwareFacingTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    UInfinityStageWingLibraryAsset* Library = NewObject<UInfinityStageWingLibraryAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Sphere(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    FInfinityWingAssetEntry& LeftEntry = Library->Entries.AddDefaulted_GetRef();
    LeftEntry.EntryGuid = FGuid::NewGuid();
    LeftEntry.Mesh = Cube;
    LeftEntry.Role = EInfinityWingAssetRole::LeftArchitectural;
    LeftEntry.FrontAxis = EInfinityWingFrontAxis::PositiveX;
    FInfinityWingAssetEntry& RightEntry = Library->Entries.AddDefaulted_GetRef();
    RightEntry.EntryGuid = FGuid::NewGuid();
    RightEntry.Mesh = Sphere;
    RightEntry.Role = EInfinityWingAssetRole::RightArchitectural;
    RightEntry.FrontAxis = EInfinityWingFrontAxis::NegativeX;
    RightEntry.PlacementAdjustment = FTransform(
        FQuat::Identity, FVector::ZeroVector, FVector(1.0, -1.0, 1.0));
    RightEntry.bPhotographicMirrorApproved = false;
    Show->WingLibrary = Library;

    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Left.bFlipImageHorizontally = true;
    Cue.WingPair.Right.Mesh = Sphere;
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    AddExpectedError(TEXT("Ignoring unapproved mirrored placement adjustment"),
        EAutomationExpectedErrorFlags::Contains, 1);
    TestTrue(TEXT("Role-facing fixture materializes"), Actor->MaterializePassage());
    const FInfinityMaterializedPanelRef* Left = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Left; });
    const FInfinityMaterializedPanelRef* Right = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Right; });
    TestNotNull(TEXT("Left reference exists"), Left);
    TestNotNull(TEXT("Right reference exists"), Right);
    if (Left && Right)
    {
        TestTrue(TEXT("Left preserves positive-X front"),
            Left->BaseWorldTransform.GetRotation().GetForwardVector().X > 0.99);
        TestTrue(TEXT("Explicit Left image flip is stored as a mirrored instance transform"),
            Left->BaseWorldTransform.ToMatrixWithScale().Determinant() < 0.0);
        TestTrue(TEXT("Right front is physically turned toward negative X"),
            Right->BaseWorldTransform.GetRotation().GetForwardVector().X < -0.99);
        TestTrue(TEXT("Unapproved photographic mirror never reaches the instance"),
            Right->BaseWorldTransform.ToMatrixWithScale().Determinant() > 0.0);
    }
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageApplyImageFlipToAllUsesTest,
    "InfinityStage.Authoring.ApplyImageFlipToAllMeshUses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageApplyImageFlipToAllUsesTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Sphere(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Index == 0 ? Cube : Sphere;
    }
    Show->Cues[1].WingPair.bHasTop = true;
    Show->Cues[1].WingPair.Top.Mesh = Cube;

    TestEqual(TEXT("Every Left/Right/Top use of Cube is changed"),
        Show->ApplyImageFlipToAllUsesOfMesh(Cube.ToSoftObjectPath(), true), 4);
    TestTrue(TEXT("First Left is flipped"), Show->Cues[0].WingPair.Left.bFlipImageHorizontally);
    TestTrue(TEXT("First Right is flipped"), Show->Cues[0].WingPair.Right.bFlipImageHorizontally);
    TestTrue(TEXT("Second Left is flipped"), Show->Cues[1].WingPair.Left.bFlipImageHorizontally);
    TestTrue(TEXT("Top use is flipped"), Show->Cues[1].WingPair.Top.bFlipImageHorizontally);
    TestFalse(TEXT("A different mesh is untouched"), Show->Cues[1].WingPair.Right.bFlipImageHorizontally);
    TestEqual(TEXT("Reapplying the same state is idempotent"),
        Show->ApplyImageFlipToAllUsesOfMesh(Cube.ToSoftObjectPath(), true), 0);
    TestEqual(TEXT("The state can be cleared for every use"),
        Show->ApplyImageFlipToAllUsesOfMesh(Cube.ToSoftObjectPath(), false), 4);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageApplyRelativeTransformToAllUsesTest,
    "InfinityStage.Authoring.ApplyRelativeTransformToAllMeshUses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageApplyRelativeTransformToAllUsesTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Sphere(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Index == 0 ? Cube : Sphere;
    }
    Show->Cues[1].WingPair.bHasTop = true;
    Show->Cues[1].WingPair.Top.Mesh = Cube;

    FTransform SourceTransform;
    SourceTransform.SetTranslation(FVector(12.0, -34.0, 56.0));
    SourceTransform.SetRotation(FRotator(7.0, 89.0, -13.0).Quaternion());
    SourceTransform.SetScale3D(FVector(1.5, 0.75, 2.25));
    Show->Cues[0].WingPair.Left.LocalTransform = SourceTransform;
    const FTransform DifferentMeshTransform(
        FRotator(-20.0, 15.0, 5.0), FVector(90.0, 80.0, 70.0), FVector(0.5));
    Show->Cues[1].WingPair.Right.LocalTransform = DifferentMeshTransform;

    TestEqual(TEXT("Every other Left/Right/Top use of Cube is changed"),
        Show->ApplyRelativeTransformToAllUsesOfMesh(Cube.ToSoftObjectPath(), SourceTransform), 3);
    TestTrue(TEXT("Source transform remains unchanged"),
        Show->Cues[0].WingPair.Left.LocalTransform.Equals(SourceTransform));
    TestTrue(TEXT("Same-mesh Right receives location, rotation and scale"),
        Show->Cues[0].WingPair.Right.LocalTransform.Equals(SourceTransform));
    TestTrue(TEXT("Same-mesh Left in another cue receives the transform"),
        Show->Cues[1].WingPair.Left.LocalTransform.Equals(SourceTransform));
    TestTrue(TEXT("Same-mesh Top receives the transform"),
        Show->Cues[1].WingPair.Top.LocalTransform.Equals(SourceTransform));
    TestTrue(TEXT("A different mesh remains untouched"),
        Show->Cues[1].WingPair.Right.LocalTransform.Equals(DifferentMeshTransform));
    TestEqual(TEXT("Reapplying the same transform is idempotent"),
        Show->ApplyRelativeTransformToAllUsesOfMesh(Cube.ToSoftObjectPath(), SourceTransform), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageTravelingUndulationAuthoringTest,
    "InfinityStage.Authoring.TravelingUndulationPreset",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageTravelingUndulationAuthoringTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    TArray<FGuid> Targets;
    for (int32 Index = 0; Index < 5; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Type = EInfinityCueType::WingPair;
        Targets.Add(Cue.CueGuid);
    }
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Type = EInfinityCueType::Scene;
    for (int32 Index = 0; Index < 5; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Type = EInfinityCueType::WingPair;
        Targets.Add(Cue.CueGuid);
    }

    TestEqual(TEXT("All ten target Wing Pairs changed"),
        Show->ApplyTravelingUndulation(Targets, 0.18, 75.0, -0.10), 10);
    TestEqual(TEXT("First Passage phase 0"), Show->Cues[0].WingPair.Mechanism.PhaseOffsetCycles, 0.0);
    TestEqual(TEXT("First Passage phase 1"), Show->Cues[1].WingPair.Mechanism.PhaseOffsetCycles, -0.10);
    TestEqual(TEXT("First Passage phase 2"), Show->Cues[2].WingPair.Mechanism.PhaseOffsetCycles, -0.20);
    TestEqual(TEXT("Phase restarts after Scene"), Show->Cues[6].WingPair.Mechanism.PhaseOffsetCycles, 0.0);
    TestEqual(TEXT("Second Passage phase 1"), Show->Cues[7].WingPair.Mechanism.PhaseOffsetCycles, -0.10);

    const auto WrappedPhase = [](const double Phase)
    {
        return Phase - FMath::FloorToDouble(Phase);
    };
    TestEqual(TEXT("Two-phase preset changes all targets"),
        Show->ApplyTravelingUndulation(Targets, 0.18, 75.0, 1.0 / 2.0), 10);
    TestTrue(TEXT("Two-phase pattern 1"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[0].WingPair.Mechanism.PhaseOffsetCycles), 0.0));
    TestTrue(TEXT("Two-phase pattern 2"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[1].WingPair.Mechanism.PhaseOffsetCycles), 0.5));
    TestTrue(TEXT("Two-phase pattern repeats at 3"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[2].WingPair.Mechanism.PhaseOffsetCycles), 0.0));
    TestTrue(TEXT("Two-phase pattern repeats at 4"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[3].WingPair.Mechanism.PhaseOffsetCycles), 0.5));
    TestTrue(TEXT("Two-phase pattern restarts after Scene"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[6].WingPair.Mechanism.PhaseOffsetCycles), 0.0));

    TestEqual(TEXT("Three-phase preset changes all targets"),
        Show->ApplyTravelingUndulation(Targets, 0.18, 75.0, 1.0 / 3.0), 10);
    TestTrue(TEXT("Three-phase pattern 1"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[0].WingPair.Mechanism.PhaseOffsetCycles), 0.0));
    TestTrue(TEXT("Three-phase pattern 2"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[1].WingPair.Mechanism.PhaseOffsetCycles), 1.0 / 3.0));
    TestTrue(TEXT("Three-phase pattern 3"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[2].WingPair.Mechanism.PhaseOffsetCycles), 2.0 / 3.0));
    TestTrue(TEXT("Three-phase pattern repeats"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[3].WingPair.Mechanism.PhaseOffsetCycles), 0.0));

    TestEqual(TEXT("Four-phase preset changes all targets"),
        Show->ApplyTravelingUndulation(Targets, 0.18, 75.0, 1.0 / 4.0), 10);
    TestTrue(TEXT("Four-phase pattern 1"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[0].WingPair.Mechanism.PhaseOffsetCycles), 0.0));
    TestTrue(TEXT("Four-phase pattern 2"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[1].WingPair.Mechanism.PhaseOffsetCycles), 0.25));
    TestTrue(TEXT("Four-phase pattern 3"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[2].WingPair.Mechanism.PhaseOffsetCycles), 0.5));
    TestTrue(TEXT("Four-phase pattern 4"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[3].WingPair.Mechanism.PhaseOffsetCycles), 0.75));
    TestTrue(TEXT("Four-phase pattern repeats"), FMath::IsNearlyEqual(WrappedPhase(Show->Cues[4].WingPair.Mechanism.PhaseOffsetCycles), 0.0));

    const FRichCurve* Curve = Show->Cues[0].WingPair.Mechanism.LeftNormalizedCurve.GetRichCurveConst();
    TestTrue(TEXT("Closed curve starts at rest"), FMath::IsNearlyZero(Curve->Eval(0.0f)));
    TestTrue(TEXT("Closed curve reaches full travel"), FMath::IsNearlyEqual(Curve->Eval(0.5f), 1.0f));
    TestTrue(TEXT("Closed curve ends at rest"), FMath::IsNearlyZero(Curve->Eval(1.0f)));
    TestTrue(TEXT("Left and Right share the same gesture"), FMath::IsNearlyEqual(
        Curve->Eval(0.25f),
        Show->Cues[0].WingPair.Mechanism.RightNormalizedCurve.GetRichCurveConst()->Eval(0.25f)));

    Show->ReconcilePassageSettings();
    TestEqual(TEXT("Whole-Passage live preset changes every target"),
        Show->ApplyTravelingUndulation(Targets, 0.18, 75.0, -0.125, true), 10);
    TestEqual(TEXT("Both Passage ranges have live movement settings"), Show->PassageSettings.Num(), 2);
    TestTrue(TEXT("First Passage derives phase from current cue order"),
        Show->PassageSettings[0].bUseLiveMechanismPhasePattern);
    TestTrue(TEXT("Live phase step is stored once on the Passage"),
        FMath::IsNearlyEqual(Show->PassageSettings[0].MechanismPhaseStepCycles, -0.125));
    TestTrue(TEXT("Rows using the live pattern are not locally phase-pinned"),
        (Show->Cues[1].WingPair.LocalOverrideMask
            & static_cast<int32>(EInfinityLocalOverride::MechanismPhase)) == 0);
    const FGuid FormerSecondGuid = Show->Cues[1].CueGuid;
    Show->Cues.Swap(0, 1);
    Show->ReconcilePassageSettings();
    TestEqual(TEXT("Reordering preserves the live Passage controller"),
        Show->PassageSettings[0].MechanismPhaseStepCycles, -0.125);
    TestEqual(TEXT("The moved row has a new live ordinal without rewriting its GUID"),
        Show->Cues[0].CueGuid, FormerSecondGuid);

    TestEqual(TEXT("Static command affects the ten targets"), Show->SetMechanismsStatic(Targets), 10);
    TestEqual(TEXT("Static command is idempotent"), Show->SetMechanismsStatic(Targets), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraGustAuthoringTest,
    "InfinityStage.Authoring.CameraGustFanRevealPreset",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraGustAuthoringTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    TArray<FGuid> Targets;
    for (int32 Index = 0; Index < 12; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.WingPair.IntervalToNext = 48000; // two seconds at the default tick resolution
        Cue.WingPair.Mechanism.InwardTravelCm = 90.0;
        Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -650.0 - Index, 0.0));
        Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 650.0 + Index, 0.0));
        Targets.Add(Cue.CueGuid);
    }

    FInfinityCameraGustSettings Settings;
    TestEqual(TEXT("All whole-Passage targets changed"), Show->ApplyCameraGust(Targets, Settings, true), 12);
    const FInfinityMechanismMotion& Motion = Show->Cues[3].WingPair.Mechanism;
    TestEqual(TEXT("Fan uses its dedicated playback mode"), Motion.PlaybackMode, EInfinityMotionPlaybackMode::CameraGust);
    TestEqual(TEXT("Default reveal follows camera travel"),
        Motion.CameraGust.TimingMode, EInfinityCameraGustTimingMode::CameraTravelWindow);
    TestEqual(TEXT("Six pairs remain revealed ahead"), Motion.CameraGust.FanDepthPairs, 6);
    TestEqual(TEXT("Opening edge is authored in pair spacing"), Motion.CameraGust.OpeningSpanPairs, 0.25);
    TestEqual(TEXT("Default policy holds open"),
        Motion.CameraGust.HoldOpenPolicy, EInfinityCameraGustHoldOpenPolicy::HoldOpenThroughPassage);
    TestEqual(TEXT("Default trigger is expressed in pairs"),
        Motion.CameraGust.TriggerOffsetUnit, EInfinityCameraGustTriggerOffsetUnit::Pairs);
    TestEqual(TEXT("Default trigger offset is one pair"), Motion.CameraGust.TriggerOffset, 1.0);
    TestEqual(TEXT("First group anchor is stable"), Motion.CameraGust.GroupAnchorCueGuid, Targets[0]);
    TestEqual(TEXT("Ordered ordinal is retained"), Motion.CameraGust.GroupOrdinal, 3);
    TestEqual(TEXT("Camera-led mode uses one continuous Passage group"), Motion.CameraGust.GroupSize, 12);
    TestEqual(TEXT("Camera-led mode does not partition its reveal window"),
        Show->Cues[8].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid, Targets[0]);
    TestEqual(TEXT("Camera-led ordinal remains continuous"),
        Show->Cues[8].WingPair.Mechanism.CameraGust.GroupOrdinal, 8);
    TestEqual(TEXT("Existing configured inward travel is preserved"), Motion.InwardTravelCm, 90.0);
    TestEqual(TEXT("Authored Left rest position is preserved"),
        Show->Cues[3].WingPair.Left.LocalTransform.GetTranslation().Y, -653.0);
    TestEqual(TEXT("Authored Right rest position is preserved"),
        Show->Cues[3].WingPair.Right.LocalTransform.GetTranslation().Y, 653.0);

    const FRichCurve* Curve = Motion.LeftNormalizedCurve.GetRichCurveConst();
    TestTrue(TEXT("Before activation the pair is fully closed"), FMath::IsNearlyEqual(Curve->Eval(0.0f), 1.0f));
    TestTrue(TEXT("After opening the pair is at authored rest/open"), FMath::IsNearlyZero(Curve->Eval(1.0f)));
    TestTrue(TEXT("Left and Right opening curves agree"), FMath::IsNearlyEqual(
        Curve->Eval(0.5f), Motion.RightNormalizedCurve.GetRichCurveConst()->Eval(0.5f)));

    TestEqual(TEXT("Reapplying the same preset is idempotent"),
        Show->ApplyCameraGust(Targets, Settings, true), 0);

    const TArray<FGuid> OrderedSelection = { Targets[2], Targets[5], Targets[9] };
    TestEqual(TEXT("Ordered multi-selection applies as one fan group"),
        Show->ApplyCameraGust(OrderedSelection, Settings, false), 3);
    TestEqual(TEXT("Selection anchor is its first ordered row"),
        Show->Cues[9].WingPair.Mechanism.CameraGust.GroupAnchorCueGuid, Targets[2]);
    TestEqual(TEXT("Non-contiguous selected order is deterministic"),
        Show->Cues[9].WingPair.Mechanism.CameraGust.GroupOrdinal, 2);
    TestEqual(TEXT("Selection is one actual group"),
        Show->Cues[9].WingPair.Mechanism.CameraGust.GroupSize, 3);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraGustEvaluationTest,
    "InfinityStage.Mechanism.CameraRevealFollowsEvaluatedCameraDistance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraGustEvaluationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    TArray<FGuid> Targets;
    for (int32 Index = 0; Index < 7; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 48000;
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
        Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
        Cue.WingPair.Mechanism.InwardTravelCm = 100.0;
        Targets.Add(Cue.CueGuid);
    }
    Show->ReconcilePassageSettings();
    FInfinityCameraGustSettings Settings;
    Settings.FanDepthPairs = 3;
    Settings.OpeningSpanPairs = 0.50;
    TestEqual(TEXT("Camera-led reveal applies to all targets"), Show->ApplyCameraGust(Targets, Settings, false), 7);

    const int32 InitialWorldActorCount = World->GetActorCount();
    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestFalse(TEXT("Passage Actor never has a per-frame Actor Tick"), Actor->PrimaryActorTick.bCanEverTick);
    TestTrue(TEXT("Gust fixture materializes into batched instances"), Actor->MaterializePassage());
    TestEqual(TEXT("Materialization creates no per-wing Actor"), World->GetActorCount(), InitialWorldActorCount + 1);

    const auto FindPanel = [Actor](const FGuid CueGuid, const EInfinityPanelSide Side)
    {
        return Actor->MaterializedPanels.FindByPredicate([CueGuid, Side](const FInfinityMaterializedPanelRef& Ref)
        {
            return Ref.CueGuid == CueGuid && Ref.Side == Side;
        });
    };
    const auto ReadTransform = [](const FInfinityMaterializedPanelRef* Ref)
    {
        FTransform Transform;
        if (Ref && Ref->Component)
        {
            Ref->Component->GetInstanceTransform(Ref->InstanceIndex, Transform, true);
        }
        return Transform;
    };

    const FInfinityMaterializedPanelRef* FirstLeft = FindPanel(Targets[0], EInfinityPanelSide::Left);
    const FInfinityMaterializedPanelRef* FourthLeft = FindPanel(Targets[3], EInfinityPanelSide::Left);
    const FInfinityMaterializedPanelRef* FourthRight = FindPanel(Targets[3], EInfinityPanelSide::Right);
    const FInfinityMaterializedPanelRef* FifthLeft = FindPanel(Targets[4], EInfinityPanelSide::Left);
    TestNotNull(TEXT("First Left panel resolves"), FirstLeft);
    TestNotNull(TEXT("Fourth Left panel resolves"), FourthLeft);
    TestNotNull(TEXT("Fourth Right panel resolves"), FourthRight);
    TestNotNull(TEXT("Fifth Left panel resolves"), FifthLeft);

    // At camera station zero, exactly the nearest three pairs are open. The
    // fourth is the closed leading edge and everything farther ahead is closed.
    TestTrue(TEXT("Initial camera station evaluates"), Actor->EvaluateMechanismsAtCameraDistance(0, 0.0));
    const FTransform FirstOpenLeft = ReadTransform(FirstLeft);
    const FTransform FourthClosedLeft = ReadTransform(FourthLeft);
    const FTransform FourthClosedRight = ReadTransform(FourthRight);
    const FTransform FifthClosedLeft = ReadTransform(FifthLeft);
    TestTrue(TEXT("Nearest pair is open at its authored rest position"),
        FirstOpenLeft.Equals(FirstLeft->BaseWorldTransform, 0.001));
    TestFalse(TEXT("Fourth pair remains closed beyond the three-pair reveal window"),
        FourthClosedLeft.Equals(FourthLeft->BaseWorldTransform, 0.001));
    TestFalse(TEXT("Fifth pair also remains closed"),
        FifthClosedLeft.Equals(FifthLeft->BaseWorldTransform, 0.001));

    // Moving the camera half a pair advances the reveal edge by half a pair.
    // With a 0.5-pair ramp the fourth pair is now fully open.
    TestTrue(TEXT("Half-pair camera move evaluates"), Actor->EvaluateMechanismsAtCameraDistance(12000, 250.0));
    const FTransform FourthOpenLeft = ReadTransform(FourthLeft);
    const FTransform FourthOpenRight = ReadTransform(FourthRight);
    TestTrue(TEXT("Next pair opens when the camera advances the reveal frontier"),
        FourthOpenLeft.Equals(FourthLeft->BaseWorldTransform, 0.001));
    TestTrue(TEXT("Left opens outward by its exact configured travel"),
        FMath::IsNearlyEqual(FourthClosedLeft.GetLocation().Y - FourthOpenLeft.GetLocation().Y, 100.0, 0.01));
    TestTrue(TEXT("Right opens outward symmetrically by the same travel"),
        FMath::IsNearlyEqual(FourthOpenRight.GetLocation().Y - FourthClosedRight.GetLocation().Y, 100.0, 0.01));

    // Master time alone cannot advance the reveal if the evaluated camera is held.
    TestTrue(TEXT("Paused camera sample evaluates"), Actor->EvaluateMechanismsAtCameraDistance(24000, 100.0));
    const FTransform PausedState = ReadTransform(FourthLeft);
    TestTrue(TEXT("Later Master frame at the same camera distance evaluates"),
        Actor->EvaluateMechanismsAtCameraDistance(48000, 100.0));
    TestTrue(TEXT("Wing progress follows camera distance, not an independent clock"),
        ReadTransform(FourthLeft).Equals(PausedState, 0.001));

    TestTrue(TEXT("Forward camera travel evaluates"), Actor->EvaluateMechanismsAtCameraDistance(48000, 1000.0));
    TestTrue(TEXT("Pairs behind the moving camera remain open"),
        ReadTransform(FirstLeft).Equals(FirstOpenLeft, 0.001));
    TestTrue(TEXT("Reverse camera seek evaluates"), Actor->EvaluateMechanismsAtCameraDistance(0, 0.0));
    TestTrue(TEXT("Reverse/direct seek reconstructs the same closed frontier"),
        ReadTransform(FourthLeft).Equals(FourthClosedLeft, 0.001));

    AInfinityStagePassageActor* ReloadedActor = World->SpawnActor<AInfinityStagePassageActor>();
    ReloadedActor->ShowAsset = Show;
    ReloadedActor->PassageGuid = Actor->PassageGuid;
    TestTrue(TEXT("Reloaded fixed Passage materializes"), ReloadedActor->MaterializePassage());
    TestTrue(TEXT("Reloaded Passage evaluates directly at the same camera station"),
        ReloadedActor->EvaluateMechanismsAtCameraDistance(12000, 250.0));
    const FInfinityMaterializedPanelRef* ReloadedFourthLeft = ReloadedActor->MaterializedPanels.FindByPredicate(
        [&Targets](const FInfinityMaterializedPanelRef& Ref)
        {
            return Ref.CueGuid == Targets[3] && Ref.Side == EInfinityPanelSide::Left;
        });
    TestTrue(TEXT("Reload/direct scrub state is identical at the same rail position"),
        ReadTransform(ReloadedFourthLeft).Equals(FourthOpenLeft, 0.001));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageWingModulationChannelTest,
    "InfinityStage.Mechanism.WingModulationChannelsIntegrateDeterministically",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageWingModulationChannelTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.IntervalToNext = 100;
        Cue.WingPair.GapToNextCm = 100.0;
    }
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (!TestEqual(TEXT("Fixture compiles one Passage"), Compiled.Passages.Num(), 1))
    {
        return false;
    }
    const FInfinityCompiledPassage& Passage = Compiled.Passages[0];
    const double StartFrame = Passage.SegmentStartFrame.Value;
    const double EndFrame = Passage.SegmentEndFrame.Value;

    UMovieSceneInfinityPassageSection* Section = NewObject<UMovieSceneInfinityPassageSection>();
    Section->PassageGuid = Passage.PassageGuid;

    TestFalse(TEXT("A neutral section reports no Wing modulation"), Section->HasWingModulation());

    // A neutral rate must integrate to plain elapsed frames, which is what keeps
    // an unmodulated Show bit-identical to the previous behaviour.
    const double NeutralIntegral = Section->GetWingCycleRateIntegralFrames(Passage, EndFrame);
    TestTrue(
        TEXT("Neutral rate integrates to elapsed frames"),
        FMath::IsNearlyEqual(NeutralIntegral, EndFrame - StartFrame, 0.01));

    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingCycleRateScale)->SetDefault(2.0);
    TestTrue(TEXT("A non-neutral default counts as modulation"), Section->HasWingModulation());
    TestTrue(
        TEXT("Doubled rate doubles the integral"),
        FMath::IsNearlyEqual(
            Section->GetWingCycleRateIntegralFrames(Passage, EndFrame),
            2.0 * (EndFrame - StartFrame),
            0.01));

    // History independence: the integral between two frames must equal the
    // difference of the integrals to each, however the playhead arrived.
    FMovieSceneDoubleChannel* Rate =
        Section->GetCameraChannel(EInfinityPassageCameraChannel::WingCycleRateScale);
    Rate->Reset();
    Rate->AddLinearKey(FFrameNumber(static_cast<int32>(StartFrame)), 0.25);
    Rate->AddLinearKey(FFrameNumber(static_cast<int32>(EndFrame)), 3.0);
    const double Midpoint = FMath::Lerp(StartFrame, EndFrame, 0.5);
    const double ToMid = Section->GetWingCycleRateIntegralFrames(Passage, Midpoint);
    const double ToEnd = Section->GetWingCycleRateIntegralFrames(Passage, EndFrame);
    TestTrue(TEXT("Rate integral is monotonic"), ToEnd >= ToMid);
    TestTrue(
        TEXT("Repeated evaluation is stable"),
        FMath::IsNearlyEqual(ToMid, Section->GetWingCycleRateIntegralFrames(Passage, Midpoint), 0.0001));
    TestTrue(
        TEXT("A negative keyed rate is clamped rather than reversing the mechanism"),
        Section->GetWingCycleRateIntegralFrames(Passage, StartFrame) >= 0.0);

    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(0.5);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingPhaseBiasCycles)->SetDefault(0.25);
    FInfinityPassageWingEvaluation Evaluation;
    TestTrue(
        TEXT("Wing modulation evaluates inside the Passage"),
        Section->EvaluateWingModulation(Passage, FFrameTime(static_cast<int32>(Midpoint)), Evaluation));
    TestEqual(TEXT("Travel scale evaluates"), Evaluation.InwardTravelScale, 0.5);
    TestEqual(TEXT("Phase bias evaluates"), Evaluation.PhaseBiasCycles, 0.25);

    FInfinityPassageWingEvaluation Outside;
    TestFalse(
        TEXT("Wing modulation refuses frames outside the Passage"),
        Section->EvaluateWingModulation(Passage, FFrameTime(static_cast<int32>(EndFrame) + 1000), Outside));

    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(-4.0);
    FInfinityPassageWingEvaluation Clamped;
    Section->EvaluateWingModulation(Passage, FFrameTime(static_cast<int32>(Midpoint)), Clamped);
    TestTrue(TEXT("Negative travel scale is clamped to zero"), Clamped.InwardTravelScale >= 0.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismRenderStateDirtyCVarTest,
    "InfinityStage.Mechanism.RenderStateDirtyCVar",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismRenderStateDirtyCVarTest::RunTest(const FString& Parameters)
{
    IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(
        TEXT("InfinityStage.Mechanism.MarkRenderStateDirty"));
    TestNotNull(TEXT("Mechanism render-state cvar exists"), CVar);
    if (CVar)
    {
        TestEqual(TEXT("Mechanism render-state cvar defaults to existing behaviour"), CVar->GetInt(), 1);
        CVar->Set(0, ECVF_SetByCode);
        TestEqual(TEXT("Mechanism render-state cvar accepts freeze diagnostic mode"), CVar->GetInt(), 0);
        CVar->Set(1, ECVF_SetByCode);
        TestEqual(TEXT("Mechanism render-state cvar accepts existing behaviour mode"), CVar->GetInt(), 1);
        CVar->Set(2, ECVF_SetByCode);
        TestEqual(TEXT("Mechanism render-state cvar accepts final-batch dirty mode"), CVar->GetInt(), 2);
        CVar->Set(1, ECVF_SetByCode);
    }
    TestNull(
        TEXT("A misspelled mechanism render-state cvar is not registered"),
        IConsoleManager::Get().FindConsoleVariable(TEXT("InfinityStage.Mechanism.MarkRenderStateDirt")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUndulationEvaluationTest,
    "InfinityStage.Mechanism.UndulationMovesPanelsDeterministically",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUndulationEvaluationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    UInfinityStageWingLibraryAsset* Library = NewObject<UInfinityStageWingLibraryAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Sphere(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    FInfinityWingAssetEntry& LeftEntry = Library->Entries.AddDefaulted_GetRef();
    LeftEntry.EntryGuid = FGuid::NewGuid();
    LeftEntry.Mesh = Cube;
    LeftEntry.Role = EInfinityWingAssetRole::LeftArchitectural;
    LeftEntry.FrontAxis = EInfinityWingFrontAxis::PositiveX;
    FInfinityWingAssetEntry& RightEntry = Library->Entries.AddDefaulted_GetRef();
    RightEntry.EntryGuid = FGuid::NewGuid();
    RightEntry.Mesh = Sphere;
    RightEntry.Role = EInfinityWingAssetRole::RightArchitectural;
    RightEntry.FrontAxis = EInfinityWingFrontAxis::NegativeX;
    Show->WingLibrary = Library;
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Sphere;
    Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
    Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;
    Show->ApplyTravelingUndulation({ Cue.CueGuid }, 0.25, 100.0, 0.0);

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Moving fixture materializes"), Actor->MaterializePassage());
    const FInfinityMaterializedPanelRef* Left = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Left; });
    const FInfinityMaterializedPanelRef* Right = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Right; });
    TestNotNull(TEXT("Moving Left instance exists"), Left);
    TestNotNull(TEXT("Moving Right instance exists"), Right);
    if (Left && Right)
    {
        TestTrue(TEXT("Left inward axis is independent of its mesh facing"),
            Left->InwardWorldDirection.Equals(FVector(0.0, 1.0, 0.0), 0.001));
        TestTrue(TEXT("Turned Right mesh retains the opposite pair-motion axis"),
            Right->BaseWorldTransform.GetRotation().GetForwardVector().X < -0.99
            && Right->InwardWorldDirection.Equals(FVector(0.0, -1.0, 0.0), 0.001));
        TestTrue(TEXT("Rest frame evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
        FTransform LeftRest;
        FTransform RightRest;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftRest, true);
        Right->Component->GetInstanceTransform(Right->InstanceIndex, RightRest, true);
        FTransform LeftRestPrevious;
        TestTrue(
            TEXT("Moving ISM exposes an explicit previous transform"),
            Left->Component->GetInstancePrevTransform(Left->InstanceIndex, LeftRestPrevious, true));
        TestTrue(
            TEXT("First mechanism evaluation seeds a zero-velocity history"),
            LeftRestPrevious.Equals(LeftRest, 0.001));

        // Half a four-second cycle is the crest of the normalized curve.
        TestTrue(TEXT("Crest frame evaluates"), Actor->EvaluateMechanismsAtMasterFrame(48000));
        FTransform LeftCrest;
        FTransform RightCrest;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftCrest, true);
        Right->Component->GetInstanceTransform(Right->InstanceIndex, RightCrest, true);
        FTransform LeftCrestPrevious;
        TestTrue(
            TEXT("Crest evaluation retains the preceding instance transform"),
            Left->Component->GetInstancePrevTransform(Left->InstanceIndex, LeftCrestPrevious, true));
        TestTrue(
            TEXT("Crest motion history points back to the rest transform"),
            LeftCrestPrevious.Equals(LeftRest, 0.001));
        TestTrue(TEXT("Left moves 100 cm inward"),
            FMath::IsNearlyEqual(LeftCrest.GetLocation().Y - LeftRest.GetLocation().Y, 100.0, 0.01));
        TestTrue(TEXT("Right moves 100 cm inward"),
            FMath::IsNearlyEqual(RightRest.GetLocation().Y - RightCrest.GetLocation().Y, 100.0, 0.01));

        IConsoleVariable* RenderStateCVar = IConsoleManager::Get().FindConsoleVariable(
            TEXT("InfinityStage.Mechanism.MarkRenderStateDirty"));
        if (TestNotNull(TEXT("Mechanism render-state cvar is available to the moving fixture"), RenderStateCVar))
        {
            RenderStateCVar->Set(0, ECVF_SetByCode);
            TestTrue(TEXT("Rest frame evaluates in freeze diagnostic mode"),
                Actor->EvaluateMechanismsAtMasterFrame(0));
            TestTrue(TEXT("Crest frame evaluates in freeze diagnostic mode"),
                Actor->EvaluateMechanismsAtMasterFrame(48000));
            FTransform LeftCrestWithoutRenderStateDirty;
            FTransform RightCrestWithoutRenderStateDirty;
            Left->Component->GetInstanceTransform(
                Left->InstanceIndex, LeftCrestWithoutRenderStateDirty, true);
            Right->Component->GetInstanceTransform(
                Right->InstanceIndex, RightCrestWithoutRenderStateDirty, true);
            TestTrue(TEXT("Left transform matches mode 1 in freeze diagnostic mode"),
                LeftCrestWithoutRenderStateDirty.Equals(LeftCrest, 0.001));
            TestTrue(TEXT("Right transform matches mode 1 in freeze diagnostic mode"),
                RightCrestWithoutRenderStateDirty.Equals(RightCrest, 0.001));

            RenderStateCVar->Set(2, ECVF_SetByCode);
            TestTrue(TEXT("Rest frame evaluates in final-batch dirty mode"),
                Actor->EvaluateMechanismsAtMasterFrame(0));
            TestTrue(TEXT("Crest frame evaluates in final-batch dirty mode"),
                Actor->EvaluateMechanismsAtMasterFrame(48000));
            FTransform LeftCrestWithFinalBatchDirty;
            FTransform RightCrestWithFinalBatchDirty;
            Left->Component->GetInstanceTransform(
                Left->InstanceIndex, LeftCrestWithFinalBatchDirty, true);
            Right->Component->GetInstanceTransform(
                Right->InstanceIndex, RightCrestWithFinalBatchDirty, true);
            TestTrue(TEXT("Left transform matches mode 1 in final-batch dirty mode"),
                LeftCrestWithFinalBatchDirty.Equals(LeftCrest, 0.001));
            TestTrue(TEXT("Right transform matches mode 1 in final-batch dirty mode"),
                RightCrestWithFinalBatchDirty.Equals(RightCrest, 0.001));
            RenderStateCVar->Set(1, ECVF_SetByCode);
        }

        TestTrue(TEXT("Later frame evaluates"), Actor->EvaluateMechanismsAtMasterFrame(96000));
        TestTrue(TEXT("Direct seek back to crest evaluates"), Actor->EvaluateMechanismsAtMasterFrame(48000));
        FTransform LeftCrestAfterSeek;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftCrestAfterSeek, true);
        TestTrue(TEXT("Crest is history independent"),
            LeftCrestAfterSeek.Equals(LeftCrest, 0.001));
    }
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismKindsEvaluationTest,
    "InfinityStage.Mechanism.KindsUseCachedPivotsAndAxes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismKindsEvaluationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Cube;
    Cue.WingPair.Right.FacingPolicy = EInfinityPanelFacingPolicy::Rotate180AroundUp;
    Cue.WingPair.bHasTop = true;   // the Top panel is only materialized when bHasTop (Types.h bHasTop = false)
    Cue.WingPair.Top.Mesh = Cube;
    // Scale the 100 cm Engine Cube to production-card proportions: 10 cm thick
    // on X, 400 cm wide on Y and 1000 cm tall on Z, with its base on z=0.
    const FVector ProductionCardScale(0.1, 4.0, 10.0);
    Cue.WingPair.Left.LocalTransform.SetScale3D(ProductionCardScale);
    Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 500.0));
    Cue.WingPair.Right.LocalTransform.SetScale3D(ProductionCardScale);
    Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 500.0));
    Cue.WingPair.Top.LocalTransform.SetScale3D(ProductionCardScale);
    Cue.WingPair.Top.LocalTransform.SetTranslation(FVector(0.0, 0.0, 1500.0));
    TestEqual(
        TEXT("Existing mechanisms default to Slide"),
        static_cast<uint8>(Cue.WingPair.Mechanism.Kind),
        static_cast<uint8>(EInfinityMechanismKind::Slide));
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;

    FInfinityMechanismMotion& Motion = Cue.WingPair.Mechanism;
    Motion.PlaybackMode = EInfinityMotionPlaybackMode::Static;
    Motion.bTopFollowsMechanism = true;
    const auto SetLinearCurve = [&Motion](const float StartValue, const float EndValue)
    {
        const auto SetCurve = [StartValue, EndValue](FRuntimeFloatCurve& RuntimeCurve)
        {
            FRichCurve* Curve = RuntimeCurve.GetRichCurve();
            Curve->Reset();
            const FKeyHandle Start = Curve->AddKey(0.0f, StartValue);
            const FKeyHandle End = Curve->AddKey(1.0f, EndValue);
            Curve->SetKeyInterpMode(Start, RCIM_Linear);
            Curve->SetKeyInterpMode(End, RCIM_Linear);
        };
        SetCurve(Motion.LeftNormalizedCurve);
        SetCurve(Motion.RightNormalizedCurve);
        SetCurve(Motion.TopNormalizedCurve);
    };
    SetLinearCurve(0.0f, 1.0f);

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (!TestTrue(TEXT("Mechanism-kind fixture compiles"), Compiled.Passages.Num() == 1))
    {
        World->DestroyWorld(false);
        return false;
    }
    UMovieSceneInfinityPassageSection* Section =
        AttachManagedPassageSection(*Show, Compiled.Passages[0].PassageGuid);
    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(1.0);

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    const auto FindLeft = [Actor]() -> FInfinityMaterializedPanelRef*
    {
        return Actor->MaterializedPanels.FindByPredicate(
            [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Left; });
    };
    const auto FindRight = [Actor]() -> FInfinityMaterializedPanelRef*
    {
        return Actor->MaterializedPanels.FindByPredicate(
            [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Right; });
    };
    const auto FindTop = [Actor]() -> FInfinityMaterializedPanelRef*
    {
        return Actor->MaterializedPanels.FindByPredicate(
            [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Top; });
    };
    const auto ReadTransform = [](const FInfinityMaterializedPanelRef& Ref)
    {
        FTransform Transform;
        Ref.Component->GetInstanceTransform(Ref.InstanceIndex, Transform, true);
        return Transform;
    };

    Motion.Kind = EInfinityMechanismKind::Topple;
    Motion.MaxAngleDeg = 90.0;
    Motion.PhaseOffsetCycles = 0.0;
    if (!TestTrue(TEXT("Topple fixture materializes"), Actor->MaterializePassage()))
    {
        World->DestroyWorld(false);
        return false;
    }
    FInfinityMaterializedPanelRef* Left = FindLeft();
    FInfinityMaterializedPanelRef* Right = FindRight();
    FInfinityMaterializedPanelRef* Top = FindTop();
    if (!TestNotNull(TEXT("Topple Left instance exists"), Left)
        || !TestNotNull(TEXT("Topple Right instance exists"), Right)
        || !TestNotNull(TEXT("Topple Top instance exists"), Top))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Left Topple without a Hinge socket caches the bounds bottom centre"),
        Left->MechanismPivotLocal.GetLocation().Equals(FVector(0.0, 0.0, -50.0), 0.1));
    TestTrue(TEXT("Right Topple without a Hinge socket caches the bounds bottom centre"),
        Right->MechanismPivotLocal.GetLocation().Equals(FVector(0.0, 0.0, -50.0), 0.1));
    TestTrue(TEXT("Left socketless Topple chooses the card width as its hinge axis"),
        FMath::IsNearlyEqual(
            FMath::Abs(FVector::DotProduct(
                Left->MechanismPivotLocal.GetRotation().GetAxisX(),
                FVector::YAxisVector)),
            1.0,
            0.001));
    TestTrue(TEXT("Right socketless Topple chooses the card width as its hinge axis"),
        FMath::IsNearlyEqual(
            FMath::Abs(FVector::DotProduct(
                Right->MechanismPivotLocal.GetRotation().GetAxisX(),
                FVector::YAxisVector)),
            1.0,
            0.001));

    FTransform StationWorld;
    FTransform PairWorld;
    if (!TestTrue(
        TEXT("Topple fixture resolves the pair frame"),
        Actor->GetCuePlacementTransforms(Cue.CueGuid, StationWorld, PairWorld)))
    {
        World->DestroyWorld(false);
        return false;
    }
    const FVector DownstageWorld = -PairWorld.GetRotation().GetForwardVector().GetSafeNormal();
    TestTrue(TEXT("Right Topple fixture carries the 180 degree facing"),
        FVector::DotProduct(
            Right->BaseWorldTransform.GetRotation().GetForwardVector(),
            PairWorld.GetRotation().GetForwardVector()) < -0.999);
    const auto OldInwardSignDot = [](const FInfinityMaterializedPanelRef& Ref)
    {
        const FVector AxisScaled = (
            Ref.MechanismPivotLocal.GetRotation().GetAxisX()
            * Ref.BaseWorldTransform.GetScale3D()).GetSafeNormal();
        const FVector AxisWorld = Ref.BaseWorldTransform.GetRotation().RotateVector(AxisScaled);
        const FVector UpWorld = Ref.BaseWorldTransform.GetRotation().GetUpVector();
        return FVector::DotProduct(
            FVector::CrossProduct(AxisWorld, UpWorld),
            Ref.InwardWorldDirection);
    };
    TestTrue(TEXT("Old inward-based Left Topple sign reference is degenerate"),
        FMath::Abs(OldInwardSignDot(*Left)) < 1.e-3);
    TestTrue(TEXT("Old inward-based Right Topple sign reference is degenerate"),
        FMath::Abs(OldInwardSignDot(*Right)) < 1.e-3);

    TestTrue(TEXT("Topple progress zero evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    TestTrue(TEXT("Left Topple progress zero equals the base transform"),
        ReadTransform(*Left).Equals(Left->BaseWorldTransform, 0.001));
    TestTrue(TEXT("Right Topple progress zero equals the base transform"),
        ReadTransform(*Right).Equals(Right->BaseWorldTransform, 0.001));

    const FVector LocalTop(0.0, 0.0, 50.0);
    const FVector LeftRestTop = Left->BaseWorldTransform.TransformPosition(LocalTop);
    const FVector RightRestTop = Right->BaseWorldTransform.TransformPosition(LocalTop);
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Positive Topple evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FVector LeftPositiveTop = ReadTransform(*Left).TransformPosition(LocalTop);
    const FVector RightPositiveTop = ReadTransform(*Right).TransformPosition(LocalTop);
    TestTrue(TEXT("A positive Left Topple brings the card top to hinge height"),
        FMath::IsNearlyEqual(
            LeftPositiveTop.Z,
            Left->BaseWorldTransform.TransformPosition(Left->MechanismPivotLocal.GetLocation()).Z,
            0.1));
    TestTrue(TEXT("A positive Right Topple brings the card top to hinge height"),
        FMath::IsNearlyEqual(
            RightPositiveTop.Z,
            Right->BaseWorldTransform.TransformPosition(Right->MechanismPivotLocal.GetLocation()).Z,
            0.1));
    TestTrue(TEXT("Positive Left Topple falls one card height toward the camera"),
        FMath::IsNearlyEqual(
            FVector::DotProduct(LeftPositiveTop - LeftRestTop, DownstageWorld),
            1000.0,
            1.0));
    TestTrue(TEXT("Positive Right Topple falls one card height toward the camera"),
        FMath::IsNearlyEqual(
            FVector::DotProduct(RightPositiveTop - RightRestTop, DownstageWorld),
            1000.0,
            1.0));

    FTransform ExpectedTopSlide = Top->BaseWorldTransform;
    ExpectedTopSlide.AddToTranslation(Top->InwardWorldDirection * Motion.InwardTravelCm);
    TestTrue(TEXT("Top panel with Kind Topple retains Slide behaviour"),
        ReadTransform(*Top).Equals(ExpectedTopSlide, 0.001));

    Motion.MaxAngleDeg = -90.0;
    TestTrue(TEXT("Negative Topple evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FVector LeftNegativeTop = ReadTransform(*Left).TransformPosition(LocalTop);
    const FVector RightNegativeTop = ReadTransform(*Right).TransformPosition(LocalTop);
    TestTrue(TEXT("Negative Left Topple falls one card height away from the camera"),
        FMath::IsNearlyEqual(
            FVector::DotProduct(LeftNegativeTop - LeftRestTop, DownstageWorld),
            -1000.0,
            1.0));
    TestTrue(TEXT("Negative Right Topple falls one card height away from the camera"),
        FMath::IsNearlyEqual(
            FVector::DotProduct(RightNegativeTop - RightRestTop, DownstageWorld),
            -1000.0,
            1.0));

    Motion.MaxAngleDeg = 90.0;
    Motion.PhaseOffsetCycles = 0.0;
    Cue.WingPair.Left.bFlipImageHorizontally = false;
    Cue.WingPair.Left.LocalTransform.SetScale3D(ProductionCardScale);
    TestTrue(TEXT("Unmirrored Topple comparison fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    if (!TestNotNull(TEXT("Unmirrored Topple comparison instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }
    const FVector UnmirroredRestTop = Left->BaseWorldTransform.TransformPosition(LocalTop);
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Unmirrored comparison Topple evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FVector UnmirroredTop = ReadTransform(*Left).TransformPosition(LocalTop);
    const FVector UnmirroredTopDisplacement = UnmirroredTop - UnmirroredRestTop;

    Cue.WingPair.Left.bFlipImageHorizontally = true;
    Motion.PhaseOffsetCycles = 0.0;
    TestTrue(TEXT("Mirrored Topple fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    if (!TestNotNull(TEXT("Mirrored Topple instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Mirrored Topple base carries scale (0.1,-4,10)"),
        Left->BaseWorldTransform.GetScale3D().Equals(FVector(0.1, -4.0, 10.0), 0.0001));
    TestTrue(TEXT("Mirrored Topple progress zero evaluates"),
        Actor->EvaluateMechanismsAtMasterFrame(0));
    // Compare matrices, not FTransform components: the ISM stores an FMatrix,
    // and reading a mirrored instance back decomposes the mirror onto X
    // (TTransform::SetFromMatrix), so (0.1,-4,10) returns as (-0.1,4,10) with
    // a different rotation. Same matrix, so component-wise Equals is false.
    const FTransform MirroredZero = ReadTransform(*Left);
    if (!TestTrue(TEXT("Mirrored Topple progress zero equals the base transform"),
        MirroredZero.ToMatrixWithScale().Equals(Left->BaseWorldTransform.ToMatrixWithScale(), 0.0001)))
    {
        AddInfo(FString::Printf(TEXT("Mirrored zero read back %s; base %s"),
            *MirroredZero.ToString(), *Left->BaseWorldTransform.ToString()));
    }
    const FVector MirroredRestTop = Left->BaseWorldTransform.TransformPosition(LocalTop);
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Mirrored positive Topple evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FVector MirroredTop = ReadTransform(*Left).TransformPosition(LocalTop);
    const FVector MirroredTopDisplacement = MirroredTop - MirroredRestTop;
    TestTrue(TEXT("Mirrored positive Topple still falls toward the camera"),
        FVector::DotProduct(MirroredTopDisplacement, DownstageWorld) > 0.0);
    TestTrue(TEXT("Mirrored and unmirrored positive Topple fall in the same world direction"),
        MirroredTopDisplacement.Equals(UnmirroredTopDisplacement, 0.01));

    const FVector NonUniformScale(0.2, 3.0, 0.5);
    const FVector RigidityPointA(-20.0, 10.0, -35.0);
    const FVector RigidityPointB(30.0, -25.0, 40.0);
    const double ScaledPointDistance = ((RigidityPointB - RigidityPointA) * NonUniformScale).Size();
    Cue.WingPair.Left.bFlipImageHorizontally = false;
    Cue.WingPair.Left.LocalTransform.SetScale3D(NonUniformScale);
    Motion.Kind = EInfinityMechanismKind::Topple;
    Motion.MaxAngleDeg = 45.0;
    Motion.PhaseOffsetCycles = 0.0;
    TestTrue(TEXT("Non-uniform Topple fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    if (!TestNotNull(TEXT("Non-uniform Topple instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Non-uniform Topple base carries scale (0.2,3,0.5)"),
        Left->BaseWorldTransform.GetScale3D().Equals(NonUniformScale, 0.0001));
    TestTrue(TEXT("Non-uniform Topple progress zero evaluates"),
        Actor->EvaluateMechanismsAtMasterFrame(0));
    TestTrue(TEXT("Non-uniform Topple progress zero equals the base transform"),
        ReadTransform(*Left).Equals(Left->BaseWorldTransform, 0.0001));
    const FVector TopplePivotLocal = Left->MechanismPivotLocal.GetLocation();
    const FVector TopplePivotWorld = Left->BaseWorldTransform.TransformPosition(TopplePivotLocal);
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Non-uniform 45 degree Topple evaluates"),
        Actor->EvaluateMechanismsAtMasterFrame(0));
    const FTransform NonUniformTopple = ReadTransform(*Left);
    TestTrue(TEXT("Non-uniform Topple keeps the scaled pivot invariant"),
        NonUniformTopple.TransformPosition(TopplePivotLocal).Equals(TopplePivotWorld, 0.01));
    TestTrue(TEXT("Non-uniform Topple remains rigid after authored scale"),
        FMath::IsNearlyEqual(
            FVector::Distance(
                NonUniformTopple.TransformPosition(RigidityPointA),
                NonUniformTopple.TransformPosition(RigidityPointB)),
            ScaledPointDistance,
            0.01));

    Motion.Kind = EInfinityMechanismKind::Turn;
    Motion.MaxAngleDeg = 90.0;
    Motion.PhaseOffsetCycles = 0.0;
    TestTrue(TEXT("Non-uniform Turn fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    if (!TestNotNull(TEXT("Non-uniform Turn instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Non-uniform Turn progress zero evaluates"),
        Actor->EvaluateMechanismsAtMasterFrame(0));
    TestTrue(TEXT("Non-uniform Turn progress zero equals the base transform"),
        ReadTransform(*Left).Equals(Left->BaseWorldTransform, 0.0001));
    const FVector TurnPivotLocal = Left->MechanismPivotLocal.GetLocation();
    const FVector TurnPivotWorld = Left->BaseWorldTransform.TransformPosition(TurnPivotLocal);
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Non-uniform 90 degree Turn evaluates"),
        Actor->EvaluateMechanismsAtMasterFrame(0));
    const FTransform NonUniformTurn = ReadTransform(*Left);
    TestTrue(TEXT("Non-uniform Turn keeps the scaled pivot invariant"),
        NonUniformTurn.TransformPosition(TurnPivotLocal).Equals(TurnPivotWorld, 0.01));
    TestTrue(TEXT("Non-uniform Turn remains rigid after authored scale"),
        FMath::IsNearlyEqual(
            FVector::Distance(
                NonUniformTurn.TransformPosition(RigidityPointA),
                NonUniformTurn.TransformPosition(RigidityPointB)),
            ScaledPointDistance,
            0.01));

    Cue.WingPair.Left.LocalTransform.SetScale3D(FVector::OneVector);

    Motion.Kind = EInfinityMechanismKind::Turn;
    Motion.MaxAngleDeg = 180.0;
    Motion.PhaseOffsetCycles = 1.0;
    TestTrue(TEXT("Turn fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    if (!TestNotNull(TEXT("Turn Left instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Turn without a Pivot socket caches the bounds centre"),
        Left->MechanismPivotLocal.GetLocation().Equals(FVector::ZeroVector, 0.1));
    TestTrue(TEXT("Turn bounds fallback uses local up as its axis"),
        Left->MechanismPivotLocal.GetRotation().GetAxisX().Equals(FVector::ZAxisVector, 0.001));

    // A transient mesh with an authored socket is impractical in this fixture.
    // Substitute a socket-equivalent cached local pivot to exercise the exact
    // pivot math independently of the bounds fallback above.
    const FVector ExplicitPivotLocal(10.0, 20.0, 0.0);
    Left->MechanismPivotLocal = FTransform(
        FVector::ZAxisVector.ToOrientationQuat(), ExplicitPivotLocal);
    const FVector BasePivotWorld = Left->BaseWorldTransform.TransformPosition(ExplicitPivotLocal);
    const FVector BaseFrontNormal =
        Left->BaseWorldTransform.TransformVectorNoScale(FVector::XAxisVector).GetSafeNormal();
    TestTrue(TEXT("Turn evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FTransform Turned = ReadTransform(*Left);
    TestTrue(TEXT("Turn keeps the explicit cached pivot invariant"),
        Turned.TransformPosition(ExplicitPivotLocal).Equals(BasePivotWorld, 0.01));
    TestTrue(TEXT("A 180 degree Turn reverses the front-face normal"),
        Turned.TransformVectorNoScale(FVector::XAxisVector).GetSafeNormal().Equals(
            -BaseFrontNormal, 0.001));

    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(0.5);
    TestTrue(TEXT("Turn angle modulation evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FVector HalfTurnNormal = ReadTransform(*Left)
        .TransformVectorNoScale(FVector::XAxisVector).GetSafeNormal();
    TestTrue(TEXT("Wing travel scale modulates Turn angle"),
        FMath::IsNearlyZero(FVector::DotProduct(HalfTurnNormal, BaseFrontNormal), 0.001));
    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(1.0);

    Motion.Kind = EInfinityMechanismKind::Trap;
    Motion.InwardTravelCm = 100.0;
    Motion.PhaseOffsetCycles = 0.5;
    SetLinearCurve(0.0f, 1.0f);
    TestTrue(TEXT("Trap fixture materializes"), Actor->MaterializePassage());
    Left = FindLeft();
    Top = FindTop();
    if (!TestNotNull(TEXT("Trap Left instance exists"), Left)
        || !TestNotNull(TEXT("Trap Top instance exists"), Top))
    {
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Positive Trap evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    TestTrue(TEXT("Trap progress 0.5 rises 50 cm along base up"),
        FMath::IsNearlyEqual(
            ReadTransform(*Left).GetLocation().Z - Left->BaseWorldTransform.GetLocation().Z,
            50.0,
            0.01));
    TestTrue(TEXT("Trap still applies to a Top panel"),
        FMath::IsNearlyEqual(
            ReadTransform(*Top).GetLocation().Z - Top->BaseWorldTransform.GetLocation().Z,
            50.0,
            0.01));
    SetLinearCurve(0.0f, -1.0f);
    TestTrue(TEXT("Negative Trap evaluates"), Actor->EvaluateMechanismsAtMasterFrame(0));
    TestTrue(TEXT("Trap progress -0.5 sinks 50 cm along base up"),
        FMath::IsNearlyEqual(
            ReadTransform(*Left).GetLocation().Z - Left->BaseWorldTransform.GetLocation().Z,
            -50.0,
            0.01));
    TestTrue(TEXT("Negative Trap still applies to a Top panel"),
        FMath::IsNearlyEqual(
            ReadTransform(*Top).GetLocation().Z - Top->BaseWorldTransform.GetLocation().Z,
            -50.0,
            0.01));

    SetLinearCurve(0.0f, 1.0f);
    Motion.PlaybackMode = EInfinityMotionPlaybackMode::OneShot;
    Motion.CycleRateHz = 1.0;
    Motion.PhaseOffsetCycles = 0.0;
    TestTrue(TEXT("Continuity frame A evaluates"), Actor->EvaluateMechanismsAtMasterFrame(12000));
    const FTransform FrameA = ReadTransform(*Left);
    TestTrue(TEXT("Continuity frame B evaluates"), Actor->EvaluateMechanismsAtMasterFrame(24000));
    FTransform FrameBPrevious;
    TestTrue(TEXT("Continuity frame B exposes a previous transform"),
        Left->Component->GetInstancePrevTransform(Left->InstanceIndex, FrameBPrevious, true));
    TestTrue(TEXT("Continuity frame B records frame A as its previous transform"),
        FrameBPrevious.Equals(FrameA, 0.01));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageWingTravelModulationEvaluationTest,
    "InfinityStage.Mechanism.WingTravelScaleModulatesMaterializedPanels",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageWingTravelModulationEvaluationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Cube;
    Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
    Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;
    Show->ApplyTravelingUndulation({ Cue.CueGuid }, 0.25, 100.0, 0.0);

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (!TestTrue(TEXT("Modulation fixture compiles"), Compiled.Passages.Num() == 1))
    {
        World->DestroyWorld(false);
        return false;
    }
    UMovieSceneInfinityPassageSection* Section =
        AttachManagedPassageSection(*Show, Compiled.Passages[0].PassageGuid);

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Modulation fixture materializes"), Actor->MaterializePassage());
    const FInfinityMaterializedPanelRef* Left = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Left; });
    if (!TestNotNull(TEXT("Modulated Left instance exists"), Left))
    {
        World->DestroyWorld(false);
        return false;
    }

    const auto LeftYAtFrame = [&](const int32 Frame)
    {
        Actor->EvaluateMechanismsAtMasterFrame(Frame);
        FTransform Transform;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, Transform, true);
        return Transform.GetLocation().Y;
    };

    // A neutral section must reproduce the unmodulated 100 cm crest exactly.
    const double RestY = LeftYAtFrame(0);
    const double NeutralCrestY = LeftYAtFrame(48000);
    TestTrue(
        TEXT("Neutral Wing channels preserve the authored 100 cm travel"),
        FMath::IsNearlyEqual(NeutralCrestY - RestY, 100.0, 0.01));

    Section->GetCameraChannel(EInfinityPassageCameraChannel::WingInwardTravelScale)->SetDefault(0.4);
    const double ScaledCrestY = LeftYAtFrame(48000);
    TestTrue(
        TEXT("Travel scale 0.4 reduces the crest to 40 cm"),
        FMath::IsNearlyEqual(ScaledCrestY - RestY, 40.0, 0.01));

    // The whole point of integrating the rate: arriving at a frame by a
    // different path must produce the same pose.
    FMovieSceneDoubleChannel* Rate =
        Section->GetCameraChannel(EInfinityPassageCameraChannel::WingCycleRateScale);
    Rate->Reset();
    Rate->AddLinearKey(FFrameNumber(0), 0.5);
    Rate->AddLinearKey(FFrameNumber(96000), 2.5);
    const double SequentialY = [&]()
    {
        for (int32 Frame = 0; Frame <= 48000; Frame += 8000)
        {
            LeftYAtFrame(Frame);
        }
        FTransform Transform;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, Transform, true);
        return Transform.GetLocation().Y;
    }();
    LeftYAtFrame(96000);
    const double SeekedY = LeftYAtFrame(48000);
    TestTrue(
        TEXT("Keyed rate scale stays history independent under seek"),
        FMath::IsNearlyEqual(SequentialY, SeekedY, 0.01));

    World->DestroyWorld(false);
    return true;
}





IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageMechanismSoundTest,
    "InfinityStage.StageContent.MechanismSoundSelectionIsDeterministic",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageMechanismSoundTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    TArray<FGuid> Cues;
    for (int32 Index = 0; Index < 6; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cues.Add(Cue.CueGuid);
    }
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    Actor->PassageGuid = Show->PassageSettings[0].PassageGuid;

    FInfinityMechanismSoundSet& Set = Show->PassageSettings[0].MechanismSound;
    TestEqual(TEXT("Disabled by default, so nothing is voiced"), Actor->GetMechanismSoundIndexForCue(Cues[0]), INDEX_NONE);

    Set.bEnabled = true;
    TestEqual(TEXT("An empty set voices nothing"), Actor->GetMechanismSoundIndexForCue(Cues[0]), INDEX_NONE);

    Set.Sounds.SetNum(3);
    Set.Policy = EInfinityMechanismSoundPolicy::RoundRobin;
    for (int32 Index = 0; Index < Cues.Num(); ++Index)
    {
        TestEqual(
            TEXT("Round robin follows Passage order"),
            Actor->GetMechanismSoundIndexForCue(Cues[Index]),
            Index % 3);
    }

    // The whole point of stable seeding: repeated queries, and queries after a
    // reorder of unrelated state, must return the same sound for the same wing.
    Set.Policy = EInfinityMechanismSoundPolicy::StableRandom;
    TArray<int32> FirstPass;
    for (const FGuid& Cue : Cues)
    {
        const int32 Index = Actor->GetMechanismSoundIndexForCue(Cue);
        TestTrue(TEXT("Stable random stays in range"), Index >= 0 && Index < 3);
        FirstPass.Add(Index);
    }
    for (int32 Index = 0; Index < Cues.Num(); ++Index)
    {
        TestEqual(
            TEXT("Stable random repeats exactly"),
            Actor->GetMechanismSoundIndexForCue(Cues[Index]),
            FirstPass[Index]);
    }

    // A muted pair is silent without disabling the Passage set.
    Show->Cues[2].WingPair.bMuteMechanismSound = true;
    TestEqual(TEXT("A muted pair is silent"), Actor->GetMechanismSoundIndexForCue(Cues[2]), INDEX_NONE);
    TestEqual(
        TEXT("Muting one pair leaves the others voiced"),
        Actor->GetMechanismSoundIndexForCue(Cues[3]),
        FirstPass[3]);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueAttachmentTest,
    "InfinityStage.StageContent.AttachmentsSurviveRespacing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueAttachmentTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
        Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
        Cue.WingPair.GapToNextCm = 500.0;
    }
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;

    // A light bolted to the second pair's Left panel, offset up and outward.
    const FGuid TargetCue = Show->Cues[1].CueGuid;
    FInfinityCueAttachment& Light = Show->Cues[1].WingPair.Attachments.AddDefaulted_GetRef();
    Light.AttachmentGuid = FGuid::NewGuid();
    Light.Kind = EInfinityAttachmentKind::Light;
    Light.Anchor = EInfinityAttachmentAnchor::LeftPanel;
    Light.RelativeTransform.SetTranslation(FVector(0.0, 0.0, 400.0));
    const FGuid LightGuid = Light.AttachmentGuid;

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Attachment fixture materializes"), Actor->MaterializePassage());

    FTransform Before;
    TestTrue(
        TEXT("Attachment resolves to a world transform"),
        Actor->GetAttachmentWorldTransform(TargetCue, LightGuid, Before));

    // Re-space the Passage, which is exactly what a music change does. The
    // attachment must follow its wing rather than stay at a stale world point.
    Show->Cues[0].WingPair.GapToNextCm = 1500.0;
    TestTrue(TEXT("Re-spaced Passage materializes"), Actor->MaterializePassage());
    FTransform After;
    TestTrue(
        TEXT("Attachment still resolves after re-spacing"),
        Actor->GetAttachmentWorldTransform(TargetCue, LightGuid, After));
    TestTrue(
        TEXT("Attachment moved with its wing"),
        !After.GetLocation().Equals(Before.GetLocation(), 1.0));

    // Its offset from the panel is what must be preserved, not its world point.
    const FInfinityMaterializedPanelRef* Panel = Actor->MaterializedPanels.FindByPredicate(
        [TargetCue](const FInfinityMaterializedPanelRef& Ref)
        { return Ref.CueGuid == TargetCue && Ref.Side == EInfinityPanelSide::Left; });
    if (TestNotNull(TEXT("Left panel exists"), Panel))
    {
        FTransform PanelWorld;
        Panel->Component->GetInstanceTransform(Panel->InstanceIndex, PanelWorld, true);
        const FVector Offset = After.GetLocation() - PanelWorld.GetLocation();
        TestTrue(
            TEXT("Relative offset from the panel is preserved"),
            FMath::IsNearlyEqual(Offset.Z, 400.0, 1.0));
    }


    // Pair-centre anchoring must track the live midpoint, so it closes in as the
    // panels travel inward rather than sitting at the rest centre.
    FInfinityCueAttachment& Centre = Show->Cues[1].WingPair.Attachments.AddDefaulted_GetRef();
    Centre.AttachmentGuid = FGuid::NewGuid();
    Centre.Kind = EInfinityAttachmentKind::Prop;
    Centre.Anchor = EInfinityAttachmentAnchor::PairCentre;
    const FGuid CentreGuid = Centre.AttachmentGuid;
    TestTrue(TEXT("Re-materialize for pair centre"), Actor->MaterializePassage());

    FTransform CentreWorld;
    if (TestTrue(
        TEXT("Pair centre resolves"),
        Actor->GetAttachmentWorldTransform(TargetCue, CentreGuid, CentreWorld)))
    {
        const FInfinityMaterializedPanelRef* L = Actor->MaterializedPanels.FindByPredicate(
            [TargetCue](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == TargetCue && Ref.Side == EInfinityPanelSide::Left; });
        const FInfinityMaterializedPanelRef* R = Actor->MaterializedPanels.FindByPredicate(
            [TargetCue](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == TargetCue && Ref.Side == EInfinityPanelSide::Right; });
        if (L && R)
        {
            FTransform LW;
            FTransform RW;
            L->Component->GetInstanceTransform(L->InstanceIndex, LW, true);
            R->Component->GetInstanceTransform(R->InstanceIndex, RW, true);
            TestTrue(
                TEXT("Pair centre sits midway between the panels"),
                CentreWorld.GetLocation().Equals((LW.GetLocation() + RW.GetLocation()) * 0.5, 1.0));
        }
    }

    // An unknown attachment must fail cleanly rather than assert.
    FTransform Unused;
    TestFalse(
        TEXT("Unknown attachment resolves to nothing"),
        Actor->GetAttachmentWorldTransform(TargetCue, FGuid::NewGuid(), Unused));


    // Placement is the point: an enabled mesh attachment must spawn an actor the
    // Passage owns, and a re-materialize must not accumulate duplicates.
    FInfinityCueAttachment& Prop = Show->Cues[0].WingPair.Attachments.AddDefaulted_GetRef();
    Prop.AttachmentGuid = FGuid::NewGuid();
    Prop.Kind = EInfinityAttachmentKind::Prop;
    Prop.Anchor = EInfinityAttachmentAnchor::Station;
    Prop.Mesh = Cube;
    TestTrue(TEXT("Materialize with a prop"), Actor->MaterializePassage());
    const int32 FirstCount = Actor->ManagedAttachmentActors.Num();
    TestTrue(TEXT("Prop actor was spawned"), FirstCount >= 1);
    TestTrue(TEXT("Re-materialize with a prop"), Actor->MaterializePassage());
    TestEqual(TEXT("Re-materializing does not accumulate actors"), Actor->ManagedAttachmentActors.Num(), FirstCount);

    // Disabling must remove it rather than leave an orphan in the level.
    Show->Cues[0].WingPair.Attachments[0].bEnabled = false;
    TestTrue(TEXT("Materialize with the prop disabled"), Actor->MaterializePassage());
    TestEqual(TEXT("Disabled attachments are not placed"), Actor->ManagedAttachmentActors.Num(), FirstCount - 1);

    Actor->ClearMaterializedPassage();
    TestEqual(TEXT("Clearing removes owned attachment actors"), Actor->ManagedAttachmentActors.Num(), 0);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageNativeLightAttachmentTest,
    "InfinityStage.StageContent.NativeLightTypesAndParametersMaterialize",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageNativeLightAttachmentTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Cube;

    FInfinityCueAttachment& Spot = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Spot.AttachmentGuid = FGuid::NewGuid();
    Spot.Kind = EInfinityAttachmentKind::Light;
    Spot.Lighting.Type = EInfinityStageLightType::Spot;
    Spot.Lighting.IntensityUnits = EInfinityStageLightIntensityUnits::Candelas;
    Spot.Lighting.Intensity = 1234.0f;
    Spot.Lighting.AttenuationRadiusCm = 3210.0f;
    Spot.Lighting.bUseTemperature = true;
    Spot.Lighting.TemperatureKelvin = 4200.0f;
    Spot.Lighting.InnerConeAngleDegrees = 11.0f;
    Spot.Lighting.OuterConeAngleDegrees = 37.0f;
    Spot.Lighting.bLightingChannel0 = false;
    Spot.Lighting.bLightingChannel1 = true;

    FInfinityCueAttachment& Rect = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Rect.AttachmentGuid = FGuid::NewGuid();
    Rect.Kind = EInfinityAttachmentKind::Light;
    Rect.Lighting.Type = EInfinityStageLightType::Rect;
    Rect.Lighting.Intensity = 2345.0f;
    Rect.Lighting.RectSourceWidthCm = 240.0f;
    Rect.Lighting.RectSourceHeightCm = 80.0f;
    Rect.Lighting.RectBarnDoorAngleDegrees = 71.0f;
    Rect.Lighting.RectBarnDoorLengthCm = 33.0f;

    FInfinityCueAttachment& Point = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Point.AttachmentGuid = FGuid::NewGuid();
    Point.Kind = EInfinityAttachmentKind::Light;
    Point.Lighting.Type = EInfinityStageLightType::Point;
    Point.Lighting.Intensity = 3456.0f;
    Point.Lighting.bUseInverseSquaredFalloff = false;
    Point.Lighting.LightFalloffExponent = 6.0f;
    Point.Lighting.SourceRadiusCm = 17.0f;
    Point.Lighting.SoftSourceRadiusCm = 9.0f;
    Point.Lighting.SourceLengthCm = 44.0f;

    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Native-light fixture materializes"), Actor->MaterializePassage());
    TestEqual(TEXT("All three native light actors spawn"), Actor->ManagedAttachmentActors.Num(), 3);

    USpotLightComponent* SpotComponent = nullptr;
    URectLightComponent* RectComponent = nullptr;
    UPointLightComponent* PointComponent = nullptr;
    for (AActor* Spawned : Actor->ManagedAttachmentActors)
    {
        TestTrue(TEXT("Generated light is parented to its Passage"), Spawned->GetAttachParentActor() == Actor);
        if (USpotLightComponent* SpotCandidate = Spawned->FindComponentByClass<USpotLightComponent>())
        {
            SpotComponent = SpotCandidate;
        }
        else if (URectLightComponent* RectCandidate = Spawned->FindComponentByClass<URectLightComponent>())
        {
            RectComponent = RectCandidate;
        }
        else if (UPointLightComponent* PointCandidate = Spawned->FindComponentByClass<UPointLightComponent>())
        {
            PointComponent = PointCandidate;
        }
    }

    if (TestNotNull(TEXT("Spot type creates a Spot Light Component"), SpotComponent))
    {
        TestEqual(TEXT("Spot intensity is applied"), SpotComponent->Intensity, 1234.0f);
        TestEqual(TEXT("Spot attenuation is applied"), SpotComponent->AttenuationRadius, 3210.0f);
        TestEqual(TEXT("Spot inner cone is applied"), SpotComponent->InnerConeAngle, 11.0f);
        TestEqual(TEXT("Spot outer cone is applied"), SpotComponent->OuterConeAngle, 37.0f);
        TestTrue(TEXT("Spot temperature is enabled"), SpotComponent->bUseTemperature);
        TestEqual(TEXT("Spot temperature is applied"), SpotComponent->Temperature, 4200.0f);
        TestFalse(TEXT("Lighting channel 0 is disabled"), SpotComponent->LightingChannels.bChannel0);
        TestTrue(TEXT("Lighting channel 1 is enabled"), SpotComponent->LightingChannels.bChannel1);
    }
    if (TestNotNull(TEXT("Rect type creates a Rect Light Component"), RectComponent))
    {
        TestEqual(TEXT("Rect intensity is applied"), RectComponent->Intensity, 2345.0f);
        TestEqual(TEXT("Rect width is applied"), RectComponent->SourceWidth, 240.0f);
        TestEqual(TEXT("Rect height is applied"), RectComponent->SourceHeight, 80.0f);
        TestEqual(TEXT("Rect barn-door angle is applied"), RectComponent->BarnDoorAngle, 71.0f);
        TestEqual(TEXT("Rect barn-door length is applied"), RectComponent->BarnDoorLength, 33.0f);
    }
    if (TestNotNull(TEXT("Point type creates a Point Light Component"), PointComponent))
    {
        TestEqual(TEXT("Point intensity is applied"), PointComponent->Intensity, 3456.0f);
        TestFalse(TEXT("Point inverse-square falloff is applied"), PointComponent->bUseInverseSquaredFalloff);
        TestEqual(TEXT("Point falloff exponent is applied"), PointComponent->LightFalloffExponent, 6.0f);
        TestEqual(TEXT("Point source radius is applied"), PointComponent->SourceRadius, 17.0f);
        TestEqual(TEXT("Point soft-source radius is applied"), PointComponent->SoftSourceRadius, 9.0f);
        TestEqual(TEXT("Point source length is applied"), PointComponent->SourceLength, 44.0f);
    }

    // Simulate an older save or editor undo losing one ownership-array entry
    // while the tagged generated actor remains parented beneath the Passage.
    // Rematerialization must recover and destroy it before spawning replacements.
    AActor* OrphanedBeforeRematerialize = Actor->ManagedAttachmentActors[0];
    Actor->ManagedAttachmentActors.RemoveAt(0);
    TestEqual(TEXT("Fixture simulates one untracked generated light"), Actor->ManagedAttachmentActors.Num(), 2);
    TestEqual(TEXT("Attachment-only rematerialization still places three lights"), Actor->MaterializeAttachments(), 3);
    TestFalse(TEXT("Rematerialization destroys the untracked prior light"), IsValid(OrphanedBeforeRematerialize));
    TestEqual(TEXT("Rematerialization owns exactly the authoritative three lights"),
        Actor->ManagedAttachmentActors.Num(), 3);

    // Clear uses the same recovery path, so a user can safely clean a level that
    // already contains stale generated light actors.
    AActor* OrphanedBeforeClear = Actor->ManagedAttachmentActors[0];
    Actor->ManagedAttachmentActors.RemoveAt(0);
    Actor->ClearMaterializedPassage();
    TestFalse(TEXT("Clearing destroys an untracked generated light"), IsValid(OrphanedBeforeClear));
    TestEqual(TEXT("Clearing removes all generated lights"), Actor->ManagedAttachmentActors.Num(), 0);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageDeletedMaterializedLightWritesBackTest,
    "InfinityStage.StageContent.DeletedMaterializedLightWritesBack",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageDeletedMaterializedLightWritesBackTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.Label = FText::FromString(TEXT("Deletion Template"));
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();

    FInfinityCueAttachment& Deleted = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Deleted.AttachmentGuid = FGuid::NewGuid();
    Deleted.Kind = EInfinityAttachmentKind::Light;
    Deleted.Label = FText::FromString(TEXT("Delete Me"));
    const FGuid DeletedGuid = Deleted.AttachmentGuid;

    FInfinityCueAttachment& Kept = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Kept.AttachmentGuid = FGuid::NewGuid();
    Kept.Kind = EInfinityAttachmentKind::Light;
    Kept.Label = FText::FromString(TEXT("Keep Me"));
    const FGuid KeptGuid = Kept.AttachmentGuid;

    FInfinityCueAttachment& Prop = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Prop.AttachmentGuid = FGuid::NewGuid();
    Prop.Kind = EInfinityAttachmentKind::Prop;
    Prop.Label = FText::FromString(TEXT("Keep Prop"));
    const FGuid PropGuid = Prop.AttachmentGuid;

    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    APointLight* DeletedActor = World->SpawnActor<APointLight>();
    DeletedActor->AttachToActor(Passage, FAttachmentTransformRules::KeepWorldTransform);
    DeletedActor->Tags.Add(FName(*FString::Printf(
        TEXT("InfinityStage.Attachment.%s|%s"),
        *Cue.CueGuid.ToString(EGuidFormats::Digits),
        *DeletedGuid.ToString(EGuidFormats::Digits))));
    Passage->ManagedAttachmentActors.Add(DeletedActor);

    GEngine->BroadcastLevelActorDeleted(DeletedActor);

    TestFalse(TEXT("Deleted materialized light is removed from the Show"),
        Cue.WingPair.Attachments.ContainsByPredicate([DeletedGuid](const FInfinityCueAttachment& Attachment)
        { return Attachment.AttachmentGuid == DeletedGuid; }));
    TestTrue(TEXT("Other template light remains"),
        Cue.WingPair.Attachments.ContainsByPredicate([KeptGuid](const FInfinityCueAttachment& Attachment)
        { return Attachment.AttachmentGuid == KeptGuid; }));
    TestTrue(TEXT("Non-light attachment remains"),
        Cue.WingPair.Attachments.ContainsByPredicate([PropGuid](const FInfinityCueAttachment& Attachment)
        { return Attachment.AttachmentGuid == PropGuid; }));
    TestFalse(TEXT("Deleted actor is removed from Passage ownership"),
        Passage->ManagedAttachmentActors.Contains(DeletedActor));

    DeletedActor->Destroy();
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightReplicationTest,
    "InfinityStage.StageContent.LightReplicationPreservesOtherAttachments",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightReplicationTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    TArray<FGuid> CueGuids;
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Label = FText::FromString(FString::Printf(TEXT("Replication Wing %d"), Index + 1));
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        CueGuids.Add(Cue.CueGuid);
    }

    FInfinityCueAttachment& SourceSpot = Show->Cues[0].WingPair.Attachments.AddDefaulted_GetRef();
    SourceSpot.AttachmentGuid = FGuid::NewGuid();
    SourceSpot.Kind = EInfinityAttachmentKind::Light;
    SourceSpot.Anchor = EInfinityAttachmentAnchor::LeftPanel;
    SourceSpot.Label = FText::FromString(TEXT("Replication Wing 1 Key"));
    SourceSpot.Lighting.Type = EInfinityStageLightType::Spot;
    SourceSpot.Lighting.Intensity = 6789.0f;
    SourceSpot.Lighting.Color = FLinearColor(0.2f, 0.4f, 0.8f);
    SourceSpot.Lighting.OuterConeAngleDegrees = 29.0f;

    FInfinityCueAttachment& SourceRect = Show->Cues[0].WingPair.Attachments.AddDefaulted_GetRef();
    SourceRect.AttachmentGuid = FGuid::NewGuid();
    SourceRect.Kind = EInfinityAttachmentKind::Light;
    SourceRect.Anchor = EInfinityAttachmentAnchor::RightPanel;
    SourceRect.Label = FText::FromString(TEXT("Replication Wing 1 Fill"));
    SourceRect.Lighting.Type = EInfinityStageLightType::Rect;
    SourceRect.Lighting.RectSourceWidthCm = 333.0f;

    FInfinityCueAttachment& SourceProp = Show->Cues[0].WingPair.Attachments.AddDefaulted_GetRef();
    SourceProp.AttachmentGuid = FGuid::NewGuid();
    SourceProp.Kind = EInfinityAttachmentKind::Prop;

    FInfinityCueAttachment& ExistingTargetLight = Show->Cues[1].WingPair.Attachments.AddDefaulted_GetRef();
    ExistingTargetLight.AttachmentGuid = FGuid::NewGuid();
    ExistingTargetLight.Kind = EInfinityAttachmentKind::Light;
    ExistingTargetLight.Lighting.Type = EInfinityStageLightType::Point;
    const FGuid StableTargetLightGuid = ExistingTargetLight.AttachmentGuid;

    FInfinityCueAttachment& TargetProp = Show->Cues[1].WingPair.Attachments.AddDefaulted_GetRef();
    TargetProp.AttachmentGuid = FGuid::NewGuid();
    TargetProp.Kind = EInfinityAttachmentKind::Prop;
    const FGuid TargetPropGuid = TargetProp.AttachmentGuid;

    FInfinityCueAttachment& TargetTrigger = Show->Cues[2].WingPair.Attachments.AddDefaulted_GetRef();
    TargetTrigger.AttachmentGuid = FGuid::NewGuid();
    TargetTrigger.Kind = EInfinityAttachmentKind::AnimationTrigger;
    const FGuid TargetTriggerGuid = TargetTrigger.AttachmentGuid;

    TestEqual(TEXT("Two destination cues are replicated"), Show->ReplicateLightAttachments(CueGuids[0], CueGuids), 2);

    TSet<FGuid> DestinationLightGuids;
    for (int32 CueIndex = 1; CueIndex < 3; ++CueIndex)
    {
        const FInfinityShowCue& Target = Show->Cues[CueIndex];
        TArray<const FInfinityCueAttachment*> Lights;
        for (const FInfinityCueAttachment& Attachment : Target.WingPair.Attachments)
        {
            if (Attachment.Kind == EInfinityAttachmentKind::Light)
            {
                Lights.Add(&Attachment);
                TestTrue(TEXT("Destination light identity is valid"), Attachment.AttachmentGuid.IsValid());
                TestFalse(TEXT("Destination identity differs from source spot"), Attachment.AttachmentGuid == SourceSpot.AttachmentGuid);
                TestFalse(TEXT("Destination identity differs from source rect"), Attachment.AttachmentGuid == SourceRect.AttachmentGuid);
                DestinationLightGuids.Add(Attachment.AttachmentGuid);
            }
        }
        TestEqual(TEXT("Each destination receives both template lights"), Lights.Num(), 2);
        if (Lights.Num() == 2)
        {
            TestEqual(TEXT("Spot type replicates"), Lights[0]->Lighting.Type, EInfinityStageLightType::Spot);
            TestEqual(TEXT("Spot intensity replicates"), Lights[0]->Lighting.Intensity, 6789.0f);
            TestEqual(TEXT("Spot cone replicates"), Lights[0]->Lighting.OuterConeAngleDegrees, 29.0f);
            TestEqual(TEXT("Rect type replicates"), Lights[1]->Lighting.Type, EInfinityStageLightType::Rect);
            TestEqual(TEXT("Rect width replicates"), Lights[1]->Lighting.RectSourceWidthCm, 333.0f);
            TestTrue(TEXT("Replicated labels follow the destination cue"),
                Lights[0]->Label.ToString().StartsWith(Target.Label.ToString()));
        }
    }
    TestEqual(TEXT("Every destination light has a distinct identity"), DestinationLightGuids.Num(), 4);
    TestTrue(TEXT("Target prop is preserved"), Show->Cues[1].WingPair.Attachments.ContainsByPredicate(
        [TargetPropGuid](const FInfinityCueAttachment& Attachment) { return Attachment.AttachmentGuid == TargetPropGuid; }));
    TestTrue(TEXT("Target trigger is preserved"), Show->Cues[2].WingPair.Attachments.ContainsByPredicate(
        [TargetTriggerGuid](const FInfinityCueAttachment& Attachment) { return Attachment.AttachmentGuid == TargetTriggerGuid; }));
    TestTrue(TEXT("First destination light keeps its existing identity"), Show->Cues[1].WingPair.Attachments.ContainsByPredicate(
        [StableTargetLightGuid](const FInfinityCueAttachment& Attachment)
        {
            return Attachment.Kind == EInfinityAttachmentKind::Light
                && Attachment.AttachmentGuid == StableTargetLightGuid;
        }));

    TArray<FGuid> BeforeReapply;
    for (const FInfinityCueAttachment& Attachment : Show->Cues[1].WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Light)
        {
            BeforeReapply.Add(Attachment.AttachmentGuid);
        }
    }
    TestEqual(TEXT("Reapplying still targets both destinations"), Show->ReplicateLightAttachments(CueGuids[0], CueGuids), 2);
    TArray<FGuid> AfterReapply;
    for (const FInfinityCueAttachment& Attachment : Show->Cues[1].WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Light)
        {
            AfterReapply.Add(Attachment.AttachmentGuid);
        }
    }
    TestTrue(TEXT("Reapplying preserves destination light identities"), AfterReapply == BeforeReapply);

    Show->Cues[0].WingPair.Attachments.RemoveAll([](const FInfinityCueAttachment& Attachment)
    {
        return Attachment.Kind == EInfinityAttachmentKind::Light
            && Attachment.Lighting.Type == EInfinityStageLightType::Rect;
    });
    TestEqual(TEXT("Deleting one template light synchronizes both destinations"),
        Show->ReplicateLightAttachments(CueGuids[0], CueGuids), 2);
    for (int32 CueIndex = 1; CueIndex < 3; ++CueIndex)
    {
        const TArray<FInfinityCueAttachment>& Attachments = Show->Cues[CueIndex].WingPair.Attachments;
        TestEqual(TEXT("Each destination drops the deleted template light"),
            Attachments.FilterByPredicate([](const FInfinityCueAttachment& Attachment)
            {
                return Attachment.Kind == EInfinityAttachmentKind::Light;
            }).Num(), 1);
    }

    // An empty template is meaningful: it removes the replicated light set from
    // every destination while preserving props, triggers and other attachments.
    Show->Cues[0].WingPair.Attachments.RemoveAll([](const FInfinityCueAttachment& Attachment)
    {
        return Attachment.Kind == EInfinityAttachmentKind::Light;
    });
    TestEqual(TEXT("Clearing the template still synchronizes both destinations"),
        Show->ReplicateLightAttachments(CueGuids[0], CueGuids), 2);
    for (int32 CueIndex = 1; CueIndex < 3; ++CueIndex)
    {
        TestFalse(TEXT("No destination retains a deleted template light"),
            Show->Cues[CueIndex].WingPair.Attachments.ContainsByPredicate([](const FInfinityCueAttachment& Attachment)
            {
                return Attachment.Kind == EInfinityAttachmentKind::Light;
            }));
    }
    TestTrue(TEXT("Target prop survives empty-template synchronization"), Show->Cues[1].WingPair.Attachments.ContainsByPredicate(
        [TargetPropGuid](const FInfinityCueAttachment& Attachment) { return Attachment.AttachmentGuid == TargetPropGuid; }));
    TestTrue(TEXT("Target trigger survives empty-template synchronization"), Show->Cues[2].WingPair.Attachments.ContainsByPredicate(
        [TargetTriggerGuid](const FInfinityCueAttachment& Attachment) { return Attachment.AttachmentGuid == TargetTriggerGuid; }));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightReplicationPassageScopeTest,
    "InfinityStage.StageContent.LightReplicationStaysInsideTemplatePassage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightReplicationPassageScopeTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const auto AddWingPair = [Show](const FString& Label) -> FGuid
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.Label = FText::FromString(Label);
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        return Cue.CueGuid;
    };
    const auto AddLight = [Show](const FGuid& CueGuid, const FString& Label, const float Intensity)
    {
        FInfinityCueAttachment& Light = Show->Cues[Show->FindCueIndex(CueGuid)].WingPair.Attachments.AddDefaulted_GetRef();
        Light.AttachmentGuid = FGuid::NewGuid();
        Light.Kind = EInfinityAttachmentKind::Light;
        Light.Anchor = EInfinityAttachmentAnchor::LeftPanel;
        Light.Label = FText::FromString(Label);
        Light.Lighting.Type = EInfinityStageLightType::Spot;
        Light.Lighting.Intensity = Intensity;
    };
    const auto CountLights = [Show](const FGuid& CueGuid, float* OutFirstIntensity = nullptr) -> int32
    {
        int32 Count = 0;
        for (const FInfinityCueAttachment& Attachment : Show->Cues[Show->FindCueIndex(CueGuid)].WingPair.Attachments)
        {
            if (Attachment.Kind == EInfinityAttachmentKind::Light)
            {
                if (OutFirstIntensity && Count == 0)
                {
                    *OutFirstIntensity = Attachment.Lighting.Intensity;
                }
                ++Count;
            }
        }
        return Count;
    };

    // Two Passages of three Wing Pairs each, split by a Scene cue, like the production spine.
    TArray<FGuid> FirstPassagePairs;
    TArray<FGuid> SecondPassagePairs;
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FirstPassagePairs.Add(AddWingPair(FString::Printf(TEXT("P01 Wing %03d"), Index + 1)));
    }
    FInfinityShowCue& SceneCue = Show->Cues.AddDefaulted_GetRef();
    SceneCue.Type = EInfinityCueType::Scene;
    SceneCue.CueGuid = FGuid::NewGuid();
    const FGuid SceneCueGuid = SceneCue.CueGuid;
    for (int32 Index = 0; Index < 3; ++Index)
    {
        SecondPassagePairs.Add(AddWingPair(FString::Printf(TEXT("P02 Wing %03d"), Index + 1)));
    }
    Show->ReconcilePassageSettings();
    TestEqual(TEXT("The Scene cue splits the spine into two Passages"), Show->PassageSettings.Num(), 2);
    if (Show->PassageSettings.Num() != 2)
    {
        return false;
    }

    const FGuid FirstPassageGuid = Show->PassageSettings[0].PassageGuid;
    const FGuid SecondPassageGuid = Show->PassageSettings[1].PassageGuid;
    TestTrue(TEXT("A first-Passage pair resolves to the first Passage"),
        Show->FindPassageGuidForCue(FirstPassagePairs[2]) == FirstPassageGuid);
    TestTrue(TEXT("The second Passage's first pair resolves to the second Passage"),
        Show->FindPassageGuidForCue(SecondPassagePairs[0]) == SecondPassageGuid);
    TestTrue(TEXT("The second Passage's last pair resolves to the second Passage"),
        Show->FindPassageGuidForCue(SecondPassagePairs[2]) == SecondPassageGuid);
    TestFalse(TEXT("A Scene cue belongs to no Passage"), Show->FindPassageGuidForCue(SceneCueGuid).IsValid());
    TestFalse(TEXT("An unknown cue belongs to no Passage"), Show->FindPassageGuidForCue(FGuid::NewGuid()).IsValid());

    TestTrue(TEXT("The second Passage lists exactly its own pairs in Show order"),
        Show->GetWingPairCueGuidsInPassage(SecondPassageGuid) == SecondPassagePairs);
    TestTrue(TEXT("The first Passage lists exactly its own pairs in Show order"),
        Show->GetWingPairCueGuidsInPassage(FirstPassageGuid) == FirstPassagePairs);
    TestEqual(TEXT("An unknown Passage lists no pairs"), Show->GetWingPairCueGuidsInPassage(FGuid()).Num(), 0);

    // Tune the second Passage's first pair, then replicate the way the Cue Desk's
    // "Whole Passage" scope does: targets come from the template's own Passage.
    AddLight(FirstPassagePairs[0], TEXT("P01 Wing 001 Key"), 111.0f);
    AddLight(SecondPassagePairs[0], TEXT("P02 Wing 001 Key"), 222.0f);
    TArray<FGuid> Targets = Show->GetWingPairCueGuidsInPassage(Show->FindPassageGuidForCue(SecondPassagePairs[0]));
    Targets.Remove(SecondPassagePairs[0]);
    TestEqual(TEXT("Only the two other pairs in the template's Passage are targeted"), Targets.Num(), 2);
    TestEqual(TEXT("Both pairs in the template's Passage receive lights"),
        Show->ReplicateLightAttachments(SecondPassagePairs[0], Targets), 2);

    for (int32 Index = 1; Index < 3; ++Index)
    {
        float Intensity = 0.0f;
        TestEqual(TEXT("A second-Passage pair receives the template light"), CountLights(SecondPassagePairs[Index], &Intensity), 1);
        TestEqual(TEXT("The received light carries the template intensity"), Intensity, 222.0f);
    }
    float FirstPassageIntensity = 0.0f;
    TestEqual(TEXT("The first Passage's tuned pair keeps its own single light"),
        CountLights(FirstPassagePairs[0], &FirstPassageIntensity), 1);
    TestEqual(TEXT("The first Passage's tuned pair keeps its own intensity"), FirstPassageIntensity, 111.0f);
    TestEqual(TEXT("The first Passage's second pair is untouched"), CountLights(FirstPassagePairs[1]), 0);
    TestEqual(TEXT("The first Passage's third pair is untouched"), CountLights(FirstPassagePairs[2]), 0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraOwnerTest,
    "InfinityStage.Camera.OwnershipResolvesPerSegment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraOwnerTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Wing = Show->Cues.AddDefaulted_GetRef();
        Wing.Type = EInfinityCueType::WingPair;
        Wing.CueGuid = FGuid::NewGuid();
        Wing.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Wing.WingPair.IntervalToNext = 1000;
    }
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 2000;
    Scene.Scene.CameraOwner = EInfinityCameraOwner::DogFreeLook;
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].CameraOwner = EInfinityCameraOwner::DogGazeOnly;

    AInfinityStageShowRoot* Root = World->SpawnActor<AInfinityStageShowRoot>();
    Root->ShowAsset = Show;

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    FFrameNumber PassageFrame(0);
    FFrameNumber SceneFrame(0);
    for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
    {
        const FFrameNumber Middle((Segment.StartFrame.Value + Segment.EndFrame.Value) / 2);
        if (Segment.Type == EInfinityCueType::WingPair)
        {
            PassageFrame = Middle;
        }
        else
        {
            SceneFrame = Middle;
        }
    }

    TestEqual(
        TEXT("Passage reports its authored owner"),
        Root->GetCameraOwnerAtFrame(PassageFrame),
        EInfinityCameraOwner::DogGazeOnly);
    TestEqual(
        TEXT("Scene reports its own authored owner"),
        Root->GetCameraOwnerAtFrame(SceneFrame),
        EInfinityCameraOwner::DogFreeLook);
    TestEqual(
        TEXT("Scene owns the exact Passage-to-Scene boundary"),
        Root->GetCameraOwnerAtFrame(Compiled.Segments[1].StartFrame),
        EInfinityCameraOwner::DogFreeLook);
    TestEqual(
        TEXT("Terminal endpoint retains the last Scene owner"),
        Root->GetCameraOwnerAtFrame(Compiled.Segments.Last().EndFrame),
        EInfinityCameraOwner::DogFreeLook);

    // A live override is a performance decision and must win everywhere without
    // touching the Show.
    Root->bOverrideCameraOwner = true;
    Root->CameraOwnerOverride = EInfinityCameraOwner::Timeline;
    TestEqual(
        TEXT("Override wins over the Passage"),
        Root->GetCameraOwnerAtFrame(PassageFrame),
        EInfinityCameraOwner::Timeline);
    TestEqual(
        TEXT("Override wins over the Scene"),
        Root->GetCameraOwnerAtFrame(SceneFrame),
        EInfinityCameraOwner::Timeline);
    TestEqual(
        TEXT("The Show itself is unchanged"),
        Show->PassageSettings[0].CameraOwner,
        EInfinityCameraOwner::DogGazeOnly);

    Root->bOverrideCameraOwner = false;
    // Off the end of the Show there is nothing authored to hand over to.
    TestEqual(
        TEXT("Outside every segment falls back to Timeline"),
        Root->GetCameraOwnerAtFrame(FFrameNumber(999999)),
        EInfinityCameraOwner::Timeline);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStagePassageSceneStopTest,
    "InfinityStage.Transport.PassageContinuesIntoScene",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStagePassageSceneStopTest::RunTest(const FString& Parameters)
{
    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>();
    const EInfinityCueType Types[] = {
        EInfinityCueType::Sequence, EInfinityCueType::WingPair,
        EInfinityCueType::Scene, EInfinityCueType::Sequence, EInfinityCueType::WingPair };
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Types); ++Index)
    {
        FInfinityTransportSegment& Segment = Transport->Segments.AddDefaulted_GetRef();
        Segment.Type = Types[Index];
        Segment.StartFrame = Index * 100;
        Segment.EndFrame = (Index + 1) * 100;
    }
    TestEqual(TEXT("Existing shows retain their explicit Passage stop"), Transport->GetForwardStopSegmentIndex(1), 1);
    Transport->bAutoPlaySceneAfterPassage = true;
    TestEqual(TEXT("Passage plays through the complete following Scene"), Transport->GetForwardStopSegmentIndex(1), 2);
    TestEqual(TEXT("Opening still holds at the next Passage start"), Transport->GetForwardStopSegmentIndex(0), 0);
    TestEqual(TEXT("Scene holds before the curtain interstitial"), Transport->GetForwardStopSegmentIndex(2), 2);
    TestEqual(TEXT("Curtain still holds at the next Passage start"), Transport->GetForwardStopSegmentIndex(3), 3);
    TestEqual(TEXT("Final Passage without a Scene stops normally"), Transport->GetForwardStopSegmentIndex(4), 4);
    TestEqual(TEXT("Invalid selection has no target"), Transport->GetForwardStopSegmentIndex(INDEX_NONE), INDEX_NONE);
    Transport->Segments[2].StartFrame = 201;
    TestEqual(TEXT("A gap is not crossed as an automatic handoff"), Transport->GetForwardStopSegmentIndex(1), 1);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageAnalysisCurveSampleTest,
    "InfinityStage.Analysis.CurveSamplesAndSectionsRoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageAnalysisCurveSampleTest::RunTest(const FString& Parameters)
{
    FInfinityAnalysisCurve Curve;
    Curve.Name = TEXT("intensity");
    Curve.RateHz = 10.0f;
    for (int32 Index = 0; Index < 11; ++Index)
    {
        Curve.Values.Add(Index / 10.0f);
    }

    TestEqual(TEXT("Start samples exactly"), Curve.Sample(0.0), 0.0f);
    TestEqual(TEXT("End samples exactly"), Curve.Sample(1.0), 1.0f);
    TestTrue(
        TEXT("Interpolates between samples"),
        FMath::IsNearlyEqual(Curve.Sample(0.55), 0.55f, 0.001f));
    // Clamping matters: a Passage can be longer than its analysed rail, and a
    // read past the end must hold rather than wrap or read out of bounds.
    TestEqual(TEXT("Past the end clamps"), Curve.Sample(99.0), 1.0f);
    TestEqual(TEXT("Before the start clamps"), Curve.Sample(-5.0), 0.0f);

    FInfinityAnalysisCurve Empty;
    TestEqual(TEXT("An empty curve is silent, not a crash"), Empty.Sample(1.0), 0.0f);

    UInfinityStageMusicMapAsset* Map = NewObject<UInfinityStageMusicMapAsset>(GetTransientPackage());
    Map->FeatureCurves.Add(Curve);
    TestNotNull(TEXT("Named lookup finds the curve"), Map->FindCurve(TEXT("intensity")));
    TestNull(TEXT("Unknown curve names return null"), Map->FindCurve(TEXT("nope")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSceneSequenceLengthTest,
    "InfinityStage.Scene.DurationFollowsSequenceLength",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSceneSequenceLengthTest::RunTest(const FString& Parameters)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Wing = Show->Cues.AddDefaulted_GetRef();
        Wing.Type = EInfinityCueType::WingPair;
        Wing.CueGuid = FGuid::NewGuid();
        Wing.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Wing.WingPair.IntervalToNext = 100;
    }
    FInfinityShowCue& Scene = Show->Cues.AddDefaulted_GetRef();
    Scene.Type = EInfinityCueType::Scene;
    Scene.CueGuid = FGuid::NewGuid();
    Scene.Scene.DurationFrames = 24000;
    Show->ReconcilePassageSettings();

    const auto SceneLength = [&Show]()
    {
        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
        for (const FInfinityCompiledSegment& Segment : Compiled.Segments)
        {
            if (Segment.Type != EInfinityCueType::WingPair)
            {
                return (Segment.EndFrame - Segment.StartFrame).Value;
            }
        }
        return 0;
    };

    TestEqual(TEXT("Authored duration is used by default"), SceneLength(), 24000);

    // A Scene sequence at the same tick resolution, so the expected conversion
    // is one to one and the test asserts the source of truth, not the maths.
    ULevelSequence* SceneSequence = NewObject<ULevelSequence>(GetTransientPackage());
    SceneSequence->Initialize();
    SceneSequence->GetMovieScene()->SetTickResolutionDirectly(Show->TickResolution);
    SceneSequence->GetMovieScene()->SetPlaybackRange(TRange<FFrameNumber>(FFrameNumber(0), FFrameNumber(9000)));
    Show->Cues[2].Scene.Sequence = SceneSequence;

    TestEqual(TEXT("Opting out still uses the authored duration"), SceneLength(), 24000);

    Show->Cues[2].Scene.bUseSequenceLength = true;
    TestEqual(TEXT("Opted in, the Scene takes its sequence's length"), SceneLength(), 9000);

    // A broken reference must degrade to the authored value rather than
    // collapsing the Show's timing to zero.
    Show->Cues[2].Scene.Sequence = nullptr;
    TestEqual(TEXT("A missing sequence falls back to the authored duration"), SceneLength(), 24000);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageTopFollowsMechanismTest,
    "InfinityStage.Mechanism.TopPanelParticipationIsControllable",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageTopFollowsMechanismTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = Cube;
    Cue.WingPair.Right.Mesh = Cube;
    Cue.WingPair.bHasTop = true;
    Cue.WingPair.Top.Mesh = Cube;
    Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
    Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;
    Show->ApplyTravelingUndulation({ Cue.CueGuid }, 0.25, 100.0, 0.0);

    // A side-only preset: clear the authored Top curve so the fallback matters.
    Show->Cues[0].WingPair.Mechanism.TopNormalizedCurve.GetRichCurve()->Reset();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Top fixture materializes"), Actor->MaterializePassage());
    const FInfinityMaterializedPanelRef* Top = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Top; });
    if (!TestNotNull(TEXT("Top instance exists"), Top))
    {
        World->DestroyWorld(false);
        return false;
    }

    const auto TopOffsetAtCrest = [&]()
    {
        Actor->EvaluateMechanismsAtMasterFrame(0);
        FTransform Rest;
        Top->Component->GetInstanceTransform(Top->InstanceIndex, Rest, true);
        Actor->EvaluateMechanismsAtMasterFrame(48000);
        FTransform Crest;
        Top->Component->GetInstanceTransform(Top->InstanceIndex, Crest, true);
        return (Crest.GetLocation() - Rest.GetLocation()).Size();
    };

    TestTrue(
        TEXT("Opted in with no authored Top curve, the Top follows the Left curve"),
        TopOffsetAtCrest() > 1.0);

    Show->Cues[0].WingPair.Mechanism.bTopFollowsMechanism = false;
    TestTrue(
        TEXT("Opted out, the Top holds at rest"),
        TopOffsetAtCrest() < UE_KINDA_SMALL_NUMBER);

    // Opting out must not disturb the sides.
    const FInfinityMaterializedPanelRef* Left = Actor->MaterializedPanels.FindByPredicate(
        [](const FInfinityMaterializedPanelRef& Ref) { return Ref.Side == EInfinityPanelSide::Left; });
    if (Left)
    {
        Actor->EvaluateMechanismsAtMasterFrame(0);
        FTransform LeftRest;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftRest, true);
        Actor->EvaluateMechanismsAtMasterFrame(48000);
        FTransform LeftCrest;
        Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftCrest, true);
        TestTrue(
            TEXT("Sides keep their 100 cm travel when the Top opts out"),
            FMath::IsNearlyEqual(LeftCrest.GetLocation().Y - LeftRest.GetLocation().Y, 100.0, 0.01));
    }

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageRouteExtensionTest,
    "InfinityStage.Route.ExtendToCompiledLength",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageRouteExtensionTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    for (int32 Index = 0; Index < 4; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.GapToNextCm = 500.0;
    }
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Auto-fit fixture materializes"), Actor->MaterializePassage());

    double RequiredCm = 0.0;
    double CurrentCm = 0.0;
    TestTrue(TEXT("Route status resolves"), Actor->GetRouteLengthStatus(RequiredCm, CurrentCm));
    TestTrue(TEXT("Compiled Passage needs a positive distance"), RequiredCm > 0.0);

    // Hand-edit the route too short, exactly the state that makes a normal
    // materialization refuse.
    Actor->bAutoFitStraightRoute = false;
    Actor->Route->ClearSplinePoints(false);
    Actor->Route->AddSplinePoint(FVector::ZeroVector, ESplineCoordinateSpace::Local, false);
    Actor->Route->AddSplinePoint(FVector(RequiredCm * 0.5, 0.0, 0.0), ESplineCoordinateSpace::Local, false);
    Actor->Route->SetSplinePointType(0, ESplinePointType::Linear, false);
    Actor->Route->SetSplinePointType(1, ESplinePointType::Linear, true);
    // Refusing a short route is the behaviour under test, so its error log is
    // expected rather than a test failure.
    AddExpectedErrorPlain(TEXT("keeping the previous materialization"));
    TestFalse(TEXT("A short route refuses materialization"), Actor->MaterializePassage());

    TestTrue(TEXT("Route extends"), Actor->ExtendRouteToCompiledLength());
    Actor->GetRouteLengthStatus(RequiredCm, CurrentCm);
    TestTrue(TEXT("Extended route covers the compiled distance"), CurrentCm + 0.01 >= RequiredCm);
    TestTrue(TEXT("Extended route materializes"), Actor->MaterializePassage());
    TestFalse(TEXT("Extending an adequate route is a no-op"), Actor->ExtendRouteToCompiledLength());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLivePhasePatternEvaluationTest,
    "InfinityStage.Mechanism.LivePassagePhaseFollowsCueOrder",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLivePhasePatternEvaluationTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    TArray<FGuid> Targets;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetTranslation(FVector(0.0, -600.0, 0.0));
        Cue.WingPair.Right.LocalTransform.SetTranslation(FVector(0.0, 600.0, 0.0));
        Targets.Add(Cue.CueGuid);
    }
    Show->ReconcilePassageSettings();
    Show->PassageSettings[0].TailFrames = 240000;
    Show->PassageSettings[0].TailDistanceCm = 1.0;
    TestEqual(TEXT("Live whole-Passage pattern applies"),
        Show->ApplyTravelingUndulation(Targets, 0.25, 100.0, 0.25, true), 2);

    AInfinityStagePassageActor* Actor = World->SpawnActor<AInfinityStagePassageActor>();
    Actor->ShowAsset = Show;
    TestTrue(TEXT("Live-pattern fixture materializes"), Actor->MaterializePassage());
    const auto ReadLeft = [Actor](const FGuid CueGuid)
    {
        FTransform Transform;
        if (const FInfinityMaterializedPanelRef* Ref = Actor->MaterializedPanels.FindByPredicate(
            [CueGuid](const FInfinityMaterializedPanelRef& Candidate)
            {
                return Candidate.CueGuid == CueGuid && Candidate.Side == EInfinityPanelSide::Left;
            }))
        {
            Ref->Component->GetInstanceTransform(Ref->InstanceIndex, Transform, true);
        }
        return Transform;
    };

    TestTrue(TEXT("Original cue order evaluates at frame zero"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FTransform OriginalFirst = ReadLeft(Targets[0]);
    const FTransform OriginalSecond = ReadLeft(Targets[1]);
    TestTrue(TEXT("Second ordinal begins farther inward than first"),
        OriginalSecond.GetLocation().Y > OriginalFirst.GetLocation().Y + 40.0);

    Show->Cues.Swap(0, 1);
    Show->ReconcilePassageSettings();
    TestTrue(TEXT("Reordered live-pattern Passage rematerializes"), Actor->MaterializePassage());
    TestTrue(TEXT("Same absolute frame evaluates after reorder"), Actor->EvaluateMechanismsAtMasterFrame(0));
    const FTransform ReorderedFormerFirst = ReadLeft(Targets[0]);
    const FTransform ReorderedFormerSecond = ReadLeft(Targets[1]);
    TestTrue(TEXT("Former second row now receives ordinal-zero phase"),
        ReorderedFormerSecond.GetLocation().Y < ReorderedFormerFirst.GetLocation().Y - 40.0);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageThreeThousandWingCompileTest,
    "InfinityStage.Scale.ThreeThousandWingCompile",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageThreeThousandWingCompileTest::RunTest(const FString& Parameters)
{
    constexpr int32 WingCount = 3000;
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>();
    Show->Cues.Reserve(WingCount);
    for (int32 Index = 0; Index < WingCount; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid(1, 0, 0, Index + 1);
        Cue.WingPair.OccurrenceGuid = FGuid(2, 0, 0, Index + 1);
        Cue.WingPair.IntervalToNext = 48000;
        Cue.WingPair.GapToNextCm = 500.0;
    }
    Show->ReconcilePassageSettings();

    const double StartSeconds = FPlatformTime::Seconds();
    const FInfinityCompileResult Result = FInfinityStageCompiler::Compile(*Show);
    const double ElapsedMilliseconds = (FPlatformTime::Seconds() - StartSeconds) * 1000.0;

    TestFalse(TEXT("3,000-row score compiles without errors"), Result.HasErrors());
    TestEqual(TEXT("One contiguous Passage"), Result.Passages.Num(), 1);
    TestEqual(TEXT("All Wing Pairs compile into dense values"), Result.Passages[0].Wings.Num(), WingCount);
    TestEqual(TEXT("Route distance is cumulative and exact"), Result.Passages[0].TotalDistanceCm, 1499500.0);
    TestTrue(TEXT("3,000-row compile remains below the initial 100 ms editor target"), ElapsedMilliseconds < 100.0);
    AddInfo(FString::Printf(TEXT("3,000 Wing Pairs compiled in %.3f ms; no Actor, component, or per-row Tick was created."), ElapsedMilliseconds));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageViewportEditProxyTest,
    "InfinityStage.Authoring.ViewportEditProxyWritesCue",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageViewportEditProxyTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
    WorldContext.SetCurrentWorld(World);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
    Cue.Type = EInfinityCueType::WingPair;
    Cue.CueGuid = FGuid::NewGuid();
    Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
    Cue.WingPair.Left.Mesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    Cue.WingPair.Right.Mesh = Cue.WingPair.Left.Mesh;
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    TestTrue(TEXT("Fixture Passage materializes"), Passage->MaterializePassage());

    AInfinityStageWingEditProxy* PairProxy = World->SpawnActor<AInfinityStageWingEditProxy>();
    TestTrue(TEXT("Pair edit proxy initializes"), PairProxy->InitializeEdit(
        Show, Passage, Cue.CueGuid, EInfinityWingEditTarget::Pair));
    PairProxy->SetActorLocation(FVector(100.0, 20.0, 0.0));
    PairProxy->PostEditMove(true);
    PairProxy->FinishEditing();
    TestEqual(TEXT("Pair gizmo writes occurrence X"), Cue.WingPair.OccurrenceOffset.GetTranslation().X, 100.0);
    TestEqual(TEXT("Pair gizmo writes occurrence Y"), Cue.WingPair.OccurrenceOffset.GetTranslation().Y, 20.0);

    AInfinityStageWingEditProxy* LeftProxy = World->SpawnActor<AInfinityStageWingEditProxy>();
    TestTrue(TEXT("Left edit proxy initializes"), LeftProxy->InitializeEdit(
        Show, Passage, Cue.CueGuid, EInfinityWingEditTarget::Left));
    LeftProxy->AddActorWorldOffset(FVector(0.0, 0.0, 50.0));
    LeftProxy->PostEditMove(true);
    LeftProxy->FinishEditing();
    TestTrue(TEXT("Panel gizmo writes a 50 cm local Z offset"),
        FMath::IsNearlyEqual(Cue.WingPair.Left.LocalTransform.GetTranslation().Z, 50.0, 0.01));

    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
    return true;
}

#endif
