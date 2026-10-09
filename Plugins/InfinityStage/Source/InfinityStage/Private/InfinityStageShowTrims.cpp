#include "InfinityStageShowTrims.h"

#include "AudioDevice.h"
#include "Components/PostProcessComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundClass.h"
#include "Sound/SoundMix.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageShowTrims, Log, All);

namespace InfinityStageShowTrims
{
float DbToGain(const float Db)
{
    return Db <= -80.0f ? 0.0f : FMath::Pow(10.0f, FMath::Clamp(Db, -80.0f, 12.0f) / 20.0f);
}

int32 BuildPostProcess(const FInfinityShowTrimValues& Values, FPostProcessSettings& Out)
{
    int32 Overrides = 0;
    Out.bOverride_ColorGain = !FMath::IsNearlyZero(Values.ExposureEv, 1.0e-3f);
    if (Out.bOverride_ColorGain)
    {
        const float Gain = FMath::Pow(2.0f, Values.ExposureEv);
        Out.ColorGain = FVector4(Gain, Gain, Gain, 1.0f);
        ++Overrides;
    }
    Out.bOverride_ColorSaturation = !FMath::IsNearlyEqual(Values.Saturation, 1.0f, 1.0e-3f);
    if (Out.bOverride_ColorSaturation)
    {
        Out.ColorSaturation = FVector4(Values.Saturation, Values.Saturation, Values.Saturation, 1.0f);
        ++Overrides;
    }
    Out.bOverride_ColorContrast = !FMath::IsNearlyEqual(Values.Contrast, 1.0f, 1.0e-3f);
    if (Out.bOverride_ColorContrast)
    {
        Out.ColorContrast = FVector4(Values.Contrast, Values.Contrast, Values.Contrast, 1.0f);
        ++Overrides;
    }
    Out.bOverride_WhiteTemp = !FMath::IsNearlyEqual(Values.WhiteTemp, 6500.0f, 0.5f);
    if (Out.bOverride_WhiteTemp)
    {
        Out.WhiteTemp = Values.WhiteTemp;
        ++Overrides;
    }
    Out.bOverride_WhiteTint = !FMath::IsNearlyZero(Values.WhiteTint, 1.0e-3f);
    if (Out.bOverride_WhiteTint)
    {
        Out.WhiteTint = Values.WhiteTint;
        ++Overrides;
    }
    return Overrides;
}
}

AInfinityStageShowTrims::AInfinityStageShowTrims()
{
    PrimaryActorTick.bCanEverTick = true;
    // After Sequencer has evaluated this frame's keys.
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"), /*bTransient*/ true);
    PostProcess->SetupAttachment(Root);
    PostProcess->bUnbound = true;
    PostProcess->BlendWeight = 1.0f;
}

void AInfinityStageShowTrims::PostRegisterAllComponents()
{
    Super::PostRegisterAllComponents();
    // bTransient does not reach spawned instances (measured on the strobe, 5 Oct): flag it here.
    if (PostProcess)
    {
        PostProcess->SetFlags(RF_Transient);
    }
}

FInfinityShowTrimValues AInfinityStageShowTrims::GetValues() const
{
    FInfinityShowTrimValues Values;
    Values.MasterGainDb = MasterGainDb;
    Values.MusicGainDb = MusicGainDb;
    Values.AmbienceGainDb = AmbienceGainDb;
    Values.ExposureEv = ExposureEv;
    Values.Saturation = Saturation;
    Values.Contrast = Contrast;
    Values.WhiteTemp = WhiteTemp;
    Values.WhiteTint = WhiteTint;
    return Values;
}

void AInfinityStageShowTrims::SetBreathMusicMix(const float VolumeMultiplier, const float PitchMultiplier)
{
    BreathMusicVolume = FMath::Clamp(VolumeMultiplier, 0.0f, 1.0f);
    BreathMusicPitch = FMath::Max(0.01f, PitchMultiplier);
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        ApplySound(GetValues());
    }
}

void AInfinityStageShowTrims::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const FInfinityShowTrimValues Values = GetValues();
    if (PostProcess)
    {
        // Runtime write only (no Modify): previewing keys in the editor never dirties the level.
        PostProcess->Priority = PostProcessPriority;
        InfinityStageShowTrims::BuildPostProcess(Values, PostProcess->Settings);
    }
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        ApplySound(Values);
    }
}

void AInfinityStageShowTrims::ApplySound(const FInfinityShowTrimValues& Values)
{
    const float Master = InfinityStageShowTrims::DbToGain(Values.MasterGainDb);
    if (!FMath::IsNearlyEqual(Master, AppliedMasterGain, 1.0e-4f))
    {
        FAudioDeviceHandle Device = GetWorld()->GetAudioDevice();
        if (Device.IsValid())
        {
            Device->SetTransientPrimaryVolume(Master);
            AppliedMasterGain = Master;
        }
    }
    const float Music = InfinityStageShowTrims::DbToGain(Values.MusicGainDb) * BreathMusicVolume;
    const float MusicPitch = BreathMusicPitch;
    const float Ambience = InfinityStageShowTrims::DbToGain(Values.AmbienceGainDb);
    const bool bMusicChanged = MusicSoundClass
        && (!FMath::IsNearlyEqual(Music, AppliedMusicGain, 1.0e-4f)
            || !FMath::IsNearlyEqual(MusicPitch, AppliedMusicPitch, 1.0e-4f));
    const bool bAmbienceChanged = AmbienceSoundClass && !FMath::IsNearlyEqual(Ambience, AppliedAmbienceGain, 1.0e-4f);
    if (!bMusicChanged && !bAmbienceChanged)
    {
        return;
    }
    if (!SoundMix)
    {
        SoundMix = NewObject<USoundMix>(this, NAME_None, RF_Transient);
    }
    if (!bMixPushed)
    {
        UGameplayStatics::PushSoundMixModifier(this, SoundMix);
        bMixPushed = true;
    }
    if (bMusicChanged)
    {
        UGameplayStatics::SetSoundMixClassOverride(this, SoundMix, MusicSoundClass, Music, MusicPitch, 0.0f, true);
        AppliedMusicGain = Music;
        AppliedMusicPitch = MusicPitch;
    }
    if (bAmbienceChanged)
    {
        UGameplayStatics::SetSoundMixClassOverride(this, SoundMix, AmbienceSoundClass, Ambience, 1.0f, 0.0f, true);
        AppliedAmbienceGain = Ambience;
    }
}

void AInfinityStageShowTrims::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    // Leave the editor's audio exactly as it was.
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        if (!FMath::IsNearlyEqual(AppliedMasterGain, 1.0f))
        {
            FAudioDeviceHandle Device = GetWorld()->GetAudioDevice();
            if (Device.IsValid())
            {
                Device->SetTransientPrimaryVolume(1.0f);
            }
        }
        if (bMixPushed && SoundMix)
        {
            UGameplayStatics::PopSoundMixModifier(this, SoundMix);
        }
    }
    AppliedMasterGain = 1.0f;
    AppliedMusicGain = 1.0f;
    AppliedMusicPitch = 1.0f;
    AppliedAmbienceGain = 1.0f;
    bMixPushed = false;
    Super::EndPlay(EndPlayReason);
}
