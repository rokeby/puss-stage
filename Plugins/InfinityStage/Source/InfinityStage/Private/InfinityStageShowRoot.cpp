#include "InfinityStageShowRoot.h"

#include "InfinityStageCompiler.h"
#include "InfinityStageCurtainRig.h"
#include "InfinityStageShowAsset.h"

#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "InfinityStageTransportController.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Sound/SoundBase.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageRoomTone, Log, All);

static TAutoConsoleVariable<float> CVarInfinityStageRoomToneVolumeDb(
    TEXT("InfinityStage.RoomTone.VolumeDb"),
    -18.0f,
    TEXT("Whole-show room-tone level in dB. Default -18 dB."));

static TAutoConsoleVariable<int32> CVarInfinityStageRoomToneEnableS6Dip(
    TEXT("InfinityStage.RoomTone.EnableS6Dip"),
    1,
    TEXT("When non-zero, MPC_S6Warp Weird applies the S6 room-tone dip."));

static TAutoConsoleVariable<float> CVarInfinityStageRoomToneS6DipDb(
    TEXT("InfinityStage.RoomTone.S6DipDb"),
    -12.0f,
    TEXT("Additional dB at Weird=1. Default -12 dB (not silence)."));

AInfinityStageShowRoot::AInfinityStageShowRoot()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    Transport = CreateDefaultSubobject<UInfinityStageTransportController>(TEXT("Transport"));
    RoomToneAudio = CreateDefaultSubobject<UAudioComponent>(TEXT("RoomToneAudio"));
    RoomToneAudio->bAutoActivate = false;
    RoomToneAudio->bAllowSpatialization = false;
    RoomToneAudio->bStopWhenOwnerDestroyed = true;
    CurtainRigClass = AInfinityStageCurtainRig::StaticClass();
    PlaybackSettings.bAutoPlay = false;
    PlaybackSettings.LoopCount.Value = 0;
}

bool AInfinityStageShowRoot::PrepareShow()
{
    if (!GetWorld() || !MasterSequence || !ShowAsset || !Transport)
    {
        return false;
    }
    if (!SequencePlayer)
    {
        ALevelSequenceActor* CreatedSequenceActor = nullptr;
        SequencePlayer = ULevelSequencePlayer::CreateLevelSequencePlayer(
            GetWorld(),
            MasterSequence,
            PlaybackSettings,
            CreatedSequenceActor);
        SequenceActor = CreatedSequenceActor;
        if (!SequencePlayer || !Transport->InitializeTransport(SequencePlayer, ShowAsset))
        {
            return false;
        }
        if (PlaybackSettings.bAutoPlay)
        {
            // Keep native autoplay initialization, then set the operator stop
            // before the first world tick. Do not pause/seek the new player.
            Transport->PlayForwardToBoundary();
        }
        else
        {
            // A held start still needs its initial curtain and camera evaluated.
            Transport->ScrubToMasterFrame(Transport->GetCurrentMasterFrame());
        }
        return true;
    }
    return SequencePlayer && Transport->InitializeTransport(SequencePlayer, ShowAsset);
}

void AInfinityStageShowRoot::BeginPlay()
{
    Super::BeginPlay();
    if (bPrepareOnBeginPlay)
    {
        PrepareShow();
    }
    EnsureCurtainRig();
    UpdateCurtainForCurrentFrame();
    if (RoomToneAudio && RoomToneSound)
    {
        RoomToneAudio->SetSound(RoomToneSound);
        UpdateRoomToneMix();
        RoomToneAudio->Play();
        UE_LOG(LogInfinityStageRoomTone, Display,
            TEXT("INFINITY_ROOM_TONE_STARTED sound=%s component=%s"),
            *RoomToneSound->GetPathName(), *RoomToneAudio->GetPathName());
    }
}

void AInfinityStageShowRoot::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (RoomToneAudio)
    {
        RoomToneAudio->Stop();
    }
    if (SequencePlayer)
    {
        SequencePlayer->StopAtCurrentTime();
    }
    if (CurtainRig)
    {
        CurtainRig->Destroy();
        CurtainRig = nullptr;
    }
    Super::EndPlay(EndPlayReason);
}

void AInfinityStageShowRoot::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateCurtainForCurrentFrame();
    UpdateRoomToneMix();
}

