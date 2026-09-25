#include "InfinityStageCameraPilotLibrary.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSequenceBuilderLibrary.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/**
 * One Passage on a turned, offset route with a raised camera, Route Look Ahead
 * and a yaw already past 180 degrees, so the solve exercises every term of the
 * rig's placement and the Euler unwinding at once.
 */
struct FCameraPilotFixture
{
    UWorld* World = nullptr;
    UInfinityStageShowAsset* Show = nullptr;
    AInfinityStageCameraRig* Rig = nullptr;
    UMovieSceneInfinityPassageSection* Section = nullptr;
    FGuid PassageGuid;
    FFrameNumber StartFrame = 0;
    FFrameNumber EndFrame = 0;

    bool Build(FAutomationTestBase& Test)
    {
        World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        FWorldContext& WorldContext = GEngine->CreateNewWorldContext(EWorldType::EditorPreview);
        WorldContext.SetCurrentWorld(World);

        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
        for (int32 Index = 0; Index < 3; ++Index)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        }
        Show->ReconcilePassageSettings();
        Show->PassageSettings[0].TailFrames = 24000;
        Show->PassageSettings[0].TailDistanceCm = 250.0;
        PassageGuid = Show->PassageSettings[0].PassageGuid;

        AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>(
            FVector(1200.0, -800.0, 50.0),
            FRotator(0.0, 35.0, 0.0));
        Passage->ShowAsset = Show;
        Passage->PassageGuid = PassageGuid;
        Test.TestTrue(TEXT("Pilot fixture Passage materializes"), Passage->MaterializePassage());

        Rig = World->SpawnActor<AInfinityStageCameraRig>();
        Rig->PassageActor = Passage;
        Rig->CameraOffset = FVector(0.0, 0.0, 180.0);
        Rig->bEnableShadowCat = false;

        ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
        Master->Initialize();
        Show->ManagedMasterSequence = Master;
        FString Report;
        Test.TestTrue(TEXT("Pilot fixture Master builds"),
            UInfinityStageSequenceBuilderLibrary::RebuildManagedMaster(Show, Master, Report));

