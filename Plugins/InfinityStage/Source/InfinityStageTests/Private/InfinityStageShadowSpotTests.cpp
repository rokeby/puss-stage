#include "InfinityStageCameraRig.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

/*
 * Puss shadow spot (PS, 7 Oct 2026). The rig's FollowLight appears for a few
 * seconds per cue: smoothstep attack, hold, smoothstep release, evaluated from
 * Passage-relative Master time. Every name here is unique: the tests module is
 * a Unity build.
 */
namespace InfinityStageShadowSpotTests
{
FInfinityShadowSpotCue MakeShadowSpotTestCue(const double Start, const float Candelas)
{
    FInfinityShadowSpotCue Cue;
    Cue.PassageSeconds = Start;
    Cue.AttackSeconds = 0.5;
    Cue.HoldSeconds = 3.0;
    Cue.ReleaseSeconds = 1.0;
    Cue.Intensity = Candelas;
    return Cue;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowSpotEnvelopeTest,
    "InfinityStage.ShadowSpot.Envelope",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowSpotEnvelopeTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageShadowSpotTests;
    float Candelas = -1.0f;

    // Empty schedule: exactly nothing.
    {
        const TArray<FInfinityShadowSpotCue> Empty;
        TestEqual(TEXT("Empty schedule weight is 0"), AInfinityStageCameraRig::EvaluateShadowSpot(Empty, 5.0, Candelas), 0.0);
        TestEqual(TEXT("Empty schedule intensity is 0"), Candelas, 0.0f);
    }

    TArray<FInfinityShadowSpotCue> Cues;
    Cues.Add(MakeShadowSpotTestCue(10.0, 15000.0f));

    struct FSample { double Seconds; double Weight; };
    const FSample Samples[] = {
        { 9.99, 0.0 },   // before
        { 10.0, 0.0 },   // attack starts at 0
        { 10.25, 0.5 },  // smoothstep midpoint
        { 10.5, 1.0 },   // attack done
        { 12.0, 1.0 },   // hold
        { 13.5, 1.0 },   // hold end
        { 14.0, 0.5 },   // release midpoint
        { 14.5, 0.0 },   // release done
        { 20.0, 0.0 },   // after
    };
    for (const FSample& Sample : Samples)
    {
        const double Weight = AInfinityStageCameraRig::EvaluateShadowSpot(Cues, Sample.Seconds, Candelas);
        TestEqual(*FString::Printf(TEXT("Weight at %.2f s"), Sample.Seconds), Weight, Sample.Weight, 1.0e-6);
        TestEqual(*FString::Printf(TEXT("Candelas at %.2f s"), Sample.Seconds),
            static_cast<double>(Candelas), Sample.Weight * 15000.0, 0.05);
    }

    // Scrub-safe: the same time gives the same answer whatever was evaluated before.
    {
        const double Forward = AInfinityStageCameraRig::EvaluateShadowSpot(Cues, 10.1, Candelas);
        AInfinityStageCameraRig::EvaluateShadowSpot(Cues, 14.2, Candelas);
        const double Again = AInfinityStageCameraRig::EvaluateShadowSpot(Cues, 10.1, Candelas);
        TestEqual(TEXT("Re-evaluating a time after a jump is identical"), Again, Forward);
        TestTrue(TEXT("Attack is strictly between 0 and 1"), Forward > 0.0 && Forward < 1.0);
    }

    // Overlapping cues take the brightest.
    {
        TArray<FInfinityShadowSpotCue> Overlap = Cues;
        Overlap.Add(MakeShadowSpotTestCue(13.0, 30000.0f));
        const double Weight = AInfinityStageCameraRig::EvaluateShadowSpot(Overlap, 13.6, Candelas);
        TestEqual(TEXT("Overlap weight is the larger"), Weight, 1.0, 1.0e-6);
        TestEqual(TEXT("Overlap intensity is the brighter cue's"), static_cast<double>(Candelas), 30000.0, 0.05);
    }

    // Zero attack and zero release are a hard cut, never a divide by zero.
    {
        TArray<FInfinityShadowSpotCue> Hard;
        FInfinityShadowSpotCue& Cue = Hard.Add_GetRef(MakeShadowSpotTestCue(1.0, 1000.0f));
        Cue.AttackSeconds = 0.0;
        Cue.ReleaseSeconds = 0.0;
        TestEqual(TEXT("Hard cue is full at its start"), AInfinityStageCameraRig::EvaluateShadowSpot(Hard, 1.0, Candelas), 1.0);
        TestEqual(TEXT("Hard cue is off after its hold"), AInfinityStageCameraRig::EvaluateShadowSpot(Hard, 4.0, Candelas), 0.0);
        TestFalse(TEXT("Hard cue intensity is finite"), FMath::IsNaN(Candelas));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageShadowSpotVisibilityTest,
    "InfinityStage.ShadowSpot.Visibility",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageShadowSpotVisibilityTest::RunTest(const FString& Parameters)
{
    // No cues: the legacy rule, bEnableFollowLight && live, is unchanged.
    TestTrue(TEXT("Legacy: enabled and live shows"), AInfinityStageCameraRig::ShouldShowFollowLight(true, true, false, 0.0));
    TestFalse(TEXT("Legacy: disabled hides"), AInfinityStageCameraRig::ShouldShowFollowLight(false, true, false, 1.0));
    TestFalse(TEXT("Legacy: not live hides"), AInfinityStageCameraRig::ShouldShowFollowLight(true, false, false, 0.0));
    // Cues: the envelope owns visibility, and a rig that is not live never shows it.
    TestFalse(TEXT("Schedule: weight 0 hides even when enabled"), AInfinityStageCameraRig::ShouldShowFollowLight(true, true, true, 0.0));
    TestTrue(TEXT("Schedule: weight > 0 shows even when disabled"), AInfinityStageCameraRig::ShouldShowFollowLight(false, true, true, 0.2));
    TestFalse(TEXT("Schedule: not live hides"), AInfinityStageCameraRig::ShouldShowFollowLight(false, false, true, 1.0));
    return true;
}

#endif
