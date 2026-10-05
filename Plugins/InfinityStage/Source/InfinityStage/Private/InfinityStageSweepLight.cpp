#include "InfinityStageSweepLight.h"

#include "Components/RectLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "EngineUtils.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"
#include "Materials/MaterialInterface.h"
#include "Math/RandomStream.h"

namespace InfinityStageSweep
{
FVector PathPoint(const FVector& Start, const FVector& End, const bool bCurved, const FVector& Control, const float U)
{
    const double T = FMath::Clamp(static_cast<double>(U), 0.0, 1.0);
    if (!bCurved)
    {
        return Start + (End - Start) * T;
    }
    // Quadratic Bezier: (1-T)^2 Start + 2(1-T)T Control + T^2 End.
    const double S = 1.0 - T;
    return Start * (S * S) + Control * (2.0 * S * T) + End * (T * T);
}

float Envelope(const double LocalSeconds, const float TravelSeconds, const float FadeInSeconds, const float FadeOutSeconds)
{
    if (TravelSeconds <= 0.0f || LocalSeconds < 0.0 || LocalSeconds > TravelSeconds)
    {
        return 0.0f;
    }
    const double In = FadeInSeconds > 0.0f ? FMath::Clamp(LocalSeconds / FadeInSeconds, 0.0, 1.0) : 1.0;
    const double Out = FadeOutSeconds > 0.0f ? FMath::Clamp((TravelSeconds - LocalSeconds) / FadeOutSeconds, 0.0, 1.0) : 1.0;
    return static_cast<float>(FMath::Min(In, Out));
}

static double PeriodOf(const FParams& Params)
{
    // Never sooner than one travel: passes do not overlap, so one lamp is always enough.
    return FMath::Max(static_cast<double>(Params.RepeatEverySeconds), static_cast<double>(FMath::Max(Params.TravelSeconds, 0.0f)));
}

double PassStartSeconds(const FParams& Params, const int32 PassIndex)
{
    if (PassIndex < 0 || PassIndex >= MaxPasses)
    {
        return TNumericLimits<double>::Max();
    }
    if (Params.RepeatEverySeconds <= 0.0f && PassIndex > 0)
    {
        return TNumericLimits<double>::Max();   // single pass
    }
    const double Period = PeriodOf(Params);
    const double Jitter = FMath::Max(0.0f, Params.RepeatJitterSeconds);
    FRandomStream Stream(Params.Seed);
    double Start = Params.StartDelaySeconds;
    for (int32 Index = 0; Index < PassIndex; ++Index)
    {
        // ONE draw per statement: two draws in one expression have an unspecified order.
        const double U = Stream.FRand();
        Start += Period + Jitter * U;
    }
    return Start;
}

FSample Evaluate(const FParams& Params, const double Seconds)
{
    FSample Sample;
    Sample.Position = Params.Start;
    double PassStart = Params.StartDelaySeconds;
    int32 Pass = INDEX_NONE;
    if (Seconds >= PassStart && Params.TravelSeconds > 0.0f)
    {
        if (Params.RepeatEverySeconds <= 0.0f)
        {
            Pass = 0;
        }
        else
        {
            // Same stream, same order as PassStartSeconds: pass k starts after k draws.
            const double Period = PeriodOf(Params);
            const double Jitter = FMath::Max(0.0f, Params.RepeatJitterSeconds);
            FRandomStream Stream(Params.Seed);
            for (int32 Index = 0; Index < MaxPasses; ++Index)
            {
                const double U = Stream.FRand();
                const double NextStart = PassStart + Period + Jitter * U;
                if (Seconds < NextStart)
                {
                    Pass = Index;
                    break;
                }
                PassStart = NextStart;
            }
        }
    }
    if (Pass == INDEX_NONE)
    {
        return Sample;
    }

    const double Local = Seconds - PassStart;
    float U = static_cast<float>(FMath::Clamp(Local / Params.TravelSeconds, 0.0, 1.0));
    if (Params.bPingPong && (Pass % 2) == 1)
    {
        U = 1.0f - U;
    }
    Sample.PathParam = U;
    Sample.Position = PathPoint(Params.Start, Params.End, Params.bCurved, Params.Control, U);
    if (Params.bAimAtTarget)
    {
        const FVector Direction = Params.AimTarget - Sample.Position;
        if (!Direction.IsNearlyZero())
        {
            Sample.Rotation = Direction.Rotation();
        }
    }
    Sample.Alpha = Envelope(Local, Params.TravelSeconds, Params.FadeInSeconds, Params.FadeOutSeconds);
    Sample.Intensity = Params.PeakIntensity * Sample.Alpha;
    Sample.PassIndex = Local <= Params.TravelSeconds ? Pass : INDEX_NONE;
    return Sample;
}

bool IsActiveInSegment(const TArray<FGuid>& Filter, const FGuid& SegmentGuid)
{
    return Filter.IsEmpty() || Filter.Contains(SegmentGuid);
}
}

