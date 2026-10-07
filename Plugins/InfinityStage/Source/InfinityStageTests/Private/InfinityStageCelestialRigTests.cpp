#include "InfinityStageCelestialRig.h"
#include "Components/DirectionalLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "HAL/PlatformProcess.h"
#include "Misc/AutomationTest.h"
#include "UObject/SoftObjectPath.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** A rig bound to its own sun, moon, sky light and fog, begun as in play. */
AInfinityStageCelestialRig* SpawnBegunCelestialRig(UWorld& World, int32* OutWalksBeforeBeginPlay = nullptr)
{
    AInfinityStageCelestialRig* Rig = World.SpawnActor<AInfinityStageCelestialRig>();
    Rig->bAutoBindActorsByTag = false;
    Rig->SunLightActor = World.SpawnActor<ADirectionalLight>();
    Rig->MoonLightActor = World.SpawnActor<ADirectionalLight>();
    Rig->SkyLightActor = World.SpawnActor<ASkyLight>();
    Rig->HeightFogActor = World.SpawnActor<AExponentialHeightFog>();
    // Construction in an editor world walks on its first lighting apply, by design.
    if (OutWalksBeforeBeginPlay)
    {
        *OutWalksBeforeBeginPlay = Rig->ForeignLightingWalkCount;
    }
    Rig->DispatchBeginPlay();
    return Rig;
}

