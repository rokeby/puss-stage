#include "InfinityStageEffectSource.h"

#include "CineCameraComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/LocalFogVolumeComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageLightDrama.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "Misc/PackageName.h"
#include "Particles/ParticleSystemComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "UObject/SoftObjectPath.h"
#if WITH_EDITOR
#include "UObject/UnrealType.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageEffects, Log, All);

namespace
{
// User parameters every effect Niagara system may read. A system that does not
// declare one simply ignores it.
const FName OutputParameter(TEXT("User.Output"));
const FName TintParameter(TEXT("User.Tint"));
const FName PumpParameter(TEXT("User.Pump"));
const FName BurnProgressParameter(TEXT("User.BurnProgress"));
const FName IgnitionParameter(TEXT("User.Ignition"));
const FName ExtentParameter(TEXT("User.Extent"));
const FName PanelOriginParameter(TEXT("User.PanelOrigin"));
const FName PanelExtentParameter(TEXT("User.PanelExtent"));
const FName IgnitionLocalParameter(TEXT("User.IgnitionLocal"));
const FName UVRectMinParameter(TEXT("User.UVRectMin"));
const FName UVRectMaxParameter(TEXT("User.UVRectMax"));
const FName FrontRadiusParameter(TEXT("User.FrontRadiusCm"));

constexpr double RigSearchIntervalSeconds = 1.0;
constexpr double LinkedLightSearchIntervalSeconds = 1.0;

const TCHAR* DefaultBlueprintPath(const EInfinityStageEffectType Type)
{
    switch (Type)
    {
    case EInfinityStageEffectType::Haze:
        return TEXT("/Game/Scenes/Effects/BP_Effect_HazePot.BP_Effect_HazePot_C");
    case EInfinityStageEffectType::Smoke:
        return TEXT("/Game/Scenes/Effects/BP_Effect_SmokePot.BP_Effect_SmokePot_C");
    case EInfinityStageEffectType::Steam:
        return TEXT("/Game/Scenes/Effects/BP_Effect_SteamKettle.BP_Effect_SteamKettle_C");
    case EInfinityStageEffectType::Fire:
        return TEXT("/Game/Scenes/Effects/BP_Effect_FireBasket.BP_Effect_FireBasket_C");
    case EInfinityStageEffectType::WingBurn:
        return TEXT("/Game/Scenes/Effects/BP_Effect_WingBurn.BP_Effect_WingBurn_C");
    case EInfinityStageEffectType::Motes:
        return TEXT("/Game/Scenes/Effects/BP_Effect_Motes.BP_Effect_Motes_C");
    }
    return nullptr;
}

bool PanelSideForAnchor(const EInfinityAttachmentAnchor InAnchor, EInfinityPanelSide& OutSide)
{
    switch (InAnchor)
    {
    case EInfinityAttachmentAnchor::LeftPanel:
        OutSide = EInfinityPanelSide::Left;
        return true;
    case EInfinityAttachmentAnchor::RightPanel:
        OutSide = EInfinityPanelSide::Right;
        return true;
    case EInfinityAttachmentAnchor::TopPanel:
        OutSide = EInfinityPanelSide::Top;
        return true;
    default:
        return false;
    }
}

/** A burning wing and drifting motes have no device of their own to show. */
bool HasApparatus(const EInfinityStageEffectType Type)
{
    return Type != EInfinityStageEffectType::WingBurn && Type != EInfinityStageEffectType::Motes;
}
}

AInfinityStageEffectSource::AInfinityStageEffectSource()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SceneRoot->SetMobility(EComponentMobility::Movable);
    SetRootComponent(SceneRoot);

    TrackingRoot = CreateDefaultSubobject<USceneComponent>(TEXT("TrackingRoot"));
    TrackingRoot->SetMobility(EComponentMobility::Movable);
    TrackingRoot->SetupAttachment(SceneRoot);

    // Greybox until the Blender apparatus exists: a squat box standing on the floor.
    Apparatus = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Apparatus"));
    Apparatus->SetMobility(EComponentMobility::Movable);
    Apparatus->SetupAttachment(TrackingRoot);
    Apparatus->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> GreyboxMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (GreyboxMesh.Succeeded())
    {
        Apparatus->SetStaticMesh(GreyboxMesh.Object);
    }
    Apparatus->SetRelativeLocation(FVector(0.0, 0.0, 40.0));
    Apparatus->SetRelativeScale3D(FVector(0.6, 0.6, 0.8));

    Medium = CreateDefaultSubobject<ULocalFogVolumeComponent>(TEXT("Medium"));
    Medium->SetMobility(EComponentMobility::Movable);
    Medium->SetupAttachment(TrackingRoot);
}

