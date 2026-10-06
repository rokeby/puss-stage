#include "InfinityStagePassageActor.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/LocalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/SplineComponent.h"
#include "InfinityStageEffectSource.h"
#include "InfinityStageEffectTypes.h"
#include "InfinityStageLightDrama.h"
#include "InfinityStageBulbBody.h"
#include "InfinityStageLightMover.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/PointLight.h"
#include "Engine/RectLight.h"
#include "Engine/Scene.h"
#include "Engine/SpotLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMeshSocket.h"
#include "Engine/Texture.h"
#include "Engine/TextureLightProfile.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageWingLibraryAsset.h"
#include "LevelSequence.h"
#include "Materials/MaterialInterface.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageMaterialization, Log, All);

static TAutoConsoleVariable<int32> CVarInfinityStageMechanismMarkRenderStateDirty(
    TEXT("InfinityStage.Mechanism.MarkRenderStateDirty"),
    1,
    TEXT("Controls how moving wing ISM batch updates become visible.\n")
    TEXT("0: do not mark render state dirty (freeze diagnostic).\n")
    TEXT("1: preserve existing behaviour with a separate MarkRenderStateDirty call (default).\n")
    TEXT("2: mark only the last contiguous batch dirty through BatchUpdateInstancesTransforms.\n")
    TEXT("Compare 1 vs 2 for the in-motion smudge; use 0 only as a freeze diagnostic."));