AInfinityStageSweepLight::AInfinityStageSweepLight()
{
    PrimaryActorTick.bCanEverTick = true;
    // After Sequencer has evaluated the frame, so keyed settings and the Master clock are this frame's.
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    // A plain, saved root carries the placement. The lights are TRANSIENT children:
    // their per-frame driven values can never be written by a level save.
    USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    Root->SetMobility(EComponentMobility::Movable);
    RootComponent = Root;

    SpotLight = CreateDefaultSubobject<USpotLightComponent>(TEXT("SpotLight"), /*bTransient*/ true);
    SpotLight->SetupAttachment(Root);
    RectLight = CreateDefaultSubobject<URectLightComponent>(TEXT("RectLight"), /*bTransient*/ true);
    RectLight->SetupAttachment(Root);
    for (ULocalLightComponent* Light : { static_cast<ULocalLightComponent*>(SpotLight.Get()), static_cast<ULocalLightComponent*>(RectLight.Get()) })
    {
        Light->SetMobility(EComponentMobility::Movable);
        Light->SetIntensityUnits(ELightUnits::Candelas);
        Light->SetCastShadows(bCastShadows);   // the whole effect is the shadow of the wing edges
        Light->SetCastVolumetricShadow(bCastVolumetricShadow);
        Light->SetAttenuationRadius(AttenuationRadiusCm);
        Light->SetVisibility(false);
    }
    SpotLight->SetInnerConeAngle(InnerConeDegrees);
    SpotLight->SetOuterConeAngle(OuterConeDegrees);
    RectLight->SetSourceWidth(RectWidthCm);
    RectLight->SetSourceHeight(RectHeightCm);
}

void AInfinityStageSweepLight::PostRegisterAllComponents()
{
    Super::PostRegisterAllComponents();
    // As the Strobe (measured 5 Oct, Strobe.EditorPreviewNeverPersists): CreateDefaultSubobject's
    // bTransient does not carry RF_Transient onto spawned instances, so flag the instances here.
    if (SpotLight)
    {
        SpotLight->SetFlags(RF_Transient);
    }
    if (RectLight)
    {
        RectLight->SetFlags(RF_Transient);
    }
}

ULocalLightComponent* AInfinityStageSweepLight::GetActiveLight() const
{
    return Shape == EInfinityStageSweepShape::Rect
        ? static_cast<ULocalLightComponent*>(RectLight.Get())
        : static_cast<ULocalLightComponent*>(SpotLight.Get());
}

void AInfinityStageSweepLight::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    double Seconds = 0.0;
    bool bActive = bSweepEnabled;
    if (World->IsGameWorld())
    {
        AInfinityStageShowRoot* Root = CachedShowRoot.Get();
        if (!Root)
        {
            for (TActorIterator<AInfinityStageShowRoot> It(World); It; ++It)
            {
                Root = *It;
                CachedShowRoot = Root;
                break;
            }
        }
        if (Root && Root->Transport && Root->ShowAsset && Root->ShowAsset->TickResolution.IsValid())
        {
            // Master time: a paused transport holds the frame, so the car holds; a scrub moves it.
            const FFrameNumber Frame = Root->Transport->GetCurrentMasterFrame();
            const double Rate = Root->ShowAsset->TickResolution.AsDecimal();
            Seconds = Frame.Value / Rate;
            const int32 Index = Root->Transport->FindSegmentAtFrame(Frame);
            const bool bHasSegment = Root->Transport->Segments.IsValidIndex(Index);
            if (bHasSegment && bTimeFromSegmentStart)
            {
                Seconds = (Frame.Value - Root->Transport->Segments[Index].StartFrame.Value) / Rate;
            }
            if (!ActiveSegmentGuids.IsEmpty())
            {
                bActive &= bHasSegment
                    && InfinityStageSweep::IsActiveInSegment(ActiveSegmentGuids, Root->Transport->Segments[Index].SegmentGuid);
            }
        }
        else
        {
            // No Show in this world: run on world time rather than not at all.
            Seconds = World->GetTimeSeconds();
        }
    }
    else
    {
        // Editor preview only: wall-clock from the first preview tick, looped so it keeps showing passes.
        const double Now = FPlatformTime::Seconds();
        if (PreviewOriginSeconds < 0.0)
        {
            PreviewOriginSeconds = Now;
        }
        const double Loop = RepeatEverySeconds > 0.0f
            ? 300.0
            : StartDelaySeconds + TravelSeconds + 1.0;
        Seconds = FMath::Fmod(Now - PreviewOriginSeconds, FMath::Max(Loop, 0.1));
    }

    if (bActive)
    {
        ApplyAtSeconds(Seconds);
    }
    else
    {
        CurrentAlpha = 0.0f;
        CurrentPass = INDEX_NONE;
        for (ULocalLightComponent* Light : { static_cast<ULocalLightComponent*>(SpotLight.Get()), static_cast<ULocalLightComponent*>(RectLight.Get()) })
        {
            if (Light && Light->IsVisible())
            {
                Light->SetVisibility(false);
            }
        }
    }
}