UClass* AInfinityStageEffectSource::ResolveDefaultClass(const FInfinityStageEffectSettings& InSettings)
{
    if (const TCHAR* Path = DefaultBlueprintPath(InSettings.Type))
    {
        const FSoftObjectPath ClassPath(Path);
        // Check before loading: until the Effects content exists the native
        // greybox is the expected answer, not a warning on every materialize.
        if (FPackageName::DoesPackageExist(ClassPath.GetLongPackageName()))
        {
            if (UClass* Loaded = TSoftClassPtr<AInfinityStageEffectSource>(ClassPath).LoadSynchronous())
            {
                return Loaded;
            }
            UE_LOG(
                LogInfinityStageEffects,
                Warning,
                TEXT("INFINITY_STAGE_EFFECT_CLASS_FALLBACK path=%s; not an Effect Source class, using the greybox."),
                Path);
        }
    }
    return AInfinityStageEffectSource::StaticClass();
}

bool AInfinityStageEffectSource::ApplyAttachment(
    AActor& Spawned,
    const FGuid& InCueGuid,
    const FInfinityCueAttachment& Attachment)
{
    AInfinityStageEffectSource* Source = Cast<AInfinityStageEffectSource>(&Spawned);
    if (!Source)
    {
        // A custom Actor Class keeps its own behaviour but still takes the
        // Show-owned look on every FX system it carries.
        return PushSystemParameters(Spawned, Attachment.Effect) > 0;
    }
    Source->CueGuid = InCueGuid;
    Source->AttachmentGuid = Attachment.AttachmentGuid;
    Source->Anchor = Attachment.Anchor;
    Source->Settings = Attachment.Effect;
    Source->ApplySettings();
    Source->BindAnchor();
    return true;
}

int32 AInfinityStageEffectSource::PushSystemParameters(AActor& Actor, const FInfinityStageEffectSettings& InSettings)
{
    TInlineComponentArray<UFXSystemComponent*> Systems(&Actor);
    for (UFXSystemComponent* System : Systems)
    {
        System->SetFloatParameter(OutputParameter, InSettings.Output);
        System->SetColorParameter(TintParameter, InSettings.Tint);
        System->SetVectorParameter(
            IgnitionParameter,
            FVector(InSettings.IgnitionUV.X, InSettings.IgnitionUV.Y, 0.0));
        System->SetVectorParameter(ExtentParameter, InSettings.MotesExtentCm);
    }
    return Systems.Num();
}

float AInfinityStageEffectSource::ComputeBurnProgress(
    const double WingAheadOfCameraCm,
    const float StartAheadCm,
    const float SpanCm)
{
    const double TravelledCm = static_cast<double>(StartAheadCm) - WingAheadOfCameraCm;
    const double Span = FMath::Max(1.0, static_cast<double>(SpanCm));
    return static_cast<float>(FMath::Clamp(TravelledCm / Span, 0.0, 1.0));
}

float AInfinityStageEffectSource::ComputePump(
    const double TimeSeconds,
    const float PeriodSeconds,
    const float Duty,
    const float InPhase01)
{
    const double Period = static_cast<double>(PeriodSeconds);
    const double ClampedDuty = FMath::Clamp(static_cast<double>(Duty), 0.05, 1.0);
    if (Period <= UE_KINDA_SMALL_NUMBER || ClampedDuty >= 1.0)
    {
        return 1.0f;
    }
    const double Cycle = FMath::Frac(TimeSeconds / Period + static_cast<double>(InPhase01));
    // Soft edges: a stroke of the bellows swells and falls rather than switching.
    const double Edge = FMath::Min(0.1, ClampedDuty * 0.5);
    const double Rise = FMath::SmoothStep(0.0, Edge, Cycle);
    const double Fall = 1.0 - FMath::SmoothStep(ClampedDuty - Edge, ClampedDuty, Cycle);
    return static_cast<float>(FMath::Clamp(Rise * Fall, 0.0, 1.0));
}