namespace
{
const FString InfinityStageAttachmentTagPrefix(TEXT("InfinityStage.Attachment."));

bool HasAttachmentIdentityTag(const AActor& Actor)
{
    return Actor.Tags.ContainsByPredicate([](const FName& Tag)
    {
        return Tag.ToString().StartsWith(InfinityStageAttachmentTagPrefix);
    });
}

void RemoveAttachmentIdentityTags(AActor& Actor)
{
    Actor.Tags.RemoveAll([](const FName& Tag)
    {
        return Tag.ToString().StartsWith(InfinityStageAttachmentTagPrefix);
    });
}

void AddAttachedGeneratedActors(const AActor& Owner, TSet<AActor*>& InOutActors)
{
    TArray<AActor*> AttachedActors;
    Owner.GetAttachedActors(AttachedActors);
    for (AActor* Attached : AttachedActors)
    {
        if (IsValid(Attached) && HasAttachmentIdentityTag(*Attached))
        {
            InOutActors.Add(Attached);
        }
    }
}

const FInfinityShowCue* FindCueByGuid(const UInfinityStageShowAsset& Show, const FGuid& CueGuid)
{
    return Show.Cues.FindByPredicate([CueGuid](const FInfinityShowCue& Cue)
    {
        return Cue.CueGuid == CueGuid;
    });
}

FString MakeRenderKey(const FInfinityPanelDesign& Panel)
{
    FString Key = Panel.Mesh.ToSoftObjectPath().ToString();
    Key += Panel.bCastShadow ? TEXT("|Shadow") : TEXT("|NoShadow");
    Key += Panel.bVisibleInMainPass ? TEXT("|Main") : TEXT("|NoMain");
    Key += FString::Printf(TEXT("|Collision=%d"), static_cast<int32>(Panel.Collision.GetValue()));
    for (const TSoftObjectPtr<UMaterialInterface>& Material : Panel.MaterialOverrides)
    {
        Key += TEXT("|");
        Key += Material.ToSoftObjectPath().ToString();
    }
    return Key;
}

FTransform ResolvePanelFacing(
    const UInfinityStageShowAsset& Show,
    const FInfinityPanelDesign& Panel,
    const EInfinityPanelSide Side)
{
    const FInfinityWingAssetEntry* Entry = nullptr;
    if (const UInfinityStageWingLibraryAsset* Library = Show.WingLibrary.LoadSynchronous())
    {
        Entry = Library->FindEntry(Panel.Mesh.ToSoftObjectPath());
    }

    bool bRotateAroundUp = Panel.FacingPolicy == EInfinityPanelFacingPolicy::Rotate180AroundUp;
    if (Panel.FacingPolicy == EInfinityPanelFacingPolicy::AutoByRole && Entry)
    {
        bRotateAroundUp = Entry->FrontAxis == EInfinityWingFrontAxis::NegativeX;
    }

    FTransform Result = bRotateAroundUp
        ? FTransform(FRotator(0.0, 180.0, 0.0))
        : FTransform::Identity;
    if (Entry)
    {
        const FVector PlacementScale = Entry->PlacementAdjustment.GetScale3D();
        const bool bMirrorsImage = PlacementScale.X * PlacementScale.Y * PlacementScale.Z < 0.0;
        if (!bMirrorsImage || Entry->bPhotographicMirrorApproved)
        {
            Result = Entry->PlacementAdjustment * Result;
        }
        else
        {
            UE_LOG(
                LogInfinityStageMaterialization,
                Warning,
                TEXT("Ignoring unapproved mirrored placement adjustment for %s."),
                *Panel.Mesh.ToSoftObjectPath().ToString());
        }
    }
    return Result;
}

FVector GetPairLocalInwardDirection(const EInfinityPanelSide Side)
{
    if (Side == EInfinityPanelSide::Right)
    {
        return FVector(0.0, -1.0, 0.0);
    }
    if (Side == EInfinityPanelSide::Top)
    {
        return FVector(0.0, 0.0, -1.0);
    }
    return FVector(0.0, 1.0, 0.0);
}

EInfinityMechanismKind ResolveMechanismKindForSide(
    const EInfinityMechanismKind Kind,
    const EInfinityPanelSide Side)
{
    if (Side == EInfinityPanelSide::Top
        && (Kind == EInfinityMechanismKind::Topple || Kind == EInfinityMechanismKind::Turn))
    {
        return EInfinityMechanismKind::Slide;
    }
    return Kind;
}

FTransform ResolveMechanismPivotLocal(
    const UStaticMesh& Mesh,
    const EInfinityMechanismKind Kind,
    const FTransform& BaseWorldTransform,
    const FVector& PairForwardWorld)
{
    if (Kind != EInfinityMechanismKind::Topple && Kind != EInfinityMechanismKind::Turn)
    {
        return FTransform::Identity;
    }

    const bool bTopple = Kind == EInfinityMechanismKind::Topple;
    const FName SocketName = bTopple ? TEXT("Hinge") : TEXT("Pivot");
    FVector PivotLocation = FVector::ZeroVector;
    FVector AxisLocal = FVector::XAxisVector;
    if (const UStaticMeshSocket* Socket = Mesh.FindSocket(SocketName))
    {
        PivotLocation = Socket->RelativeLocation;
        AxisLocal = Socket->RelativeRotation.Quaternion().GetAxisX().GetSafeNormal();
    }
    else
    {
        const FBox Bounds = Mesh.GetBoundingBox();
        PivotLocation = Bounds.GetCenter();
        if (bTopple)
        {
            PivotLocation.Z = Bounds.Min.Z;
            const FVector Extent = Bounds.GetExtent();
            const FVector BaseScale = BaseWorldTransform.GetScale3D().GetAbs();
            AxisLocal = Extent.X * BaseScale.X >= Extent.Y * BaseScale.Y
                ? FVector::XAxisVector
                : FVector::YAxisVector;
        }
        else
        {
            AxisLocal = FVector::ZAxisVector;
        }
    }

    // A positive Topple angle falls toward the camera (downstage), opposite the
    // pair frame's forward direction. Socket +X defines the hinge line, but the
    // asset contract intentionally does not require a direction along that line,
    // so cache the sign once here using the scaled axis.
    if (bTopple)
    {
        const FTransform RigidBase(
            BaseWorldTransform.GetRotation(),
            BaseWorldTransform.GetTranslation());
        const FVector AxisScaled = (AxisLocal * BaseWorldTransform.GetScale3D()).GetSafeNormal();
        const FVector AxisWorld = RigidBase.GetRotation().RotateVector(AxisScaled);
        const FVector UpWorld = RigidBase.GetRotation().GetUpVector();
        const double DownstageSign = FVector::DotProduct(
            FVector::CrossProduct(AxisWorld, UpWorld),
            -PairForwardWorld);
        if (FMath::Abs(DownstageSign) < 0.1)
        {
            // The reference cannot orient a hinge parallel to the route. Keep
            // the socket/fallback axis sign rather than choosing arbitrarily.
            static bool bWarnedDegenerateToppleAxis = false;
            if (!bWarnedDegenerateToppleAxis)
            {
                bWarnedDegenerateToppleAxis = true;
                UE_LOG(
                    LogInfinityStageMaterialization,
                    Warning,
                    TEXT("INFINITY_STAGE_TOPPLE_AXIS_SIGN_DEGENERATE mesh='%s' dot=%.3f; keeping hinge axis sign"),
                    *Mesh.GetPathName(),
                    DownstageSign);
            }
        }
        else if (DownstageSign < 0.0)
        {
            AxisLocal *= -1.0;
        }
    }
    return FTransform(AxisLocal.ToOrientationQuat(), PivotLocation);
}

double InterpolateFrame(
    const double FrameA,
    const double ValueA,
    const double FrameB,
    const double ValueB,
    const double TargetValue)
{
    if (FMath::IsNearlyEqual(ValueA, ValueB))
    {
        return FrameA;
    }
    return FMath::Lerp(FrameA, FrameB, FMath::Clamp((TargetValue - ValueA) / (ValueB - ValueA), 0.0, 1.0));
}

double FrameAtPassageDistance(const FInfinityCompiledPassage& Passage, const double TargetDistanceCm)
{
    if (TargetDistanceCm <= 0.0)
    {
        return Passage.SegmentStartFrame.Value;
    }
    if (TargetDistanceCm <= Passage.FirstPassDistanceCm)
    {
        return InterpolateFrame(
            Passage.SegmentStartFrame.Value, 0.0,
            Passage.FirstPassFrame.Value, Passage.FirstPassDistanceCm,
            TargetDistanceCm);
    }
    for (int32 WingIndex = 1; WingIndex < Passage.Wings.Num(); ++WingIndex)
    {
        const FInfinityCompiledWing& A = Passage.Wings[WingIndex - 1];
        const FInfinityCompiledWing& B = Passage.Wings[WingIndex];
        if (TargetDistanceCm <= B.DistanceCm)
        {
            return InterpolateFrame(
                A.PassFrame.Value, A.DistanceCm,
                B.PassFrame.Value, B.DistanceCm,
                TargetDistanceCm);
        }
    }
    return InterpolateFrame(
        Passage.LastPassFrame.Value, Passage.LastPassDistanceCm,
        Passage.SegmentEndFrame.Value, Passage.TotalDistanceCm,
        FMath::Min(TargetDistanceCm, Passage.TotalDistanceCm));
}

double FrameAtWingOrdinal(const FInfinityCompiledPassage& Passage, const double TargetOrdinal)
{
    if (Passage.Wings.IsEmpty() || TargetOrdinal < 0.0)
    {
        return Passage.SegmentStartFrame.Value;
    }
    const int32 LowerIndex = FMath::Clamp(FMath::FloorToInt(TargetOrdinal), 0, Passage.Wings.Num() - 1);
    const int32 UpperIndex = FMath::Min(LowerIndex + 1, Passage.Wings.Num() - 1);
    return FMath::Lerp(
        static_cast<double>(Passage.Wings[LowerIndex].PassFrame.Value),
        static_cast<double>(Passage.Wings[UpperIndex].PassFrame.Value),
        FMath::Clamp(TargetOrdinal - LowerIndex, 0.0, 1.0));
}

/** Continuous pair index at a physical camera distance. Irregular pair spacing is
 * respected, so the reveal is spatially attached to the actual camera rather than
 * to a second clock. */
double WingOrdinalAtPassageDistance(const FInfinityCompiledPassage& Passage, const double CameraDistanceCm)
{
    if (Passage.Wings.IsEmpty())
    {
        return -1.0;
    }
    if (Passage.Wings.Num() == 1)
    {
        return CameraDistanceCm >= Passage.Wings[0].DistanceCm ? 0.0 : -1.0;
    }

    if (CameraDistanceCm <= Passage.Wings[0].DistanceCm)
    {
        const double FirstGap = FMath::Max(
            1.0,
            Passage.Wings[1].DistanceCm - Passage.Wings[0].DistanceCm);
        return (CameraDistanceCm - Passage.Wings[0].DistanceCm) / FirstGap;
    }
    for (int32 Index = 1; Index < Passage.Wings.Num(); ++Index)
    {
        const FInfinityCompiledWing& A = Passage.Wings[Index - 1];
        const FInfinityCompiledWing& B = Passage.Wings[Index];
        if (CameraDistanceCm <= B.DistanceCm)
        {
            const double Gap = FMath::Max(1.0, B.DistanceCm - A.DistanceCm);
            return (Index - 1) + (CameraDistanceCm - A.DistanceCm) / Gap;
        }
    }

    const int32 LastIndex = Passage.Wings.Num() - 1;
    const double LastGap = FMath::Max(
        1.0,
        Passage.Wings[LastIndex].DistanceCm - Passage.Wings[LastIndex - 1].DistanceCm);
    return LastIndex + (CameraDistanceCm - Passage.Wings[LastIndex].DistanceCm) / LastGap;
}

/** The managed Master section owning this Passage's keyed camera/Wing channels. */
const UMovieSceneInfinityPassageSection* FindPassageSection(
    const UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid)
{
    ULevelSequence* MasterSequence = Show.ManagedMasterSequence.LoadSynchronous();
    UMovieScene* MovieScene = MasterSequence ? MasterSequence->GetMovieScene() : nullptr;
    UMovieSceneInfinityPassageTrack* Track = MovieScene
        ? MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>()
        : nullptr;
    if (!Track)
    {
        return nullptr;
    }
    for (const UMovieSceneSection* RawSection : Track->GetAllSections())
    {
        const UMovieSceneInfinityPassageSection* Section =
            Cast<UMovieSceneInfinityPassageSection>(RawSection);
        if (Section && Section->PassageGuid == PassageGuid)
        {
            return Section;
        }
    }
    return nullptr;
}

struct FCameraGustTiming
{
    double GroupTriggerFrame = 0.0;
    double EffectiveOpeningSeconds = 0.45;
    double EffectiveStaggerSeconds = 0.10;
};

FCameraGustTiming ResolveCameraGustTiming(
    const UInfinityStageShowAsset& Show,
    const FInfinityCompiledPassage& Passage,
    const FInfinityCameraGustSettings& Gust)
{
    FCameraGustTiming Result;
    const int32 AnchorIndex = Passage.Wings.IndexOfByPredicate([&Gust](const FInfinityCompiledWing& Wing)
    {
        return Wing.CueGuid == Gust.GroupAnchorCueGuid;
    });
    if (!Passage.Wings.IsValidIndex(AnchorIndex))
    {
        Result.GroupTriggerFrame = Passage.SegmentStartFrame.Value;
        return Result;
    }

    const FInfinityCompiledWing& Anchor = Passage.Wings[AnchorIndex];
    if (Gust.TriggerOffsetUnit == EInfinityCameraGustTriggerOffsetUnit::Pairs)
    {
        Result.GroupTriggerFrame = FrameAtWingOrdinal(Passage, AnchorIndex - FMath::Max(0.0, Gust.TriggerOffset));
    }
    else if (Gust.TriggerOffsetUnit == EInfinityCameraGustTriggerOffsetUnit::Metres)
    {
        Result.GroupTriggerFrame = FrameAtPassageDistance(
            Passage,
            Anchor.DistanceCm - FMath::Max(0.0, Gust.TriggerOffset) * 100.0);
    }
    else
    {
        Result.GroupTriggerFrame = Anchor.PassFrame.Value
            - FMath::Max(0.0, Gust.TriggerOffset) * Show.TickResolution.AsDecimal();
    }
    Result.GroupTriggerFrame = FMath::Clamp(
        Result.GroupTriggerFrame,
        static_cast<double>(Passage.SegmentStartFrame.Value),
        static_cast<double>(Passage.SegmentEndFrame.Value));

    const double CascadeSeconds = FMath::Max(0.01, Gust.CascadeDurationSeconds);
    Result.EffectiveOpeningSeconds = FMath::Min(
        FMath::Max(0.01, Gust.PairOpeningDurationSeconds),
        CascadeSeconds);
    const int32 DelayCount = FMath::Max(0, Gust.GroupSize - 1);
    const double MaximumStagger = DelayCount > 0
        ? FMath::Max(0.0, CascadeSeconds - Result.EffectiveOpeningSeconds) / DelayCount
        : 0.0;
    Result.EffectiveStaggerSeconds = DelayCount > 0
        ? FMath::Min(FMath::Max(0.0, Gust.PairStaggerSeconds), MaximumStagger)
        : 0.0;
    return Result;
}

ELightUnits ResolveLightUnits(const EInfinityStageLightIntensityUnits Units)
{
    switch (Units)
    {
    case EInfinityStageLightIntensityUnits::Unitless:
        return ELightUnits::Unitless;
    case EInfinityStageLightIntensityUnits::Candelas:
        return ELightUnits::Candelas;
    case EInfinityStageLightIntensityUnits::EV:
        return ELightUnits::EV;
    case EInfinityStageLightIntensityUnits::Nits:
        return ELightUnits::Nits;
    case EInfinityStageLightIntensityUnits::Lumens:
    default:
        return ELightUnits::Lumens;
    }
}

UClass* ResolveNativeLightClass(const EInfinityStageLightType Type)
{
    switch (Type)
    {
    case EInfinityStageLightType::Rect:
        return ARectLight::StaticClass();
    case EInfinityStageLightType::Point:
        return APointLight::StaticClass();
    case EInfinityStageLightType::Spot:
    default:
        return ASpotLight::StaticClass();
    }
}

bool ApplyAttachmentLightSettings(AActor& Actor, const FInfinityStageLightSettings& Settings)
{
    ULightComponent* Light = Actor.FindComponentByClass<ULightComponent>();
    if (!Light)
    {
        return false;
    }

    Light->SetIntensity(FMath::Max(0.0f, Settings.Intensity));
    Light->SetLightColor(Settings.Color, false);
    Light->SetUseTemperature(Settings.bUseTemperature);
    Light->SetTemperature(FMath::Clamp(Settings.TemperatureKelvin, 1000.0f, 15000.0f));
    Light->SetIndirectLightingIntensity(FMath::Max(0.0f, Settings.IndirectLightingIntensity));
    Light->SetVolumetricScatteringIntensity(FMath::Max(0.0f, Settings.VolumetricScatteringIntensity));
    Light->SetDiffuseScale(FMath::Max(0.0f, Settings.DiffuseScale));
    Light->SetSpecularScale(FMath::Max(0.0f, Settings.SpecularScale));
    Light->SetAffectTranslucentLighting(Settings.bAffectTranslucentLighting);
    Light->SetTransmission(Settings.bTransmission);
    Light->SetCastShadows(Settings.bCastShadows);
    Light->SetCastVolumetricShadow(Settings.bCastVolumetricShadow);
    Light->SetAffectReflection(Settings.bAffectReflection);
    Light->SetAffectGlobalIllumination(Settings.bAffectGlobalIllumination);
    Light->SetShadowBias(FMath::Clamp(Settings.ShadowBias, 0.0f, 1.0f));
    Light->SetShadowSlopeBias(FMath::Clamp(Settings.ShadowSlopeBias, 0.0f, 1.0f));
    Light->SetForceCachedShadowsForMovablePrimitives(Settings.bForceCachedShadowsForMovablePrimitives);
    Light->SetUseRayTracedDistanceFieldShadows(Settings.bUseRayTracedDistanceFieldShadows);
    Light->SetLightingChannels(
        Settings.bLightingChannel0,
        Settings.bLightingChannel1,
        Settings.bLightingChannel2);
    Light->SetMaxDrawDistance(FMath::Max(0.0f, Settings.MaxDrawDistanceCm));
    Light->SetMaxDistanceFadeRange(FMath::Max(0.0f, Settings.MaxDistanceFadeRangeCm));
    Light->SetLightFunctionMaterial(Settings.LightFunctionMaterial.LoadSynchronous());
    Light->SetLightFunctionScale(Settings.LightFunctionScale);
    Light->SetLightFunctionFadeDistance(FMath::Max(0.0f, Settings.LightFunctionFadeDistanceCm));
    Light->SetLightFunctionDisabledBrightness(FMath::Max(0.0f, Settings.LightFunctionDisabledBrightness));
    Light->SetIESTexture(Settings.IESTexture.LoadSynchronous());
    Light->SetUseIESBrightness(Settings.bUseIESBrightness);
    Light->SetIESBrightnessScale(FMath::Max(0.0f, Settings.IESBrightnessScale));

    if (ULocalLightComponent* Local = Cast<ULocalLightComponent>(Light))
    {
        Local->SetAttenuationRadius(FMath::Max(0.0f, Settings.AttenuationRadiusCm));
        Local->SetIntensityUnits(ResolveLightUnits(Settings.IntensityUnits));
    }
    if (UPointLightComponent* Point = Cast<UPointLightComponent>(Light))
    {
        Point->SetUseInverseSquaredFalloff(Settings.bUseInverseSquaredFalloff);
        Point->SetLightFalloffExponent(FMath::Clamp(Settings.LightFalloffExponent, 2.0f, 16.0f));
        Point->SetInverseExposureBlend(FMath::Clamp(Settings.InverseExposureBlend, 0.0f, 1.0f));
        Point->SetSourceRadius(FMath::Max(0.0f, Settings.SourceRadiusCm));
        Point->SetSoftSourceRadius(FMath::Max(0.0f, Settings.SoftSourceRadiusCm));
        Point->SetSourceLength(FMath::Max(0.0f, Settings.SourceLengthCm));
    }
    if (USpotLightComponent* Spot = Cast<USpotLightComponent>(Light))
    {
        const float OuterAngle = FMath::Clamp(Settings.OuterConeAngleDegrees, 1.0f, 89.0f);
        Spot->SetOuterConeAngle(OuterAngle);
        Spot->SetInnerConeAngle(FMath::Clamp(Settings.InnerConeAngleDegrees, 0.0f, OuterAngle));
    }
    if (URectLightComponent* Rect = Cast<URectLightComponent>(Light))
    {
        Rect->SetSourceWidth(FMath::Max(0.1f, Settings.RectSourceWidthCm));
        Rect->SetSourceHeight(FMath::Max(0.1f, Settings.RectSourceHeightCm));
        Rect->SetBarnDoorAngle(FMath::Clamp(Settings.RectBarnDoorAngleDegrees, 0.0f, 90.0f));
        Rect->SetBarnDoorLength(FMath::Max(0.0f, Settings.RectBarnDoorLengthCm));
        Rect->SetSourceTexture(Settings.RectSourceTexture.LoadSynchronous());
    }
    return true;
}
}