void AInfinityStageSweepLight::ApplyComponentSettings(ULocalLightComponent* Light) const
{
    // Runtime setters only, each only on change (no Modify / PostEditChange): the preview never
    // dirties the level and a steady frame sends nothing to the render thread but the move.
    if (!FMath::IsNearlyEqual(Light->AttenuationRadius, AttenuationRadiusCm))
    {
        Light->SetAttenuationRadius(AttenuationRadiusCm);
    }
    if (static_cast<bool>(Light->CastShadows) != bCastShadows)
    {
        Light->SetCastShadows(bCastShadows);
    }
    if (static_cast<bool>(Light->bCastVolumetricShadow) != bCastVolumetricShadow)
    {
        Light->SetCastVolumetricShadow(bCastVolumetricShadow);
    }
    if (!Light->GetLightColor().Equals(Color))
    {
        Light->SetLightColor(Color);
    }
    if (static_cast<bool>(Light->bUseTemperature) != bUseTemperature)
    {
        Light->SetUseTemperature(bUseTemperature);
    }
    if (!FMath::IsNearlyEqual(Light->Temperature, TemperatureKelvin))
    {
        Light->SetTemperature(TemperatureKelvin);
    }
    if (Light->LightFunctionMaterial != LightFunctionMaterial)
    {
        Light->SetLightFunctionMaterial(LightFunctionMaterial);
    }
    if (USpotLightComponent* Spot = Cast<USpotLightComponent>(Light))
    {
        if (!FMath::IsNearlyEqual(Spot->InnerConeAngle, InnerConeDegrees))
        {
            Spot->SetInnerConeAngle(InnerConeDegrees);
        }
        if (!FMath::IsNearlyEqual(Spot->OuterConeAngle, OuterConeDegrees))
        {
            Spot->SetOuterConeAngle(OuterConeDegrees);
        }
    }
    else if (URectLightComponent* Rect = Cast<URectLightComponent>(Light))
    {
        if (!FMath::IsNearlyEqual(Rect->SourceWidth, RectWidthCm))
        {
            Rect->SetSourceWidth(RectWidthCm);
        }
        if (!FMath::IsNearlyEqual(Rect->SourceHeight, RectHeightCm))
        {
            Rect->SetSourceHeight(RectHeightCm);
        }
    }
}

void AInfinityStageSweepLight::ApplyAtSeconds(const double Seconds)
{
    InfinityStageSweep::FParams Params;
    Params.Start = StartOffset;
    Params.End = EndOffset;
    Params.bCurved = bCurvedPath;
    Params.Control = ArcControlOffset;
    Params.bAimAtTarget = bAimAtTarget;
    Params.AimTarget = AimTargetLocal;
    Params.StartDelaySeconds = StartDelaySeconds;
    Params.TravelSeconds = TravelSeconds;
    Params.RepeatEverySeconds = RepeatEverySeconds;
    Params.RepeatJitterSeconds = RepeatJitterSeconds;
    Params.Seed = RandomSeed;
    Params.bPingPong = bPingPong;
    Params.FadeInSeconds = FadeInSeconds;
    Params.FadeOutSeconds = FadeOutSeconds;
    Params.PeakIntensity = PeakIntensity;
    const InfinityStageSweep::FSample Sample = InfinityStageSweep::Evaluate(Params, Seconds);
    CurrentAlpha = Sample.Alpha;
    CurrentPass = Sample.PassIndex;

    ULocalLightComponent* Active = GetActiveLight();
    for (ULocalLightComponent* Light : { static_cast<ULocalLightComponent*>(SpotLight.Get()), static_cast<ULocalLightComponent*>(RectLight.Get()) })
    {
        if (!Light)
        {
            continue;
        }
        // Switched off rather than set to zero between passes, as the Strobe does.
        const bool bLit = Light == Active && Sample.Alpha > UE_KINDA_SMALL_NUMBER;
        if (Light->IsVisible() != bLit)
        {
            Light->SetVisibility(bLit);
        }
        if (!bLit)
        {
            continue;
        }
        ApplyComponentSettings(Light);
        Light->SetRelativeLocationAndRotation(Sample.Position, Sample.Rotation);
        Light->SetIntensity(Sample.Intensity);
    }
}

#if WITH_EDITOR
void AInfinityStageSweepLight::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);
    // Tick stops when the preview is switched off; do not leave a lit car parked mid-pass.
    PreviewOriginSeconds = -1.0;
    if (!bPreviewInEditor && GetWorld() && !GetWorld()->IsGameWorld())
    {
        for (ULocalLightComponent* Light : { static_cast<ULocalLightComponent*>(SpotLight.Get()), static_cast<ULocalLightComponent*>(RectLight.Get()) })
        {
            if (Light && Light->IsVisible())
            {
                Light->SetVisibility(false);
            }
        }
    }
}
#endif