float AInfinityStageEffectSource::ComputePhase(const FGuid& InCueGuid, const FGuid& InAttachmentGuid)
{
    const uint32 Hash = HashCombine(GetTypeHash(InCueGuid), GetTypeHash(InAttachmentGuid));
    return static_cast<float>(Hash % 10007u) / 10007.0f;
}

float AInfinityStageEffectSource::ComputeFlicker(const double TimeSeconds, const float InPhase01)
{
    const double Phase = UE_DOUBLE_TWO_PI * static_cast<double>(InPhase01);
    const double Value = 0.5 * FMath::Sin(UE_DOUBLE_TWO_PI * 1.7 * TimeSeconds + Phase)
        + 0.3 * FMath::Sin(UE_DOUBLE_TWO_PI * 4.3 * TimeSeconds + 2.0 * Phase)
        + 0.2 * FMath::Sin(UE_DOUBLE_TWO_PI * 9.1 * TimeSeconds + 3.0 * Phase);
    return static_cast<float>(Value);
}

bool AInfinityStageEffectSource::ComputeBurnFront(
    const FInfinityStageEffectSettings& InSettings,
    const float Progress,
    FVector& OutIgnitionLocal,
    float& OutRadiusCm)
{
    const double ScaleU = InSettings.BurnUAxis.X;
    const double ScaleV = InSettings.BurnVAxis.X;
    if (FMath::IsNearlyZero(ScaleU) || FMath::IsNearlyZero(ScaleV))
    {
        return false;
    }
    const double IgnitionU = InSettings.IgnitionUV.X;
    const double IgnitionV = InSettings.IgnitionUV.Y;
    // Invert U = a * Y + b and V = a * Z + b. The signs vary by mesh (V runs down
    // on every wing, U on most), so they are never assumed.
    OutIgnitionLocal = FVector(
        0.0,
        (IgnitionU - InSettings.BurnUAxis.Y) / ScaleU,
        (IgnitionV - InSettings.BurnVAxis.Y) / ScaleV);
    // One UV unit spans 1 / |a| cm; the farthest corner of the UV square bounds
    // the front, and the master's pad takes the ragged edge to hole depth.
    const double ReachUCm = FMath::Max(IgnitionU, 1.0 - IgnitionU) / FMath::Abs(ScaleU);
    const double ReachVCm = FMath::Max(IgnitionV, 1.0 - IgnitionV) / FMath::Abs(ScaleV);
    const double FarthestCornerCm = FMath::Sqrt(ReachUCm * ReachUCm + ReachVCm * ReachVCm);
    OutRadiusCm = static_cast<float>(
        FMath::Clamp(static_cast<double>(Progress), 0.0, 1.0)
        * (FarthestCornerCm + static_cast<double>(InfinityStageWingBurn::FrontPadCm)));
    return true;
}

void AInfinityStageEffectSource::ApplySettings()
{
    Phase01 = ComputePhase(CueGuid, AttachmentGuid);

    if (Apparatus)
    {
        const bool bShowApparatus = HasApparatus(Settings.Type);
        Apparatus->SetVisibility(bShowApparatus);
        Apparatus->SetHiddenInGame(!bShowApparatus);
    }
    if (Medium)
    {
        const bool bFeeds = Settings.bFeedsLocalMedium && Settings.MediumDensity > 0.0f;
        // The volume's unit sphere spans GetBaseVolumeSize() at scale 1; the first
        // rendered spike confirms whether that reads as radius or diameter.
        const float Scale = Settings.MediumRadiusCm / ULocalFogVolumeComponent::GetBaseVolumeSize();
        Medium->SetRelativeLocation(Settings.MediumOffsetCm);
        Medium->SetRelativeScale3D(FVector(FMath::Max(0.01f, Scale)));
        Medium->SetRadialFogExtinction(bFeeds ? Settings.MediumDensity : 0.0f);
        Medium->SetHeightFogExtinction(bFeeds ? Settings.MediumDensity : 0.0f);
        Medium->SetHeightFogFalloff(Settings.MediumHeightFalloff);
        Medium->SetFogAlbedo(Settings.Tint);
        Medium->SetVisibility(bFeeds);
    }
    PushSystemParameters(*this, Settings);
}

