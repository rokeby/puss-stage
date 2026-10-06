#include "InfinityStageLightMover.h"

#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTypes.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Club "mover" spots (patch MV, 6 Oct, P05): a seeded, rapid, jolting yaw/pitch
 * routine that starts calm and turns haywire, triggered by distance or always on.
 */
namespace
{
FInfinityLightMoverSettings MakeMover()
{
    FInfinityLightMoverSettings Mover;
    Mover.bEnabled = true;
    Mover.Trigger = EInfinityLightMoverTrigger::OnApproach;
    Mover.ApproachDistanceCm = 2500.0;
    Mover.ErraticRampCm = 1500.0;
    Mover.CalmScale = 0.15f;
    return Mover;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightMoverRoutineTest,
    "InfinityStage.LightMover.RoutineIsSeededBoundedAndRamps",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightMoverRoutineTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageLightMover;
    constexpr double Lamp = 10000.0;
    const FGuid Identity = FGuid::NewGuid();
    const FInfinityLightMoverSettings Off;
    TestFalse(TEXT("Off by default"), Off.bEnabled);
    TestTrue(TEXT("Off: no offset"), Evaluate(Off, Identity, Lamp, Lamp, 3.3).IsNearlyZero());

    FInfinityLightMoverSettings Mover = MakeMover();
    TestTrue(TEXT("Before the approach: rests on the authored (ground) focus"),
        Evaluate(Mover, Identity, Lamp, Lamp - 3000.0, 3.3).IsNearlyZero());
    TestTrue(TEXT("At the onset: calm"), FMath::IsNearlyEqual(ErraticScale(Mover, Lamp, Lamp - 2500.0), 0.15f, 1.0e-4f));
    TestTrue(TEXT("After the ramp: full haywire"), FMath::IsNearlyEqual(ErraticScale(Mover, Lamp, Lamp - 500.0), 1.0f, 1.0e-4f));

    bool bBounded = true;
    bool bRepeat = true;
    double CalmPeak = 0.0;
    double WildPeak = 0.0;
    for (double Seconds = 0.0; Seconds < 20.0; Seconds += 0.01)
    {
        const FRotator Wild = Evaluate(Mover, Identity, Lamp, Lamp - 500.0, Seconds);
        const FRotator Calm = Evaluate(Mover, Identity, Lamp, Lamp - 2499.0, Seconds);
        bBounded &= FMath::Abs(Wild.Yaw) <= Mover.YawAmplitudeDegrees + 1.0e-3
            && FMath::Abs(Wild.Pitch) <= Mover.PitchAmplitudeDegrees + 1.0e-3 && Wild.Roll == 0.0;
        bRepeat &= Wild.Equals(Evaluate(Mover, Identity, Lamp, Lamp - 500.0, Seconds), 0.0);
        WildPeak = FMath::Max(WildPeak, FMath::Abs(Wild.Yaw));
        CalmPeak = FMath::Max(CalmPeak, FMath::Abs(Calm.Yaw));
    }
    TestTrue(TEXT("Bounded by its amplitudes, no roll"), bBounded);
    TestTrue(TEXT("Deterministic: the same time and distance give the same aim"), bRepeat);
    TestTrue(TEXT("Calm is much smaller than haywire"), CalmPeak < WildPeak * 0.3 && WildPeak > 15.0);

    // Jolting: within a step it moves fast, then holds still.
    const double StepSeconds = 1.0 / Mover.StepsPerSecond;
    const double StepStart = 7.0 * StepSeconds;
    const FRotator HoldA = Evaluate(Mover, Identity, Lamp, Lamp - 500.0, StepStart + StepSeconds * 0.5);
    const FRotator HoldB = Evaluate(Mover, Identity, Lamp, Lamp - 500.0, StepStart + StepSeconds * 0.95);
    TestTrue(TEXT("Holds after its ease"), HoldA.Equals(HoldB, 1.0e-6));
    const FRotator Moving = Evaluate(Mover, Identity, Lamp, Lamp - 500.0, StepStart + StepSeconds * 0.05);
    TestFalse(TEXT("Moves during its ease"), Moving.Equals(HoldA, 1.0e-3));

    FInfinityLightMoverSettings Reseeded = Mover;
    Reseeded.Seed = 3;
    TestFalse(TEXT("The seed changes the routine"),
        Evaluate(Mover, Identity, Lamp, Lamp - 500.0, 2.0).Equals(Evaluate(Reseeded, Identity, Lamp, Lamp - 500.0, 2.0), 1.0e-3));
    TestFalse(TEXT("Two movers do not move in unison"),
        Evaluate(Mover, Identity, Lamp, Lamp - 500.0, 2.0).Equals(Evaluate(Mover, FGuid::NewGuid(), Lamp, Lamp - 500.0, 2.0), 1.0e-3));

    Mover.Trigger = EInfinityLightMoverTrigger::AlwaysInPassage;
    TestTrue(TEXT("Always: moving from the Passage start"), ErraticScale(Mover, Lamp, 0.0) > 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightMoverPassageTest,
    "InfinityStage.LightMover.TurnsTheLampInGameOnly",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightMoverPassageTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetLocation(FVector(0.0, -400.0, 0.0));
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Right.LocalTransform.SetLocation(FVector(0.0, 400.0, 0.0));
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    FInfinityCueAttachment& Lamp = Show->Cues[1].WingPair.Attachments.AddDefaulted_GetRef();
    Lamp.AttachmentGuid = FGuid::NewGuid();
    Lamp.Kind = EInfinityAttachmentKind::Light;
    Lamp.Lighting.Type = EInfinityStageLightType::Spot;
    Lamp.RelativeTransform = FTransform(FRotator(-80.0, 0.0, 0.0), FVector(0.0, 300.0, 50.0));
    Lamp.Mover = MakeMover();
    const FGuid LampGuid = Lamp.AttachmentGuid;
    Show->ReconcilePassageSettings();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    if (!TestTrue(TEXT("Fixture compiles"), Compiled.Passages.Num() == 1 && Compiled.Passages[0].Wings.Num() == 3))
    {
        return false;
    }
    const double LampCm = Compiled.Passages[0].Wings[1].DistanceCm;
    const FFrameNumber Frame = Compiled.Passages[0].SegmentStartFrame;

    const auto FindLamp = [&LampGuid](const AInfinityStagePassageActor& Passage) -> AActor*
    {
        for (AActor* Actor : Passage.ManagedAttachmentActors)
        {
            FGuid Cue;
            FGuid Attachment;
            if (Actor && Passage.FindAttachmentByActor(Actor, Cue, Attachment) && Attachment == LampGuid)
            {
                return Actor;
            }
        }
        return nullptr;
    };

    {
        UWorld* Preview = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = Preview->SpawnActor<AInfinityStagePassageActor>();
        Passage->ShowAsset = Show;
        Passage->MaterializePassage();
        AActor* Actor = FindLamp(*Passage);
        const FQuat Before = Actor ? Actor->GetActorQuat() : FQuat::Identity;
        Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 500.0);
        TestTrue(TEXT("Editor world: the lamp keeps its authored aim (no level write)"),
            Actor && Actor->GetActorQuat().Equals(Before, 1.0e-6));
        Preview->DestroyWorld(false);
    }

    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    Passage->MaterializePassage();
    AActor* Actor = FindLamp(*Passage);
    if (!TestNotNull(TEXT("The lamp is placed"), Actor))
    {
        World->DestroyWorld(false);
        return false;
    }
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 3000.0);
    const FQuat Authored = Actor->GetActorQuat();
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 500.0);
    const FQuat Wild = Actor->GetActorQuat();
    TestFalse(TEXT("Past the approach: the lamp has turned off its ground focus"), Wild.Equals(Authored, 1.0e-4));
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 3000.0);
    TestTrue(TEXT("Back before the approach (a rewind): exactly the authored aim again"),
        Actor->GetActorQuat().Equals(Authored, 1.0e-5));
    // Re-materialize: the mover is Show data, so it is still there.
    Passage->MaterializePassage();
    AActor* Again = FindLamp(*Passage);
    TestNotNull(TEXT("Survives re-materialize"), Again);
    if (Again)
    {
        Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 500.0);
        TestTrue(TEXT("...and moves the same way"), Again->GetActorQuat().Equals(Wild, 1.0e-4));
    }
    World->DestroyWorld(false);
    return true;
}

#endif
