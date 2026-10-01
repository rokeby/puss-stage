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
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/PlatformTime.h"
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
    InvalidateStarsMaterialParameterCache();
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
    InvalidateStarsMaterialParameterCache();
    ResolveEnvironmentBindings();
    if (bSuppressForeignEnvironmentLighting)
    {
        if (!LevelAddedHandle.IsValid())
        {
            LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(
                this, &AInfinityStageCelestialRig::HandleLevelAddedToWorld);
        }
        UWorld* World = GetWorld();
        if (World && !ActorSpawnedHandle.IsValid())
        {
            ActorSpawnedHandle = World->AddOnActorSpawnedHandler(
                FOnActorSpawned::FDelegate::CreateUObject(this, &AInfinityStageCelestialRig::HandleActorSpawned));
        }
        // Everything already in the world, once; arrivals are handled as they come.
        SuppressForeignEnvironmentLighting();
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
    if (ActorSpawnedHandle.IsValid())
    {
        if (UWorld* World = GetWorld())
        {
            World->RemoveOnActorSpawnedHandler(ActorSpawnedHandle);
        }
        ActorSpawnedHandle.Reset();
    }
    Super::EndPlay(EndPlayReason);
}

void AInfinityStageCelestialRig::ResolveEnvironmentBindings()
{
    if (!bAutoBindActorsByTag)
    {
        return;
    }
    const ADirectionalLight* PreviousSunLightActor = SunLightActor;
    const ADirectionalLight* PreviousMoonLightActor = MoonLightActor;
    const ASkyLight* PreviousSkyLightActor = SkyLightActor;
    const AExponentialHeightFog* PreviousHeightFogActor = HeightFogActor;
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
    if (SunLightActor.Get() != PreviousSunLightActor
        || MoonLightActor.Get() != PreviousMoonLightActor
        || SkyLightActor.Get() != PreviousSkyLightActor
        || HeightFogActor.Get() != PreviousHeightFogActor)
    {
        InvalidateStarsMaterialParameterCache();
    }
}

void AInfinityStageCelestialRig::InvalidateStarsMaterialParameterCache()
{
    LastStarsBrightnessWritten = TNumericLimits<float>::Max();
    LastSunBrightnessWritten = TNumericLimits<float>::Max();
    LastCloudOpacityWritten = TNumericLimits<float>::Max();
    LastSunHeightWritten = TNumericLimits<float>::Max();
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

bool AInfinityStageCelestialRig::SuppressIfForeign(AActor* Actor)
{
    if (!Actor)
    {
        return false;
    }
    const AActor* const Own[] = {
        this, SunLightActor.Get(), MoonLightActor.Get(), SkyLightActor.Get(), HeightFogActor.Get()};
    for (const AActor* Mine : Own)
    {
        if (Actor == Mine)
        {
            return false;
        }
    }
    bool bForeign = false;
    TInlineComponentArray<UActorComponent*> Components(Actor);
    for (UActorComponent* Component : Components)
    {
        const bool bExteriorLight = Component->IsA<UDirectionalLightComponent>() || Component->IsA<USkyLightComponent>()
            || Component->IsA<USkyAtmosphereComponent>() || Component->IsA<UExponentialHeightFogComponent>()
            || Component->IsA<UVolumetricCloudComponent>()
            || (Component->IsA<UStaticMeshComponent>() && Actor->GetActorNameOrLabel().Contains(TEXT("SkySphere")));
        if (bExteriorLight)
        {
            // Lights keep their authored values; a hidden light simply stops
            // contributing. Re-hiding an already hidden component is a no-op.
            Cast<USceneComponent>(Component)->SetVisibility(false, true);
            bForeign = true;
        }
    }
    if (!bForeign)
    {
        return false;
    }
    Actor->SetActorHiddenInGame(true);
    bool bAlreadySuppressed = false;
    SuppressedForeignActors.Add(Actor, &bAlreadySuppressed);
    if (!bAlreadySuppressed)
    {
        ++ForeignLightingSuppressedCount;
        UE_LOG(LogTemp, Display, TEXT("CELESTIAL_FOREIGN_LIGHTING_SUPPRESSED|world=%s|actor=%s|total=%d"),
            *GetNameSafe(GetWorld()), *Actor->GetActorNameOrLabel(), ForeignLightingSuppressedCount);
    }
    return true;
}

int32 AInfinityStageCelestialRig::SuppressForeignEnvironmentLighting()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return 0;
    }
    ResolveEnvironmentBindings();
    ++ForeignLightingWalkCount;
    LastForeignLightingWalkSeconds = FPlatformTime::Seconds();
    LastForeignLightingCheckSeconds = LastForeignLightingWalkSeconds;
    int32 Foreign = 0;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        Foreign += SuppressIfForeign(*It) ? 1 : 0;
    }
    return Foreign;
}