void AInfinityStageEffectSource::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    // Blueprint construction recreates its FX components, which drops any
    // parameters pushed to the previous ones.
    ApplySettings();
}

bool AInfinityStageEffectSource::ShouldTickIfViewportsOnly() const
{
    // Plumes, pumping and panel tracking should read in the editor as they will
    // in the show. Nothing the editor tick does writes to another actor.
    return true;
}

void AInfinityStageEffectSource::BeginPlay()
{
    Super::BeginPlay();
    // Weak references do not survive duplication into a PIE or render world.
    ApplySettings();
    BindAnchor();
    bLinkedLightYieldedToDrama = false;
    BindLinkedLight();
    bActivityKnown = false;
}

void AInfinityStageEffectSource::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    RestoreLinkedLight();
    Super::EndPlay(EndPlayReason);
}

AInfinityStagePassageActor* AInfinityStageEffectSource::GetOwningPassage() const
{
    return Cast<AInfinityStagePassageActor>(GetAttachParentActor());
}

void AInfinityStageEffectSource::BindAnchor()
{
    PanelComponent.Reset();
    PanelInstanceIndex = INDEX_NONE;
    PanelBaseWorld = FTransform::Identity;
    bHaveAnchorRouteDistance = false;
    bWarnedNoCustomData = false;
    LastWrittenBurnProgress = -1.0f;

    AInfinityStagePassageActor* Passage = GetOwningPassage();
    if (!Passage)
    {
        return;
    }

    FVector AnchorLocation = GetActorLocation();
    EInfinityPanelSide Side = EInfinityPanelSide::Left;
    if (PanelSideForAnchor(Anchor, Side))
    {
        const FGuid OwnCueGuid = CueGuid;
        const FInfinityMaterializedPanelRef* Panel = Passage->MaterializedPanels.FindByPredicate(
            [OwnCueGuid, Side](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == OwnCueGuid && Ref.Side == Side; });
        if (Panel && Panel->Component && Panel->InstanceIndex != INDEX_NONE)
        {
            PanelComponent = Panel->Component.Get();
            PanelInstanceIndex = Panel->InstanceIndex;
            PanelBaseWorld = Panel->BaseWorldTransform;
            AnchorLocation = Panel->BaseWorldTransform.GetLocation();
            const UStaticMesh* PanelMesh = Panel->Component->GetStaticMesh();
            if (PanelMesh && Settings.Type == EInfinityStageEffectType::WingBurn)
            {
                PushBurnGeometry(*PanelMesh);
            }
        }
    }
    if (Settings.Type == EInfinityStageEffectType::WingBurn && !PanelComponent.IsValid())
    {
        UE_LOG(
            LogInfinityStageEffects,
            Warning,
            TEXT("INFINITY_STAGE_EFFECT_BURN_NO_PANEL actor='%s' cue=%s; a Wing Burn needs a Left, Right or Top panel anchor on a materialized pair."),
            *GetActorNameOrLabel(),
            *CueGuid.ToString(EGuidFormats::DigitsWithHyphens));
    }
    if (Passage->Route)
    {
        // Measured once: the anchor's station does not move along the route.
        AnchorRouteDistanceCm = Passage->Route->GetDistanceAlongSplineAtLocation(
            AnchorLocation,
            ESplineCoordinateSpace::World);
        bHaveAnchorRouteDistance = true;
    }
}

