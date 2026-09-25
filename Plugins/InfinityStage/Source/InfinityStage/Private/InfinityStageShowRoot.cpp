#include "InfinityStageShowRoot.h"

#include "InfinityStageCompiler.h"
#include "InfinityStageCurtainRig.h"
#include "InfinityStageShowAsset.h"

#include "InfinityStageTransportController.h"
#include "LevelSequenceActor.h"
#include "LevelSequencePlayer.h"

AInfinityStageShowRoot::AInfinityStageShowRoot()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork;
    Transport = CreateDefaultSubobject<UInfinityStageTransportController>(TEXT("Transport"));
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
}

void AInfinityStageShowRoot::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
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

EInfinityCameraOwner AInfinityStageShowRoot::GetCameraOwnerAtFrame(const FFrameNumber MasterFrame) const
{
    if (bOverrideCameraOwner)
    {
        return CameraOwnerOverride;
    }
    if (!ShowAsset)
    {
        return EInfinityCameraOwner::Timeline;
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
            return Settings ? Settings->CameraOwner : EInfinityCameraOwner::Timeline;
        }
        const FInfinityShowCue* Cue = ShowAsset->Cues.FindByPredicate(
            [&Segment](const FInfinityShowCue& Candidate)
            { return Candidate.CueGuid == Segment.SegmentGuid; });
        return Cue ? Cue->Scene.CameraOwner : EInfinityCameraOwner::Timeline;
    }
    // Outside every segment there is nothing authored to hand over to.
    return EInfinityCameraOwner::Timeline;
}

EInfinityCameraOwner AInfinityStageShowRoot::GetCurrentCameraOwner() const
{
    return GetCameraOwnerAtFrame(Transport ? Transport->GetCurrentMasterFrame() : FFrameNumber(0));
}
