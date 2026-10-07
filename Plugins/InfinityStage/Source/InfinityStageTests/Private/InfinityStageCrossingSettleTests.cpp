#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "Algo/Reverse.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

/*
 * Crossing settle (CS, 5 Oct 2026). Measured in PIE that morning, P01 -> Scene 1:
 * the rig's last frame was 33 cm short of and 17 cm below the Entry Handoff
 * camera, still walking at about 250 cm/s. The fixture below reproduces that
 * walk: the last interval runs at 250 cm/s, and earlier intervals alternate
 * 350 / 250 cm/s so the walk carries velocity steps of its own at its pass
 * frames - the yardstick the C1 assertion is measured against.
 */
namespace InfinityStageCrossingSettleTests
{
constexpr int32 SettleWingCount = 6;
constexpr int32 IntervalTicks = 30000;          // 1.25 s at 24 kHz
constexpr double TickRate = 24000.0;            // UInfinityStageShowAsset default
constexpr int32 DisplayStepTicks = 960;         // one 25 fps display frame
constexpr int32 HitchLastFrameTicks = 3200;     // 0.133 s: the measured last rig frame
constexpr int32 SettleTicks = 24000;            // the 1.0 s default
const double SettleGapsCm[SettleWingCount - 1] = {312.5, 437.5, 312.5, 437.5, 312.5};

struct FShowFixture
{
    UInfinityStageShowAsset* Show = nullptr;
    UMovieSceneInfinityPassageSection* Section = nullptr;
    FInfinityCompiledPassage Passage;
    bool bValid = false;

    FShowFixture()
    {
        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
        for (int32 Index = 0; Index < SettleWingCount; ++Index)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
            Cue.WingPair.IntervalToNext = FFrameNumber(IntervalTicks);
            Cue.WingPair.GapToNextCm = SettleGapsCm[FMath::Min(Index, SettleWingCount - 2)];
        }
        Show->EnsureStableIds();
        Show->ReconcilePassageSettings();
        if (Show->PassageSettings.Num() == 1)
        {
            FInfinityPassageSettings& Settings = Show->PassageSettings[0];
            Settings.LeadInFrames = FFrameNumber(0);
            Settings.TailFrames = FFrameNumber(0);
            Settings.LeadInDistanceCm = 0.0;
            Settings.TailDistanceCm = 0.0;
        }
        const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
        if (Compiled.Passages.Num() != 1)
        {
            return;
        }
        Passage = Compiled.Passages[0];

        ULevelSequence* Master = NewObject<ULevelSequence>(GetTransientPackage());
        Master->Initialize();
        UMovieSceneInfinityPassageTrack* Track =
            Master->GetMovieScene()->AddTrack<UMovieSceneInfinityPassageTrack>();
        Section = CastChecked<UMovieSceneInfinityPassageSection>(Track->CreateNewSection());
        Section->PassageGuid = Passage.PassageGuid;
        Section->BlockGuid = Passage.PassageGuid;
        Track->AddSection(*Section);
        Show->ManagedMasterSequence = Master;
        bValid = Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value == (SettleWingCount - 1) * IntervalTicks;
    }

    int32 End() const { return Passage.SegmentEndFrame.Value; }
};

struct FRigFixture
{
    UWorld* World = nullptr;
    AInfinityStagePassageActor* PassageActor = nullptr;
    AInfinityStageCameraRig* Rig = nullptr;

    FRigFixture(const FShowFixture& ShowFixture, const bool bCurvedRoute)
    {
        World = UWorld::CreateWorld(EWorldType::Game, false);
        PassageActor = World->SpawnActor<AInfinityStagePassageActor>();
        Rig = World->SpawnActor<AInfinityStageCameraRig>();
        if (!PassageActor || !Rig)
        {
            return;
        }
        PassageActor->bAutoFitStraightRoute = false;
        PassageActor->ShowAsset = ShowFixture.Show;
        PassageActor->PassageGuid = ShowFixture.Passage.PassageGuid;
        // Straight: exact arc-length parameterization, so the only velocity
        // steps are the walk's own. Curved: the heading changes near the end,
        // so the orientation assertions can fail.
        PassageActor->Route->SetSplinePoints(
            bCurvedRoute
                ? TArray<FVector>{FVector::ZeroVector, FVector(1200.0, 0.0, 0.0), FVector(2400.0, 900.0, 0.0)}
                : TArray<FVector>{FVector::ZeroVector, FVector(4000.0, 0.0, 0.0)},
            ESplineCoordinateSpace::Local,
            true);
        Rig->PassageActor = PassageActor;
    }