void AInfinityStageEffectSource::PushBurnGeometry(const UStaticMesh& PanelMesh)
{
    TInlineComponentArray<UFXSystemComponent*> Systems(this);
    // Bounds only for the panel's thickness (X): the UV square, not the bounds,
    // is what the char is drawn across.
    const FBoxSphereBounds Bounds = PanelMesh.GetBounds();
    for (UFXSystemComponent* System : Systems)
    {
        System->SetVectorParameter(PanelOriginParameter, Bounds.Origin);
        System->SetVectorParameter(PanelExtentParameter, Bounds.BoxExtent);
    }

    FVector IgnitionLocal;
    float UnusedRadiusCm = 0.0f;
    if (!ComputeBurnFront(Settings, 0.0f, IgnitionLocal, UnusedRadiusCm))
    {
        UE_LOG(
            LogInfinityStageEffects,
            Warning,
            TEXT("INFINITY_STAGE_EFFECT_BURN_NO_UV_MAPPING actor='%s' mesh=%s; the wing still chars, but its flames cannot be placed on the front until the UV mapping is set."),
            *GetActorNameOrLabel(),
            *PanelMesh.GetPathName());
        return;
    }
    if (!Settings.BurnUVMeasuredMesh.IsNull()
        && Settings.BurnUVMeasuredMesh.ToSoftObjectPath() != FSoftObjectPath(&PanelMesh))
    {
        UE_LOG(
            LogInfinityStageEffects,
            Warning,
            TEXT("INFINITY_STAGE_EFFECT_BURN_UV_STALE actor='%s' measured=%s panel=%s; re-measure, or the flames may leave the char line."),
            *GetActorNameOrLabel(),
            *Settings.BurnUVMeasuredMesh.ToString(),
            *PanelMesh.GetPathName());
    }
    // Corners of the UV square in mesh-local Y and Z.
    const double Y0 = -Settings.BurnUAxis.Y / Settings.BurnUAxis.X;
    const double Y1 = (1.0 - Settings.BurnUAxis.Y) / Settings.BurnUAxis.X;
    const double Z0 = -Settings.BurnVAxis.Y / Settings.BurnVAxis.X;
    const double Z1 = (1.0 - Settings.BurnVAxis.Y) / Settings.BurnVAxis.X;
    const FVector RectMin(0.0, FMath::Min(Y0, Y1), FMath::Min(Z0, Z1));
    const FVector RectMax(0.0, FMath::Max(Y0, Y1), FMath::Max(Z0, Z1));
    for (UFXSystemComponent* System : Systems)
    {
        System->SetVectorParameter(IgnitionLocalParameter, IgnitionLocal);
        System->SetVectorParameter(UVRectMinParameter, RectMin);
        System->SetVectorParameter(UVRectMaxParameter, RectMax);
    }
}

void AInfinityStageEffectSource::BindLinkedLight()
{
    LinkedLight.Reset();
    if (!Settings.LinkedLightAttachmentGuid.IsValid())
    {
        return;
    }
    AInfinityStagePassageActor* Passage = GetOwningPassage();
    if (!Passage || !Passage->ShowAsset)
    {
        return;
    }
    const FGuid OwnCueGuid = CueGuid;
    const FGuid LightGuid = Settings.LinkedLightAttachmentGuid;
    const FInfinityShowCue* Cue = Passage->ShowAsset->Cues.FindByPredicate(
        [OwnCueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == OwnCueGuid; });
    const FInfinityCueAttachment* LightAttachment = Cue
        ? Cue->WingPair.Attachments.FindByPredicate(
            [LightGuid](const FInfinityCueAttachment& Candidate)
            { return Candidate.AttachmentGuid == LightGuid && Candidate.Kind == EInfinityAttachmentKind::Light; })
        : nullptr;
    if (!LightAttachment)
    {
        return;
    }
    if (InfinityStageLightDrama::IsActive(LightAttachment->Lighting.Drama))
    {
        // One writer per lamp. A light with drama is the rig's to animate, and a
        // flicker on top would fight it frame by frame.
        bLinkedLightYieldedToDrama = true;
        UE_LOG(
            LogInfinityStageEffects,
            Warning,
            TEXT("INFINITY_STAGE_EFFECT_LIGHT_YIELDED actor='%s' light=%s; the linked light has drama, so this effect will not flicker it."),
            *GetActorNameOrLabel(),
            *LightGuid.ToString(EGuidFormats::DigitsWithHyphens));
        return;
    }
    for (AActor* Candidate : Passage->ManagedAttachmentActors)
    {
        FGuid FoundCueGuid;
        FGuid FoundAttachmentGuid;
        if (!IsValid(Candidate)
            || !Passage->FindAttachmentByActor(Candidate, FoundCueGuid, FoundAttachmentGuid)
            || FoundCueGuid != OwnCueGuid
            || FoundAttachmentGuid != LightGuid)
        {
            continue;
        }
        if (ULightComponent* Light = Candidate->FindComponentByClass<ULightComponent>())
        {
            LinkedLight = Light;
            // The base is the Show's value, never the actor's, which this flickers.
            LinkedLightBaseIntensity = LightAttachment->Lighting.Intensity;
        }
        return;
    }
}

