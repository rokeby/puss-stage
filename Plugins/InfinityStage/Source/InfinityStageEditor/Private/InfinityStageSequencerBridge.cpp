#include "InfinityStageSequencerBridge.h"

#include "ISequencer.h"
#include "ISequencerModule.h"
#include "Modules/ModuleManager.h"
#include "MovieSceneSequence.h"

TArray<TWeakPtr<ISequencer>> FInfinityStageSequencerBridge::TrackedSequencers;
FDelegateHandle FInfinityStageSequencerBridge::CreatedHandle;
bool FInfinityStageSequencerBridge::bPushing = false;

void FInfinityStageSequencerBridge::Register()
{
    if (CreatedHandle.IsValid() || !FModuleManager::Get().IsModuleLoaded(TEXT("Sequencer")))
    {
        return;
    }
    ISequencerModule& SequencerModule = FModuleManager::LoadModuleChecked<ISequencerModule>(TEXT("Sequencer"));
    CreatedHandle = SequencerModule.RegisterOnSequencerCreated(
        FOnSequencerCreated::FDelegate::CreateStatic(
            &FInfinityStageSequencerBridge::HandleSequencerCreated));
}

void FInfinityStageSequencerBridge::Unregister()
{
    if (CreatedHandle.IsValid() && FModuleManager::Get().IsModuleLoaded(TEXT("Sequencer")))
    {
        FModuleManager::GetModuleChecked<ISequencerModule>(TEXT("Sequencer"))
            .UnregisterOnSequencerCreated(CreatedHandle);
    }
    CreatedHandle.Reset();
    TrackedSequencers.Reset();
}

void FInfinityStageSequencerBridge::HandleSequencerCreated(TSharedRef<ISequencer> InSequencer)
{
    // Weak only: Sequencer owns its own lifetime and closing a tab must not be
    // kept alive by this list.
    TrackedSequencers.RemoveAll([](const TWeakPtr<ISequencer>& Entry) { return !Entry.IsValid(); });
    TrackedSequencers.Add(InSequencer);
}

int32 FInfinityStageSequencerBridge::PushRootFrame(
    const UMovieSceneSequence* ExpectedRoot,
    const FFrameTime RootTime)
{
    if (bPushing || !ExpectedRoot)
    {
        return 0;
    }
    TGuardValue<bool> ReentryGuard(bPushing, true);

    int32 Moved = 0;
    TrackedSequencers.RemoveAll([](const TWeakPtr<ISequencer>& Entry) { return !Entry.IsValid(); });
    for (const TWeakPtr<ISequencer>& Entry : TrackedSequencers)
    {
        const TSharedPtr<ISequencer> Sequencer = Entry.Pin();
        if (!Sequencer.IsValid() || Sequencer->GetRootMovieSceneSequence() != ExpectedRoot)
        {
            continue;
        }
        // Already there: avoid an evaluation that would only cost time and could
        // fight an in-progress Sequencer drag.
        if (Sequencer->GetGlobalTime().Time.FrameNumber == RootTime.FrameNumber)
        {
            continue;
        }
        Sequencer->SetGlobalTime(RootTime);
        ++Moved;
    }
    return Moved;
}