    ~FRigFixture()
    {
        if (World)
        {
            World->DestroyWorld(false);
        }
    }

    bool IsValid() const
    {
        return PassageActor && Rig && PassageActor->Route
            && PassageActor->Route->GetSplineLength() > 1900.0;
    }

    FTransform Pose(const int32 Frame) const
    {
        FTransform Out;
        Rig->GetCameraTransformAtMasterFrame(FFrameNumber(Frame), Out);
        return Out;
    }

    FVector Location(const int32 Frame) const
    {
        return Pose(Frame).GetLocation();
    }

    /** |v(t+) - v(t-)| in cm/s from one-sided differences over H ticks. */
    double VelocityJump(const int32 Frame, const int32 H) const
    {
        const FVector Before = (Location(Frame) - Location(Frame - H)) * (TickRate / H);
        const FVector After = (Location(Frame + H) - Location(Frame)) * (TickRate / H);
        return (After - Before).Size();
    }

    double Speed(const int32 FromFrame, const int32 ToFrame) const
    {
        return FVector::Distance(Location(ToFrame), Location(FromFrame)) * TickRate / (ToFrame - FromFrame);
    }
};

double AngleDegrees(const FTransform& A, const FTransform& B)
{
    return FMath::RadiansToDegrees(A.GetRotation().AngularDistance(B.GetRotation()));
}
}

using namespace InfinityStageCrossingSettleTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettleArrivesAtRouteEndTest,
    "InfinityStage.Camera.CrossingSettle.LastFrameIsRouteEndPose",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettleArrivesAtRouteEndTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Default ON: a new rig settles over 1.0 s"),
        GetDefault<AInfinityStageCameraRig>()->CrossingSettleSeconds, 1.0);

    const FShowFixture ShowFixture;
    TestTrue(TEXT("Fixture: one 6.25 s Passage compiles"), ShowFixture.bValid);
    const FRigFixture Fixture(ShowFixture, true);
    TestTrue(TEXT("Fixture: a rig on a curved route long enough for the Passage"), Fixture.IsValid());
    if (!ShowFixture.bValid || !Fixture.IsValid())
    {
        return false;
    }
    const int32 End = ShowFixture.End();
    const int32 LastFrame = End - DisplayStepTicks;
    const int32 HitchFrame = End - HitchLastFrameTicks;

    // Control first: the old behaviour still walking into the cut.
    Fixture.Rig->CrossingSettleSeconds = 0.0;
    const FTransform EndOff = Fixture.Pose(End);
    const FTransform LastOff = Fixture.Pose(LastFrame);
    const FTransform HitchOff = Fixture.Pose(HitchFrame);
    const double LastGapOff = FVector::Distance(LastOff.GetLocation(), EndOff.GetLocation());
    const double LastAngleOff = AngleDegrees(LastOff, EndOff);
    const double HitchGapOff = FVector::Distance(HitchOff.GetLocation(), EndOff.GetLocation());
    TestTrue(FString::Printf(TEXT("Control (settle off): last display frame is %.2f cm short of the route end (> 0.5)"), LastGapOff),
        LastGapOff > 0.5);
    TestTrue(FString::Printf(TEXT("Control (settle off): last display frame is %.3f deg off the route-end heading (> 0.05)"), LastAngleOff),
        LastAngleOff > 0.05);
    TestTrue(FString::Printf(TEXT("Control (settle off): the measured 0.133 s hitch frame is %.2f cm short (> 25, PIE: 33)"), HitchGapOff),
        HitchGapOff > 25.0);

    Fixture.Rig->CrossingSettleSeconds = 1.0;
    const FTransform EndOn = Fixture.Pose(End);
    const FTransform LastOn = Fixture.Pose(LastFrame);
    const FTransform HitchOn = Fixture.Pose(HitchFrame);
    TestTrue(TEXT("The route-end pose itself is unchanged, so the Entry Handoff camera needs no re-match"),
        EndOn.Equals(EndOff, 1.0e-6));
    const double LastGapOn = FVector::Distance(LastOn.GetLocation(), EndOn.GetLocation());
    const double LastAngleOn = AngleDegrees(LastOn, EndOn);
    const double HitchGapOn = FVector::Distance(HitchOn.GetLocation(), EndOn.GetLocation());
    TestTrue(FString::Printf(TEXT("Settled: last display frame within 0.5 cm of the route end (%.4f cm)"), LastGapOn),
        LastGapOn < 0.5);
    TestTrue(FString::Printf(TEXT("Settled: last display frame within 0.05 deg of the route-end heading (%.5f deg)"), LastAngleOn),
        LastAngleOn < 0.05);
    TestTrue(FString::Printf(TEXT("Settled: the 0.133 s hitch frame is within 1 cm of the route end (%.3f cm)"), HitchGapOn),
        HitchGapOn < 1.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettleC1Test,
    "InfinityStage.Camera.CrossingSettle.C1AtSettleStartAndStopsAtEnd",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettleC1Test::RunTest(const FString& Parameters)
{
    const FShowFixture ShowFixture;
    const FRigFixture Fixture(ShowFixture, false);
    TestTrue(TEXT("Fixture: Passage and straight-route rig"), ShowFixture.bValid && Fixture.IsValid());
    if (!ShowFixture.bValid || !Fixture.IsValid())
    {
        return false;
    }
    const int32 End = ShowFixture.End();
    const int32 SettleStart = End - SettleTicks;
    const int32 WalkStepFrame = ShowFixture.Passage.Wings[3].PassFrame.Value; // 250 -> 350 cm/s
    constexpr int32 H = 24;                                                  // 1 ms
    TestTrue(TEXT("Fixture: the settle start is not a pass frame"),
        SettleStart > ShowFixture.Passage.Wings[4].PassFrame.Value + 10 * H);

    // The walk's own step, measured on the unsettled walk where the pass frame
    // is a known Master frame (the settle renormalizes the span, which moves
    // where in Master time the camera reaches that wing).
    Fixture.Rig->CrossingSettleSeconds = 0.0;
    const double WalkJump = Fixture.VelocityJump(WalkStepFrame, H);
    Fixture.Rig->CrossingSettleSeconds = 1.0;
    const double SettleJump = Fixture.VelocityJump(SettleStart, H);
    // Positive control: the same instrument sees the walk's own velocity step.
    TestTrue(FString::Printf(TEXT("Control: the walk's own velocity step is visible (%.2f cm/s > 50)"), WalkJump),
        WalkJump > 50.0);
    TestTrue(FString::Printf(TEXT("C1: the settle start's velocity step (%.4f cm/s) is smaller than the walk's own (%.2f)"),
            SettleJump, WalkJump),
        SettleJump < WalkJump);
    TestTrue(FString::Printf(TEXT("C1: the settle start has no velocity step (%.4f cm/s < 1)"), SettleJump),
        SettleJump < 1.0);

    const double EndSpeedOn = Fixture.Speed(End - H, End);
    double PeakSpeedOn = 0.0;
    for (int32 Frame = ShowFixture.Passage.Wings[4].PassFrame.Value; Frame + DisplayStepTicks <= End; Frame += DisplayStepTicks)
    {
        PeakSpeedOn = FMath::Max(PeakSpeedOn, Fixture.Speed(Frame, Frame + DisplayStepTicks));
    }
    Fixture.Rig->CrossingSettleSeconds = 0.0;
    const double EndSpeedOff = Fixture.Speed(End - H, End);
    TestTrue(FString::Printf(TEXT("Control (settle off): still walking into the cut (%.1f cm/s > 200)"), EndSpeedOff),
        EndSpeedOff > 200.0);
    TestTrue(FString::Printf(TEXT("Settled: stopped at the boundary (%.4f cm/s < 0.5)"), EndSpeedOn),
        EndSpeedOn < 0.5);
    TestTrue(FString::Printf(TEXT("Settled: only slightly faster earlier in the span (peak %.1f vs walk %.1f cm/s, < 1.15x)"),
            PeakSpeedOn, EndSpeedOff),
        PeakSpeedOn < 1.15 * EndSpeedOff);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettleBobWeightTest,
    "InfinityStage.Camera.CrossingSettle.BobWeightZeroAtBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettleBobWeightTest::RunTest(const FString& Parameters)
{
    // The pure composition: the bias Gary saw (-15 cm, rolled) and its fade.
    const FInfinityGaitBob Biased{-15.0, 1.2};
    const FInfinityGaitBob Full = AInfinityStageCameraRig::SettleGaitBob(Biased, 1.0);
    const FInfinityGaitBob Half = AInfinityStageCameraRig::SettleGaitBob(Biased, 0.5);
    const FInfinityGaitBob None = AInfinityStageCameraRig::SettleGaitBob(Biased, 0.0);
    TestEqual(TEXT("Weight 1 keeps the bob height"), Full.HeightCm, -15.0);
    TestEqual(TEXT("Weight 1 keeps the bob roll"), Full.RollDeg, 1.2);
    TestEqual(TEXT("Weight 0.5 halves the bob height"), Half.HeightCm, -7.5);
    TestEqual(TEXT("Weight 0.5 halves the roll with it"), Half.RollDeg, 0.6);
    TestTrue(TEXT("Weight 0 leaves no height"), None.HeightCm == 0.0);
    TestTrue(TEXT("Weight 0 leaves no roll"), None.RollDeg == 0.0);

    // The envelope on Master frames.
    TestEqual(TEXT("Envelope is 1 before the window"),
        UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(99.0, 100.0, 200.0), 1.0);
    TestEqual(TEXT("Envelope is 1 at the window start"),
        UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(100.0, 100.0, 200.0), 1.0);
    TestEqual(TEXT("Envelope is 0.5 at the window midpoint"),
        UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(150.0, 100.0, 200.0), 0.5);
    TestEqual(TEXT("Envelope is exactly 0 at the window end"),
        UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(200.0, 100.0, 200.0), 0.0);
    TestEqual(TEXT("A zero-length window disables the envelope"),
        UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(200.0, 200.0, 200.0), 1.0);

    // Wired through the rig at Master frames.
    const FShowFixture ShowFixture;
    const FRigFixture Fixture(ShowFixture, false);
    TestTrue(TEXT("Fixture: Passage and straight-route rig"), ShowFixture.bValid && Fixture.IsValid());
    if (!ShowFixture.bValid || !Fixture.IsValid())
    {
        return false;
    }
    const int32 End = ShowFixture.End();
    AInfinityStageCameraRig* Rig = Fixture.Rig;
    Rig->CrossingSettleSeconds = 1.0;

    double PreviousWeight = 1.0;
    bool bMonotone = true;
    for (int32 Frame = End - SettleTicks - 4 * DisplayStepTicks; Frame < End; Frame += DisplayStepTicks)
    {
        Rig->EvaluateAtMasterFrame(FFrameNumber(Frame));
        bMonotone = bMonotone && Rig->CurrentCrossingSettleWeight <= PreviousWeight + 1.0e-12;
        PreviousWeight = Rig->CurrentCrossingSettleWeight;
    }
    TestTrue(TEXT("Settle weight never rises toward the boundary"), bMonotone);

    TestTrue(TEXT("Evaluates before the settle window"),
        Rig->EvaluateAtMasterFrame(FFrameNumber(End - SettleTicks - DisplayStepTicks)));
    TestEqual(TEXT("Bob weight is full before the settle window"), Rig->CurrentCrossingSettleWeight, 1.0);
    TestTrue(TEXT("Evaluates mid-window"), Rig->EvaluateAtMasterFrame(FFrameNumber(End - SettleTicks / 2)));
    TestTrue(TEXT("Bob weight is partial mid-window"),
        Rig->CurrentCrossingSettleWeight > 0.25 && Rig->CurrentCrossingSettleWeight < 0.75);
    TestTrue(TEXT("Evaluates at the boundary"), Rig->EvaluateAtMasterFrame(FFrameNumber(End)));
    TestTrue(TEXT("Bob weight is exactly 0 at the boundary"), Rig->CurrentCrossingSettleWeight == 0.0);
    TestTrue(TEXT("No bob height is applied at the boundary"), Rig->CurrentShadowCatCameraBobCm == 0.0);
    const FTransform Applied = Rig->GetActorTransform();
    const FTransform RouteEnd = Fixture.Pose(End);
    TestTrue(TEXT("The applied boundary pose is the un-bobbed route end (0.5 cm)"),
        FVector::Distance(Applied.GetLocation(), RouteEnd.GetLocation()) < 0.5);
    TestTrue(TEXT("The applied boundary pose carries no roll (0.05 deg)"), AngleDegrees(Applied, RouteEnd) < 0.05);

    // Control: with the settle off the boundary keeps the full bob weight.
    Rig->CrossingSettleSeconds = 0.0;
    Rig->EvaluateAtMasterFrame(FFrameNumber(End));
    TestEqual(TEXT("Control (settle off): bob weight stays full at the boundary"), Rig->CurrentCrossingSettleWeight, 1.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettleScrubTest,
    "InfinityStage.Camera.CrossingSettle.ScrubAndReverseMatchPlay",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettleScrubTest::RunTest(const FString& Parameters)
{
    const FShowFixture ShowFixture;
    const FRigFixture Fixture(ShowFixture, true);
    TestTrue(TEXT("Fixture: Passage and curved-route rig"), ShowFixture.bValid && Fixture.IsValid());
    if (!ShowFixture.bValid || !Fixture.IsValid())
    {
        return false;
    }
    AInfinityStageCameraRig* Rig = Fixture.Rig;
    Rig->CrossingSettleSeconds = 1.0;
    // The gait lift is MR's own history-dependent filter (it re-primes on
    // reverse by design, and GaitBobMasterTimed covers it). With it off this
    // compares the route + settle pose alone; the walk weight still runs.
    Rig->bShadowCatCameraBob = false;

    const int32 End = ShowFixture.End();
    TArray<int32> Frames;
    for (int32 Frame = End - SettleTicks - 6 * DisplayStepTicks; Frame < End; Frame += DisplayStepTicks)
    {
        Frames.Add(Frame);
    }
    Frames.Add(End);

    struct FSample
    {
        FTransform Pose;
        double SettleWeight = -1.0;
        double WalkWeight = -1.0;
    };
    const auto Run = [Rig](const TArray<int32>& Order)
    {
        TMap<int32, FSample> Samples;
        for (const int32 Frame : Order)
        {
            Rig->EvaluateAtMasterFrame(FFrameNumber(Frame));
            Samples.Add(Frame, FSample{Rig->GetActorTransform(), Rig->CurrentCrossingSettleWeight, Rig->CurrentShadowCatBobWalkWeight});
        }
        return Samples;
    };

    const TMap<int32, FSample> Play = Run(Frames);
    TArray<int32> Reverse = Frames;
    Algo::Reverse(Reverse);
    const TMap<int32, FSample> Reversed = Run(Reverse);
    TArray<int32> Scrub = Frames;
    FRandomStream Stream(0x5E771E);
    for (int32 Index = Scrub.Num() - 1; Index > 0; --Index)
    {
        Scrub.Swap(Index, Stream.RandRange(0, Index));
    }
    const TMap<int32, FSample> Scrubbed = Run(Scrub);
    // Pause: the same frame evaluated twice in a row.
    Rig->EvaluateAtMasterFrame(FFrameNumber(Frames[Frames.Num() / 2]));
    const FTransform PausedFirst = Rig->GetActorTransform();
    Rig->EvaluateAtMasterFrame(FFrameNumber(Frames[Frames.Num() / 2]));
    TestTrue(TEXT("Pause: a held frame repeats its pose exactly"), Rig->GetActorTransform().Equals(PausedFirst, 1.0e-9));

    // Tolerances. The pose is a pure function of the Master frame, but it is
    // read back through the actor: USceneComponent keeps a stateful
    // Rotator<->Quat conversion cache (SceneComponent.h:360-363, 960), so the
    // stored rotation can differ in the last bits depending on the previous
    // frame, and FQuat::AngularDistance is acos(2d^2 - 1) (Quat.h:1228-1231),
    // which turns a 1e-16 dot-product difference into about 1e-6 degrees. The
    // first CI run measured 2.41e-6. 1e-3 cm and 1e-4 deg are about 400x that
    // floor and still 500x tighter than the 0.5 cm / 0.05 deg crossing spec,
    // so any real history dependence (a stateful settle would differ by
    // centimetres) still fails. The control below proves the instrument sees
    // a one-display-frame difference far above both tolerances.
    constexpr double SettlePositionToleranceCm = 1.0e-3;
    constexpr double AngleToleranceDeg = 1.0e-4;
    double MaxPositionError = 0.0;
    double MaxAngleError = 0.0;
    double MaxWeightError = 0.0;
    double MaxWalkWeightDifference = 0.0;
    for (const int32 Frame : Frames)
    {
        const FSample& P = Play.FindChecked(Frame);
        for (const FSample* Other : {&Reversed.FindChecked(Frame), &Scrubbed.FindChecked(Frame)})
        {
            MaxPositionError = FMath::Max(MaxPositionError, FVector::Distance(P.Pose.GetLocation(), Other->Pose.GetLocation()));
            MaxAngleError = FMath::Max(MaxAngleError, AngleDegrees(P.Pose, Other->Pose));
            MaxWeightError = FMath::Max(MaxWeightError, FMath::Abs(P.SettleWeight - Other->SettleWeight));
        }
        MaxWalkWeightDifference = FMath::Max(MaxWalkWeightDifference, FMath::Abs(P.WalkWeight - Reversed.FindChecked(Frame).WalkWeight));
    }
    // History control: the orders really did leave the rig in different states.
    TestTrue(FString::Printf(TEXT("Control: play and reverse built different rig histories (walk weight differs by %.3f > 0.05)"),
            MaxWalkWeightDifference),
        MaxWalkWeightDifference > 0.05);
    // Instrument control: one display frame apart, early in the window, on the curve.
    const FTransform& Adjacent0 = Play.FindChecked(Frames[0]).Pose;
    const FTransform& Adjacent1 = Play.FindChecked(Frames[1]).Pose;
    const double AdjacentPositionCm = FVector::Distance(Adjacent0.GetLocation(), Adjacent1.GetLocation());
    const double AdjacentAngleDeg = AngleDegrees(Adjacent0, Adjacent1);
    TestTrue(FString::Printf(TEXT("Control: adjacent frames differ by %.3f cm, far above the %.0e cm tolerance"),
            AdjacentPositionCm, SettlePositionToleranceCm),
        AdjacentPositionCm > 1000.0 * SettlePositionToleranceCm);
    TestTrue(FString::Printf(TEXT("Control: adjacent frames differ by %.5f deg, far above the %.0e deg tolerance"),
            AdjacentAngleDeg, AngleToleranceDeg),
        AdjacentAngleDeg > 100.0 * AngleToleranceDeg);
    TestTrue(FString::Printf(TEXT("Reverse and scrub give play's position at every frame (max error %.2e cm < %.0e)"),
            MaxPositionError, SettlePositionToleranceCm),
        MaxPositionError < SettlePositionToleranceCm);
    TestTrue(FString::Printf(TEXT("Reverse and scrub give play's orientation at every frame (max error %.2e deg < %.0e)"),
            MaxAngleError, AngleToleranceDeg),
        MaxAngleError < AngleToleranceDeg);
    TestTrue(FString::Printf(TEXT("Reverse and scrub give play's settle weight (max error %.2e)"), MaxWeightError),
        MaxWeightError == 0.0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettleZeroDisablesTest,
    "InfinityStage.Camera.CrossingSettle.ZeroSecondsDisablesExactly",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettleZeroDisablesTest::RunTest(const FString& Parameters)
{
    const FShowFixture ShowFixture;
    TestTrue(TEXT("Fixture: one Passage compiles"), ShowFixture.bValid);
    if (!ShowFixture.bValid)
    {
        return false;
    }
    const UMovieSceneInfinityPassageSection& Section = *ShowFixture.Section;
    const int32 Start = ShowFixture.Passage.SegmentStartFrame.Value;
    const int32 End = ShowFixture.End();

    // Section: 0 (and negative) is the previous evaluation, bit for bit.
    bool bIdentical = true;
    bool bWeightOne = true;
    for (int32 Frame = Start; Frame <= End; Frame += 480)
    {
        FInfinityPassageCameraEvaluation Legacy;
        FInfinityPassageCameraEvaluation Zero;
        FInfinityPassageCameraEvaluation Negative;
        Section.EvaluateCamera(ShowFixture.Passage, FFrameTime(Frame), Legacy);
        Section.EvaluateCamera(ShowFixture.Passage, FFrameTime(Frame), Zero, 0.0);
        Section.EvaluateCamera(ShowFixture.Passage, FFrameTime(Frame), Negative, -1.0);
        bIdentical = bIdentical
            && Legacy.DistanceMasterFrame == Zero.DistanceMasterFrame
            && Legacy.DistanceMasterFrame == Negative.DistanceMasterFrame;
        bWeightOne = bWeightOne && Zero.SettleWeight == 1.0 && Negative.SettleWeight == 1.0;
    }
    TestTrue(TEXT("Settle 0 s evaluates the exact previous distance frame everywhere"), bIdentical);
    TestTrue(TEXT("Settle 0 s reports full weight everywhere"), bWeightOne);

    // Rig: 0 s reproduces the unsettled route pose exactly; 1 s does not.
    const FRigFixture Fixture(ShowFixture, false);
    TestTrue(TEXT("Fixture: straight-route rig"), Fixture.IsValid());
    if (!Fixture.IsValid())
    {
        return false;
    }
    const auto UnsettledLocation = [&ShowFixture, &Section, &Fixture](const int32 Frame)
    {
        FInfinityPassageCameraEvaluation Evaluation;
        Section.EvaluateCamera(ShowFixture.Passage, FFrameTime(Frame), Evaluation);
        const double DistanceCm = FInfinityStageCompiler::EvaluateDistanceAtFrame(ShowFixture.Passage, Evaluation.DistanceMasterFrame);
        return Fixture.PassageActor->Route->GetLocationAtDistanceAlongSpline(DistanceCm, ESplineCoordinateSpace::World);
    };
    double MaxErrorOff = 0.0;
    double MaxErrorOn = 0.0;
    for (int32 Frame = End - SettleTicks - 4 * DisplayStepTicks; Frame <= End; Frame += DisplayStepTicks / 2)
    {
        Fixture.Rig->CrossingSettleSeconds = 0.0;
        MaxErrorOff = FMath::Max(MaxErrorOff, FVector::Distance(Fixture.Location(Frame), UnsettledLocation(Frame)));
        Fixture.Rig->CrossingSettleSeconds = 1.0;
        MaxErrorOn = FMath::Max(MaxErrorOn, FVector::Distance(Fixture.Location(Frame), UnsettledLocation(Frame)));
    }
    TestTrue(FString::Printf(TEXT("Control: with 1 s the rig departs from the unsettled walk (%.2f cm > 5)"), MaxErrorOn),
        MaxErrorOn > 5.0);
    TestTrue(FString::Printf(TEXT("Rig at 0 s reproduces the unsettled walk exactly (%.2e cm)"), MaxErrorOff),
        MaxErrorOff < 1.0e-6);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCrossingSettlePinsTest,
    "InfinityStage.Camera.CrossingSettle.PinsAndEndStayAbsolute",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCrossingSettlePinsTest::RunTest(const FString& Parameters)
{
    const FShowFixture ShowFixture;
    TestTrue(TEXT("Fixture: one Passage compiles"), ShowFixture.bValid);
    if (!ShowFixture.bValid)
    {
        return false;
    }
    UMovieSceneInfinityPassageSection& Section = *ShowFixture.Section;
    const FInfinityCompiledPassage& Passage = ShowFixture.Passage;
    const int32 Start = Passage.SegmentStartFrame.Value;
    const int32 End = ShowFixture.End();
    const int32 PinFrame = Passage.Wings[4].PassFrame.Value;
    const auto DistanceFrame = [&Section, &Passage](const int32 Frame, const double Settle)
    {
        FInfinityPassageCameraEvaluation Evaluation;
        Section.EvaluateCamera(Passage, FFrameTime(Frame), Evaluation, Settle);
        return Evaluation;
    };

    // Unpinned, the whole Passage is one span: start and end stay exact, and the
    // walk is renormalized, so an interior wing is reached early (the control).
    TestTrue(TEXT("Settled: the Passage start is exact"),
        FMath::IsNearlyEqual(DistanceFrame(Start, SettleTicks).DistanceMasterFrame.AsDecimal(), static_cast<double>(Start), 1.0e-6));
    TestTrue(TEXT("Settled: the Passage end is exact"),
        FMath::IsNearlyEqual(DistanceFrame(End, SettleTicks).DistanceMasterFrame.AsDecimal(), static_cast<double>(End), 1.0e-6));
    const double UnpinnedLead = DistanceFrame(PinFrame, SettleTicks).DistanceMasterFrame.AsDecimal() - PinFrame;
    TestTrue(FString::Printf(TEXT("Control: unpinned, the walk reaches the 5th wing early (%.0f ticks > 100)"), UnpinnedLead),
        UnpinnedLead > 100.0);
    double Previous = -1.0;
    bool bMonotone = true;
    for (int32 Frame = Start; Frame <= End; Frame += 240)
    {
        const double Current = DistanceFrame(Frame, SettleTicks).DistanceMasterFrame.AsDecimal();
        bMonotone = bMonotone && Current + 1.0e-6 >= Previous;
        Previous = Current;
    }
    TestTrue(TEXT("Settled: the walk never reverses"), bMonotone);

    // Pinned wing: pins travel, keys don't - the pin keeps its frame.
    Section.PinnedWingCueGuids.Add(Passage.Wings[4].CueGuid);
    TestTrue(TEXT("Pinned: the 5th wing is reached at its own frame with the settle on"),
        FMath::IsNearlyEqual(DistanceFrame(PinFrame, SettleTicks).DistanceMasterFrame.AsDecimal(), static_cast<double>(PinFrame), 0.001));
    TestEqual(TEXT("Pinned: the settle does not reach back past the last pin"),
        DistanceFrame(PinFrame + 1, SettleTicks).SettleWeight, 1.0);
    TestTrue(TEXT("Pinned: a span before the last is untouched by the settle"),
        DistanceFrame(Passage.Wings[2].PassFrame.Value + 1000, SettleTicks).DistanceMasterFrame
            == DistanceFrame(Passage.Wings[2].PassFrame.Value + 1000, 0.0).DistanceMasterFrame);

    // A last span shorter than the settle: the window shrinks to the span.
    Section.PinnedWingCueGuids.Reset();
    const int32 LatePinRelative = End - Start - 10000;
    Section.PinnedPassageFrames.Add(FFrameNumber(LatePinRelative));
    const int32 LatePin = Start + LatePinRelative;
    TestTrue(TEXT("Short last span: the late pin keeps its frame"),
        FMath::IsNearlyEqual(DistanceFrame(LatePin, SettleTicks).DistanceMasterFrame.AsDecimal(), static_cast<double>(LatePin), 0.001));
    // Unclamped, a 1 s window would already be at 0.37 here.
    TestEqual(TEXT("Short last span: the window shrinks to the span (full weight just after its opening pin)"),
        DistanceFrame(LatePin + 1, SettleTicks).SettleWeight, 1.0);
    TestEqual(TEXT("Short last span: zero weight at the end"), DistanceFrame(End, SettleTicks).SettleWeight, 0.0);
    const double TailTicks = End - DistanceFrame(End - 24, SettleTicks).DistanceMasterFrame.AsDecimal();
    TestTrue(FString::Printf(TEXT("Short last span: still stopped at the end (%.4f ticks behind 1 ms out)"), TailTicks),
        TailTicks >= 0.0 && TailTicks < 0.05);
    Section.PinnedPassageFrames.Reset();
    return true;
}

#endif