        Section = UInfinityStageCameraPilotLibrary::FindPassageSection(*Show, PassageGuid);
        Test.TestNotNull(TEXT("Pilot fixture has a Passage camera section"), Section);
        if (!Section)
        {
            return false;
        }
        Section->LookAheadDistanceCm.SetDefault(600.0);
        Section->YawDegrees.SetDefault(350.0);
        Section->PitchDegrees.SetDefault(-4.0);

        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
        const FInfinityCompiledPassage* CompiledPassage = Compiled.Passages.FindByPredicate(
            [this](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == PassageGuid; });
        Test.TestNotNull(TEXT("Pilot fixture Passage compiles"), CompiledPassage);
        if (!CompiledPassage)
        {
            return false;
        }
        StartFrame = CompiledPassage->SegmentStartFrame;
        EndFrame = CompiledPassage->SegmentEndFrame;
        return EndFrame > StartFrame;
    }

    FFrameNumber FrameAt(const double Alpha) const
    {
        return FFrameNumber(FMath::RoundToInt32(FMath::Lerp(
            static_cast<double>(StartFrame.Value),
            static_cast<double>(EndFrame.Value),
            Alpha)));
    }

    bool GetView(const FFrameNumber Frame, FTransform& OutView, float& OutFocal, float& OutFocus) const
    {
        return UInfinityStageCameraPilotLibrary::GetCameraView(*Rig, Frame, OutView, OutFocal, OutFocus);
    }

    int32 CountKeys(const EInfinityPassageCameraChannel Channel) const
    {
        const FMovieSceneDoubleChannel* Data = Section ? Section->GetCameraChannel(Channel) : nullptr;
        return Data ? Data->GetNumKeys() : INDEX_NONE;
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

bool ViewsMatch(const FTransform& A, const FTransform& B)
{
    return FVector::Distance(A.GetLocation(), B.GetLocation()) <= 0.01
        && FMath::RadiansToDegrees(A.GetRotation().AngularDistance(B.GetRotation())) <= 0.01;
}

/** A deliberate reframe: move the camera in world space and turn it about its own axes. */
FTransform Reframe(const FTransform& View, const FVector& WorldMoveCm, const FRotator& LocalTurn)
{
    FTransform Result = View;
    Result.SetLocation(View.GetLocation() + WorldMoveCm);
    Result.SetRotation((View.GetRotation() * LocalTurn.Quaternion()).GetNormalized());
    return Result;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraPilotRoundTripTest,
    "InfinityStage.Editor.CameraPilot.RoundTrip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraPilotRoundTripTest::RunTest(const FString& Parameters)
{
    FCameraPilotFixture Fixture;
    if (!Fixture.Build(*this))
    {
        Fixture.Destroy();
        return false;
    }

    const FFrameNumber Frame = Fixture.FrameAt(0.4);
    FTransform Authored;
    float Focal = 0.0f;
    float Focus = 0.0f;
    TestTrue(TEXT("Authored view evaluates"), Fixture.GetView(Frame, Authored, Focal, Focus));

    // Solving the authored view must reproduce the authored channels: the solve is the rig's exact inverse.
    FInfinityCameraPilotAnchor Anchor;
    FInfinityCameraPilotSolution Unchanged;
    FString Error;
    TestTrue(TEXT("Anchor resolves"), UInfinityStageCameraPilotLibrary::ResolveAnchor(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, Frame, Anchor, Error));
    TestTrue(TEXT("Authored view solves"), UInfinityStageCameraPilotLibrary::Solve(Anchor, Authored, Unchanged, Error));
    TestTrue(TEXT("Authored view solves to the authored offset"),
        Unchanged.LocalOffsetCm.Equals(Anchor.CurrentLocalOffsetCm, 0.01));
    TestTrue(TEXT("Authored view solves to the authored rotation"),
        Unchanged.LocalRotation.Equals(Anchor.CurrentLocalRotation, 0.01));

    const FTransform Piloted = Reframe(Authored, FVector(35.0, -120.0, 45.0), FRotator(-7.0, 12.0, 2.0));
    FString Report;
    TestTrue(TEXT("Piloted pose keys"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, Frame, Piloted, nullptr, Report));

    FTransform ReadBack;
    TestTrue(TEXT("Keyed view evaluates"), Fixture.GetView(Frame, ReadBack, Focal, Focus));
    TestTrue(TEXT("Rig reads back exactly the piloted view"), ViewsMatch(ReadBack, Piloted));

    for (const EInfinityPassageCameraChannel Channel : {
        EInfinityPassageCameraChannel::LongitudinalOffsetCm,
        EInfinityPassageCameraChannel::LateralOffsetCm,
        EInfinityPassageCameraChannel::HeightOffsetCm,
        EInfinityPassageCameraChannel::PitchDegrees,
        EInfinityPassageCameraChannel::YawDegrees,
        EInfinityPassageCameraChannel::RollDegrees })
    {
        TestEqual(TEXT("Each pose channel carries one key"), Fixture.CountKeys(Channel), 1);
    }
    TestEqual(TEXT("Pose-only key leaves focal length unkeyed"),
        Fixture.CountKeys(EInfinityPassageCameraChannel::FocalLengthMm), 0);
    TestEqual(TEXT("Pose-only key leaves focus unkeyed"),
        Fixture.CountKeys(EInfinityPassageCameraChannel::FocusDistanceCm), 0);
    TestEqual(TEXT("Pose-only key leaves speed unkeyed"),
        Fixture.CountKeys(EInfinityPassageCameraChannel::SpeedMultiplier), 0);

    double KeyedYaw = 0.0;
    Fixture.Section->YawDegrees.Evaluate(FFrameTime(Frame), KeyedYaw);
    TestTrue(TEXT("Yaw is unwound next to the authored 350 degrees, not wrapped to near zero"), KeyedYaw > 180.0);

    TestTrue(TEXT("A first pose key reports that the Passage endpoints moved"),
        Report.Contains(TEXT("Check All Scenes")));

    // Keying the same view again is idempotent: same values, still one key per channel.
    FString SecondReport;
    TestTrue(TEXT("Re-keying the same view succeeds"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, Frame, ReadBack, nullptr, SecondReport));
    TestEqual(TEXT("Re-keying replaces rather than adds"),
        Fixture.CountKeys(EInfinityPassageCameraChannel::YawDegrees), 1);
    TestFalse(TEXT("Re-keying an unchanged view does not report moved endpoints"),
        SecondReport.Contains(TEXT("Check All Scenes")));

    Fixture.Destroy();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCameraPilotLensAndRefusalTest,
    "InfinityStage.Editor.CameraPilot.LensAndRefusal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCameraPilotLensAndRefusalTest::RunTest(const FString& Parameters)
{
    FCameraPilotFixture Fixture;
    if (!Fixture.Build(*this))
    {
        Fixture.Destroy();
        return false;
    }

    const FFrameNumber FirstFrame = Fixture.FrameAt(0.25);
    const FFrameNumber SecondFrame = Fixture.FrameAt(0.75);
    FTransform FirstView;
    FTransform SecondView;
    float Focal = 0.0f;
    float Focus = 0.0f;
    Fixture.GetView(FirstFrame, FirstView, Focal, Focus);
    Fixture.GetView(SecondFrame, SecondView, Focal, Focus);

    const FTransform FirstPiloted = Reframe(FirstView, FVector(0.0, 60.0, -30.0), FRotator(3.0, -9.0, 0.0));
    FString Report;
    TestTrue(TEXT("First pose keys"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, FirstFrame, FirstPiloted, nullptr, Report));

    FInfinityCameraPilotLens Lens;
    Lens.FocalLengthMm = 50.0;
    Lens.FocusDistanceCm = 750.0;
    const FTransform SecondPiloted = Reframe(SecondView, FVector(-40.0, 0.0, 20.0), FRotator(0.0, 6.0, -1.0));
    TestTrue(TEXT("Second pose keys with lens"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, SecondFrame, SecondPiloted, &Lens, Report));

    FTransform ReadBack;
    TestTrue(TEXT("Second view evaluates"), Fixture.GetView(SecondFrame, ReadBack, Focal, Focus));
    TestTrue(TEXT("Second view reads back exactly"), ViewsMatch(ReadBack, SecondPiloted));
    TestTrue(TEXT("Focal length reads back"), FMath::IsNearlyEqual(Focal, 50.0f, 0.001f));
    TestTrue(TEXT("Focus distance reads back"), FMath::IsNearlyEqual(Focus, 750.0f, 0.01f));
    TestTrue(TEXT("First view evaluates"), Fixture.GetView(FirstFrame, ReadBack, Focal, Focus));
    TestTrue(TEXT("A later key does not disturb an earlier keyed view"), ViewsMatch(ReadBack, FirstPiloted));
    TestEqual(TEXT("Two pose keys on a channel"), Fixture.CountKeys(EInfinityPassageCameraChannel::HeightOffsetCm), 2);
    TestEqual(TEXT("One lens key"), Fixture.CountKeys(EInfinityPassageCameraChannel::FocalLengthMm), 1);

    // Refusals write nothing.
    AddExpectedErrorPlain(TEXT("INFINITY_CAMERA_PILOT_REFUSED"), EAutomationExpectedErrorFlags::Contains, 4);
    const FFrameNumber PastEnd(Fixture.EndFrame.Value + 1000);
    TestFalse(TEXT("A frame outside the Passage is refused"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, PastEnd, SecondPiloted, nullptr, Report));
    TestFalse(TEXT("An unknown Passage is refused"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, FGuid::NewGuid(), SecondFrame, SecondPiloted, nullptr, Report));

    FInfinityCameraPilotLens BadLens;
    BadLens.FocalLengthMm = 0.0;
    TestFalse(TEXT("A lens below 1 mm is refused"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, SecondFrame, SecondPiloted, &BadLens, Report));

    const TSoftObjectPtr<ULevelSequence> Master = Fixture.Show->ManagedMasterSequence;
    Fixture.Show->ManagedMasterSequence = nullptr;
    TestFalse(TEXT("A Show without a managed Master is refused"), UInfinityStageCameraPilotLibrary::KeyPose(
        *Fixture.World, *Fixture.Show, Fixture.PassageGuid, SecondFrame, SecondPiloted, nullptr, Report));
    TestTrue(TEXT("The refusal says to rebuild the Master"), Report.Contains(TEXT("Rebuild the Master")));
    Fixture.Show->ManagedMasterSequence = Master;

    TestEqual(TEXT("Refusals added no pose keys"), Fixture.CountKeys(EInfinityPassageCameraChannel::HeightOffsetCm), 2);
    TestEqual(TEXT("Refusals added no lens keys"), Fixture.CountKeys(EInfinityPassageCameraChannel::FocalLengthMm), 1);

    Fixture.Destroy();
    return true;
}

#endif
