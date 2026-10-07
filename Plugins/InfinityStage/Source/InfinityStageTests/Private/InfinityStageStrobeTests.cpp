#include "InfinityStageStrobeLight.h"
#include "Misc/AutomationTest.h"
#include "Components/PointLightComponent.h"
#include "Engine/World.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStrobeShapeTest,
    "InfinityStage.Strobe.FlashThenAfterglow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStrobeShapeTest::RunTest(const FString& Parameters)
{
    using InfinityStageStrobe::LevelAt;
    // Period 1 s, flash 0.04 s, decay 0.33 s, no phase.
    TestEqual(TEXT("Full at the start of a flash"), LevelAt(10.0, 1.0f, 0.04f, 0.33f, 0.0f), 1.0f);
    TestEqual(TEXT("Still full inside the flash"), LevelAt(10.03, 1.0f, 0.04f, 0.33f, 0.0f), 1.0f);
    const float Early = LevelAt(10.06, 1.0f, 0.04f, 0.33f, 0.0f);
    const float Mid = LevelAt(10.20, 1.0f, 0.04f, 0.33f, 0.0f);
    TestTrue(TEXT("The afterglow starts high"), Early > 0.5f && Early < 1.0f);
    TestTrue(TEXT("...and falls"), Mid < Early && Mid > 0.0f);
    TestEqual(TEXT("Black once the decay has run"), LevelAt(10.40, 1.0f, 0.04f, 0.33f, 0.0f), 0.0f);
    TestEqual(TEXT("Black until the next flash"), LevelAt(10.95, 1.0f, 0.04f, 0.33f, 0.0f), 0.0f);
    TestEqual(TEXT("Control: zero decay is a bare flash"), LevelAt(10.06, 1.0f, 0.04f, 0.0f, 0.0f), 0.0f);
    TestEqual(TEXT("Control: a non-positive period never lights"), LevelAt(10.0, 0.0f, 0.04f, 0.33f, 0.0f), 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStrobeDeterminismTest,
    "InfinityStage.Strobe.DeterministicOnMasterTime",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// The same Master second gives the same level, whatever order frames are visited in
// (scrub, reverse, re-run); it repeats each period; and the phase offsets it.
bool FInfinityStageStrobeDeterminismTest::RunTest(const FString& Parameters)
{
    using InfinityStageStrobe::LevelAt;
    TArray<double> Times;
    for (int32 Index = 0; Index < 200; ++Index)
    {
        Times.Add(Index * 0.0137);
    }
    TArray<float> Forward;
    for (const double T : Times)
    {
        Forward.Add(LevelAt(T, 0.7f, 0.05f, 0.3f, 0.25f));
    }
    bool bSame = true;
    for (int32 Index = Times.Num() - 1; Index >= 0; --Index)
    {
        bSame &= LevelAt(Times[Index], 0.7f, 0.05f, 0.3f, 0.25f) == Forward[Index];
    }
    TestTrue(TEXT("Reverse visiting gives identical levels"), bSame);
    TestTrue(TEXT("It repeats every period"),
        FMath::IsNearlyEqual(LevelAt(3.1, 0.7f, 0.05f, 0.3f, 0.0f), LevelAt(3.1 + 7 * 0.7, 0.7f, 0.05f, 0.3f, 0.0f), 1.0e-4f));
    TestEqual(TEXT("Half a cycle of phase moves the flash half a period"),
        LevelAt(0.5, 1.0f, 0.04f, 0.33f, 0.5f), 1.0f);
    TestEqual(TEXT("Control: without the phase that moment is dark"),
        LevelAt(0.5, 1.0f, 0.04f, 0.33f, 0.0f), 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStrobeSegmentFilterTest,
    "InfinityStage.Strobe.SegmentFilter",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStrobeSegmentFilterTest::RunTest(const FString& Parameters)
{
    const FGuid Passage = FGuid::NewGuid();
    const FGuid Scene = FGuid::NewGuid();
    TArray<FGuid> Filter;
    TestTrue(TEXT("No filter: active everywhere"), InfinityStageStrobe::IsActiveInSegment(Filter, Scene));
    Filter.Add(Passage);
    TestTrue(TEXT("Listed segment: active"), InfinityStageStrobe::IsActiveInSegment(Filter, Passage));
    TestFalse(TEXT("Control: unlisted segment: dark"), InfinityStageStrobe::IsActiveInSegment(Filter, Scene));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStrobeEditorPreviewTest,
    "InfinityStage.Strobe.EditorPreviewNeverPersists",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Review (5 Oct): the editor preview drives the light every frame, so a level save
// must never persist a mid-flash value, and the preview must not dirty the level.
bool FInfinityStageStrobeEditorPreviewTest::RunTest(const FString& Parameters)
{
    const FProperty* LightProperty = AInfinityStageStrobeLight::StaticClass()->FindPropertyByName(TEXT("Light"));
    const FProperty* PeakProperty = AInfinityStageStrobeLight::StaticClass()->FindPropertyByName(TEXT("PeakIntensity"));
    TestTrue(TEXT("The driven light component is Transient (never saved)"),
        LightProperty && LightProperty->HasAnyPropertyFlags(CPF_Transient));
    TestTrue(TEXT("Control: the authored peak IS saved"),
        PeakProperty && !PeakProperty->HasAnyPropertyFlags(CPF_Transient));

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageStrobeLight* Strobe = World->SpawnActor<AInfinityStageStrobeLight>();
    TestTrue(TEXT("The light object itself is RF_Transient, so a save skips it"),
        Strobe->Light && Strobe->Light->HasAnyFlags(RF_Transient));
    TestFalse(TEXT("Control: the root, which carries the placement, is saved"),
        Strobe->GetRootComponent() && Strobe->GetRootComponent()->HasAnyFlags(RF_Transient));
    Strobe->PeakIntensity = 12345.0f;
    Strobe->PeriodSeconds = 0.05f;   // short, so a few ticks cross flashes and gaps
    UPackage* Package = World->GetOutermost();
    Package->SetDirtyFlag(false);
    for (int32 Tick = 0; Tick < 20; ++Tick)
    {
        Strobe->Tick(0.016f);
    }
    TestEqual(TEXT("Preview ticks leave the authored peak unchanged"), Strobe->PeakIntensity, 12345.0f);
    TestFalse(TEXT("Preview ticks do not dirty the level package"), Package->IsDirty());
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStrobeCastShadowsToggleTest,
    "InfinityStage.Strobe.CastShadowsToggle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

// Gary (7 Oct): P04 strobes should throw the wings' shadows. The light is transient, so the
// switch lives on the actor and is synced each frame; off by default keeps today's cost.
bool FInfinityStageStrobeCastShadowsToggleTest::RunTest(const FString& Parameters)
{
    const FProperty* CastProperty = AInfinityStageStrobeLight::StaticClass()->FindPropertyByName(TEXT("bCastShadows"));
    TestTrue(TEXT("The shadow switch is a saved actor property"),
        CastProperty && !CastProperty->HasAnyPropertyFlags(CPF_Transient));

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStageStrobeLight* Strobe = World->SpawnActor<AInfinityStageStrobeLight>();
    if (!TestNotNull(TEXT("Strobe spawned"), Strobe) || !TestNotNull(TEXT("Strobe light"), Strobe->Light.Get()))
    {
        World->DestroyWorld(false);
        return false;
    }
    const float OriginalSourceRadius = Strobe->Light->SourceRadius;
    Strobe->Tick(0.016f);
    TestFalse(TEXT("Default: the light casts no shadows"), static_cast<bool>(Strobe->Light->CastShadows));
    TestFalse(TEXT("Default: no volumetric shadow"), static_cast<bool>(Strobe->Light->bCastVolumetricShadow));

    Strobe->bCastShadows = true;
    Strobe->bCastVolumetricShadow = true;
    Strobe->ShadowSourceRadiusCm = 7.5f;
    TestFalse(TEXT("Control: before the sync the light is unchanged"), static_cast<bool>(Strobe->Light->CastShadows));
    Strobe->Tick(0.016f);
    TestTrue(TEXT("After the sync the light casts shadows"), static_cast<bool>(Strobe->Light->CastShadows));
    TestTrue(TEXT("...and volumetric shadows"), static_cast<bool>(Strobe->Light->bCastVolumetricShadow));
    TestEqual(TEXT("...with the shadow source radius"), Strobe->Light->SourceRadius, 7.5f);

    Strobe->bCastShadows = false;
    Strobe->bCastVolumetricShadow = false;
    Strobe->Tick(0.016f);
    TestFalse(TEXT("Toggled back: no shadows"), static_cast<bool>(Strobe->Light->CastShadows));
    TestFalse(TEXT("Toggled back: no volumetric shadow"), static_cast<bool>(Strobe->Light->bCastVolumetricShadow));
    TestEqual(TEXT("Toggled back: the original source radius returns"), Strobe->Light->SourceRadius, OriginalSourceRadius);
    World->DestroyWorld(false);
    return true;
}

#endif
