#include "InfinityStageStrobeLight.h"

#include "Components/PointLightComponent.h"
#include "EngineUtils.h"
#include "Engine/PostProcessVolume.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageShowRoot.h"
#include "InfinityStageTransportController.h"

namespace InfinityStageStrobe
{
float LevelAt(const double ShowSeconds, const float PeriodSeconds, const float FlashSeconds, const float DecaySeconds, const float PhaseCycles)
{
    if (PeriodSeconds <= 0.0f)
    {
        return 0.0f;
    }
    double Cycle = FMath::Fmod(ShowSeconds / PeriodSeconds + PhaseCycles, 1.0);
    if (Cycle < 0.0)
    {
        Cycle += 1.0;
    }
    const double Local = Cycle * PeriodSeconds;
    const double Flash = FMath::Max(0.0f, FlashSeconds);
    if (Local < Flash)
    {
        return 1.0f;
    }
    const double After = Local - Flash;
    if (DecaySeconds <= 0.0f || After >= DecaySeconds)
    {
        return 0.0f;
    }
    // e^-4.6 ~= 1%: the tail is all but gone by DecaySeconds, where it is cut.
    const double Tau = DecaySeconds / 4.6;
    return static_cast<float>(FMath::Exp(-After / Tau));
}

bool IsActiveInSegment(const TArray<FGuid>& Filter, const FGuid& SegmentGuid)
{
    return Filter.IsEmpty() || Filter.Contains(SegmentGuid);
}
}

AInfinityStageStrobeLight::AInfinityStageStrobeLight()
{
    PrimaryActorTick.bCanEverTick = true;
    // After Sequencer has evaluated the frame, so keyed settings and the Master clock are this frame's.
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    // A plain, saved root carries the placement. The light is a TRANSIENT child
    // (RF_Transient): its per-frame driven values can never be written by a level save.
    USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    Root->SetMobility(EComponentMobility::Movable);
    RootComponent = Root;
    Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("Light"), /*bTransient*/ true);
    Light->SetupAttachment(Root);
    Light->SetMobility(EComponentMobility::Movable);
    Light->SetIntensityUnits(ELightUnits::Candelas);
    Light->SetCastShadows(false);   // cost: a strobe in an area should not pay for a shadow map
    Light->SetAttenuationRadius(AttenuationRadiusCm);
    UnshadowedSourceRadius = Light->SourceRadius;
    SyncShadowSettings();   // class defaults: shadows off, so this changes nothing
}

void AInfinityStageStrobeLight::PostRegisterAllComponents()
{
    Super::PostRegisterAllComponents();
    // CreateDefaultSubobject(..., bTransient) does not carry RF_Transient onto spawned instances (measured 5 Oct,
    // Strobe.EditorPreviewNeverPersists). Flag the instance so a level save never stores the previewed light.
    if (Light)
    {
        Light->SetFlags(RF_Transient);
    }
    // The instance's saved shadow settings are loaded by now; apply them before the first tick.
    SyncShadowSettings();
}

void AInfinityStageStrobeLight::SyncShadowSettings()
{
    if (!Light)
    {
        return;
    }
    // Runtime setters only, and only on change: each one re-creates the light's render state.
    if (static_cast<bool>(Light->CastShadows) != bCastShadows)
    {
        Light->SetCastShadows(bCastShadows);
    }
    if (static_cast<bool>(Light->bCastVolumetricShadow) != bCastVolumetricShadow)
    {
        Light->SetCastVolumetricShadow(bCastVolumetricShadow);
    }
    const float WantedSourceRadius = bCastShadows ? FMath::Max(0.0f, ShadowSourceRadiusCm) : UnshadowedSourceRadius;
    if (!FMath::IsNearlyEqual(Light->SourceRadius, WantedSourceRadius))
    {
        Light->SetSourceRadius(WantedSourceRadius);
    }
}

void AInfinityStageStrobeLight::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UWorld* World = GetWorld();
    if (!World)
    {
        return;
    }

    double Seconds = 0.0;
    bool bActive = bStrobeEnabled;
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
            const FFrameNumber Frame = Root->Transport->GetCurrentMasterFrame();
            Seconds = Frame.Value / Root->ShowAsset->TickResolution.AsDecimal();
            if (!ActiveSegmentGuids.IsEmpty())
            {
                const int32 Index = Root->Transport->FindSegmentAtFrame(Frame);
                bActive &= Root->Transport->Segments.IsValidIndex(Index)
                    && InfinityStageStrobe::IsActiveInSegment(ActiveSegmentGuids, Root->Transport->Segments[Index].SegmentGuid);
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
        Seconds = FPlatformTime::Seconds();   // editor preview only
    }

    ApplyLevel(bActive
        ? InfinityStageStrobe::LevelAt(Seconds, PeriodSeconds, FlashSeconds, DecaySeconds, PhaseCycles)
        : 0.0f);

    // The ghost follows the same phase with its own, independent fade.
    CurrentGhost = bActive
        ? GhostMaxWeight * InfinityStageStrobe::LevelAt(Seconds, PeriodSeconds, FlashSeconds, GhostSeconds, PhaseCycles)
        : 0.0f;
    if (GhostVolume && World->IsGameWorld())
    {
        GhostVolume->BlendWeight = CurrentGhost;
    }
}

void AInfinityStageStrobeLight::ApplyLevel(const float Level)
{
    CurrentLevel = Level;
    if (!Light)
    {
        return;
    }
    // Runtime setters only (no Modify / PostEditChange): the editor preview never dirties
    // the level, and the transient component is never saved.
    if (!FMath::IsNearlyEqual(Light->AttenuationRadius, AttenuationRadiusCm))
    {
        Light->SetAttenuationRadius(AttenuationRadiusCm);
    }
    SyncShadowSettings();   // saved on the actor, so they may be keyed or edited at any time
    // Switched off rather than set to zero between flashes, as Light Drama does.
    const bool bLit = Level > UE_KINDA_SMALL_NUMBER;
    if (Light->IsVisible() != bLit)
    {
        Light->SetVisibility(bLit);
    }
    if (bLit)
    {
        Light->SetIntensity(PeakIntensity * Level);
        if (!Light->GetLightColor().Equals(Color))
        {
            Light->SetLightColor(Color);
        }
    }
}