bool AInfinityStageShowRoot::GetCurtainStateAtFrame(
    const FFrameNumber MasterFrame,
    float& OutProgress) const
{
    OutProgress = 0.0f;
    if (!ShowAsset)
    {
        return false;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    for (int32 SegmentIndex = 0; SegmentIndex < Compiled.Segments.Num(); ++SegmentIndex)
    {
        const FInfinityCompiledSegment& Segment = Compiled.Segments[SegmentIndex];
        const bool bAtTerminalEnd = SegmentIndex == Compiled.Segments.Num() - 1
            && MasterFrame == Segment.EndFrame;
        if (MasterFrame < Segment.StartFrame
            || (MasterFrame >= Segment.EndFrame && !bAtTerminalEnd)
            || Segment.Type == EInfinityCueType::WingPair
            || !ShowAsset->Cues.IsValidIndex(Segment.FirstCueIndex))
        {
            continue;
        }

        const FInfinitySceneCueData& Scene = ShowAsset->Cues[Segment.FirstCueIndex].Scene;
        if (Scene.CurtainMode == EInfinityCurtainCueMode::None
            || Scene.bSequenceOwnsCurtain)
        {
            return false;
        }

        const int32 LocalFrame = FMath::Max(0, (MasterFrame - Segment.StartFrame).Value);
        const int32 EntryFrames = FMath::Max(0, Scene.CurtainEntryTransitionFrames.Value);
        const int32 HoldFrames = FMath::Max(0, Scene.CurtainHoldFrames.Value);
        const int32 ExitFrames = FMath::Max(0, Scene.CurtainExitTransitionFrames.Value);

        switch (Scene.CurtainMode)
        {
        case EInfinityCurtainCueMode::OpeningReveal:
            if (LocalFrame < HoldFrames)
            {
                OutProgress = 1.0f;
            }
            else if (ExitFrames > 0 && LocalFrame < HoldFrames + ExitFrames)
            {
                OutProgress = 1.0f - FMath::Clamp(
                    static_cast<float>(LocalFrame - HoldFrames) / static_cast<float>(ExitFrames),
                    0.0f,
                    1.0f);
            }
            break;

        case EInfinityCurtainCueMode::PostSceneInterstitial:
            if (EntryFrames > 0 && LocalFrame < EntryFrames)
            {
                OutProgress = FMath::Clamp(
                    static_cast<float>(LocalFrame) / static_cast<float>(EntryFrames),
                    0.0f,
                    1.0f);
            }
            else if (LocalFrame < EntryFrames + HoldFrames)
            {
                OutProgress = 1.0f;
            }
            else if (ExitFrames > 0 && LocalFrame < EntryFrames + HoldFrames + ExitFrames)
            {
                OutProgress = 1.0f - FMath::Clamp(
                    static_cast<float>(LocalFrame - EntryFrames - HoldFrames) / static_cast<float>(ExitFrames),
                    0.0f,
                    1.0f);
            }
            break;

        case EInfinityCurtainCueMode::ClosingCover:
            OutProgress = EntryFrames > 0 && LocalFrame < EntryFrames
                ? FMath::Clamp(
                    static_cast<float>(LocalFrame) / static_cast<float>(EntryFrames),
                    0.0f,
                    1.0f)
                : 1.0f;
            break;

        default:
            break;
        }
        return true;
    }
    return false;
}

bool AInfinityStageShowRoot::ShouldUseLegacyAutomaticCurtain() const
{
    if (!ShowAsset)
    {
        return false;
    }
    return ShowAsset->Cues.ContainsByPredicate([](const FInfinityShowCue& Cue)
    {
        return Cue.Type != EInfinityCueType::WingPair
            && Cue.Scene.CurtainMode != EInfinityCurtainCueMode::None
            && !Cue.Scene.bSequenceOwnsCurtain;
    });
}

void AInfinityStageShowRoot::EnsureCurtainRig()
{
    UWorld* World = GetWorld();
    if (CurtainRig
        || !World
        || !World->IsGameWorld()
        || !ShouldUseLegacyAutomaticCurtain())
    {
        return;
    }

    TSubclassOf<AInfinityStageCurtainRig> ClassToSpawn = CurtainRigClass;
    if (!ClassToSpawn)
    {
        ClassToSpawn = AInfinityStageCurtainRig::StaticClass();
    }
    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Owner = this;
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    CurtainRig = World->SpawnActor<AInfinityStageCurtainRig>(
        ClassToSpawn,
        FTransform::Identity,
        SpawnParameters);
    if (CurtainRig)
    {
        CurtainRig->Tags.AddUnique(TEXT("InfinityStage.RuntimeCurtain"));
    }
}

void AInfinityStageShowRoot::UpdateCurtainForCurrentFrame()
{
    EnsureCurtainRig();
    if (!CurtainRig)
    {
        return;
    }
    float Progress = 0.0f;
    const FFrameNumber Frame = Transport ? Transport->GetCurrentMasterFrame() : FFrameNumber(0);
    const bool bActive = GetCurtainStateAtFrame(Frame, Progress);
    CurtainRig->SetCurtainState(Progress, bActive);
}

float AInfinityStageShowRoot::ComputeRoomToneGainDb(
    const float BaseDb,
    const float S6DipDb,
    const float Weird,
    const bool bEnableS6Dip)
{
    const float Dip = bEnableS6Dip ? FMath::Min(0.0f, S6DipDb) * FMath::Clamp(Weird, 0.0f, 1.0f) : 0.0f;
    return FMath::Clamp(BaseDb + Dip, -80.0f, 12.0f);
}

void AInfinityStageShowRoot::UpdateRoomToneMix()
{
    if (!RoomToneAudio || !RoomToneSound)
    {
        return;
    }
    float Weird = 0.0f;
    if (RoomToneWarpParameters && GetWorld())
    {
        if (UMaterialParameterCollectionInstance* Instance =
                GetWorld()->GetParameterCollectionInstance(RoomToneWarpParameters))
        {
            Instance->GetScalarParameterValue(RoomToneWarpParameter, Weird);
        }
    }
    const float GainDb = ComputeRoomToneGainDb(
        CVarInfinityStageRoomToneVolumeDb.GetValueOnGameThread(),
        CVarInfinityStageRoomToneS6DipDb.GetValueOnGameThread(),
        Weird,
        CVarInfinityStageRoomToneEnableS6Dip.GetValueOnGameThread() != 0);
    RoomToneAudio->SetVolumeMultiplier(GainDb <= -80.0f ? 0.0f : FMath::Pow(10.0f, GainDb / 20.0f));
}

EInfinityCameraOwner AInfinityStageShowRoot::GetCameraOwnerAtFrame(const FFrameNumber MasterFrame) const
{
    // Forcing Timeline is the dog-failure drill (F.4): it wins everywhere.
    if (bOverrideCameraOwner && CameraOwnerOverride == EInfinityCameraOwner::Timeline)
    {
        return EInfinityCameraOwner::Timeline;
    }
    if (!ShowAsset)
    {
        return bOverrideCameraOwner ? CameraOwnerOverride : EInfinityCameraOwner::Timeline;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*ShowAsset);
    for (int32 SegmentIndex = 0; SegmentIndex < Compiled.Segments.Num(); ++SegmentIndex)
    {
        const FInfinityCompiledSegment& Segment = Compiled.Segments[SegmentIndex];
        const bool bAtTerminalEnd = SegmentIndex == Compiled.Segments.Num() - 1
            && MasterFrame == Segment.EndFrame;
        if (MasterFrame < Segment.StartFrame
            || (MasterFrame >= Segment.EndFrame && !bAtTerminalEnd))
        {
            continue;
        }
        if (Segment.Type == EInfinityCueType::WingPair)
        {
            const FInfinityPassageSettings* Settings = ShowAsset->PassageSettings.FindByPredicate(
                [&Segment](const FInfinityPassageSettings& Candidate)
                { return Candidate.PassageGuid == Segment.SegmentGuid; });
            if (bOverrideCameraOwner)
            {
                return CameraOwnerOverride;
            }
            return Settings ? Settings->CameraOwner : EInfinityCameraOwner::Timeline;
        }
        const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate(
            [&Segment](const FInfinityShowCue& Candidate)
            { return Candidate.CueGuid == Segment.SegmentGuid; });
        const EInfinityCameraOwner Authored = Cue ? Cue->Scene.CameraOwner : EInfinityCameraOwner::Timeline;
        // Sequence cues (the Opening, the Interactions, the Closing) are locked
        // against a live Dog override, so the camera cannot swing behind the
        // curtain while the dog is being walked (A.5, Gary 2026-09-26). Only the
        // override is refused; the authored owner still stands.
        if (bOverrideCameraOwner && Segment.Type != EInfinityCueType::Sequence)
        {
            return CameraOwnerOverride;
        }
        return Authored;
    }
    // Outside every segment there is nothing authored to hand over to.
    return bOverrideCameraOwner ? CameraOwnerOverride : EInfinityCameraOwner::Timeline;
}

EInfinityCameraOwner AInfinityStageShowRoot::GetCurrentCameraOwner() const
{
    return GetCameraOwnerAtFrame(Transport ? Transport->GetCurrentMasterFrame() : FFrameNumber(0));
}