TSoftObjectPtr<UWorld> MakeCelestialTestWorldReference(const FString& ObjectPath)
{
    return TSoftObjectPtr<UWorld>(FSoftObjectPath(ObjectPath));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialExemptPackageTest,
    "InfinityStage.Celestial.ForeignLightingExemptPackageNames",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialExemptPackageTest::RunTest(const FString& Parameters)
{
    TArray<TSoftObjectPtr<UWorld>> Exempt;
    Exempt.Add(TSoftObjectPtr<UWorld>()); // Null entries are ignored.
    Exempt.Add(MakeCelestialTestWorldReference(TEXT("/Game/KK_S1_Animals/L_Animals.L_Animals")));

    TestTrue(TEXT("An exempt long package name matches case-insensitively"),
        AInfinityStageCelestialRig::IsExemptLevelPackage(
            TEXT("/game/kk_s1_animals/l_animals"), FString(), Exempt));
    TestTrue(TEXT("A PIE-prefixed level package resolves to the exempt source package"),
        AInfinityStageCelestialRig::IsExemptLevelPackage(
            TEXT("/Game/KK_S1_Animals/UEDPIE_0_L_Animals"), FString(), Exempt));
    TestTrue(TEXT("A level instance matches through its streaming world asset package"),
        AInfinityStageCelestialRig::IsExemptLevelPackage(
            TEXT("/Game/KK_S1_Animals/L_Animals_LevelInstance_1"),
            TEXT("/Game/KK_S1_Animals/L_Animals"),
            Exempt));
    TestFalse(TEXT("A non-exempt package does not match"),
        AInfinityStageCelestialRig::IsExemptLevelPackage(
            TEXT("/Game/KK_S4_Children/L_KK_children"), FString(), Exempt));
    TestFalse(TEXT("An empty exemption list never matches"),
        AInfinityStageCelestialRig::IsExemptLevelPackage(
            TEXT("/Game/KK_S1_Animals/L_Animals"),
            TEXT("/Game/KK_S1_Animals/L_Animals"),
            TArray<TSoftObjectPtr<UWorld>>()));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialForeignArrivalTest,
    "InfinityStage.Celestial.ForeignSkyIsSilencedWhenItArrives",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialForeignArrivalTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    int32 WalksBeforeBeginPlay = 0;
    AInfinityStageCelestialRig* Rig = SpawnBegunCelestialRig(*World, &WalksBeforeBeginPlay);
    TestEqual(TEXT("BeginPlay walks the world once"), Rig->ForeignLightingWalkCount, WalksBeforeBeginPlay + 1);
    TestEqual(TEXT("The rig's own lights are not foreign"), Rig->ForeignLightingSuppressedCount, 0);
    TestTrue(TEXT("The rig's own sun stays visible"), Rig->SunLightActor->GetLightComponent()->IsVisible());

    // A sky arriving after BeginPlay, as a Sequencer spawnable would.
    ADirectionalLight* Foreign = World->SpawnActor<ADirectionalLight>();
    TestFalse(TEXT("An arriving foreign sun is silenced"), Foreign->GetLightComponent()->IsVisible());
    TestTrue(TEXT("An arriving foreign sun is hidden in game"), Foreign->IsHidden());
    TestEqual(TEXT("The arrival is handled without walking the world"), Rig->ForeignLightingWalkCount, WalksBeforeBeginPlay + 1);
    TestEqual(TEXT("One foreign actor silenced"), Rig->ForeignLightingSuppressedCount, 1);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialForeignArrivalExemptionTest,
    "InfinityStage.Celestial.ForeignSkyRespectsLevelExemption",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialForeignArrivalExemptionTest::RunTest(const FString& Parameters)
{
    // One real level per test world. The arrival fixture runs once with that
    // level exempt and once with an unrelated package in the exemption list.
    for (const bool bExempt : {true, false})
    {
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStageCelestialRig* Rig = SpawnBegunCelestialRig(*World);
        if (bExempt)
        {
            const FString WorldObjectPath = FString::Printf(
                TEXT("%s.%s"), *World->GetOutermost()->GetName(), *World->GetName());
            Rig->ForeignLightingExemptLevels.Add(MakeCelestialTestWorldReference(WorldObjectPath));
        }
        else
        {
            Rig->ForeignLightingExemptLevels.Add(MakeCelestialTestWorldReference(
                TEXT("/Game/InfinityStage/Tests/L_Different.L_Different")));
        }

        ADirectionalLight* Foreign = World->SpawnActor<ADirectionalLight>();
        const TCHAR* CaseName = bExempt ? TEXT("Exempt") : TEXT("Non-exempt");
        TestEqual(*FString::Printf(TEXT("%s level: foreign visibility"), CaseName),
            Foreign->GetLightComponent()->IsVisible(), bExempt);
        TestEqual(*FString::Printf(TEXT("%s level: actor hidden-in-game"), CaseName),
            Foreign->IsHidden(), !bExempt);
        TestEqual(*FString::Printf(TEXT("%s level: suppressed count"), CaseName),
            Rig->ForeignLightingSuppressedCount, bExempt ? 0 : 1);

        World->DestroyWorld(false);
    }
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
    const int32 ReappliesAfterBeginPlay = Rig->ForeignLightingReapplyCount;
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
    TestEqual(TEXT("The safety net runs once when due"), Rig->ForeignLightingReapplyCount, ReappliesAfterBeginPlay + 1);
    TestEqual(TEXT("The safety net never walks the world"), Rig->ForeignLightingWalkCount, WalksAfterBeginPlay);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageCelestialRepeatedPhaseSkipsMaterialWritesTest,
    "InfinityStage.Celestial.RepeatedPhaseSkipsMaterialParameterWrites",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageCelestialRepeatedPhaseSkipsMaterialWritesTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageCelestialRig* Rig = SpawnBegunCelestialRig(*World);
    const int32 WritesBeforeFirstApply = Rig->GetStarsMaterialParameterWriteCountForTests();

    Rig->ApplyCyclePhase(0.0);
    const int32 WritesAfterFirstApply = Rig->GetStarsMaterialParameterWriteCountForTests();
    Rig->ApplyCyclePhase(0.0);

    TestTrue(TEXT("The first new phase writes star material parameters"), WritesAfterFirstApply > WritesBeforeFirstApply);
    TestEqual(TEXT("Applying the same phase twice performs no second material parameter write"),
        Rig->GetStarsMaterialParameterWriteCountForTests(), WritesAfterFirstApply);

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

    // Re-shown again, the throttled safety net catches it without a walk.
    Baked->GetLightComponent()->SetVisibility(true);
    const int32 WalksBefore = Rig->ForeignLightingWalkCount;
    Rig->ForeignLightingRecheckSeconds = 0.000001f;
    FPlatformProcess::Sleep(0.01f);
    Rig->ApplyCyclePhase(0.25);
    TestFalse(TEXT("The safety net silences a re-shown sun"), Baked->GetLightComponent()->IsVisible());
    TestEqual(TEXT("The safety net does not walk the world"), Rig->ForeignLightingWalkCount, WalksBefore);
    TestEqual(TEXT("Nor does it log again"), Rig->ForeignLightingSuppressedCount, 1);

    World->DestroyWorld(false);
    return true;
}

#endif