void AInfinityStageEffectSource::RestoreLinkedLight()
{
    if (ULightComponent* Light = LinkedLight.Get())
    {
        Light->SetIntensity(LinkedLightBaseIntensity);
    }
}

void AInfinityStageEffectSource::TrackAnchor()
{
    UInstancedStaticMeshComponent* Panel = PanelComponent.Get();
    FTransform PanelWorld;
    if (!Panel || !TrackingRoot || !Panel->GetInstanceTransform(PanelInstanceIndex, PanelWorld, true))
    {
        return;
    }
    // The actor stands where materialization put it against the panel's rest
    // pose. Carry its current offset from that pose onto the live panel, so both
    // the wing's inward travel and a drag in the viewport move what is seen.
    const FTransform OffsetFromPanel = GetActorTransform().GetRelativeTransform(PanelBaseWorld);
    TrackingRoot->SetWorldTransform(OffsetFromPanel * PanelWorld);
}

bool AInfinityStageEffectSource::IsWithinRenderedViewRadius() const
{
    const UWorld* World = GetWorld();
    if (!World || World->ViewLocationsRenderedLastFrame.IsEmpty())
    {
        // Nothing rendered to measure from, e.g. the first frame: run rather than
        // hide an effect someone is looking for.
        return true;
    }
    const FVector Here = TrackingRoot ? TrackingRoot->GetComponentLocation() : GetActorLocation();
    const double RadiusSquared = FMath::Square(static_cast<double>(Settings.ActiveRadiusCm));
    for (const FVector& View : World->ViewLocationsRenderedLastFrame)
    {
        if (FVector::DistSquared(View, Here) <= RadiusSquared)
        {
            return true;
        }
    }
    return false;
}

void AInfinityStageEffectSource::SetEffectActive(const bool bNewActive)
{
    if (bActivityKnown && bEffectActive == bNewActive)
    {
        return;
    }
    bActivityKnown = true;
    bEffectActive = bNewActive;
    TInlineComponentArray<UFXSystemComponent*> Systems(this);
    for (UFXSystemComponent* System : Systems)
    {
        if (bNewActive)
        {
            System->Activate(false);
        }
        else
        {
            // Deactivate stops spawning and lets what is in the air finish.
            System->Deactivate();
        }
    }
}

bool AInfinityStageEffectSource::ResolveShowCameraRouteDistance(double& OutRouteDistanceCm) const
{
    AInfinityStagePassageActor* Passage = GetOwningPassage();
    const UWorld* World = GetWorld();
    if (!Passage || !Passage->Route || !World)
    {
        return false;
    }

    AInfinityStageCameraRig* Rig = CachedRig.Get();
    if (!Rig)
    {
        const double Now = World->GetTimeSeconds();
        if (Now < NextRigSearchSeconds)
        {
            return false;
        }
        NextRigSearchSeconds = Now + RigSearchIntervalSeconds;
        for (TActorIterator<AInfinityStageCameraRig> It(World); It; ++It)
        {
            // Prefer the rig driving this Passage; any rig is better than none.
            if (!Rig || It->PassageActor.Get() == Passage)
            {
                Rig = *It;
            }
            if (It->PassageActor.Get() == Passage)
            {
                break;
            }
        }
        CachedRig = Rig;
    }
    if (!Rig || !Rig->Camera)
    {
        return false;
    }
    if (Rig->PassageActor && Rig->PassageActor.Get() != Passage)
    {
        // The show camera is in another Passage, so this wing is not in shot.
        return false;
    }
    // The evaluated show camera, not whichever viewport is looking: the burn must
    // be the same on every scrub and every render.
    OutRouteDistanceCm = Passage->Route->GetDistanceAlongSplineAtLocation(
        Rig->Camera->GetComponentLocation(),
        ESplineCoordinateSpace::World);
    return true;
}

