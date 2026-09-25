#include "InfinityStageCelestialRig.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
template <typename ActorType>
ActorType* FindFirstActorWithTag(UWorld* World, const FName Tag)
{
    if (!World || Tag.IsNone())
    {
        return nullptr;
    }
    for (TActorIterator<ActorType> It(World); It; ++It)
    {
        if (It->ActorHasTag(Tag))
        {
            return *It;
        }
    }
    return nullptr;
}

UDirectionalLightComponent* GetDirectionalComponent(const ADirectionalLight* Light)
{
    return Light ? Cast<UDirectionalLightComponent>(Light->GetLightComponent()) : nullptr;
}
}

AInfinityStageCelestialRig::AInfinityStageCelestialRig()
{
    PrimaryActorTick.bCanEverTick = false;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);

    StarsDome = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("StarsDome"));
    StarsDome->SetupAttachment(SceneRoot);
    StarsDome->SetMobility(EComponentMobility::Movable);
    StarsDome->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    StarsDome->SetCastShadow(false);
    StarsDome->SetReceivesDecals(false);
    StarsDome->SetRelativeScale3D(FVector(10000.0));

    static ConstructorHelpers::FObjectFinder<UStaticMesh> SkySphere(
        TEXT("/Engine/EngineSky/SM_SkySphere.SM_SkySphere"));
    if (SkySphere.Succeeded())
    {
        StarsDome->SetStaticMesh(SkySphere.Object);
    }
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> StarsMaterial(
        TEXT("/Engine/EngineSky/M_Sky_Panning_Clouds2.M_Sky_Panning_Clouds2"));
    if (StarsMaterial.Succeeded())
    {
        StarsDome->SetMaterial(0, StarsMaterial.Object);
    }
}

void AInfinityStageCelestialRig::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ResolveEnvironmentBindings();
    if (IsManualEditorLightingActive())
    {
        ApplyEditorPreviewLighting();
    }
    else
    {
        ApplyCyclePhase(InitialPhaseCycles);
    }
}

void AInfinityStageCelestialRig::BeginPlay()
{
    Super::BeginPlay();
    ResolveEnvironmentBindings();
    if (bSuppressForeignEnvironmentLighting && !LevelAddedHandle.IsValid())
    {
        LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(
            this, &AInfinityStageCelestialRig::HandleLevelAddedToWorld);
    }
    if (IsManualEditorLightingActive())
    {
        // Pinned show: establish the manual hour before the first Master tick.
        ApplyEditorPreviewLighting();
        UE_LOG(LogTemp, Display, TEXT("CELESTIAL_MANUAL_LIGHTING_IN_GAME|hours=%.2f|phase=%.4f|daylight=%.3f"),
            EditorPreviewTimeHours, CurrentNormalizedPhase, CurrentDaylightAmount);
    }
}

void AInfinityStageCelestialRig::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (LevelAddedHandle.IsValid())
    {
        FWorldDelegates::LevelAddedToWorld.Remove(LevelAddedHandle);
        LevelAddedHandle.Reset();
    }
    Super::EndPlay(EndPlayReason);
}

void AInfinityStageCelestialRig::ResolveEnvironmentBindings()
{
    if (!bAutoBindActorsByTag)
    {
        return;
    }
    if (!SunLightActor)
    {
        SunLightActor = FindFirstActorWithTag<ADirectionalLight>(GetWorld(), SunActorTag);
    }
    if (!MoonLightActor)
    {
        MoonLightActor = FindFirstActorWithTag<ADirectionalLight>(GetWorld(), MoonActorTag);
    }
    if (!SkyLightActor)
    {
        SkyLightActor = FindFirstActorWithTag<ASkyLight>(GetWorld(), SkyLightActorTag);
    }
    if (!HeightFogActor)
    {
        HeightFogActor = FindFirstActorWithTag<AExponentialHeightFog>(GetWorld(), HeightFogActorTag);
    }
}

bool AInfinityStageCelestialRig::EvaluateAtMasterFrame(
    UInfinityStageShowAsset* ShowAsset,
    const FGuid PassageGuid,
    const FFrameNumber MasterFrame)
{
    // Editor preview is a view/authoring concern only. It deliberately intercepts
    // Sequencer/Cue Desk evaluation in an editor world so a scrub cannot strand the
    // whole stage at midnight. Game worlds always continue into Master evaluation.
    if (IsManualEditorLightingActive())
    {
        ResolveEnvironmentBindings();
        ApplyEditorPreviewLighting();
        return true;
    }
    if (!ShowAsset)
    {
        return false;
    }

    double Phase = 0.0;
    if (!FInfinityStageCompiler::EvaluateCelestialPhase(
        *ShowAsset,
        PassageGuid,
        FFrameTime(MasterFrame),
        InitialPhaseCycles,
        Phase))
    {
        return false;
    }

    ResolveEnvironmentBindings();
    ApplyCyclePhase(Phase);
    return true;
}

