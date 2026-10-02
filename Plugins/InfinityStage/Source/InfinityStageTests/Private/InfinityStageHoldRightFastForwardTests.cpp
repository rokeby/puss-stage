#include "InfinityStageTransportController.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageHoldRightFastForwardsTest,
    "InfinityStage.Transport.HoldRightFastForwards",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageHoldRightFastForwardsTest::RunTest(const FString& Parameters)
{
    constexpr float Threshold = 0.30f;
    const UInfinityStageTransportController* Defaults =
        GetDefault<UInfinityStageTransportController>();
    TestEqual(TEXT("The editable hold threshold defaults to 0.30 seconds"),
        Defaults->HoldThresholdSeconds, Threshold);
    TestEqual(TEXT("The editable fast-forward rate defaults to 4x"),
        Defaults->FastForwardRate, 4.0f);

    {
        FInfinityHoldRightState State;
        State.Press(false);
        TestEqual(TEXT("A tap does nothing before release"),
            State.Tick(0.29f, Threshold), EInfinityHoldRightAction::None);
        TestEqual(TEXT("A tap keeps the old advance path"),
            State.Release(), EInfinityHoldRightAction::Advance);
    }

    {
        FInfinityHoldRightState State;
        State.Press(false);
        TestEqual(TEXT("Crossing the threshold begins fast-forward"),
            State.Tick(Threshold, Threshold), EInfinityHoldRightAction::BeginFastForward);
        State.ResolveFastForwardStart(EInfinityTransportResult::Succeeded);
        TestTrue(TEXT("The rate-changing hold is active after the transport accepts it"),
            State.bFastForwardActive);
        TestEqual(TEXT("Release restores 1x and holds when playback began held"),
            State.Release(), EInfinityHoldRightAction::EndFastForwardHeld);
    }

    {
        FInfinityHoldRightState State;
        State.Press(true);
        TestEqual(TEXT("A playing transport also enters fast-forward at the threshold"),
            State.Tick(Threshold, Threshold), EInfinityHoldRightAction::BeginFastForward);
        State.ResolveFastForwardStart(EInfinityTransportResult::Succeeded);
        TestEqual(TEXT("Release restores 1x and keeps prior playback playing"),
            State.Release(), EInfinityHoldRightAction::EndFastForwardPlaying);
    }

    {
        FInfinityHoldRightState State;
        State.Press(false);
        TestEqual(TEXT("The held gesture reaches the transport once"),
            State.Tick(Threshold, Threshold), EInfinityHoldRightAction::BeginFastForward);
        State.ResolveFastForwardStart(EInfinityTransportResult::UnsafeExternalClock);
        TestFalse(TEXT("The performance interlock refusal never activates fast-forward"),
            State.bFastForwardActive);
        TestEqual(TEXT("The refused hold is consumed and cannot become a tap advance"),
            State.Release(), EInfinityHoldRightAction::None);
    }

    return true;
}

#endif