void AInfinityStageEffectSource::UpdateWingBurn(const bool bDriveWing)
{
    double CameraRouteDistanceCm = 0.0;
    if (!bHaveAnchorRouteDistance || !ResolveShowCameraRouteDistance(CameraRouteDistanceCm))
    {
        return;
    }
    CurrentBurnProgress = ComputeBurnProgress(
        AnchorRouteDistanceCm - CameraRouteDistanceCm,
        Settings.BurnStartAheadCm,
        Settings.BurnSpanCm);

    FVector IgnitionLocal;
    float FrontRadiusCm = 0.0f;
    const bool bHaveFront = ComputeBurnFront(Settings, CurrentBurnProgress, IgnitionLocal, FrontRadiusCm);
    TInlineComponentArray<UFXSystemComponent*> Systems(this);
    for (UFXSystemComponent* System : Systems)
    {
        System->SetFloatParameter(BurnProgressParameter, CurrentBurnProgress);
        if (bHaveFront)
        {
            System->SetFloatParameter(FrontRadiusParameter, FrontRadiusCm);
        }
    }

    UInstancedStaticMeshComponent* Panel = PanelComponent.Get();
    if (!bDriveWing || !Panel || FMath::IsNearlyEqual(CurrentBurnProgress, LastWrittenBurnProgress, 1.0e-4f))
    {
        return;
    }
    if (Panel->NumCustomDataFloats < InfinityStageWingCustomData::NumFloats)
    {
        if (!bWarnedNoCustomData)
        {
            bWarnedNoCustomData = true;
            UE_LOG(
                LogInfinityStageEffects,
                Warning,
                TEXT("INFINITY_STAGE_EFFECT_BURN_NO_CUSTOM_DATA actor='%s' floats=%d required=%d; the wing chars only once the Passage allocates custom data."),
                *GetActorNameOrLabel(),
                Panel->NumCustomDataFloats,
                InfinityStageWingCustomData::NumFloats);
        }
        return;
    }
    Panel->SetCustomDataValue(
        PanelInstanceIndex,
        InfinityStageWingCustomData::IgnitionU,
        static_cast<float>(Settings.IgnitionUV.X),
        false);
    Panel->SetCustomDataValue(
        PanelInstanceIndex,
        InfinityStageWingCustomData::IgnitionV,
        static_cast<float>(Settings.IgnitionUV.Y),
        false);
    Panel->SetCustomDataValue(
        PanelInstanceIndex,
        InfinityStageWingCustomData::BurnProgress,
        CurrentBurnProgress,
        true);
    LastWrittenBurnProgress = CurrentBurnProgress;
}

void AInfinityStageEffectSource::UpdateLinkedLight(const double TimeSeconds)
{
    if (!Settings.LinkedLightAttachmentGuid.IsValid() || bLinkedLightYieldedToDrama)
    {
        return;
    }
    if (!LinkedLight.IsValid())
    {
        // Attachments spawn in cue order, so the light may appear after us.
        if (TimeSeconds < NextLinkedLightSearchSeconds)
        {
            return;
        }
        NextLinkedLightSearchSeconds = TimeSeconds + LinkedLightSearchIntervalSeconds;
        BindLinkedLight();
        if (!LinkedLight.IsValid())
        {
            return;
        }
    }
    float Envelope = 1.0f;
    if (Settings.Type == EInfinityStageEffectType::WingBurn)
    {
        // A burning wing throws light only while it burns: none before, none once consumed.
        Envelope = FMath::Sin(UE_PI * CurrentBurnProgress);
    }
    const float Flicker = 1.0f + Settings.FlickerAmount * ComputeFlicker(TimeSeconds, Phase01);
    LinkedLight->SetIntensity(FMath::Max(0.0f, LinkedLightBaseIntensity * Envelope * Flicker));
}