bool AInfinityStagePassageActor::CaptureAttachmentLightSettings(
    const AActor& Actor,
    FInfinityStageLightSettings& OutSettings)
{
    const ULightComponent* Light = Actor.FindComponentByClass<ULightComponent>();
    if (!Light)
    {
        return false;
    }
    // Only fields the apply path writes are read back, so a capture followed by
    // a materialize is a round trip and nothing the Show never owned leaks in.
    OutSettings.Intensity = Light->Intensity;
    OutSettings.Color = Light->GetLightColor();
    OutSettings.bUseTemperature = Light->bUseTemperature != 0;
    OutSettings.TemperatureKelvin = Light->Temperature;
    OutSettings.IndirectLightingIntensity = Light->IndirectLightingIntensity;
    OutSettings.VolumetricScatteringIntensity = Light->VolumetricScatteringIntensity;
    OutSettings.DiffuseScale = Light->DiffuseScale;
    OutSettings.SpecularScale = Light->SpecularScale;
    OutSettings.bAffectTranslucentLighting = Light->bAffectTranslucentLighting != 0;
    OutSettings.bTransmission = Light->bTransmission != 0;
    OutSettings.bCastShadows = Light->CastShadows != 0;
    OutSettings.bCastVolumetricShadow = Light->bCastVolumetricShadow != 0;
    OutSettings.bAffectReflection = Light->bAffectReflection != 0;
    OutSettings.bAffectGlobalIllumination = Light->bAffectGlobalIllumination != 0;
    OutSettings.ShadowBias = Light->ShadowBias;
    OutSettings.ShadowSlopeBias = Light->ShadowSlopeBias;
    OutSettings.bForceCachedShadowsForMovablePrimitives = Light->bForceCachedShadowsForMovablePrimitives != 0;
    OutSettings.bUseRayTracedDistanceFieldShadows = Light->bUseRayTracedDistanceFieldShadows != 0;
    OutSettings.bLightingChannel0 = Light->LightingChannels.bChannel0 != 0;
    OutSettings.bLightingChannel1 = Light->LightingChannels.bChannel1 != 0;
    OutSettings.bLightingChannel2 = Light->LightingChannels.bChannel2 != 0;
    OutSettings.MaxDrawDistanceCm = Light->MaxDrawDistance;
    OutSettings.MaxDistanceFadeRangeCm = Light->MaxDistanceFadeRange;
    OutSettings.LightFunctionMaterial = Light->LightFunctionMaterial;
    OutSettings.LightFunctionScale = Light->LightFunctionScale;
    OutSettings.LightFunctionFadeDistanceCm = Light->LightFunctionFadeDistance;
    OutSettings.LightFunctionDisabledBrightness = Light->DisabledBrightness;
    OutSettings.IESTexture = Light->IESTexture;
    OutSettings.bUseIESBrightness = Light->bUseIESBrightness != 0;
    OutSettings.IESBrightnessScale = Light->IESBrightnessScale;

    if (const ULocalLightComponent* Local = Cast<ULocalLightComponent>(Light))
    {
        OutSettings.AttenuationRadiusCm = Local->AttenuationRadius;
        switch (Local->IntensityUnits)
        {
        case ELightUnits::Unitless: OutSettings.IntensityUnits = EInfinityStageLightIntensityUnits::Unitless; break;
        case ELightUnits::Candelas: OutSettings.IntensityUnits = EInfinityStageLightIntensityUnits::Candelas; break;
        case ELightUnits::EV: OutSettings.IntensityUnits = EInfinityStageLightIntensityUnits::EV; break;
        case ELightUnits::Nits: OutSettings.IntensityUnits = EInfinityStageLightIntensityUnits::Nits; break;
        default: OutSettings.IntensityUnits = EInfinityStageLightIntensityUnits::Lumens; break;
        }
        OutSettings.InverseExposureBlend = Local->InverseExposureBlend;
    }
    if (const UPointLightComponent* Point = Cast<UPointLightComponent>(Light))
    {
        OutSettings.bUseInverseSquaredFalloff = Point->bUseInverseSquaredFalloff != 0;
        OutSettings.LightFalloffExponent = Point->LightFalloffExponent;
        OutSettings.SourceRadiusCm = Point->SourceRadius;
        OutSettings.SoftSourceRadiusCm = Point->SoftSourceRadius;
        OutSettings.SourceLengthCm = Point->SourceLength;
    }
    if (const USpotLightComponent* Spot = Cast<USpotLightComponent>(Light))
    {
        OutSettings.InnerConeAngleDegrees = Spot->InnerConeAngle;
        OutSettings.OuterConeAngleDegrees = Spot->OuterConeAngle;
    }
    if (const URectLightComponent* Rect = Cast<URectLightComponent>(Light))
    {
        OutSettings.RectSourceWidthCm = Rect->SourceWidth;
        OutSettings.RectSourceHeightCm = Rect->SourceHeight;
        OutSettings.RectBarnDoorAngleDegrees = Rect->BarnDoorAngle;
        OutSettings.RectBarnDoorLengthCm = Rect->BarnDoorLength;
        OutSettings.RectSourceTexture = Rect->SourceTexture;
    }
    return true;
}

AInfinityStagePassageActor::AInfinityStagePassageActor()
{
    PrimaryActorTick.bCanEverTick = false;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);

    Route = CreateDefaultSubobject<USplineComponent>(TEXT("Route"));
    Route->SetupAttachment(SceneRoot);
}

void AInfinityStagePassageActor::ClearMaterializedPassage()
{
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        UE_LOG(LogInfinityStageMaterialization, Warning, TEXT("Refusing to clear fixed passage content in a game world."));
        return;
    }

    Modify();

    // ManagedComponents is the normal ownership record, but editor undo,
    // reinstancing or an older serialized actor can leave an owned generated
    // component alive after that array loses its reference. Recover those
    // components by the tag AddPanelInstance assigns to every generated ISM.
    // Without this fallback, the next materialize creates a tracked moving set
    // on top of an untracked stationary set.
    TSet<UInstancedStaticMeshComponent*> ComponentsToDestroy;
    for (UInstancedStaticMeshComponent* Component : ManagedComponents)
    {
        if (IsValid(Component))
        {
            ComponentsToDestroy.Add(Component);
        }
    }
    const int32 ReferencedComponentCount = ComponentsToDestroy.Num();
    TInlineComponentArray<UInstancedStaticMeshComponent*> OwnedInstanceComponents(this);
    for (UInstancedStaticMeshComponent* Component : OwnedInstanceComponents)
    {
        if (IsValid(Component) && Component->ComponentTags.Contains(TEXT("InfinityStage.Managed")))
        {
            ComponentsToDestroy.Add(Component);
        }
    }
    const int32 RecoveredOrphanCount = ComponentsToDestroy.Num() - ReferencedComponentCount;
    if (RecoveredOrphanCount > 0)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_ORPHAN_COMPONENTS_RECOVERED actor='%s' components=%d"),
            *GetActorLabel(),
            RecoveredOrphanCount);
    }

    for (UInstancedStaticMeshComponent* Component : ComponentsToDestroy)
    {
        if (IsValid(Component))
        {
            Component->Modify();
            RemoveInstanceComponent(Component);
            Component->DestroyComponent();
        }
    }
    TSet<AActor*> AttachmentActorsToDestroy;
    for (AActor* Attachment : ManagedAttachmentActors)
    {
        if (IsValid(Attachment))
        {
            AttachmentActorsToDestroy.Add(Attachment);
        }
    }
    const int32 ReferencedAttachmentActorCount = AttachmentActorsToDestroy.Num();
    // Older saves and editor undo can leave generated attachment actors parented
    // to the Passage after the ownership array loses its reference. Recover them
    // by the same stable identity tag used for transform/deletion write-back.
    AddAttachedGeneratedActors(*this, AttachmentActorsToDestroy);
    const int32 RecoveredAttachmentActorCount =
        AttachmentActorsToDestroy.Num() - ReferencedAttachmentActorCount;
    if (RecoveredAttachmentActorCount > 0)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_ORPHAN_ATTACHMENTS_RECOVERED actor='%s' actors=%d phase=clear"),
            *GetActorLabel(),
            RecoveredAttachmentActorCount);
    }
    for (AActor* Attachment : AttachmentActorsToDestroy)
    {
        // Editor deletion of a tagged generated light is an authoring gesture:
        // the editor module removes that attachment from the Show. Clearing or
        // rebuilding a Passage is only internal lifecycle work, so strip the
        // identity before destroying managed actors here.
        RemoveAttachmentIdentityTags(*Attachment);
        Attachment->Destroy();
    }
    ManagedAttachmentActors.Reset();
    ManagedComponents.Reset();
    MaterializedPanels.Reset();
    MaterializedWingPairCount = 0;
    MarkPackageDirty();
}

