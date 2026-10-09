#include "SInfinityStageCueDesk.h"

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCueDeskRehearsalPreferenceOnPieStartTest,
    "InfinityStage.Editor.CueDesk.RehearsalPreferenceAppliedOnPIEStart",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCueDeskRehearsalPreferenceOnPieStartTest::RunTest(const FString& Parameters)
{
    // Positive control: a normal PIE start still pushes the saved Rehearsal /
    // Performance preference when start-at-playhead is disabled.
    TestEqual(
        TEXT("Normal PIE applies the preference without seeking"),
        SInfinityStageCueDesk::ResolvePostPieAction(false, true, true, false),
        EInfinityCueDeskPostPieAction::ApplyTransportPreference);

    TestEqual(
        TEXT("Start-at-playhead applies the same preference before seeking"),
        SInfinityStageCueDesk::ResolvePostPieAction(false, true, true, true),
        EInfinityCueDeskPostPieAction::ApplyTransportPreferenceAndSeek);

    // Negative controls: simulation and an unbound desk must not touch a PIE transport.
    TestEqual(
        TEXT("Simulate does not push the PIE preference"),
        SInfinityStageCueDesk::ResolvePostPieAction(true, true, true, true),
        EInfinityCueDeskPostPieAction::None);
    TestEqual(
        TEXT("A desk without a Show does nothing"),
        SInfinityStageCueDesk::ResolvePostPieAction(false, false, true, false),
        EInfinityCueDeskPostPieAction::None);
    TestEqual(
        TEXT("No engine means no PIE transports"),
        SInfinityStageCueDesk::ResolvePostPieAction(false, true, false, false),
        EInfinityCueDeskPostPieAction::None);
    return true;
}

#endif