bool AInfinityStageCelestialRig::IsManualEditorLightingActive() const
{
    const UWorld* World = GetWorld();
    if (!bUseManualEditorLighting || !World)
    {
        return false;
    }
    // Game worlds follow the manual hour only when the show is pinned to one
    // fixed time of day; otherwise the Master remains the authority there.
    return !World->IsGameWorld() || bApplyManualLightingInGame;
}

void AInfinityStageCelestialRig::ApplyEditorPreviewLighting()
{
    ResolveEnvironmentBindings();
    const double Hours = FMath::Clamp(EditorPreviewTimeHours, 0.0, 24.0);
    ApplyCyclePhase(Hours / 24.0);
}

void AInfinityStageCelestialRig::SetEditorPreviewTimeHours(const double TimeHours)
{
    EditorPreviewTimeHours = FMath::Clamp(TimeHours, 0.0, 24.0);
    if (IsManualEditorLightingActive())
    {
        ApplyEditorPreviewLighting();
    }
}

void AInfinityStageCelestialRig::SetUseManualEditorLighting(const bool bEnabled)
{
    bUseManualEditorLighting = bEnabled;
    if (IsManualEditorLightingActive())
    {
        ApplyEditorPreviewLighting();
    }
}

int32 AInfinityStageCelestialRig::SuppressForeignEnvironmentLighting()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return 0;
    }
    ResolveEnvironmentBindings();
    const TSet<const AActor*> Own = {
        static_cast<const AActor*>(SunLightActor),
        static_cast<const AActor*>(MoonLightActor),
        static_cast<const AActor*>(SkyLightActor),
        static_cast<const AActor*>(HeightFogActor),
        static_cast<const AActor*>(this)};

    int32 Touched = 0;
    FString TouchedLabels;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (!Actor || Own.Contains(Actor))
        {
            continue;
        }
        bool bForeign = false;
        TInlineComponentArray<UActorComponent*> Components(Actor);
        for (UActorComponent* Component : Components)
        {
            if (Component->IsA<UDirectionalLightComponent>() || Component->IsA<USkyLightComponent>())
            {
                // Lights keep their authored values; a hidden light simply stops contributing.
                Cast<USceneComponent>(Component)->SetVisibility(false, true);
                bForeign = true;
            }
            else if (Component->IsA<USkyAtmosphereComponent>() || Component->IsA<UExponentialHeightFogComponent>()
                || Component->IsA<UVolumetricCloudComponent>())
            {
                Cast<USceneComponent>(Component)->SetVisibility(false, true);
                bForeign = true;
            }
            else if (Component->IsA<UStaticMeshComponent>() && Actor->GetActorNameOrLabel().Contains(TEXT("SkySphere")))
            {
                Cast<USceneComponent>(Component)->SetVisibility(false, true);
                bForeign = true;
            }
        }
        if (bForeign)
        {
            Actor->SetActorHiddenInGame(true);
            ++Touched;
            TouchedLabels += (TouchedLabels.IsEmpty() ? TEXT("") : TEXT(",")) + Actor->GetActorNameOrLabel();
        }
    }
    if (Touched > 0)
    {
        UE_LOG(LogTemp, Display, TEXT("CELESTIAL_FOREIGN_LIGHTING_SUPPRESSED|world=%s|actors=%d|labels=%s"),
            *World->GetName(), Touched, *TouchedLabels);
    }
    return Touched;
}

void AInfinityStageCelestialRig::HandleLevelAddedToWorld(ULevel* Level, UWorld* World)
{
    // Level Instances and streamed scenes arrive after BeginPlay; each one can
    // carry its own sky, so the suppression must follow them in.
    if (bSuppressForeignEnvironmentLighting && World && World == GetWorld())
    {
        SuppressForeignEnvironmentLighting();
    }
}

