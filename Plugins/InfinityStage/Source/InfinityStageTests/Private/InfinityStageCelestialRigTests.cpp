#include "InfinityStageCelestialRig.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "HAL/PlatformProcess.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** A rig bound to its own sun, moon, sky light and fog, begun as in play. */
AInfinityStageCelestialRig* SpawnBegunCelestialRig(UWorld& World)
{
    AInfinityStageCelestialRig* Rig = World.SpawnActor<AInfinityStageCelestialRig>();
    Rig->bAutoBindActorsByTag = false;
    Rig->SunLightActor = World.SpawnActor<ADirectionalLight>();
    Rig->MoonLightActor = World.SpawnActor<ADirectionalLight>();
    Rig->SkyLightActor = World.SpawnActor<ASkyLight>();
    Rig->HeightFogActor = World.SpawnActor<AExponentialHeightFog>();
    Rig->DispatchBeginPlay();
    return Rig;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialForeignArrivalTest,
    "InfinityStage.Celestial.ForeignSkyIsSilencedWhenItArrives",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialForeignArrivalTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCelestialRig* Rig = SpawnBegunCelestialRig(*World);
    TestEqual(TEXT("BeginPlay walks the world once"), Rig->ForeignLightingWalkCount, 1);
    TestEqual(TEXT("The rig's own lights are not foreign"), Rig->ForeignLightingSuppressedCount, 0);
    TestTrue(TEXT("The rig's own sun stays visible"), Rig->SunLightActor->GetLightComponent()->IsVisible());

    // A sky arriving after BeginPlay, as a Sequencer spawnable would.
    ADirectionalLight* Foreign = World->SpawnActor<ADirectionalLight>();
    TestFalse(TEXT("An arriving foreign sun is silenced"), Foreign->GetLightComponent()->IsVisible());
    TestTrue(TEXT("An arriving foreign sun is hidden in game"), Foreign->IsHidden());
    TestEqual(TEXT("The arrival is handled without walking the world"), Rig->ForeignLightingWalkCount, 1);
    TestEqual(TEXT("One foreign actor silenced"), Rig->ForeignLightingSuppressedCount, 1);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialPhaseDoesNotWalkTest,
    "InfinityStage.Celestial.PhaseAppliesDoNotWalkTheWorld",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialPhaseDoesNotWalkTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCelestialRig* Rig = SpawnBegunCelestialRig(*World);
    Rig->ForeignLightingRecheckSeconds = 60.0f;
    const int32 WalksAfterBeginPlay = Rig->ForeignLightingWalkCount;
    // A second of show at 60 fps, as the Master applies it.
    for (int32 Frame = 0; Frame < 60; ++Frame)
    {
        Rig->ApplyCyclePhase(Frame / 600.0);
    }
    TestEqual(TEXT("Phase applies inside the safety-net interval do not walk the world"),
        Rig->ForeignLightingWalkCount, WalksAfterBeginPlay);
    TestTrue(TEXT("The phase itself still applies"), FMath::IsNearlyEqual(Rig->CurrentNormalizedPhase, 59.0 / 600.0));

    // With the interval elapsed (zero-length here), the next apply is the safety net.
    Rig->ForeignLightingRecheckSeconds = 0.000001f;
    FPlatformProcess::Sleep(0.01f);
    Rig->ApplyCyclePhase(0.25);
    TestEqual(TEXT("The safety net walks once when due"), Rig->ForeignLightingWalkCount, WalksAfterBeginPlay + 1);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialLogsOnceTest,
    "InfinityStage.Celestial.EachForeignSkyIsLoggedOnce",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialLogsOnceTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCelestialRig* Rig = World->SpawnActor<AInfinityStageCelestialRig>();
    Rig->bAutoBindActorsByTag = false;
    // Present before the rig begins, like a sky baked into a scene.
    ADirectionalLight* Baked = World->SpawnActor<ADirectionalLight>();
    Rig->SunLightActor = World->SpawnActor<ADirectionalLight>();
    TestEqual(TEXT("A walk finds the baked foreign sun"), Rig->SuppressForeignEnvironmentLighting(), 1);
    TestEqual(TEXT("Repeated walks still find it"), Rig->SuppressForeignEnvironmentLighting(), 1);
    TestEqual(TEXT("It is counted, and logged, once"), Rig->ForeignLightingSuppressedCount, 1);
    TestFalse(TEXT("It stays silenced"), Baked->GetLightComponent()->IsVisible());

    // A sequence re-shows it; the next walk hides it again without a new log.
    Baked->GetLightComponent()->SetVisibility(true);
    Rig->SuppressForeignEnvironmentLighting();
    TestFalse(TEXT("A re-shown foreign sun is silenced again"), Baked->GetLightComponent()->IsVisible());
    TestEqual(TEXT("Re-silencing is not a new log"), Rig->ForeignLightingSuppressedCount, 1);

    World->DestroyWorld(false);
    return true;
}

#endif