bool AInfinityStagePassageActor::MaterializePassage()
{
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        UE_LOG(LogInfinityStageMaterialization, Error, TEXT("MaterializePassage is editor authoring only; fixed stage content must exist before PIE."));
        return false;
    }
    if (!ShowAsset)
    {
        UE_LOG(LogInfinityStageMaterialization, Error, TEXT("Passage Actor has no Show Asset."));
        return false;
    }

    ShowAsset->EnsureStableIds();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    if (Compiled.HasErrors() || Compiled.Passages.IsEmpty())
    {
        UE_LOG(LogInfinityStageMaterialization, Error, TEXT("Show does not compile into a valid Passage."));
        return false;
    }

    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([this](const FInfinityCompiledPassage& Candidate)
    {
        return PassageGuid.IsValid() && Candidate.PassageGuid == PassageGuid;
    });
    if (!Passage)
    {
        Passage = &Compiled.Passages[0];
        PassageGuid = Passage->PassageGuid;
    }

    // Validate the entire replacement before removing the currently visible stage. In
    // particular, an artist choosing one new mesh can introduce one new render key; a
    // budget error must leave the last valid materialization intact.
    TSet<FString> RequiredRenderKeys;
    for (const FInfinityCompiledWing& CompiledWing : Passage->Wings)
    {
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CompiledWing.CueGuid);
        if (!Cue)
        {
            UE_LOG(LogInfinityStageMaterialization, Error, TEXT("Compiled Cue no longer exists; keeping the previous materialization."));
            return false;
        }
        const FInfinityWingOccurrence& Wing = Cue->WingPair;
        if (!Wing.Left.Mesh.IsNull()) RequiredRenderKeys.Add(MakeRenderKey(Wing.Left));
        if (!Wing.Right.Mesh.IsNull()) RequiredRenderKeys.Add(MakeRenderKey(Wing.Right));
        if (Wing.bHasTop && !Wing.Top.Mesh.IsNull()) RequiredRenderKeys.Add(MakeRenderKey(Wing.Top));
    }
    if (RequiredRenderKeys.Num() > ComponentBudget)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Error,
            TEXT("Passage needs %d render components but its budget is %d; keeping the previous materialization."),
            RequiredRenderKeys.Num(),
            ComponentBudget);
        return false;
    }
    if (!bAutoFitStraightRoute && Route->GetSplineLength() + UE_KINDA_SMALL_NUMBER < Passage->TotalDistanceCm)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Error,
            TEXT("Route is %.1f cm long but Passage requires %.1f cm; keeping the previous materialization."),
            Route->GetSplineLength(),
            Passage->TotalDistanceCm);
        return false;
    }

    ClearMaterializedPassage();
    Modify();

    if (bAutoFitStraightRoute)
    {
        // Auto Fit replaces the spline outright. A route with extra points or a
        // curved point type was shaped by hand, so say so loudly rather than
        // discarding it silently; scripted materialization never sees the
        // Details-panel route workflow.
        const int32 RoutePointCount = Route->GetNumberOfSplinePoints();
        bool bRouteWasShaped = RoutePointCount > 2;
        for (int32 PointIndex = 0; !bRouteWasShaped && PointIndex < RoutePointCount; ++PointIndex)
        {
            // A default or previously auto-fitted route lies on the local +X
            // axis, so lateral or vertical displacement is authored shape. The
            // spline point type is not a usable signal here: a freshly
            // constructed USplineComponent defaults to curve-type points, which
            // would make this warn on every untouched Passage.
            const FVector Location = Route->GetLocationAtSplinePoint(
                PointIndex,
                ESplineCoordinateSpace::Local);
            bRouteWasShaped = FMath::Abs(Location.Y) > 1.0 || FMath::Abs(Location.Z) > 1.0;
        }
        if (bRouteWasShaped)
        {
            UE_LOG(
                LogInfinityStageMaterialization,
                Warning,
                TEXT("INFINITY_STAGE_ROUTE_AUTOFIT_OVERWRITE actor='%s' passage=%s points=%d; ")
                TEXT("Auto Fit Straight Route replaced a hand-authored route. Disable Auto Fit ")
                TEXT("(Details > Route > Edit Route) before materializing to keep the curve."),
                *GetActorLabel(),
                *PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
                RoutePointCount);
        }

        Route->Modify();
        Route->ClearSplinePoints(false);
        Route->AddSplinePoint(FVector::ZeroVector, ESplineCoordinateSpace::Local, false);
        Route->AddSplinePoint(FVector(Passage->TotalDistanceCm, 0.0, 0.0), ESplineCoordinateSpace::Local, false);
        Route->SetSplinePointType(0, ESplinePointType::Linear, false);
        Route->SetSplinePointType(1, ESplinePointType::Linear, false);
        Route->UpdateSpline();
    }
    TMap<FString, UInstancedStaticMeshComponent*> ComponentsByKey;
    FString Error;
    for (const FInfinityCompiledWing& CompiledWing : Passage->Wings)
    {
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CompiledWing.CueGuid);
        if (!Cue)
        {
            UE_LOG(LogInfinityStageMaterialization, Error, TEXT("Compiled Cue no longer exists."));
            ClearMaterializedPassage();
            return false;
        }

        const FTransform StationTransform = Route->GetTransformAtDistanceAlongSpline(
            CompiledWing.DistanceCm,
            ESplineCoordinateSpace::World,
            true);
        const FInfinityWingOccurrence& Wing = Cue->WingPair;
        if (!AddPanelInstance(Cue->CueGuid, EInfinityPanelSide::Left, Wing.Left, Wing.OccurrenceOffset, StationTransform, ComponentsByKey, Error)
            || !AddPanelInstance(Cue->CueGuid, EInfinityPanelSide::Right, Wing.Right, Wing.OccurrenceOffset, StationTransform, ComponentsByKey, Error)
            || (Wing.bHasTop && !AddPanelInstance(Cue->CueGuid, EInfinityPanelSide::Top, Wing.Top, Wing.OccurrenceOffset, StationTransform, ComponentsByKey, Error)))
        {
            UE_LOG(LogInfinityStageMaterialization, Error, TEXT("%s"), *Error);
            ClearMaterializedPassage();
            return false;
        }
        ++MaterializedWingPairCount;
    }

    // Attachments are placed after the panels exist, because panel and
    // pair-centre anchors read live instance transforms.
    MaterializeAttachments();

    MarkPackageDirty();
    return true;
}

int32 AInfinityStagePassageActor::MaterializeAttachments()
{
    UWorld* World = GetWorld();
    if (!World || !ShowAsset)
    {
        return 0;
    }
    TSet<AActor*> AttachmentActorsToDestroy;
    for (AActor* Existing : ManagedAttachmentActors)
    {
        if (IsValid(Existing))
        {
            AttachmentActorsToDestroy.Add(Existing);
        }
    }
    const int32 ReferencedAttachmentActorCount = AttachmentActorsToDestroy.Num();
    AddAttachedGeneratedActors(*this, AttachmentActorsToDestroy);
    const int32 RecoveredAttachmentActorCount =
        AttachmentActorsToDestroy.Num() - ReferencedAttachmentActorCount;
    if (RecoveredAttachmentActorCount > 0)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_ORPHAN_ATTACHMENTS_RECOVERED actor='%s' actors=%d phase=materialize"),
            *GetActorLabel(),
            RecoveredAttachmentActorCount);
    }
    for (AActor* Existing : AttachmentActorsToDestroy)
    {
        RemoveAttachmentIdentityTags(*Existing);
        Existing->Destroy();
    }
    ManagedAttachmentActors.Reset();
    BulbBodies.Reset();

    int32 Placed = 0;
    int32 PlacedLights = 0;
    int32 Skipped = 0;
    for (const FInfinityShowCue& Cue : ShowAsset->Cues)
    {
        if (Cue.Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        for (const FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
        {
            if (!Attachment.bEnabled)
            {
                continue;
            }
            FTransform WorldTransform;
            if (!GetAttachmentWorldTransform(Cue.CueGuid, Attachment.AttachmentGuid, WorldTransform))
            {
                continue;
            }

            UClass* SpawnClass = Attachment.ActorClass.LoadSynchronous();
            if (!SpawnClass && Attachment.Kind == EInfinityAttachmentKind::Light)
            {
                SpawnClass = ResolveNativeLightClass(Attachment.Lighting.Type);
            }
            if (!SpawnClass && Attachment.Kind == EInfinityAttachmentKind::Effect)
            {
                SpawnClass = AInfinityStageEffectSource::ResolveDefaultClass(Attachment.Effect);
            }
            if (!SpawnClass)
            {
                // A mesh-only prop needs no Blueprint; anything else with no
                // class is simply not placeable yet, which is not an error.
                if (Attachment.Mesh.IsNull())
                {
                    continue;
                }
                SpawnClass = AStaticMeshActor::StaticClass();
            }

            FActorSpawnParameters Params;
            Params.ObjectFlags |= RF_Transactional;
            AActor* Spawned = World->SpawnActor<AActor>(SpawnClass, WorldTransform, Params);
            if (!Spawned)
            {
                // A broken reference must warn and skip, never block the
                // materialize, exactly as a too-short route now warns.
                ++Skipped;
                UE_LOG(
                    LogInfinityStageMaterialization,
                    Warning,
                    TEXT("INFINITY_STAGE_ATTACHMENT_SKIPPED cue=%s attachment=%s; could not spawn."),
                    *Cue.CueGuid.ToString(EGuidFormats::DigitsWithHyphens),
                    *Attachment.AttachmentGuid.ToString(EGuidFormats::DigitsWithHyphens));
                continue;
            }
            if (AStaticMeshActor* MeshActor = Cast<AStaticMeshActor>(Spawned))
            {
                if (UStaticMesh* Mesh = Attachment.Mesh.LoadSynchronous())
                {
                    MeshActor->GetStaticMeshComponent()->SetStaticMesh(Mesh);
                }
            }
#if WITH_EDITOR
            Spawned->SetActorLabel(Attachment.Label.IsEmpty()
                ? FString::Printf(TEXT("Attachment %s"), *Attachment.AttachmentGuid.ToString(EGuidFormats::Digits).Left(8))
                : Attachment.Label.ToString());
#endif
            // Attached so ordinary level editing of the Passage moves its content
            // with it, while materialization remains the owner.
            // Identity by tag, not by spawn order: a duplicated or reordered
            // actor must never end up writing another attachment's offset.
            Spawned->Tags.Add(FName(*FString::Printf(
                TEXT("InfinityStage.Attachment.%s|%s"),
                *Cue.CueGuid.ToString(EGuidFormats::Digits),
                *Attachment.AttachmentGuid.ToString(EGuidFormats::Digits))));
            // Spawned actors default to Static mobility, which cannot attach to
            // this actor's movable root — the attach silently aborts and the
            // attachment is left loose in the world. Make it movable first.
            if (USceneComponent* SpawnedRoot = Spawned->GetRootComponent())
            {
                SpawnedRoot->SetMobility(EComponentMobility::Movable);
            }
            // SpawnActor composes the spawn transform with the class default root
            // transform. ASpotLight's root is authored pitched -90 (pointing down),
            // so a spot would materialize 90 degrees off its authored offset and
            // could never round-trip through the actor-move write-back. Set the
            // authored world transform explicitly so the Show is the only authority.
            Spawned->SetActorTransform(WorldTransform, false, nullptr, ETeleportType::TeleportPhysics);
            Spawned->AttachToActor(this, FAttachmentTransformRules::KeepWorldTransform);
            // Native light actors reconstruct some type-specific defaults while
            // their movable root is parented. Apply the Show-owned settings only
            // after parenting so cone, radius and source shape remain authoritative.
            if (Attachment.Kind == EInfinityAttachmentKind::Effect)
            {
                AInfinityStageEffectSource::ApplyAttachment(*Spawned, Cue.CueGuid, Attachment);
            }
            if (Attachment.Kind == EInfinityAttachmentKind::Light)
            {
                if (!ApplyAttachmentLightSettings(*Spawned, Attachment.Lighting))
                {
                    ++Skipped;
                    UE_LOG(
                        LogInfinityStageMaterialization,
                        Warning,
                        TEXT("INFINITY_STAGE_LIGHT_ATTACHMENT_SKIPPED cue=%s attachment=%s; actor has no Light Component."),
                        *Cue.CueGuid.ToString(EGuidFormats::DigitsWithHyphens),
                        *Attachment.AttachmentGuid.ToString(EGuidFormats::DigitsWithHyphens));
                    RemoveAttachmentIdentityTags(*Spawned);
                    Spawned->Destroy();
                    continue;
                }
                ++PlacedLights;
            }
            ManagedAttachmentActors.Add(Spawned);
            ++Placed;
        }
    }

    if (Placed > 0 || Skipped > 0)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_ATTACHMENTS_OK actor='%s' placed=%d skipped=%d"),
            *GetActorLabel(),
            Placed,
            Skipped);
    }
    if (PlacedLights > 0)
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_LIGHTS_MATERIALIZED actor='%s' lights=%d"),
            *GetActorLabel(),
            PlacedLights);
    }
    return Placed;
}

