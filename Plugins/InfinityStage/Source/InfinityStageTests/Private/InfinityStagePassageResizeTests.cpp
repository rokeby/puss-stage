#include "InfinityStagePassageResizeLibrary.h"

#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR

namespace
{
struct FPassageResizeFixture
{
    UInfinityStageShowAsset* Show = nullptr;
    UWorld* World = nullptr;
    AInfinityStagePassageActor* PassageActor = nullptr;
    FGuid PassageGuid;
    TArray<FGuid> OriginalCueGuids;
    TArray<FGuid> OriginalOccurrenceGuids;

    FPassageResizeFixture()
    {
        Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
        for (int32 Index = 0; Index < 23; ++Index)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
            Cue.WingPair.IntervalToNext = FFrameNumber(48000); // two seconds at 24 kHz
            Cue.WingPair.GapToNextCm = 500.0;
            Cue.Label = FText::Format(
                NSLOCTEXT("InfinityStageTests", "ResizeWingLabel", "Test Wing {0}"),
                FText::AsNumber(Index + 1));
            OriginalCueGuids.Add(Cue.CueGuid);
            OriginalOccurrenceGuids.Add(Cue.WingPair.OccurrenceGuid);
        }
        Show->EnsureStableIds();
        Show->ReconcilePassageSettings();
        check(Show->PassageSettings.Num() == 1);
        FInfinityPassageSettings& Settings = Show->PassageSettings[0];
        PassageGuid = Settings.PassageGuid;
        Settings.Label = FText::FromString(TEXT("Test Passage"));
        Settings.FitMode = EInfinityPassageFitMode::ManualPassage;
        Settings.PreferredCameraSpeedCmPerSecond = 250.0;
        Settings.PreferredSpacingCm = 500.0;
        Settings.LeadInFrames = FFrameNumber(0);
        Settings.TailFrames = FFrameNumber(81600); // 44.0 + 3.4 = 47.4 seconds
        Settings.LeadInDistanceCm = 0.0;
        // A 350 cm physical tail makes the 180 s fit select 90 pairs; the exact
        // frame residual is then explicitly absorbed as a 500 cm / 2 s tail.
        Settings.TailDistanceCm = 350.0;

        World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        PassageActor = World->SpawnActor<AInfinityStagePassageActor>();
        PassageActor->ShowAsset = Show;
        PassageActor->PassageGuid = PassageGuid;
        SetStraightRoute(50000.0);
    }

    ~FPassageResizeFixture()
    {
        World->DestroyWorld(false);
    }

    void SetStraightRoute(const double LengthCm)
    {
        PassageActor->Route->SetSplinePoints(
            {FVector::ZeroVector, FVector(LengthCm, 0.0, 0.0)},
            ESplineCoordinateSpace::Local,
            true);
    }

