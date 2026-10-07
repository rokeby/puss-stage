#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "LevelSequence.h"
#include "Misc/AutomationTest.h"
#include "MovieScene.h"

#if WITH_DEV_AUTOMATION_TESTS

/*
 * Cat counters the eye height (CH, 7 Oct 2026). The eye is route z +
 * CameraOffset + the Master section's Camera.HeightOffsetCm; the shadow cat
 * rides the rig, so before CH a keyed eye drop (P05, -90 cm) sank the cat into
 * the floor. The rig now subtracts the evaluated offset from the cat root,
 * exactly as it subtracts the gait bob. Everything here has a unique name:
 * the tests module is a Unity build.
 */
namespace InfinityStageCatHeightOffsetTests
{
constexpr int32 CatHeightWingCount = 5;
constexpr int32 CatHeightIntervalTicks = 24000;

struct FCatHeightShow
{
    UInfinityStageShowAsset* Show = nullptr;
    UMovieSceneInfinityPassageSection* Section = nullptr;
    FInfinityCompiledPassage Passage;
    bool bValid = false;

    FCatHeightShow()
    {
        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
        for (int32 Index = 0; Index < CatHeightWingCount; ++Index)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
            Cue.WingPair.IntervalToNext = FFrameNumber(CatHeightIntervalTicks);
            Cue.WingPair.GapToNextCm = 400.0;
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
        bValid = Passage.SegmentEndFrame.Value > Passage.SegmentStartFrame.Value;
    }

    FMovieSceneDoubleChannel& Height() const
    {
        return *Section->GetCameraChannel(EInfinityPassageCameraChannel::HeightOffsetCm);
    }

    void ClearHeight() const
    {
        Height().Reset();
        Height().SetDefault(0.0);
    }

    /** Five frames spread over the Passage, ends excluded. */
    TArray<int32> SampleFrames() const
    {
        TArray<int32> Frames;
        const int32 Start = Passage.SegmentStartFrame.Value;
        const int32 Span = Passage.SegmentEndFrame.Value - Start;
        for (int32 Step = 1; Step <= 5; ++Step)
        {
            Frames.Add(Start + Span * Step / 6);
        }
        return Frames;
    }
};

struct FCatHeightRig
{
    UWorld* World = nullptr;
    AInfinityStagePassageActor* PassageActor = nullptr;
    AInfinityStageCameraRig* Rig = nullptr;

    FCatHeightRig(const FCatHeightShow& ShowFixture, const bool bSlopedRoute)
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
        // Sloped: the route's up axis is not world Z, so the counter must be
        // the offset's world displacement, not a bare world-Z subtraction.
        PassageActor->Route->SetSplinePoints(
            bSlopedRoute
                ? TArray<FVector>{FVector::ZeroVector, FVector(1500.0, 300.0, 250.0), FVector(3000.0, 900.0, 600.0)}
                : TArray<FVector>{FVector::ZeroVector, FVector(3000.0, 0.0, 0.0)},
            ESplineCoordinateSpace::Local,
            true);
        Rig->PassageActor = PassageActor;
        // Isolate the height offset from the gait bob (no lift sampled).
        Rig->bShadowCatCameraBob = false;
    }

    ~FCatHeightRig()
    {
        if (World)
        {
            World->DestroyWorld(false);
        }
    }

    bool IsValid() const
    {
        return PassageActor && Rig && Rig->ShadowFigureRoot && PassageActor->Route
            && PassageActor->Route->GetSplineLength() > 1700.0;
    }

    /** Evaluates one frame; returns the cat root and the applied eye. */
    bool Evaluate(const int32 Frame, FVector& OutCat, FVector& OutEye, FVector& OutUncountered) const
    {
        if (!Rig->EvaluateAtMasterFrame(FFrameNumber(Frame)))
        {
            return false;
        }
        OutCat = Rig->ShadowFigureRoot->GetComponentLocation();
        OutEye = Rig->GetActorLocation();
        // The pre-CH placement: rig + rotated figure offset - bob, no height counter.
        OutUncountered = Rig->GetActorLocation()
            + Rig->GetActorTransform().TransformVectorNoScale(Rig->ShadowFigureOffset)
            - FVector(0.0, 0.0, Rig->CurrentShadowCatCameraBobCm);
        return true;
    }
};
}

using namespace InfinityStageCatHeightOffsetTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCatCountersHeightOffsetTest,
    "InfinityStage.Camera.ShadowCat.CountersHeightOffset",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCatCountersHeightOffsetTest::RunTest(const FString& Parameters)
{
    const FCatHeightShow ShowFixture;
    TestTrue(TEXT("Fixture: one compiled Passage with a Master section"), ShowFixture.bValid);
    if (!ShowFixture.bValid)
    {
        return false;
    }
    const TArray<int32> Frames = ShowFixture.SampleFrames();

    for (const bool bSloped : {false, true})
    {
        const TCHAR* RouteName = bSloped ? TEXT("sloped") : TEXT("flat");
        const FCatHeightRig Fixture(ShowFixture, bSloped);
        TestTrue(FString::Printf(TEXT("Fixture (%s): rig, Passage actor and route"), RouteName), Fixture.IsValid());
        if (!Fixture.IsValid())
        {
            return false;
        }

        // Baseline at offset 0. At 0 the counter is an exact zero vector (a
        // rotated zero), so the placement is the pre-CH one; the tolerance only
        // absorbs the component's world->relative->world round trip.
        ShowFixture.ClearHeight();
        TArray<FVector> BaseCat;
        TArray<FVector> BaseEye;
        for (const int32 Frame : Frames)
        {
            FVector Cat, Eye, Uncountered;
            TestTrue(FString::Printf(TEXT("(%s) evaluates at offset 0, frame %d"), RouteName, Frame),
                Fixture.Evaluate(Frame, Cat, Eye, Uncountered));
            TestTrue(FString::Printf(TEXT("(%s) bob is off in this fixture"), RouteName),
                Fixture.Rig->CurrentShadowCatCameraBobCm == 0.0);
            TestTrue(FString::Printf(TEXT("(%s) offset 0: cat placement equals pre-CH (1e-4 cm), frame %d"), RouteName, Frame),
                FVector::Distance(Cat, Uncountered) < 1.0e-4);
            BaseCat.Add(Cat);
            BaseEye.Add(Eye);
        }

        // Constant offsets: the eye moves by the offset, the cat does not move.
        for (const double OffsetCm : {-90.0, 120.0})
        {
            ShowFixture.ClearHeight();
            ShowFixture.Height().SetDefault(OffsetCm);
            for (int32 Index = 0; Index < Frames.Num(); ++Index)
            {
                FVector Cat, Eye, Uncountered;
                Fixture.Evaluate(Frames[Index], Cat, Eye, Uncountered);
                // Control: the offset really moved the eye (along the route up axis).
                TestTrue(FString::Printf(TEXT("(%s, %+.0f cm) control: eye moved by the offset, frame %d"), RouteName, OffsetCm, Frames[Index]),
                    FMath::IsNearlyEqual(FVector::Distance(Eye, BaseEye[Index]), FMath::Abs(OffsetCm), 1.0e-3));
                // Negative control: without the counter the cat would have moved with the eye.
                TestTrue(FString::Printf(TEXT("(%s, %+.0f cm) control: uncountered cat would move, frame %d"), RouteName, OffsetCm, Frames[Index]),
                    FVector::Distance(Uncountered, BaseCat[Index]) > 0.5 * FMath::Abs(OffsetCm));
                TestTrue(FString::Printf(TEXT("(%s, %+.0f cm) cat world z unchanged (1e-3 cm), frame %d"), RouteName, OffsetCm, Frames[Index]),
                    FMath::IsNearlyEqual(Cat.Z, BaseCat[Index].Z, 1.0e-3));
                TestTrue(FString::Printf(TEXT("(%s, %+.0f cm) cat world location unchanged (1e-3 cm), frame %d"), RouteName, OffsetCm, Frames[Index]),
                    FVector::Distance(Cat, BaseCat[Index]) < 1.0e-3);
            }
        }

        // Keyed: the P05 shape, eye easing down 90 cm across the Passage.
        ShowFixture.ClearHeight();
        ShowFixture.Height().AddCubicKey(ShowFixture.Passage.SegmentStartFrame, 0.0);
        ShowFixture.Height().AddCubicKey(ShowFixture.Passage.SegmentEndFrame, -90.0);
        for (int32 Index = 0; Index < Frames.Num(); ++Index)
        {
            FVector Cat, Eye, Uncountered;
            Fixture.Evaluate(Frames[Index], Cat, Eye, Uncountered);
            TestTrue(FString::Printf(TEXT("(%s, keyed) control: eye is lowered, frame %d"), RouteName, Frames[Index]),
                FVector::Distance(Eye, BaseEye[Index]) > 1.0);
            TestTrue(FString::Printf(TEXT("(%s, keyed) cat world z unchanged (1e-3 cm), frame %d"), RouteName, Frames[Index]),
                FMath::IsNearlyEqual(Cat.Z, BaseCat[Index].Z, 1.0e-3));
        }
        ShowFixture.ClearHeight();
    }
    return true;
}

#endif