void AInfinityStagePassageActor::MaterializePassageInEditor()
{
    if (MaterializePassage())
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Display,
            TEXT("INFINITY_STAGE_MATERIALIZE_OK actor='%s' passage=%s wing_pairs=%d"),
            *GetActorLabel(),
            *PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
            MaterializedWingPairCount);
    }
    else
    {
        UE_LOG(
            LogInfinityStageMaterialization,
            Error,
            TEXT("Infinity Stage Materialize Passage editor action failed for '%s'; the previous valid materialization was retained when possible."),
            *GetActorLabel());
    }
}

bool AInfinityStagePassageActor::AddPanelInstance(
    const FGuid& CueGuid,
    const EInfinityPanelSide Side,
    const FInfinityPanelDesign& Panel,
    const FTransform& OccurrenceOffset,
    const FTransform& StationTransform,
    TMap<FString, UInstancedStaticMeshComponent*>& ComponentsByKey,
    FString& OutError)
{
    UStaticMesh* Mesh = Panel.Mesh.LoadSynchronous();
    if (!Mesh)
    {
        return true;
    }

    const FString RenderKey = MakeRenderKey(Panel);
    UInstancedStaticMeshComponent*& Component = ComponentsByKey.FindOrAdd(RenderKey);
    if (!Component)
    {
        if (ManagedComponents.Num() >= ComponentBudget)
        {
            OutError = FString::Printf(TEXT("Component budget %d exceeded; reduce unique render keys or raise the explicit budget."), ComponentBudget);
            return false;
        }

        const FName ComponentName = MakeUniqueObjectName(
            this,
            UInstancedStaticMeshComponent::StaticClass(),
            *FString::Printf(TEXT("InfinityManaged_%08X"), GetTypeHash(RenderKey)));
        Component = NewObject<UInstancedStaticMeshComponent>(this, ComponentName, RF_Transactional);
        Component->CreationMethod = EComponentCreationMethod::Instance;
        Component->ComponentTags.Add(TEXT("InfinityStage.Managed"));
        Component->SetupAttachment(SceneRoot);
        Component->SetStaticMesh(Mesh);
        Component->SetMobility(EComponentMobility::Movable);
        // Mechanism-driven ISM motion needs an explicit previous transform for
        // temporal AA, Lumen reflections and motion blur. Existing serialized
        // components are also enabled defensively in the evaluation path.
        Component->SetHasPerInstancePrevTransforms(true);
        // Per-instance floats the wing material and Wing Burn effects read.
        // Reserved before the first instance is added, because widening the
        // stride afterwards discards values already written.
        Component->SetNumCustomDataFloats(InfinityStageWingCustomData::NumFloats);
        Component->SetCastShadow(Panel.bCastShadow);
        Component->SetVisibility(true, true);
        Component->SetRenderInMainPass(Panel.bVisibleInMainPass);
        Component->SetCollisionEnabled(Panel.Collision);
        for (int32 MaterialIndex = 0; MaterialIndex < Panel.MaterialOverrides.Num(); ++MaterialIndex)
        {
            if (UMaterialInterface* Material = Panel.MaterialOverrides[MaterialIndex].LoadSynchronous())
            {
                Component->SetMaterial(MaterialIndex, Material);
            }
        }
        AddInstanceComponent(Component);
        Component->RegisterComponent();
        ManagedComponents.Add(Component);
    }

    const FTransform FacingTransform = ResolvePanelFacing(*ShowAsset, Panel, Side);
    const FTransform ImageTransform = Panel.bFlipImageHorizontally
        ? FTransform(FQuat::Identity, FVector::ZeroVector, FVector(1.0, -1.0, 1.0))
        : FTransform::Identity;
    const FTransform WorldTransform = ImageTransform * FacingTransform
        * Panel.LocalTransform * OccurrenceOffset * StationTransform;
    const int32 InstanceIndex = Component->AddInstance(WorldTransform, true);
    // Deterministic variation seed from cue + side, so the same wing carries the
    // same tint and wear at every performance. PerInstanceRandom is not stable
    // across a rebuild, and this show is performed repeatedly.
    if (Component->NumCustomDataFloats > InfinityStageWingCustomData::VariationSeed)
    {
        const uint32 SeedHash = HashCombine(GetTypeHash(CueGuid), GetTypeHash(static_cast<uint8>(Side)));
        Component->SetCustomDataValue(
            InstanceIndex,
            InfinityStageWingCustomData::VariationSeed,
            static_cast<float>(SeedHash % 100000u) / 100000.0f,
            false);
    }
    FInfinityMaterializedPanelRef& Ref = MaterializedPanels.AddDefaulted_GetRef();
    Ref.CueGuid = CueGuid;
    Ref.Side = Side;
    Ref.Component = Component;
    Ref.InstanceIndex = InstanceIndex;
    Ref.BaseWorldTransform = WorldTransform;
    const FTransform PairWorldTransform = OccurrenceOffset * StationTransform;
    Ref.InwardWorldDirection = PairWorldTransform.GetRotation()
        .RotateVector(GetPairLocalInwardDirection(Side))
        .GetSafeNormal();
    const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CueGuid);
    const EInfinityMechanismKind MechanismKind = ResolveMechanismKindForSide(
        Cue ? Cue->WingPair.Mechanism.Kind : EInfinityMechanismKind::Slide,
        Side);
    Ref.MechanismPivotLocal = ResolveMechanismPivotLocal(
        *Mesh,
        MechanismKind,
        WorldTransform,
        PairWorldTransform.GetRotation().GetForwardVector().GetSafeNormal());
    return true;
}

bool AInfinityStagePassageActor::GetRouteLengthStatus(
    double& OutRequiredCm,
    double& OutCurrentCm) const
{
    OutRequiredCm = 0.0;
    OutCurrentCm = Route ? Route->GetSplineLength() : 0.0;
    if (!ShowAsset || !Route)
    {
        return false;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
        [this](const FInfinityCompiledPassage& Candidate)
        {
            return PassageGuid.IsValid() && Candidate.PassageGuid == PassageGuid;
        });
    if (!Passage)
    {
        return false;
    }
    OutRequiredCm = Passage->TotalDistanceCm;
    return true;
}

bool AInfinityStagePassageActor::ExtendRouteToCompiledLength()
{
    double RequiredCm = 0.0;
    double CurrentCm = 0.0;
    if (!GetRouteLengthStatus(RequiredCm, CurrentCm)
        || RequiredCm <= 0.0
        || CurrentCm + UE_KINDA_SMALL_NUMBER >= RequiredCm)
    {
        return false;
    }

    const int32 LastIndex = Route->GetNumberOfSplinePoints() - 1;
    if (LastIndex < 0)
    {
        return false;
    }

    const FVector LastLocation = Route->GetLocationAtSplinePoint(LastIndex, ESplineCoordinateSpace::Local);
    FVector Direction = Route->GetTangentAtSplinePoint(LastIndex, ESplineCoordinateSpace::Local).GetSafeNormal();
    if (Direction.IsNearlyZero() && LastIndex > 0)
    {
        Direction = (LastLocation
            - Route->GetLocationAtSplinePoint(LastIndex - 1, ESplineCoordinateSpace::Local)).GetSafeNormal();
    }
    if (Direction.IsNearlyZero())
    {
        Direction = FVector::ForwardVector;
    }

    Modify();
    Route->Modify();
    const int32 NewIndex = LastIndex + 1;
    Route->AddSplinePoint(LastLocation + Direction * (RequiredCm - CurrentCm), ESplineCoordinateSpace::Local, false);
    Route->SetSplinePointType(NewIndex, ESplinePointType::Linear, true);

    // A curved preceding segment means the added straight run may still fall
    // short. Converge deterministically instead of assuming one pass is enough.
    for (int32 Attempt = 0; Attempt < 8 && Route->GetSplineLength() + UE_KINDA_SMALL_NUMBER < RequiredCm; ++Attempt)
    {
        const double Deficit = RequiredCm - Route->GetSplineLength();
        Route->SetLocationAtSplinePoint(
            NewIndex,
            Route->GetLocationAtSplinePoint(NewIndex, ESplineCoordinateSpace::Local) + Direction * Deficit,
            ESplineCoordinateSpace::Local,
            true);
    }

    MarkPackageDirty();
    UE_LOG(
        LogInfinityStageMaterialization,
        Display,
        TEXT("INFINITY_STAGE_ROUTE_EXTEND_OK actor='%s' required=%.1f previous=%.1f current=%.1f"),
        *GetActorLabel(),
        RequiredCm,
        CurrentCm,
        Route->GetSplineLength());
    return true;
}

bool AInfinityStagePassageActor::EvaluateMechanismsAtMasterFrame(const FFrameNumber MasterFrame)
{
    return EvaluateMechanismsInternal(MasterFrame, TOptional<double>());
}

bool AInfinityStagePassageActor::EvaluateMechanismsAtCameraDistance(
    const FFrameNumber MasterFrame,
    const double CameraDistanceCm)
{
    return EvaluateMechanismsInternal(MasterFrame, CameraDistanceCm);
}

