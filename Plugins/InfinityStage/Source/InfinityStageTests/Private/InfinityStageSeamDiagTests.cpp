#include "InfinityStageTransportController.h"

#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Seam diagnostic (InfinityStage.SeamDiag), for the "snap at the hangar after a
 * pause" report of 6 Oct. Diagnostic only: it changes no behaviour, so these
 * tests prove that it is silent when off, speaks with both clocks when on, and
 * that its frame filter and range lookup are right.
 */
namespace
{
struct FScopedSeamDiag
{
    IConsoleVariable* Variable = nullptr;
    int32 Previous = 0;
    explicit FScopedSeamDiag(const int32 Value)
    {
        Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("InfinityStage.SeamDiag"));
        if (Variable)
        {
            Previous = Variable->GetInt();
            Variable->Set(Value, ECVF_SetByConsole);
        }
    }
    ~FScopedSeamDiag()
    {
        if (Variable)
        {
            Variable->Set(Previous, ECVF_SetByConsole);
        }
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSeamDiagGateTest,
    "InfinityStage.Transport.SeamDiag.SilentWhenOffBothClocksWhenOn",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSeamDiagGateTest::RunTest(const FString& Parameters)
{
    UInfinityStageTransportController* Transport = NewObject<UInfinityStageTransportController>(GetTransientPackage());
    TArray<FString> Lines;
    Transport->SeamDiagSinkForTests = [&Lines](const FString& Line) { Lines.Add(Line); };
    {
        FScopedSeamDiag Off(0);
        TestNotNull(TEXT("The cvar exists"), Off.Variable);
        Transport->PauseTransport();
        Transport->ResumeForward();
        TestEqual(TEXT("Off (default): no line at all"), Lines.Num(), 0);
    }
    {
        FScopedSeamDiag On(1);
        const EInfinityTransportResult Result = Transport->PauseTransport();
        TestEqual(TEXT("Behaviour unchanged: no player is still NoPlayer"), Result, EInfinityTransportResult::NoPlayer);
        TestEqual(TEXT("On: one line for the pause"), Lines.Num(), 1);
        const FString Line = Lines.IsEmpty() ? FString() : Lines[0];
        TestTrue(TEXT("Tagged pause"), Line.StartsWith(TEXT("INFINITY_SEAM_DIAG|ev=pause|")));
        TestTrue(TEXT("Carries the Master clock"), Line.Contains(TEXT("|frame=")) && Line.Contains(TEXT("|master_s=")));
        TestTrue(TEXT("Carries the world clocks"), Line.Contains(TEXT("|world_s=")) && Line.Contains(TEXT("|unpaused_s="))
            && Line.Contains(TEXT("|real_s=")) && Line.Contains(TEXT("|dt=")));
        TestTrue(TEXT("Carries the segment by both tables"), Line.Contains(TEXT("|seg=")) && Line.Contains(TEXT("|seg_by_master=")));
        TestTrue(TEXT("Carries the result"), Line.Contains(TEXT("|result=1")));
    }
    Transport->SeamDiagSinkForTests = nullptr;
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSeamDiagPureTest,
    "InfinityStage.Transport.SeamDiag.FrameFilterAndRanges",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSeamDiagPureTest::RunTest(const FString& Parameters)
{
    using T = UInfinityStageTransportController;
    TestTrue(TEXT("Inside the boundary window"), T::ShouldLogSeamFrame(0.5, 1.0, 0.016, 0.0, 0.0, 5.0, 2.0));
    TestFalse(TEXT("Quiet mid-segment frame"), T::ShouldLogSeamFrame(30.0, 1.0, 0.016, 2.0, 0.5, 5.0, 2.0));
    TestTrue(TEXT("A 0.4 s hitch frame (MaxUndilatedFrameTime clamp)"), T::ShouldLogSeamFrame(30.0, 1.0, 0.4, 0.0, 0.0, 5.0, 2.0));
    TestTrue(TEXT("A positional snap"), T::ShouldLogSeamFrame(30.0, 1.0, 0.016, 33.0, 0.0, 5.0, 2.0));
    TestTrue(TEXT("A rotational snap"), T::ShouldLogSeamFrame(30.0, 1.0, 0.016, 0.0, 7.0, 5.0, 2.0));

    TArray<TRange<FFrameNumber>> Ranges;
    Ranges.Add(TRange<FFrameNumber>(FFrameNumber(0), FFrameNumber(100)));
    Ranges.Add(TRange<FFrameNumber>(FFrameNumber(100), FFrameNumber(200)));
    TestEqual(TEXT("Inside the first"), T::FindRangeIndex(Ranges, 50), 0);
    TestEqual(TEXT("Half-open: a shared boundary belongs to the next"), T::FindRangeIndex(Ranges, 100), 1);
    TestEqual(TEXT("Past the end: none"), T::FindRangeIndex(Ranges, 200), INDEX_NONE);
    return true;
}

/**
 * Documents the 6 Oct "Master vs compiled differ by 2 ticks" reading
 * (p06_tail_extend records): the Python tool read Master section ranges through
 * GetStartFrameSeconds/GetEndFrameSeconds, which return FLOAT seconds
 * (MovieSceneSectionExtensions.h:54,81), then multiplied by 24000. At ~2100 s a
 * float32 step is ~0.24 ms = ~5.9 ticks, so the round trip itself moves the
 * value. Every recorded number is reproduced here; the earlier boundaries that
 * matched exactly (0 offset) are reproduced as well.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageSeamDiagFloatSecondsTest,
    "InfinityStage.Transport.SeamDiag.FloatSecondsRoundTripExplainsTwoTickOffsets",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageSeamDiagFloatSecondsTest::RunTest(const FString& Parameters)
{
    const auto RoundTrip = [](const int32 Ticks)
    {
        const float Seconds = static_cast<float>(static_cast<double>(Ticks) / 24000.0);
        return static_cast<int32>(FMath::RoundToDouble(static_cast<double>(Seconds) * 24000.0));
    };
    TestEqual(TEXT("P06 end before: 50603059 reads as 50603057 (-2)"), RoundTrip(50603059), 50603057);
    TestEqual(TEXT("P06 end after: 50973619 reads as 50973621 (+2)"), RoundTrip(50973619), 50973621);
    TestEqual(TEXT("Scene 6 end before: 51347059 reads as 51347057"), RoundTrip(51347059), 51347057);
    TestEqual(TEXT("Closing end before: 51707059 reads as 51707057"), RoundTrip(51707059), 51707057);
    TestEqual(TEXT("Control: P06 start 47949592 survives exactly"), RoundTrip(47949592), 47949592);
    TestEqual(TEXT("Control: P05 end 45010072 survives exactly"), RoundTrip(45010072), 45010072);
    return true;
}

#endif