void AInfinityStageCelestialRig::ApplyCyclePhase(const double NormalizedPhase)
{
    if (bSuppressForeignEnvironmentLighting)
    {
        SuppressForeignEnvironmentLighting();
    }
    if (!FMath::IsFinite(NormalizedPhase))
    {
        return;
    }

    CurrentNormalizedPhase = NormalizedPhase - FMath::FloorToDouble(NormalizedPhase);
    const double AngleRadians = CurrentNormalizedPhase * UE_TWO_PI;
    const float SolarAltitude = static_cast<float>(-FMath::Cos(AngleRadians));
    const float Band = FMath::Max(TwilightAltitudeBand, 0.001f);
    CurrentDaylightAmount = FMath::SmoothStep(-Band, Band, SolarAltitude);
    const float MoonlightAmount = FMath::SmoothStep(-Band, Band, -SolarAltitude);
    CurrentStarsAmount = FMath::Pow(MoonlightAmount, 1.35f);

    const float SunPitch = 90.0f - static_cast<float>(CurrentNormalizedPhase * 360.0);
    if (SunLightActor)
    {
        SunLightActor->SetActorRotation(FRotator(SunPitch, SunAzimuthDegrees, 0.0f));
        if (UDirectionalLightComponent* Sun = GetDirectionalComponent(SunLightActor))
        {
            const float HeightBlend = FMath::Sqrt(FMath::Clamp(SolarAltitude, 0.0f, 1.0f));
            Sun->SetIntensity(MaximumSunIntensity * CurrentDaylightAmount);
            Sun->SetLightColor(FMath::Lerp(HorizonSunColor, NoonSunColor, HeightBlend), false);
            Sun->SetAtmosphereSunLight(true);
            Sun->SetAtmosphereSunLightIndex(0);
        }
    }

    if (MoonLightActor)
    {
        MoonLightActor->SetActorRotation(FRotator(SunPitch + 180.0f, SunAzimuthDegrees, 0.0f));
        if (UDirectionalLightComponent* Moon = GetDirectionalComponent(MoonLightActor))
        {
            Moon->SetIntensity(MaximumMoonIntensity * MoonlightAmount);
            Moon->SetLightColor(MoonColor, false);
            Moon->SetAtmosphereSunLight(true);
            Moon->SetAtmosphereSunLightIndex(1);
        }
    }

    if (SkyLightActor)
    {
        if (USkyLightComponent* Sky = SkyLightActor->GetLightComponent())
        {
            Sky->SetIntensity(FMath::Lerp(NightSkyLightIntensity, DaySkyLightIntensity, CurrentDaylightAmount));
            Sky->SetLightColor(FMath::Lerp(NightSkyLightColor, DaySkyLightColor, CurrentDaylightAmount));
        }
    }

    if (HeightFogActor)
    {
        if (UExponentialHeightFogComponent* Fog = HeightFogActor->GetComponent())
        {
            const FLinearColor FogColor = FMath::Lerp(NightFogColor, DayFogColor, CurrentDaylightAmount);
            Fog->SetFogInscatteringColor(FogColor);
            Fog->SetDirectionalInscatteringColor(FMath::Lerp(MoonColor, HorizonSunColor, CurrentDaylightAmount));
        }
    }

    if (StarsDome)
    {
        const bool bStarsVisible = bShowBuiltInStars && CurrentStarsAmount > 0.002f;
        StarsDome->SetVisibility(bStarsVisible, true);
        StarsDome->SetRelativeRotation(FRotator(
            static_cast<float>(CurrentNormalizedPhase * 360.0),
            SunAzimuthDegrees,
            0.0f));
        if (bStarsVisible)
        {
            StarsDome->SetScalarParameterValueOnMaterials(
                TEXT("Stars brightness"),
                MaximumStarsBrightness * CurrentStarsAmount);
            StarsDome->SetScalarParameterValueOnMaterials(TEXT("Sun brightness"), 0.0f);
            StarsDome->SetScalarParameterValueOnMaterials(TEXT("Cloud opacity"), 0.0f);
            StarsDome->SetScalarParameterValueOnMaterials(TEXT("Sun height"), SolarAltitude);
        }
    }

    OnCelestialPhaseEvaluated.Broadcast(
        CurrentNormalizedPhase,
        CurrentDaylightAmount,
        CurrentStarsAmount);
}

#if WITH_EDITOR
void AInfinityStageCelestialRig::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    ResolveEnvironmentBindings();
    if (IsManualEditorLightingActive())
    {
        ApplyEditorPreviewLighting();
    }
    else
    {
        // Reapply the current preview phase so lighting/color edits are visible
        // immediately without changing the timeline's phase.
        ApplyCyclePhase(CurrentNormalizedPhase);
    }
}
#endif