bool AInfinityStagePassageActor::EvaluateMechanismsInternal(
    const FFrameNumber MasterFrame,
    const TOptional<double> CameraDistanceCm)
{
    if (!ShowAsset || MaterializedPanels.IsEmpty())
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([this](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == PassageGuid;
    });
    if (!Passage || MasterFrame < Passage->SegmentStartFrame || MasterFrame > Passage->SegmentEndFrame)
    {
        return false;
    }

    const double EvaluatedCameraDistanceCm = CameraDistanceCm.Get(
        FInfinityStageCompiler::EvaluateDistanceAtFrame(*Passage, FFrameTime(MasterFrame)));
    const double CameraWingOrdinal = WingOrdinalAtPassageDistance(*Passage, EvaluatedCameraDistanceCm);
    const FInfinityPassageSettings* PassageSettings = ShowAsset->PassageSettings.FindByPredicate(
        [Passage](const FInfinityPassageSettings& Candidate)
        {
            return Candidate.PassageGuid == Passage->PassageGuid;
        });
    TMap<FGuid, int32> WingOrdinalsByCue;
    TMap<FGuid, FCameraGustTiming> GustTimingsByCue;
    for (int32 WingOrdinal = 0; WingOrdinal < Passage->Wings.Num(); ++WingOrdinal)
    {
        const FInfinityCompiledWing& Wing = Passage->Wings[WingOrdinal];
        WingOrdinalsByCue.Add(Wing.CueGuid, WingOrdinal);
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, Wing.CueGuid);
        if (!Cue || Cue->WingPair.Mechanism.PlaybackMode != EInfinityMotionPlaybackMode::CameraGust)
        {
            continue;
        }
        const FInfinityCameraGustSettings& Gust = Cue->WingPair.Mechanism.CameraGust;
        if (Gust.GroupAnchorCueGuid.IsValid())
        {
            GustTimingsByCue.Add(
                Wing.CueGuid,
                ResolveCameraGustTiming(*ShowAsset, *Passage, Gust));
        }
    }

    // Wing modulation is opt-in. With no keys anywhere the section lookup is
    // skipped entirely and evaluation stays identical to an unmodulated Show.
    const UMovieSceneInfinityPassageSection* WingSection =
        FindPassageSection(*ShowAsset, PassageGuid);
    FInfinityPassageWingEvaluation WingModulation;
    bool bHasWingModulation = false;
    if (WingSection && WingSection->HasWingModulation())
    {
        bHasWingModulation = WingSection->EvaluateWingModulation(
            *Passage,
            FFrameTime(MasterFrame),
            WingModulation);
    }
    // Most cues share a phase origin, so the rate integral is resolved once per
    // distinct origin frame rather than once per panel.
    TMap<int64, double> RateIntegralByOriginFrame;

    struct FPendingMechanismInstanceTransform
    {
        int32 InstanceIndex = INDEX_NONE;
        FTransform PreviousWorldTransform = FTransform::Identity;
        FTransform NewWorldTransform = FTransform::Identity;
    };
    TMap<UInstancedStaticMeshComponent*, TArray<FPendingMechanismInstanceTransform>> PendingUpdatesByComponent;
    for (const FInfinityMaterializedPanelRef& Ref : MaterializedPanels)
    {
        if (!IsValid(Ref.Component) || Ref.InstanceIndex == INDEX_NONE)
        {
            continue;
        }
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, Ref.CueGuid);
        const FInfinityCompiledWing* CompiledWing = Passage->Wings.FindByPredicate([&Ref](const FInfinityCompiledWing& Candidate)
        {
            return Candidate.CueGuid == Ref.CueGuid;
        });
        if (!Cue || !CompiledWing)
        {
            continue;
        }

        const FInfinityMechanismMotion& Motion = Cue->WingPair.Mechanism;
        double Phase = 0.0;
        if (Motion.PlaybackMode == EInfinityMotionPlaybackMode::CameraGust)
        {
            const FInfinityCameraGustSettings& Gust = Motion.CameraGust;
            if (Gust.TimingMode == EInfinityCameraGustTimingMode::CameraTravelWindow)
            {
                const int32* WingOrdinal = WingOrdinalsByCue.Find(Ref.CueGuid);
                if (!WingOrdinal)
                {
                    continue;
                }
                const double RevealFrontOrdinal = CameraWingOrdinal + FMath::Max(1, Gust.FanDepthPairs);
                Phase = FMath::Clamp(
                    (RevealFrontOrdinal - *WingOrdinal) / FMath::Max(0.01, Gust.OpeningSpanPairs),
                    0.0,
                    1.0);
            }
            else
            {
                const FCameraGustTiming* Timing = GustTimingsByCue.Find(Ref.CueGuid);
                if (!Timing)
                {
                    continue;
                }
                const int32 StaggerOrdinal = Gust.Direction == EInfinityCameraGustDirection::NearestToFarthest
                    ? Gust.GroupOrdinal
                    : FMath::Max(0, Gust.GroupSize - 1 - Gust.GroupOrdinal);
                const double ActivationFrame = Timing->GroupTriggerFrame
                    + StaggerOrdinal * Timing->EffectiveStaggerSeconds * ShowAsset->TickResolution.AsDecimal();
                const double OpeningFrames = Timing->EffectiveOpeningSeconds * ShowAsset->TickResolution.AsDecimal();
                Phase = OpeningFrames > UE_DOUBLE_SMALL_NUMBER
                    ? FMath::Clamp((MasterFrame.Value - ActivationFrame) / OpeningFrames, 0.0, 1.0)
                    : (MasterFrame.Value >= ActivationFrame ? 1.0 : 0.0);
            }
            // Camera-window pairs behind the camera remain open; in either mode,
            // closing occurs only when the absolute camera/frame position rewinds
            // before that pair's reveal frontier.
        }
        else
        {
            double OriginFrame = Passage->SegmentStartFrame.Value;
            if (Motion.PhaseOrigin == EInfinityMotionPhaseOrigin::PassFrame)
            {
                OriginFrame = CompiledWing->PassFrame.Value;
            }
            else if (Motion.PhaseOrigin == EInfinityMotionPhaseOrigin::ExplicitFrame)
            {
                OriginFrame = Motion.ExplicitOriginFrame.Value;
            }
            const double Rate = FMath::Max(0.0, Motion.CycleRateHz);
            // Cycle Rate Scale is a rate, so elapsed mechanism time is the
            // integral of that rate, not a sample of it. Differencing two
            // integrals taken from the Passage start keeps scrub, seek and
            // reverse agreeing with sequential playback.
            double ElapsedFrames = MasterFrame.Value - OriginFrame;
            if (bHasWingModulation)
            {
                const int64 OriginKey = static_cast<int64>(FMath::RoundToInt64(OriginFrame));
                const double* CachedIntegral = RateIntegralByOriginFrame.Find(OriginKey);
                const double OriginIntegral = CachedIntegral
                    ? *CachedIntegral
                    : RateIntegralByOriginFrame.Add(
                        OriginKey,
                        WingSection->GetWingCycleRateIntegralFrames(*Passage, OriginFrame));
                ElapsedFrames = WingModulation.CycleRateIntegralFrames - OriginIntegral;
            }
            const double Seconds = ElapsedFrames / ShowAsset->TickResolution.AsDecimal();
            const bool bUseLivePhase = PassageSettings
                && PassageSettings->bUseLiveMechanismPhasePattern
                && Motion.PlaybackMode == EInfinityMotionPlaybackMode::ContinuousLoop
                && (Cue->WingPair.LocalOverrideMask
                    & static_cast<int32>(EInfinityLocalOverride::MechanismPhase)) == 0;
            const int32 WingOrdinal = WingOrdinalsByCue.FindRef(Ref.CueGuid);
            const double PhaseOffset = (bUseLivePhase
                ? PassageSettings->MechanismPhaseOffsetCycles
                    + WingOrdinal * PassageSettings->MechanismPhaseStepCycles
                : Motion.PhaseOffsetCycles)
                + (bHasWingModulation ? WingModulation.PhaseBiasCycles : 0.0);
            Phase = PhaseOffset + Seconds * Rate;
            if (Motion.PlaybackMode == EInfinityMotionPlaybackMode::Static)
            {
                Phase = PhaseOffset;
            }
            else if (Motion.PlaybackMode == EInfinityMotionPlaybackMode::OneShot)
            {
                Phase = FMath::Clamp(Phase, 0.0, 1.0);
            }
            else
            {
                Phase = Phase - FMath::Floor(Phase);
            }
        }

        const FRuntimeFloatCurve* Curve = &Motion.LeftNormalizedCurve;
        if (Ref.Side == EInfinityPanelSide::Right)
        {
            Curve = &Motion.RightNormalizedCurve;
        }
        else if (Ref.Side == EInfinityPanelSide::Top)
        {
            if (!Motion.bTopFollowsMechanism)
            {
                // Held at rest, whatever curve the preset authored.
                Curve = nullptr;
            }
            else if (Motion.TopNormalizedCurve.GetRichCurveConst()->GetNumKeys() > 0)
            {
                Curve = &Motion.TopNormalizedCurve;
            }
            // Otherwise fall through to the Left curve, so a side-only preset
            // still drives the ceiling once the artist opts the Top in.
        }
        const float NormalizedTravel = Curve
            ? Curve->GetRichCurveConst()->Eval(static_cast<float>(Phase), 0.0f)
            : 0.0f;
        FVector InwardWorldDirection = Ref.InwardWorldDirection;
        if (InwardWorldDirection.IsNearlyZero())
        {
            // Compatibility for actors serialized before InwardWorldDirection was
            // added. Newly materialized passages always take the fast stored path.
            FTransform StationWorld;
            FTransform PairWorld;
            if (GetCuePlacementTransforms(Ref.CueGuid, StationWorld, PairWorld))
            {
                InwardWorldDirection = PairWorld.GetRotation()
                    .RotateVector(GetPairLocalInwardDirection(Ref.Side))
                    .GetSafeNormal();
            }
        }
        // The same authored modulation channel scales linear travel for Slide /
        // Trap and angular travel for Topple / Turn in every playback mode.
        const double TravelScale = bHasWingModulation ? WingModulation.InwardTravelScale : 1.0;
        const EInfinityMechanismKind MechanismKind = ResolveMechanismKindForSide(Motion.Kind, Ref.Side);
        FTransform NewWorldTransform = Ref.BaseWorldTransform;
        if (MechanismKind == EInfinityMechanismKind::Trap)
        {
            const FVector UpWorld = Ref.BaseWorldTransform.GetRotation().GetUpVector();
            NewWorldTransform.AddToTranslation(
                UpWorld * NormalizedTravel * Motion.InwardTravelCm * TravelScale);
        }
        else if (MechanismKind == EInfinityMechanismKind::Topple
            || MechanismKind == EInfinityMechanismKind::Turn)
        {
            const FVector PivotLocal = Ref.MechanismPivotLocal.GetLocation();
            const FVector AxisLocal = Ref.MechanismPivotLocal.GetRotation().GetAxisX().GetSafeNormal();
            const FVector BaseScale = Ref.BaseWorldTransform.GetScale3D();
            const FVector PivotScaled = PivotLocal * BaseScale;
            const FVector AxisScaled = (AxisLocal * BaseScale).GetSafeNormal();
            const FTransform RigidBase(
                Ref.BaseWorldTransform.GetRotation(),
                Ref.BaseWorldTransform.GetTranslation());
            const double AngleRadians = FMath::DegreesToRadians(
                NormalizedTravel * Motion.MaxAngleDeg * TravelScale);
            // FTransform A * B applies A then B. Apply the authored scale first,
            // then rotate rigidly about the correspondingly scaled pivot/axis.
            // Every factor after BaseScaleTransform has unit scale, avoiding the
            // shear produced by rotating before a non-uniform scale.
            const FTransform BaseScaleTransform(
                FQuat::Identity,
                FVector::ZeroVector,
                BaseScale);
            NewWorldTransform = BaseScaleTransform
                * FTransform(FQuat::Identity, -PivotScaled)
                * FTransform(FQuat(AxisScaled, AngleRadians))
                * FTransform(FQuat::Identity, PivotScaled)
                * RigidBase;
        }
        else
        {
            NewWorldTransform.AddToTranslation(
                InwardWorldDirection * NormalizedTravel * Motion.InwardTravelCm * TravelScale);
        }

        FTransform PreviousWorldTransform;
        if (!Ref.Component->GetInstanceTransform(Ref.InstanceIndex, PreviousWorldTransform, true))
        {
            UE_LOG(
                LogInfinityStageMaterialization,
                Warning,
                TEXT("INFINITY_STAGE_MECHANISM_HISTORY_UPDATE_FAILED actor='%s' instance=%d reason=missing_current_transform"),
                *GetActorLabel(),
                Ref.InstanceIndex);
            continue;
        }

        FPendingMechanismInstanceTransform& Pending =
            PendingUpdatesByComponent.FindOrAdd(Ref.Component).AddDefaulted_GetRef();
        Pending.InstanceIndex = Ref.InstanceIndex;
        Pending.PreviousWorldTransform = PreviousWorldTransform;
        Pending.NewWorldTransform = NewWorldTransform;
    }

    bool bAllUpdatesSucceeded = true;
    for (TPair<UInstancedStaticMeshComponent*, TArray<FPendingMechanismInstanceTransform>>& Pair
        : PendingUpdatesByComponent)
    {
        UInstancedStaticMeshComponent* Component = Pair.Key;
        TArray<FPendingMechanismInstanceTransform>& Updates = Pair.Value;
        if (!IsValid(Component) || Updates.IsEmpty())
        {
            continue;
        }

        int32 RenderStateUpdateMode =
            CVarInfinityStageMechanismMarkRenderStateDirty.GetValueOnGameThread();
        if (RenderStateUpdateMode < 0 || RenderStateUpdateMode > 2)
        {
            RenderStateUpdateMode = 1;
        }

        Component->SetHasPerInstancePrevTransforms(true);
        Updates.Sort([](
            const FPendingMechanismInstanceTransform& A,
            const FPendingMechanismInstanceTransform& B)
        {
            return A.InstanceIndex < B.InstanceIndex;
        });

        TArray<FTransform> NewWorldTransforms;
        TArray<FTransform> PreviousWorldTransforms;
        NewWorldTransforms.Reserve(Updates.Num());
        PreviousWorldTransforms.Reserve(Updates.Num());
        int32 SpanStartIndex = INDEX_NONE;
        int32 ExpectedInstanceIndex = INDEX_NONE;

        const auto FlushContiguousSpan = [&](const bool bMarkRenderStateDirty)
        {
            if (SpanStartIndex == INDEX_NONE || NewWorldTransforms.IsEmpty())
            {
                return;
            }
            const bool bUpdated = Component->BatchUpdateInstancesTransforms(
                SpanStartIndex,
                NewWorldTransforms,
                PreviousWorldTransforms,
                true,
                bMarkRenderStateDirty,
                false);
            if (!bUpdated)
            {
                bAllUpdatesSucceeded = false;
                UE_LOG(
                    LogInfinityStageMaterialization,
                    Warning,
                    TEXT("INFINITY_STAGE_MECHANISM_HISTORY_UPDATE_FAILED actor='%s' component='%s' start=%d count=%d reason=batch_rejected"),
                    *GetActorLabel(),
                    *Component->GetName(),
                    SpanStartIndex,
                    NewWorldTransforms.Num());
            }
            NewWorldTransforms.Reset();
            PreviousWorldTransforms.Reset();
            SpanStartIndex = INDEX_NONE;
            ExpectedInstanceIndex = INDEX_NONE;
        };

        for (const FPendingMechanismInstanceTransform& Update : Updates)
        {
            if (SpanStartIndex == INDEX_NONE)
            {
                SpanStartIndex = Update.InstanceIndex;
                ExpectedInstanceIndex = Update.InstanceIndex;
            }
            else if (Update.InstanceIndex != ExpectedInstanceIndex)
            {
                FlushContiguousSpan(false);
                SpanStartIndex = Update.InstanceIndex;
                ExpectedInstanceIndex = Update.InstanceIndex;
            }
            NewWorldTransforms.Add(Update.NewWorldTransform);
            PreviousWorldTransforms.Add(Update.PreviousWorldTransform);
            ++ExpectedInstanceIndex;
        }
        FlushContiguousSpan(RenderStateUpdateMode == 2);
        if (RenderStateUpdateMode == 1)
        {
            Component->MarkRenderStateDirty();
        }
    }
    // Light drama belongs to Rig & atmosphere (InfinityStageLightDrama.cpp). Game
    // worlds only: in the editor a lamp must keep its authored values, because
    // editing it captures live settings and aim back into the Show.
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        const double ShowSeconds = MasterFrame.Value / ShowAsset->TickResolution.AsDecimal();
        for (AActor* Lamp : ManagedAttachmentActors)
        {
            FGuid CueGuid;
            FGuid AttachmentGuid;
            if (!IsValid(Lamp) || !FindAttachmentByActor(Lamp, CueGuid, AttachmentGuid))
            {
                continue;
            }
            const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CueGuid);
            const FInfinityCueAttachment* Attachment = Cue
                ? Cue->WingPair.Attachments.FindByPredicate([&AttachmentGuid](const FInfinityCueAttachment& Candidate)
                    { return Candidate.AttachmentGuid == AttachmentGuid; })
                : nullptr;
            const FInfinityCompiledWing* Wing = Passage->Wings.FindByPredicate([&CueGuid](const FInfinityCompiledWing& Candidate)
                { return Candidate.CueGuid == CueGuid; });
            if (!Attachment || !Wing || Attachment->Kind != EInfinityAttachmentKind::Light
                || Attachment->Anchor != EInfinityAttachmentAnchor::Station
                || !InfinityStageLightDrama::IsActive(Attachment->Lighting.Drama))
            {
                continue;
            }
            // Station anchor: the authored pose is the offset on the pair root,
            // computed here without a recompile per lamp.
            const FTransform AuthoredWorld = Attachment->RelativeTransform
                * Cue->WingPair.OccurrenceOffset
                * Route->GetTransformAtDistanceAlongSpline(Wing->DistanceCm, ESplineCoordinateSpace::World, true);
            InfinityStageLightDrama::ApplyToLamp(
                *Lamp,
                Attachment->Lighting.Drama,
                Attachment->Lighting.Intensity,
                AuthoredWorld,
                AttachmentGuid,
                Wing->DistanceCm + Attachment->RelativeTransform.GetLocation().X,
                EvaluatedCameraDistanceCm,
                ShowSeconds);
        }
        // Movers after Light Drama: a mover owns its lamp's aim while it runs.
        UpdateLightMovers(*Passage, EvaluatedCameraDistanceCm, ShowSeconds);
        // After the lamps, so a body that also drives its light has the last word.
        UpdateBulbBodies(*Passage, EvaluatedCameraDistanceCm, ShowSeconds);
    }

    return bAllUpdatesSucceeded;
}

