#include "InfinityStageLightDrama.h"
#include "Components/LightComponent.h"
#include "Engine/SpotLight.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
constexpr double DramaLampCm = 10000.0;

FInfinityStageLightDrama MakeCleanStrike()
{
    FInfinityStageLightDrama Drama;
    Drama.bStrikeOnApproach = true;
    Drama.StrikeDistanceCm = 2500.0;
    Drama.StrikeRampCm = 250.0;
    Drama.IgnitionStutter = 0.0f;
    return Drama;
}

float StrikeAt(const FInfinityStageLightDrama& Drama, const FGuid& Lamp, const double CameraCm)
{
    return InfinityStageLightDrama::Evaluate(Drama, Lamp, DramaLampCm, CameraCm, 0.0).IntensityScale;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightDramaStrikeTest,
    "InfinityStage.LightDrama.StrikeIsDrivenByDistance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightDramaStrikeTest::RunTest(const FString& Parameters)
{
    const FGuid Lamp = FGuid::NewGuid();
    const FInfinityStageLightDrama Steady;
    TestFalse(TEXT("Default drama is inactive"), InfinityStageLightDrama::IsActive(Steady));
    const FInfinityLightDramaPose Untouched = InfinityStageLightDrama::Evaluate(Steady, Lamp, DramaLampCm, 0.0, 3.0);
    TestEqual(TEXT("Default drama leaves brightness alone"), Untouched.IntensityScale, 1.0f);
    TestTrue(TEXT("Default drama leaves aim alone"), Untouched.AimOffset.IsNearlyZero());

    FInfinityStageLightDrama Drama = MakeCleanStrike();
    TestTrue(TEXT("Strike makes drama active"), InfinityStageLightDrama::IsActive(Drama));
    TestEqual(TEXT("Dark while the camera is far off"), StrikeAt(Drama, Lamp, DramaLampCm - 3000.0), 0.0f);
    TestTrue(TEXT("Half up at the middle of the ramp"),
        FMath::IsNearlyEqual(StrikeAt(Drama, Lamp, DramaLampCm - 2375.0), 0.5f, 0.001f));
    TestEqual(TEXT("Full once caught"), StrikeAt(Drama, Lamp, DramaLampCm - 2000.0), 1.0f);
    TestEqual(TEXT("Hold keeps it lit behind the camera"), StrikeAt(Drama, Lamp, DramaLampCm + 5000.0), 1.0f);

    bool bMonotonic = true;
    float Previous = -1.0f;
    for (double Camera = DramaLampCm - 2600.0; Camera <= DramaLampCm - 2200.0; Camera += 10.0)
    {
        const float Level = StrikeAt(Drama, Lamp, Camera);
        bMonotonic &= Level + 1.0e-5f >= Previous;
        Previous = Level;
    }
    TestTrue(TEXT("Without stutter the strike only rises"), bMonotonic);

    Drama.IgnitionStutter = 1.0f;
    bool bStuttered = false;
    bool bRepeatable = true;
    const FInfinityStageLightDrama Clean = MakeCleanStrike();
    for (double Camera = DramaLampCm - 2500.0; Camera < DramaLampCm - 2250.0; Camera += 5.0)
    {
        const float Level = StrikeAt(Drama, Lamp, Camera);
        bStuttered |= Level < StrikeAt(Clean, Lamp, Camera) - 0.01f;
        bRepeatable &= Level == StrikeAt(Drama, Lamp, Camera);
    }
    TestTrue(TEXT("Stutter dips below the clean ramp"), bStuttered);
    TestTrue(TEXT("Stutter replays identically at the same distance"), bRepeatable);

    FInfinityStageLightDrama Pilot = MakeCleanStrike();
    Pilot.UnstruckIntensityScale = 0.1f;
    TestTrue(TEXT("A pilot flame glows before the strike"),
        FMath::IsNearlyEqual(StrikeAt(Pilot, Lamp, DramaLampCm - 3000.0), 0.1f, 0.0001f));

    FInfinityStageLightDrama Snuffed = MakeCleanStrike();
    Snuffed.AfterPass = EInfinityLightAfterPass::Extinguish;
    Snuffed.AfterPassDistanceCm = 600.0;
    TestEqual(TEXT("Extinguish waits for the after-pass distance"), StrikeAt(Snuffed, Lamp, DramaLampCm + 500.0), 1.0f);
    TestEqual(TEXT("Extinguish then snuffs the lamp"), StrikeAt(Snuffed, Lamp, DramaLampCm + 700.0), 0.0f);

    FInfinityStageLightDrama Fading = MakeCleanStrike();
    Fading.AfterPass = EInfinityLightAfterPass::Decay;
    Fading.AfterPassDistanceCm = 600.0;
    Fading.DecayDistanceCm = 1500.0;
    TestTrue(TEXT("Decay is halfway down halfway through"),
        FMath::IsNearlyEqual(StrikeAt(Fading, Lamp, DramaLampCm + 600.0 + 750.0), 0.5f, 0.001f));
    TestEqual(TEXT("Decay ends dark"), StrikeAt(Fading, Lamp, DramaLampCm + 5000.0), 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightDramaSlowMoveTest,
    "InfinityStage.LightDrama.SlowMoveIsPeriodicAndDesynchronised",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightDramaSlowMoveTest::RunTest(const FString& Parameters)
{
    FInfinityStageLightDrama Drama;
    Drama.bSlowMove = true;
    Drama.PanAmplitudeDegrees = 6.0f;
    Drama.TiltAmplitudeDegrees = 3.0f;
    Drama.PeriodSeconds = 14.0f;
    const FGuid LampA = FGuid::NewGuid();
    const FGuid LampB = FGuid::NewGuid();

    bool bBounded = true;
    bool bPeriodic = true;
    for (double Seconds = 0.0; Seconds < 14.0; Seconds += 0.5)
    {
        const FRotator Now = InfinityStageLightDrama::Evaluate(Drama, LampA, 0.0, 0.0, Seconds).AimOffset;
        const FRotator Later = InfinityStageLightDrama::Evaluate(Drama, LampA, 0.0, 0.0, Seconds + 14.0).AimOffset;
        bBounded &= FMath::Abs(Now.Yaw) <= 6.0 + 1.0e-3 && FMath::Abs(Now.Pitch) <= 3.0 + 1.0e-3 && Now.Roll == 0.0;
        bPeriodic &= Now.Equals(Later, 1.0e-3);
    }
    TestTrue(TEXT("The sweep stays inside its amplitudes"), bBounded);
    TestTrue(TEXT("The sweep repeats every period"), bPeriodic);
    TestFalse(TEXT("Two lamps do not sweep in unison"),
        InfinityStageLightDrama::Evaluate(Drama, LampA, 0.0, 0.0, 0.0).AimOffset.Equals(
            InfinityStageLightDrama::Evaluate(Drama, LampB, 0.0, 0.0, 0.0).AimOffset, 1.0e-3));

    Drama.bPhaseFromIdentity = false;
    const FRotator Start = InfinityStageLightDrama::Evaluate(Drama, LampA, 0.0, 0.0, 0.0).AimOffset;
    TestTrue(TEXT("At phase zero pan is centred and tilt a quarter cycle behind"),
        FMath::IsNearlyZero(Start.Yaw, 1.0e-3) && FMath::IsNearlyEqual(Start.Pitch, -3.0, 1.0e-3));
    TestEqual(TEXT("Slow move alone leaves brightness alone"),
        InfinityStageLightDrama::Evaluate(Drama, LampA, 0.0, 99999.0, 0.0).IntensityScale, 1.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightDramaApplyTest,
    "InfinityStage.LightDrama.UnstruckLampIsSwitchedOff",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightDramaApplyTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    const FTransform Authored(FRotator(-40.0, 20.0, 0.0), FVector(0.0, 0.0, 1000.0));
    ASpotLight* Lamp = World->SpawnActor<ASpotLight>(Authored.GetLocation(), Authored.Rotator());
    ULightComponent* Light = Lamp ? Lamp->FindComponentByClass<ULightComponent>() : nullptr;
    if (!Light)
    {
        AddError(TEXT("Spot light fixture did not spawn."));
        World->DestroyWorld(false);
        return false;
    }
    const FGuid Identity = FGuid::NewGuid();
    FInfinityStageLightDrama Drama = MakeCleanStrike();

    InfinityStageLightDrama::ApplyToLamp(*Lamp, Drama, 50.0f, Authored, Identity, DramaLampCm, DramaLampCm - 3000.0, 0.0);
    TestFalse(TEXT("An unstruck lamp is switched off, costing no shadow map"), Light->IsVisible());
    InfinityStageLightDrama::ApplyToLamp(*Lamp, Drama, 50.0f, Authored, Identity, DramaLampCm, DramaLampCm - 1000.0, 0.0);
    TestTrue(TEXT("A struck lamp is switched back on"), Light->IsVisible());
    TestTrue(TEXT("A struck lamp returns to its authored intensity"), FMath::IsNearlyEqual(Light->Intensity, 50.0f, 0.001f));

    Drama.bSlowMove = true;
    Drama.bPhaseFromIdentity = false;
    Drama.TiltAmplitudeDegrees = 3.0f;
    InfinityStageLightDrama::ApplyToLamp(*Lamp, Drama, 50.0f, Authored, Identity, DramaLampCm, DramaLampCm - 1000.0, 0.0);
    const FQuat Expected = Authored.GetRotation() * FRotator(-3.0, 0.0, 0.0).Quaternion();
    TestTrue(TEXT("Slow move turns the lamp in its own frame from the authored aim"),
        Lamp->GetActorQuat().Equals(Expected, 1.0e-4));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageLightDramaFlashTest,
    "InfinityStage.LightDrama.FlashIsBriefAndKeyedToDistance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageLightDramaFlashTest::RunTest(const FString& Parameters)
{
    const FGuid Lamp = FGuid::NewGuid();
    FInfinityStageLightDrama Drama;
    Drama.bFlash = true;
    Drama.FlashCameraOffsetsCm = { -400.0f, -100.0f };
    Drama.FlashAttackCm = 3.0f;
    Drama.FlashDecayCm = 18.0f;
    TestTrue(TEXT("Flash makes drama active"), InfinityStageLightDrama::IsActive(Drama));

    const auto At = [&](const double CameraPastLampCm)
    {
        return InfinityStageLightDrama::Evaluate(Drama, Lamp, DramaLampCm, DramaLampCm + CameraPastLampCm, 0.0).IntensityScale;
    };
    TestEqual(TEXT("Dark before the first flash"), At(-500.0), 0.0f);
    TestEqual(TEXT("Dark just before the attack"), At(-403.5), 0.0f);
    TestTrue(TEXT("Peak while the camera is still 4 m short of the lamp"), FMath::IsNearlyEqual(At(-400.0), 1.0f, 1.0e-4f));
    TestTrue(TEXT("Cubic fall: under an eighth by half the decay"), At(-391.0) < 0.126f);
    TestEqual(TEXT("Dark again after the decay"), At(-381.0), 0.0f);
    TestTrue(TEXT("The second flash fires"), FMath::IsNearlyEqual(At(-100.0), 1.0f, 1.0e-4f));
    TestEqual(TEXT("Dark once both have passed"), At(0.0), 0.0f);

    Drama.FlashRestScale = 0.02f;
    TestTrue(TEXT("Rest scale is the floor between flashes"), FMath::IsNearlyEqual(At(-250.0), 0.02f, 1.0e-6f));

    Drama.bStrikeOnApproach = true;
    Drama.StrikeDistanceCm = 50.0;
    Drama.StrikeRampCm = 10.0;
    Drama.IgnitionStutter = 0.0f;
    TestTrue(TEXT("A strike lamp still flashes before it strikes (max)"), FMath::IsNearlyEqual(At(-400.0), 1.0f, 1.0e-4f));
    TestTrue(TEXT("Before the strike it rests at the flash floor"), At(-250.0) < 0.03f);
    return true;
}

#endif