    void SetShortShapedRoute()
    {
        PassageActor->Route->SetSplinePoints(
            {FVector::ZeroVector, FVector(1000.0, 500.0, 0.0), FVector(2000.0, 0.0, 0.0)},
            ESplineCoordinateSpace::Local,
            true);
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEditorPassageResizeAppendsToDurationTest,
    "InfinityStage.Editor.PassageResizeAppendsToDuration",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEditorPassageResizeAppendsToDurationTest::RunTest(const FString& Parameters)
{
    FPassageResizeFixture Fixture;
    const FInfinityCompileResult Before = FInfinityStageCompiler::Compile(*Fixture.Show);
    TestEqual(TEXT("The source fixture has one Passage"), Before.Passages.Num(), 1);
    if (Before.Passages.Num() != 1)
    {
        return false;
    }
    const double OldDuration =
        (Before.Passages[0].SegmentEndFrame - Before.Passages[0].SegmentStartFrame).Value
        / Fixture.Show->TickResolution.AsDecimal();
    TestEqual(TEXT("The source fixture has 23 pairs"), Before.Passages[0].Wings.Num(), 23);
    TestTrue(TEXT("The source fixture is exactly 47.4 seconds"),
        FMath::IsNearlyEqual(OldDuration, 47.4, 1.0e-9));

    const FInfinityPassageResizePlan Applied =
        UInfinityStagePassageResizeLibrary::ResizePassageToDuration(
            Fixture.Show,
            Fixture.World,
            nullptr,
            Fixture.PassageGuid,
            180.0,
            EInfinityPassageResizePolicy::PreserveSpeedAndSpacing,
            false,
            false);
    TestTrue(TEXT("The exact 180-second resize can apply"), Applied.bCanApply);
    TestTrue(TEXT("The exact 180-second resize applies"), Applied.bApplied);
    TestEqual(TEXT("The resize derives 90 pairs"), Applied.NewWingPairCount, 90);
    TestEqual(TEXT("The resize appends 67 pairs"), Applied.PairsAppended, 67);
    TestTrue(TEXT("The plan reports exactly 180.000 seconds"),
        FMath::IsNearlyEqual(Applied.NewDurationSeconds, 180.0, 1.0e-9));
    TestEqual(TEXT("The mutated Show has 90 rows"), Fixture.Show->Cues.Num(), 90);

    TSet<FGuid> AllCueGuids;
    TSet<FGuid> AllOccurrenceGuids;
    for (int32 Index = 0; Index < Fixture.Show->Cues.Num(); ++Index)
    {
        const FInfinityShowCue& Cue = Fixture.Show->Cues[Index];
        TestTrue(*FString::Printf(TEXT("Cue GUID %d is valid"), Index), Cue.CueGuid.IsValid());
        TestTrue(*FString::Printf(TEXT("Occurrence GUID %d is valid"), Index),
            Cue.WingPair.OccurrenceGuid.IsValid());
        TestFalse(*FString::Printf(TEXT("Cue GUID %d is unique"), Index),
            AllCueGuids.Contains(Cue.CueGuid));
        TestFalse(*FString::Printf(TEXT("Occurrence GUID %d is unique"), Index),
            AllOccurrenceGuids.Contains(Cue.WingPair.OccurrenceGuid));
        AllCueGuids.Add(Cue.CueGuid);
        AllOccurrenceGuids.Add(Cue.WingPair.OccurrenceGuid);
        if (Index < 23)
        {
            TestEqual(*FString::Printf(TEXT("Existing cue GUID %d stays in order"), Index),
                Cue.CueGuid, Fixture.OriginalCueGuids[Index]);
            TestEqual(*FString::Printf(TEXT("Existing occurrence GUID %d stays in order"), Index),
                Cue.WingPair.OccurrenceGuid, Fixture.OriginalOccurrenceGuids[Index]);
        }
        else
        {
            TestFalse(*FString::Printf(TEXT("Appended cue GUID %d is new"), Index),
                Fixture.OriginalCueGuids.Contains(Cue.CueGuid));
            TestFalse(*FString::Printf(TEXT("Appended occurrence GUID %d is new"), Index),
                Fixture.OriginalOccurrenceGuids.Contains(Cue.WingPair.OccurrenceGuid));
        }
    }
    const FInfinityCompileResult After = FInfinityStageCompiler::Compile(*Fixture.Show);
    const double NewDuration =
        (After.Passages[0].SegmentEndFrame - After.Passages[0].SegmentStartFrame).Value
        / Fixture.Show->TickResolution.AsDecimal();
    TestTrue(TEXT("The applied Show compiles to exactly 180.000 seconds"),
        FMath::IsNearlyEqual(NewDuration, 180.0, 1.0e-9));

    FPassageResizeFixture ResidualFixture;
    ResidualFixture.Show->TickResolution = FFrameRate(25, 1);
    const FInfinityPassageResizePlan ResidualRefusal =
        UInfinityStagePassageResizeLibrary::ResizePassageToDuration(
            ResidualFixture.Show,
            ResidualFixture.World,
            nullptr,
            ResidualFixture.PassageGuid,
            180.02,
            EInfinityPassageResizePolicy::PreserveSpeedAndSpacing,
            true,
            false);
    TestFalse(TEXT("A target whose frame residual cannot close is refused"),
        ResidualRefusal.bCanApply);
    TestTrue(TEXT("The residual refusal explains exact representation or closure"),
        ResidualRefusal.RefusalReasons.ContainsByPredicate([](const FString& Reason)
        {
            return Reason.Contains(TEXT("representable")) || Reason.Contains(TEXT("Residual did not close"));
        }));
    TestEqual(TEXT("A residual refusal leaves all source rows untouched"),
        ResidualFixture.Show->Cues.Num(), 23);

    FPassageResizeFixture ShapedFixture;
    ShapedFixture.SetShortShapedRoute();
    const FInfinityPassageResizePlan ShapedRefusal =
        UInfinityStagePassageResizeLibrary::ResizePassageToDuration(
            ShapedFixture.Show,
            ShapedFixture.World,
            nullptr,
            ShapedFixture.PassageGuid,
            180.0,
            EInfinityPassageResizePolicy::PreserveSpeedAndSpacing,
            true,
            false);
    TestFalse(TEXT("A shaped route shorter than the derived extent is refused"),
        ShapedRefusal.bCanApply);
    TestTrue(TEXT("The shaped-route refusal names the Auto Fit risk"),
        ShapedRefusal.RefusalReasons.ContainsByPredicate([](const FString& Reason)
        {
            return Reason.Contains(TEXT("Shaped route")) && Reason.Contains(TEXT("Auto Fit"));
        }));
    TestEqual(TEXT("A shaped-route refusal leaves all source rows untouched"),
        ShapedFixture.Show->Cues.Num(), 23);

    // Negative control: with ResizePassageToDuration stubbed, the apply remains at
    // 23 rows/47.4 s and fails the 90/67/180/GUID sentinels; if either refusal is
    // removed, its explicit bCanApply and unchanged-row sentinels fail.
    return true;
}

#endif