void AInfinityStagePassageActor::UpdateLightMovers(
    const FInfinityCompiledPassage& Passage,
    const double CameraDistanceCm,
    const double ShowSeconds)
{
    if (!Route)
    {
        return;
    }
    for (AActor* Lamp : ManagedAttachmentActors)
    {
        FGuid CueGuid;
        FGuid AttachmentGuid;
        if (!IsValid(Lamp) || !FindAttachmentByActor(Lamp, CueGuid, AttachmentGuid))
        {
            continue;
        }
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CueGuid);
        const FInfinityCueAttachment* Attachment = Cue
            ? Cue->WingPair.Attachments.FindByPredicate([&AttachmentGuid](const FInfinityCueAttachment& Candidate)
                { return Candidate.AttachmentGuid == AttachmentGuid; })
            : nullptr;
        if (!Attachment || !Attachment->Mover.bEnabled || Attachment->Kind != EInfinityAttachmentKind::Light
            || Attachment->Anchor != EInfinityAttachmentAnchor::Station)
        {
            continue;
        }
        const FInfinityCompiledWing* Wing = Passage.Wings.FindByPredicate([&CueGuid](const FInfinityCompiledWing& Candidate)
            { return Candidate.CueGuid == CueGuid; });
        if (!Wing)
        {
            continue;
        }
        const double LampCm = Wing->DistanceCm + Attachment->RelativeTransform.GetLocation().X;
        const float Scale = InfinityStageLightMover::ErraticScale(Attachment->Mover, LampCm, CameraDistanceCm);
        if (Scale <= 0.0f && Attachment->Lighting.Drama.bSlowMove)
        {
            // Not started yet: Light Drama's slow move keeps the aim.
            continue;
        }
        // The authored pose exactly as the Light Drama pass computes it.
        const FTransform AuthoredWorld = Attachment->RelativeTransform
            * Cue->WingPair.OccurrenceOffset
            * Route->GetTransformAtDistanceAlongSpline(Wing->DistanceCm, ESplineCoordinateSpace::World, true);
        const FRotator Offset = InfinityStageLightMover::Evaluate(
            Attachment->Mover, AttachmentGuid, LampCm, CameraDistanceCm, ShowSeconds);
        const FQuat Wanted = AuthoredWorld.GetRotation() * Offset.Quaternion();
        if (!Lamp->GetActorQuat().Equals(Wanted, 1.0e-6))
        {
            Lamp->SetActorRotation(Wanted, ETeleportType::TeleportPhysics);
        }
    }
}

float AInfinityStagePassageActor::GetBulbBodyLevelForTests(const AActor* Body) const
{
    const FBulbBodyRuntime* Runtime = Body ? BulbBodies.Find(FObjectKey(Body)) : nullptr;
    return Runtime ? Runtime->Level : -1.0f;
}