int32 AInfinityStageCelestialRig::ReapplyForeignSuppression()
{
    // Only the actors already silenced. Every foreign sky present at BeginPlay
    // was found by the first walk, and every arrival by the spawn and level
    // hooks, so a sequence re-showing one of these is the only case left. A walk
    // of a full show level every couple of seconds was a periodic frame hitch.
    ++ForeignLightingReapplyCount;
    LastForeignLightingCheckSeconds = FPlatformTime::Seconds();
    int32 Rehidden = 0;
    for (const TWeakObjectPtr<AActor>& Known : SuppressedForeignActors.Array())
    {
        if (AActor* Actor = Known.Get())
        {
            Rehidden += SuppressIfForeign(Actor) ? 1 : 0;
        }
        else
        {
            SuppressedForeignActors.Remove(Known);
        }
    }
    return Rehidden;
}

void AInfinityStageCelestialRig::HandleActorSpawned(AActor* Actor)
{
    // A spawned actor arrives with its components; check it alone, never the world.
    if (bSuppressForeignEnvironmentLighting)
    {
        SuppressIfForeign(Actor);
    }
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
    // The Master applies a phase every frame, so the world walk is not done here:
    // once if nothing has walked yet (the editor, before BeginPlay), then at most
    // every ForeignLightingRecheckSeconds a re-hide of the actors already
    // silenced, for skies a sequence re-shows. Arrivals are handled by the spawn
    // and level hooks.
    if (bSuppressForeignEnvironmentLighting)
    {
        // In a game world BeginPlay makes the first walk, with the arrival hooks
        // bound; a phase applied before it (at construction) must not walk as
        // well. Only the editor, which never begins play, walks on its first apply.
        const UWorld* World = GetWorld();
        const bool bBeforeGameBegins = World && World->IsGameWorld() && !HasActorBegunPlay();
        const bool bNeverWalked = LastForeignLightingWalkSeconds < 0.0;
        const bool bRecheckDue = ForeignLightingRecheckSeconds > 0.0f
            && FPlatformTime::Seconds() - LastForeignLightingCheckSeconds >= ForeignLightingRecheckSeconds;
        if (!bBeforeGameBegins && bNeverWalked)
        {
            SuppressForeignEnvironmentLighting();
        }
        else if (!bBeforeGameBegins && bRecheckDue)
        {
            ReapplyForeignSuppression();
        }
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

    // Every write below is skipped when the value is already in place. Editor Sequencer and Cue Desk preview can
    // re-apply one unchanged phase every frame, and rotating a directional light invalidates its whole shadow
    // cache. Where the engine's own quantisation is not visible from its headers, a mismatch only means the
    // setter runs as it always did, so the checks can only remove writes, never change a value.
    const float SunPitch = 90.0f - static_cast<float>(CurrentNormalizedPhase * 360.0);
    const auto SetRotationIfChanged = [](AActor* Actor, const FRotator& Rotation)
    {
        if (!Actor->GetActorQuat().Equals(Rotation.Quaternion(), 1.0e-6f))
        {
            Actor->SetActorRotation(Rotation);
        }
    };
    const auto SetDirectionalIfChanged = [](UDirectionalLightComponent* Light, float Intensity, const FLinearColor& Color, uint8 AtmosphereIndex)
    {
        if (Light->Intensity != Intensity)
        {
            Light->SetIntensity(Intensity);
        }
        if (Light->LightColor != Color.ToFColor(false))
        {
            Light->SetLightColor(Color, false);
        }
        if (!Light->IsUsedAsAtmosphereSunLight())
        {
            Light->SetAtmosphereSunLight(true);
        }
        if (Light->GetAtmosphereSunLightIndex() != AtmosphereIndex)
        {
            Light->SetAtmosphereSunLightIndex(AtmosphereIndex);
        }
    };
    if (SunLightActor)
    {
        SetRotationIfChanged(SunLightActor, FRotator(SunPitch, SunAzimuthDegrees, 0.0f));
        if (UDirectionalLightComponent* Sun = GetDirectionalComponent(SunLightActor))
        {
            const float HeightBlend = FMath::Sqrt(FMath::Clamp(SolarAltitude, 0.0f, 1.0f));
            SetDirectionalIfChanged(Sun, MaximumSunIntensity * CurrentDaylightAmount, FMath::Lerp(HorizonSunColor, NoonSunColor, HeightBlend), 0);
        }
    }

    if (MoonLightActor)
    {
        SetRotationIfChanged(MoonLightActor, FRotator(SunPitch + 180.0f, SunAzimuthDegrees, 0.0f));
        if (UDirectionalLightComponent* Moon = GetDirectionalComponent(MoonLightActor))
        {
            SetDirectionalIfChanged(Moon, MaximumMoonIntensity * MoonlightAmount, MoonColor, 1);
        }
    }

    if (SkyLightActor)
    {
        if (USkyLightComponent* Sky = SkyLightActor->GetLightComponent())
        {
            const float SkyIntensity = FMath::Lerp(NightSkyLightIntensity, DaySkyLightIntensity, CurrentDaylightAmount);
            const FLinearColor SkyColor = FMath::Lerp(NightSkyLightColor, DaySkyLightColor, CurrentDaylightAmount);
            if (Sky->Intensity != SkyIntensity)
            {
                Sky->SetIntensity(SkyIntensity);
            }
            if (Sky->LightColor != SkyColor.ToFColor(true))
            {
                Sky->SetLightColor(SkyColor);
            }
        }
    }

    if (HeightFogActor)
    {
        if (UExponentialHeightFogComponent* Fog = HeightFogActor->GetComponent())
        {
            const FLinearColor FogColor = FMath::Lerp(NightFogColor, DayFogColor, CurrentDaylightAmount);
            const FLinearColor DirectionalColor = FMath::Lerp(MoonColor, HorizonSunColor, CurrentDaylightAmount);
            if (Fog->FogInscatteringLuminance != FogColor)
            {
                Fog->SetFogInscatteringColor(FogColor);
            }
            if (Fog->DirectionalInscatteringLuminance != DirectionalColor)
            {
                Fog->SetDirectionalInscatteringColor(DirectionalColor);
            }
        }
    }

    if (StarsDome)
    {
        const bool bStarsVisible = bShowBuiltInStars && CurrentStarsAmount > 0.002f;
        if (StarsDome->GetVisibleFlag() != bStarsVisible)
        {
            StarsDome->SetVisibility(bStarsVisible, true);
            InvalidateStarsMaterialParameterCache();
        }
        const FRotator StarsRotation(static_cast<float>(CurrentNormalizedPhase * 360.0), SunAzimuthDegrees, 0.0f);
        if (!StarsDome->GetRelativeRotation().Equals(StarsRotation, 1.0e-4f))
        {
            StarsDome->SetRelativeRotation(StarsRotation);
        }
        if (bStarsVisible)
        {
            const auto SetScalarParameterIfChanged = [this](
                const FName ParameterName,
                const float Value,
                float& LastWrittenValue)
            {
                if (!FMath::IsFinite(LastWrittenValue) || FMath::Abs(Value - LastWrittenValue) > 1.0e-6f)
                {
                    StarsDome->SetScalarParameterValueOnMaterials(ParameterName, Value);
                    LastWrittenValue = Value;
#if WITH_DEV_AUTOMATION_TESTS
                    ++StarsMaterialParameterWriteCountForTests;
#endif
                }
            };
            SetScalarParameterIfChanged(
                TEXT("Stars brightness"),
                MaximumStarsBrightness * CurrentStarsAmount,
                LastStarsBrightnessWritten);
            SetScalarParameterIfChanged(TEXT("Sun brightness"), 0.0f, LastSunBrightnessWritten);
            SetScalarParameterIfChanged(TEXT("Cloud opacity"), 0.0f, LastCloudOpacityWritten);
            SetScalarParameterIfChanged(TEXT("Sun height"), SolarAltitude, LastSunHeightWritten);
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