void AInfinityStageEffectSource::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    TrackAnchor();
    SetEffectActive(IsWithinRenderedViewRadius());

    // Game worlds (PIE, Movie Render Queue) are never saved, so only there may an
    // effect write into another actor: the wing's custom data, the rig's light.
    const bool bGameWorld = World->IsGameWorld();
    const double Now = World->GetTimeSeconds();

    if (Settings.Type == EInfinityStageEffectType::WingBurn)
    {
        // Evaluated even when out of range, so a scrub past the wing leaves it burnt.
        UpdateWingBurn(bGameWorld);
    }
    if (bGameWorld && (bEffectActive || Settings.Type == EInfinityStageEffectType::WingBurn))
    {
        UpdateLinkedLight(Now);
    }
    if (!bEffectActive)
    {
        return;
    }

    const float Pump = ComputePump(Now, Settings.PulsePeriodSeconds, Settings.PulseDuty, Phase01);
    TInlineComponentArray<UFXSystemComponent*> Systems(this);
    for (UFXSystemComponent* System : Systems)
    {
        System->SetFloatParameter(PumpParameter, Pump);
    }
}

#if WITH_EDITOR
void AInfinityStageEffectSource::PostEditChangeProperty(FPropertyChangedEvent& Event)
{
    Super::PostEditChangeProperty(Event);
    ApplySettings();
    // Preview while a slider drags; write to the Show once, on release.
    if (Event.ChangeType == EPropertyChangeType::Interactive)
    {
        return;
    }
    const FName MemberName = Event.MemberProperty ? Event.MemberProperty->GetFName() : NAME_None;
    if (MemberName == GET_MEMBER_NAME_CHECKED(AInfinityStageEffectSource, Settings))
    {
        WriteSettingsToShow(Event);
    }
}

void AInfinityStageEffectSource::WriteSettingsToShow(const FPropertyChangedEvent& Event)
{
    const UWorld* World = GetWorld();
    if (IsTemplate() || !World || World->IsGameWorld())
    {
        return;
    }
    AInfinityStagePassageActor* Passage = GetOwningPassage();
    if (!Passage || !Passage->ShowAsset)
    {
        return;
    }
    FGuid FoundCueGuid;
    FGuid FoundAttachmentGuid;
    if (!Passage->FindAttachmentByActor(this, FoundCueGuid, FoundAttachmentGuid))
    {
        return;
    }
    FInfinityShowCue* Cue = Passage->ShowAsset->Cues.FindByPredicate(
        [FoundCueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == FoundCueGuid; });
    FInfinityCueAttachment* Attachment = Cue
        ? Cue->WingPair.Attachments.FindByPredicate(
            [FoundAttachmentGuid](const FInfinityCueAttachment& Candidate)
            { return Candidate.AttachmentGuid == FoundAttachmentGuid; })
        : nullptr;
    if (!Attachment || Attachment->Kind != EInfinityAttachmentKind::Effect)
    {
        return;
    }

    FInfinityStageEffectSettings Written = Settings;
    // Provenance belongs to replication, not to a Details edit.
    Written.ReplicatedFromAttachmentGuid = Attachment->Effect.ReplicatedFromAttachmentGuid;
    Passage->ShowAsset->Modify();
    Attachment->Effect = Written;
    Settings.ReplicatedFromAttachmentGuid = Written.ReplicatedFromAttachmentGuid;
    UE_LOG(
        LogInfinityStageEffects,
        Display,
        TEXT("INFINITY_STAGE_ATTACHMENT_EFFECT_UPDATED cue='%s' attachment='%s' property=%s replicated=%s; written to the Show, save it intentionally."),
        *Cue->Label.ToString(),
        *Attachment->Label.ToString(),
        Event.Property ? *Event.Property->GetName() : TEXT("?"),
        Written.ReplicatedFromAttachmentGuid.IsValid() ? TEXT("true") : TEXT("false"));
}
#endif