void AInfinityStagePassageActor::UpdateBulbBodies(
    const FInfinityCompiledPassage& Passage,
    const double CameraDistanceCm,
    const double ShowSeconds)
{
    // Light actors by attachment GUID, built only if some body drives its light.
    TMap<FGuid, AActor*> LightActors;
    bool bLightActorsBuilt = false;

    for (AActor* Body : ManagedAttachmentActors)
    {
        FGuid CueGuid;
        FGuid AttachmentGuid;
        if (!IsValid(Body) || !FindAttachmentByActor(Body, CueGuid, AttachmentGuid))
        {
            continue;
        }
        const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CueGuid);
        const FInfinityCueAttachment* Attachment = Cue
            ? Cue->WingPair.Attachments.FindByPredicate([&AttachmentGuid](const FInfinityCueAttachment& Candidate)
                { return Candidate.AttachmentGuid == AttachmentGuid; })
            : nullptr;
        if (!Attachment || !Attachment->Body.bFollowLight || Attachment->Kind == EInfinityAttachmentKind::Light)
        {
            continue;
        }
        const FInfinityCompiledWing* Wing = Passage.Wings.FindByPredicate([&CueGuid](const FInfinityCompiledWing& Candidate)
            { return Candidate.CueGuid == CueGuid; });
        if (!Wing)
        {
            continue;
        }
        const FInfinityBulbBodySettings& Settings = Attachment->Body;
        const FGuid WantedLight = Settings.LightAttachmentGuid;
        const FInfinityCueAttachment* LightAttachment = Cue->WingPair.Attachments.FindByPredicate(
            [&WantedLight](const FInfinityCueAttachment& Candidate)
            {
                return Candidate.bEnabled && Candidate.Kind == EInfinityAttachmentKind::Light
                    && (!WantedLight.IsValid() || Candidate.AttachmentGuid == WantedLight);
            });
        // The lamp's route position, as the drama loop computes it; the body's own without a light.
        const FInfinityCueAttachment& Placed = LightAttachment ? *LightAttachment : *Attachment;
        const double LampCm = Wing->DistanceCm + Placed.RelativeTransform.GetLocation().X;
        const float DramaScale = LightAttachment && InfinityStageLightDrama::IsActive(LightAttachment->Lighting.Drama)
            ? InfinityStageLightDrama::Evaluate(LightAttachment->Lighting.Drama, LightAttachment->AttachmentGuid,
                LampCm, CameraDistanceCm, ShowSeconds).IntensityScale
            : 1.0f;
        const float Flicker = InfinityStageBulbBody::FlickerScale(Settings, AttachmentGuid, ShowSeconds, CameraDistanceCm - LampCm);

        FBulbBodyRuntime& Runtime = BulbBodies.FindOrAdd(FObjectKey(Body));
        if (!Runtime.bPrepared)
        {
            Runtime.bPrepared = true;
            float Authored = 1.0f;
            UStaticMeshComponent* Mesh = Body->FindComponentByClass<UStaticMeshComponent>();
            if (Mesh && Mesh->GetNumMaterials() > 0)
            {
                if (const UMaterialInterface* Base = Mesh->GetMaterial(0))
                {
                    float Read = 0.0f;
                    if (Base->GetScalarParameterValue(FHashedMaterialParameterInfo(FMaterialParameterInfo(Settings.IntensityParameter)), Read))
                    {
                        Authored = Read;
                    }
                }
                // A transient instance on the game-world copy only; the level never sees it.
                Runtime.Material = Mesh->CreateDynamicMaterialInstance(0);
            }
            Runtime.FullIntensity = Settings.FullIntensity > 0.0f ? Settings.FullIntensity : Authored;
        }
        const float Level = InfinityStageBulbBody::BodyIntensity(Runtime.FullIntensity, DramaScale, Flicker);
        if (Level != Runtime.Level)
        {
            Runtime.Level = Level;
            if (UMaterialInstanceDynamic* Material = Runtime.Material.Get())
            {
                Material->SetScalarParameterValue(Settings.IntensityParameter, Level);
            }
        }

        if (Settings.bFlickerAlsoDrivesLight && LightAttachment)
        {
            if (!bLightActorsBuilt)
            {
                bLightActorsBuilt = true;
                for (AActor* Candidate : ManagedAttachmentActors)
                {
                    FGuid CandidateCue;
                    FGuid CandidateAttachment;
                    if (IsValid(Candidate) && FindAttachmentByActor(Candidate, CandidateCue, CandidateAttachment))
                    {
                        LightActors.Add(CandidateAttachment, Candidate);
                    }
                }
            }
            AActor* const* LightActor = LightActors.Find(LightAttachment->AttachmentGuid);
            ULightComponent* Light = LightActor && *LightActor ? (*LightActor)->FindComponentByClass<ULightComponent>() : nullptr;
            if (Light)
            {
                const float Scale = DramaScale * Flicker;
                const bool bLit = Scale > UE_KINDA_SMALL_NUMBER;
                if (Light->IsVisible() != bLit)
                {
                    Light->SetVisibility(bLit);
                }
                if (bLit)
                {
                    Light->SetIntensity(FMath::Max(0.0f, LightAttachment->Lighting.Intensity) * Scale);
                }
            }
        }
    }
}

bool AInfinityStagePassageActor::GetCuePlacementTransforms(
    const FGuid CueGuid,
    FTransform& OutStationWorld,
    FTransform& OutPairWorld) const
{
    if (!ShowAsset || !Route)
    {
        return false;
    }
    const FInfinityShowCue* Cue = FindCueByGuid(*ShowAsset, CueGuid);
    if (!Cue || Cue->Type != EInfinityCueType::WingPair)
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate([this](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == PassageGuid;
    });
    if (!Passage)
    {
        return false;
    }
    const FInfinityCompiledWing* Wing = Passage->Wings.FindByPredicate([CueGuid](const FInfinityCompiledWing& Candidate)
    {
        return Candidate.CueGuid == CueGuid;
    });
    if (!Wing)
    {
        return false;
    }
    OutStationWorld = Route->GetTransformAtDistanceAlongSpline(
        Wing->DistanceCm,
        ESplineCoordinateSpace::World,
        true);
    OutPairWorld = Cue->WingPair.OccurrenceOffset * OutStationWorld;
    return true;
}

bool AInfinityStagePassageActor::GetAttachmentAnchorWorldTransform(
    const FGuid CueGuid,
    const FGuid AttachmentGuid,
    FTransform& OutAnchorWorld) const
{
    if (!ShowAsset)
    {
        return false;
    }
    const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate(
        [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
    if (!Cue || Cue->Type != EInfinityCueType::WingPair)
    {
        return false;
    }
    const FInfinityCueAttachment* Attachment = Cue->WingPair.Attachments.FindByPredicate(
        [AttachmentGuid](const FInfinityCueAttachment& Candidate)
        { return Candidate.AttachmentGuid == AttachmentGuid; });
    if (!Attachment)
    {
        return false;
    }

    FTransform StationWorld;
    FTransform PairWorld;
    if (!GetCuePlacementTransforms(CueGuid, StationWorld, PairWorld))
    {
        return false;
    }

    // Station anchoring uses the pair root, which already carries the occurrence
    // offset, so a prop keeps its place when the pair is nudged as a whole.
    FTransform AnchorWorld = PairWorld;
    if (Attachment->Anchor == EInfinityAttachmentAnchor::PairCentre)
    {
        // Track the live midpoint so the anchor closes in with the panels. Keep
        // the pair's rotation and scale: only the position is derived.
        const FInfinityMaterializedPanelRef* Left = MaterializedPanels.FindByPredicate(
            [CueGuid](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == CueGuid && Ref.Side == EInfinityPanelSide::Left; });
        const FInfinityMaterializedPanelRef* Right = MaterializedPanels.FindByPredicate(
            [CueGuid](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == CueGuid && Ref.Side == EInfinityPanelSide::Right; });
        FTransform LeftWorld;
        FTransform RightWorld;
        if (Left && Left->Component && Right && Right->Component
            && Left->Component->GetInstanceTransform(Left->InstanceIndex, LeftWorld, true)
            && Right->Component->GetInstanceTransform(Right->InstanceIndex, RightWorld, true))
        {
            AnchorWorld.SetLocation(
                (LeftWorld.GetLocation() + RightWorld.GetLocation()) * 0.5);
        }
        // Otherwise the pair root already is the sensible centre.
    }
    else if (Attachment->Anchor != EInfinityAttachmentAnchor::Station)
    {
        const EInfinityPanelSide Side =
            Attachment->Anchor == EInfinityAttachmentAnchor::LeftPanel ? EInfinityPanelSide::Left
            : Attachment->Anchor == EInfinityAttachmentAnchor::RightPanel ? EInfinityPanelSide::Right
            : EInfinityPanelSide::Top;
        const FInfinityMaterializedPanelRef* Panel = MaterializedPanels.FindByPredicate(
            [CueGuid, Side](const FInfinityMaterializedPanelRef& Ref)
            { return Ref.CueGuid == CueGuid && Ref.Side == Side; });
        if (!Panel || !Panel->Component || Panel->InstanceIndex == INDEX_NONE)
        {
            // The panel does not exist — an unmaterialized Passage, or a pair with
            // no Top. Fall back to the station rather than losing the attachment.
            AnchorWorld = PairWorld;
        }
        else
        {
            // Read the live instance so the attachment follows inward travel,
            // rather than the rest pose stored at materialization time.
            FTransform PanelWorld;
            if (Panel->Component->GetInstanceTransform(Panel->InstanceIndex, PanelWorld, true))
            {
                AnchorWorld = PanelWorld;
            }
            else
            {
                AnchorWorld = Panel->BaseWorldTransform;
            }
        }
    }

    OutAnchorWorld = AnchorWorld;
    return true;
}

bool AInfinityStagePassageActor::GetAttachmentWorldTransform(
    const FGuid CueGuid,
    const FGuid AttachmentGuid,
    FTransform& OutWorldTransform) const
{
    FTransform AnchorWorld;
    if (!GetAttachmentAnchorWorldTransform(CueGuid, AttachmentGuid, AnchorWorld))
    {
        return false;
    }
    const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate(
        [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
    const FInfinityCueAttachment* Attachment = Cue
        ? Cue->WingPair.Attachments.FindByPredicate(
            [AttachmentGuid](const FInfinityCueAttachment& Candidate)
            { return Candidate.AttachmentGuid == AttachmentGuid; })
        : nullptr;
    if (!Attachment)
    {
        return false;
    }
    OutWorldTransform = Attachment->RelativeTransform * AnchorWorld;
    return true;
}

bool AInfinityStagePassageActor::FindAttachmentByActor(
    const AActor* Actor,
    FGuid& OutCueGuid,
    FGuid& OutAttachmentGuid) const
{
    if (!Actor)
    {
        return false;
    }
    for (const FName& Tag : Actor->Tags)
    {
        const FString Value = Tag.ToString();
        if (!Value.StartsWith(InfinityStageAttachmentTagPrefix))
        {
            continue;
        }
        FString CuePart;
        FString AttachmentPart;
        if (!Value.RightChop(InfinityStageAttachmentTagPrefix.Len()).Split(TEXT("|"), &CuePart, &AttachmentPart))
        {
            continue;
        }
        if (FGuid::Parse(CuePart, OutCueGuid) && FGuid::Parse(AttachmentPart, OutAttachmentGuid))
        {
            return true;
        }
    }
    return false;
}

int32 AInfinityStagePassageActor::GetMechanismSoundIndexForCue(const FGuid CueGuid) const
{
    if (!ShowAsset)
    {
        return INDEX_NONE;
    }
    const FInfinityPassageSettings* Settings = ShowAsset->PassageSettings.FindByPredicate(
        [this](const FInfinityPassageSettings& Candidate)
        { return Candidate.PassageGuid == PassageGuid; });
    if (!Settings)
    {
        return INDEX_NONE;
    }
    const FInfinityMechanismSoundSet& Set = Settings->MechanismSound;
    if (!Set.bEnabled || Set.Sounds.IsEmpty())
    {
        return INDEX_NONE;
    }

    const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate(
        [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
    if (!Cue || Cue->Type != EInfinityCueType::WingPair || Cue->WingPair.bMuteMechanismSound)
    {
        return INDEX_NONE;
    }

    // Ordinal within the Passage, so RoundRobin follows the visible order.
    int32 Ordinal = 0;
    for (const FInfinityShowCue& Candidate : ShowAsset->Cues)
    {
        if (Candidate.CueGuid == CueGuid)
        {
            break;
        }
        if (Candidate.Type == EInfinityCueType::WingPair)
        {
            ++Ordinal;
        }
    }

    switch (Set.Policy)
    {
    case EInfinityMechanismSoundPolicy::RoundRobin:
        return Ordinal % Set.Sounds.Num();

    case EInfinityMechanismSoundPolicy::ByCycleRate:
    {
        // Order the set by effort: a faster mechanism reaches further into it.
        const double Rate = FMath::Max(0.0, Cue->WingPair.Mechanism.CycleRateHz);
        const double Normalized = FMath::Clamp(Rate / 1.0, 0.0, 1.0);
        return FMath::Clamp(
            FMath::FloorToInt32(Normalized * Set.Sounds.Num()),
            0,
            Set.Sounds.Num() - 1);
    }

    case EInfinityMechanismSoundPolicy::StableRandom:
    default:
    {
        // Seeded from the cue GUID, never from a call counter or world time, so
        // the choice survives scrub, reverse, reload and re-materialization.
        const uint32 Seed = GetTypeHash(CueGuid);
        return static_cast<int32>(Seed % static_cast<uint32>(Set.Sounds.Num()));
    }
    }
}
