#include "InfinityStageHandoffWatch.h"

#include "Components/SplineComponent.h"
#include "CoreGlobals.h"
#include "Editor.h"
#include "EngineUtils.h"
#include "Framework/Notifications/NotificationManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "ScopedTransaction.h"
#include "UObject/Package.h"
#include "Widgets/Notifications/SNotificationList.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageHandoffWatch, Log, All);

namespace
{
TAutoConsoleVariable<int32> CVarInfinityStageHandoffWatch(
    TEXT("InfinityStage.HandoffWatch"),
    1,
    TEXT("1 reports Scene camera handoffs that an edit has just made stale. 0 disables the watch."));

/** Edits come in bursts (a drag, a curve reshape); check once they settle. */
constexpr double HandoffWatchQuietSeconds = 1.0;

UWorld* GetHandoffWatchEditorWorld()
{
    return GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
}

/** Off for automation and unattended runs: those edit fixtures in bulk, and the watch is for a person at the desk. */
bool IsHandoffWatchEnabled()
{
    return CVarInfinityStageHandoffWatch.GetValueOnGameThread() != 0
        && !GIsAutomationTesting
        && !FApp::IsUnattended();
}

/**
 * The Shows whose Passage endpoints an edited object can move, and a name for
 * the edit. Only objects placed in the editor world count: preview worlds and
 * scratch objects belong to tests and tools, not to the Show on stage.
 */
void CollectAffectedShows(
    UObject& Object,
    UWorld& World,
    TArray<UInfinityStageShowAsset*>& OutShows,
    FString& OutTrigger)
{
    if (const UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(&Object))
    {
        const ULevelSequence* Master = Section->GetTypedOuter<ULevelSequence>();
        for (TActorIterator<AInfinityStagePassageActor> It(&World); It && Master; ++It)
        {
            if (It->ShowAsset && It->ShowAsset->ManagedMasterSequence.Get() == Master)
            {
                OutShows.AddUnique(It->ShowAsset);
            }
        }
        OutTrigger = TEXT("A Passage camera edit");
        return;
    }

    AInfinityStagePassageActor* Passage = Cast<AInfinityStagePassageActor>(&Object);
    OutTrigger = TEXT("A Passage actor edit");
    if (const USplineComponent* Route = Cast<USplineComponent>(&Object))
    {
        Passage = Cast<AInfinityStagePassageActor>(Route->GetOwner());
        OutTrigger = TEXT("A Passage route edit");
    }
    if (Passage)
    {
        if (Passage->ShowAsset && Passage->GetWorld() == &World)
        {
            OutShows.AddUnique(Passage->ShowAsset);
        }
        return;
    }

    if (const AInfinityStageCameraRig* Rig = Cast<AInfinityStageCameraRig>(&Object))
    {
        if (Rig->PassageActor && Rig->PassageActor->ShowAsset && Rig->GetWorld() == &World)
        {
            OutShows.AddUnique(Rig->PassageActor->ShowAsset);
        }
        OutTrigger = TEXT("A Passage camera rig edit");
        return;
    }

    if (UInfinityStageShowAsset* Show = Cast<UInfinityStageShowAsset>(&Object))
    {
        for (TActorIterator<AInfinityStagePassageActor> It(&World); It; ++It)
        {
            if (It->ShowAsset == Show)
            {
                OutShows.AddUnique(Show);
                break;
            }
        }
        OutTrigger = TEXT("A Show timing or cue edit");
    }
}

FString DescribeScenes(const UInfinityStageShowAsset& Show, const TArray<FGuid>& SceneGuids)
{
    TArray<FString> Labels;
    for (const FGuid& SceneGuid : SceneGuids)
    {
        const FInfinityShowCue* Cue = Show.Cues.FindByPredicate(
            [&SceneGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == SceneGuid; });
        Labels.Add(Cue && !Cue->Label.IsEmpty() ? Cue->Label.ToString() : SceneGuid.ToString(EGuidFormats::DigitsWithHyphens));
    }
    return FString::Join(Labels, TEXT(", "));
}

void FadeNotification(const TSharedRef<TWeakPtr<SNotificationItem>>& Holder, const SNotificationItem::ECompletionState State)
{
    if (const TSharedPtr<SNotificationItem> Item = Holder->Pin())
    {
        Item->SetCompletionState(State);
        Item->ExpireAndFadeout();
    }
}
}

void UInfinityStageHandoffWatchSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    ObjectModifiedHandle = FCoreUObjectDelegates::OnObjectModified.AddUObject(
        this, &UInfinityStageHandoffWatchSubsystem::HandleObjectModified);
    UndoRedoHandle = FEditorDelegates::PostUndoRedo.AddUObject(
        this, &UInfinityStageHandoffWatchSubsystem::HandleUndoRedo);
    TickHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateUObject(this, &UInfinityStageHandoffWatchSubsystem::Tick),
        0.25f);
}

void UInfinityStageHandoffWatchSubsystem::Deinitialize()
{
    FCoreUObjectDelegates::OnObjectModified.Remove(ObjectModifiedHandle);
    FEditorDelegates::PostUndoRedo.Remove(UndoRedoHandle);
    FTSTicker::GetCoreTicker().RemoveTicker(TickHandle);
    States.Reset();
    Super::Deinitialize();
}

UInfinityStageHandoffWatchSubsystem::FShowWatchState& UInfinityStageHandoffWatchSubsystem::GetState(
    UInfinityStageShowAsset& Show)
{
    return States.FindOrAdd(TWeakObjectPtr<UInfinityStageShowAsset>(&Show));
}

void UInfinityStageHandoffWatchSubsystem::CaptureBaseline(UInfinityStageShowAsset& Show, UWorld& World)
{
    TGuardValue<bool> Guard(bChecking, true);
    FShowWatchState& State = GetState(Show);
    TArray<FGuid> Stale;
    FString Report;
    State.bHasBaseline = FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(Show, World, TArray<FGuid>(), Stale, Report);
    State.KnownStale = TSet<FGuid>(Stale);
}

TArray<FGuid> UInfinityStageHandoffWatchSubsystem::CheckNow(
    UInfinityStageShowAsset& Show,
    UWorld& World,
    const FString& Trigger,
    const bool bNotify)
{
    TGuardValue<bool> Guard(bChecking, true);
    FShowWatchState& State = GetState(Show);
    State.bPending = false;

    TArray<FGuid> Stale;
    FString Report;
    if (!FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(Show, World, TArray<FGuid>(), Stale, Report))
    {
        // Mid-edit the Show may not compile; keep the last good baseline.
        UE_LOG(LogInfinityStageHandoffWatch, Verbose, TEXT("Handoff watch skipped: %s"), *Report);
        return TArray<FGuid>();
    }

    // Without a baseline there is nothing to attribute: adopt the current state quietly.
    TArray<FGuid> NewlyStale;
    if (State.bHasBaseline)
    {
        for (const FGuid& SceneGuid : Stale)
        {
            if (!State.KnownStale.Contains(SceneGuid))
            {
                NewlyStale.Add(SceneGuid);
            }
        }
    }
    State.KnownStale = TSet<FGuid>(Stale);
    State.bHasBaseline = true;

    if (!NewlyStale.IsEmpty())
    {
        UE_LOG(
            LogInfinityStageHandoffWatch,
            Display,
            TEXT("INFINITY_HANDOFF_WATCH_STALE|show=%s|newly_stale=%d|scenes=%s|trigger=%s|check=%s"),
            *Show.GetName(),
            NewlyStale.Num(),
            *DescribeScenes(Show, NewlyStale),
            *Trigger,
            *Report);
        if (bNotify)
        {
            NotifyNewlyStale(Show, NewlyStale, Trigger);
        }
    }
    return NewlyStale;
}

void UInfinityStageHandoffWatchSubsystem::HandleObjectModified(UObject* Object)
{
    // This fires for every Modify() in the editor, so reject cheaply first.
    if (!Object || bChecking || GIsTransacting || !GEditor || GEditor->PlayWorld || !IsHandoffWatchEnabled())
    {
        return;
    }
    if (!Object->IsA<UMovieSceneInfinityPassageSection>()
        && !Object->IsA<AInfinityStagePassageActor>()
        && !Object->IsA<USplineComponent>()
        && !Object->IsA<AInfinityStageCameraRig>()
        && !Object->IsA<UInfinityStageShowAsset>())
    {
        return;
    }
    if (Object->GetPackage() == GetTransientPackage())
    {
        return;
    }
    UWorld* World = GetHandoffWatchEditorWorld();
    if (!World)
    {
        return;
    }

    TArray<UInfinityStageShowAsset*> Shows;
    FString Trigger;
    CollectAffectedShows(*Object, *World, Shows, Trigger);
    for (UInfinityStageShowAsset* Show : Shows)
    {
        FShowWatchState& State = GetState(*Show);
        if (!State.bPending)
        {
            // Modify() runs before the change, so this is the state the burst started from.
            CaptureBaseline(*Show, *World);
            State.bPending = true;
            State.Trigger = Trigger;
        }
    }
    if (!Shows.IsEmpty())
    {
        LastRelevantChangeSeconds = FPlatformTime::Seconds();
    }
}

void UInfinityStageHandoffWatchSubsystem::HandleUndoRedo()
{
    if (!IsHandoffWatchEnabled())
    {
        return;
    }
    // Undo restores objects without Modify(); compare against the last known state.
    bool bAny = false;
    for (TPair<TWeakObjectPtr<UInfinityStageShowAsset>, FShowWatchState>& Pair : States)
    {
        if (Pair.Key.IsValid() && Pair.Value.bHasBaseline)
        {
            Pair.Value.bPending = true;
            Pair.Value.Trigger = TEXT("Undo or redo");
            bAny = true;
        }
    }
    if (bAny)
    {
        LastRelevantChangeSeconds = FPlatformTime::Seconds();
    }
}

bool UInfinityStageHandoffWatchSubsystem::Tick(float)
{
    if (!GEditor || GEditor->PlayWorld
        || FPlatformTime::Seconds() - LastRelevantChangeSeconds < HandoffWatchQuietSeconds)
    {
        return true;
    }
    UWorld* World = GetHandoffWatchEditorWorld();
    if (!World)
    {
        return true;
    }

    TArray<TPair<TWeakObjectPtr<UInfinityStageShowAsset>, FString>> Due;
    for (auto It = States.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid())
        {
            It.RemoveCurrent();
        }
        else if (It.Value().bPending)
        {
            Due.Emplace(It.Key(), It.Value().Trigger);
        }
    }
    for (const TPair<TWeakObjectPtr<UInfinityStageShowAsset>, FString>& Item : Due)
    {
        if (UInfinityStageShowAsset* Show = Item.Key.Get())
        {
            if (IsHandoffWatchEnabled())
            {
                CheckNow(*Show, *World, Item.Value, true);
            }
            else
            {
                GetState(*Show).bPending = false;
            }
        }
    }
    return true;
}

void UInfinityStageHandoffWatchSubsystem::NotifyNewlyStale(
    UInfinityStageShowAsset& Show,
    const TArray<FGuid>& NewlyStale,
    const FString& Trigger)
{
    FNotificationInfo Info(FText::Format(
        NSLOCTEXT("InfinityStage", "HandoffWatchStale", "{0} made {1} Scene camera handoff(s) stale"),
        FText::FromString(Trigger),
        FText::AsNumber(NewlyStale.Num())));
    Info.SubText = FText::Format(
        NSLOCTEXT(
            "InfinityStage",
            "HandoffWatchStaleDetail",
            "{0}. The Passage endpoint moved, so the cut will jump unless it is deliberate."),
        FText::FromString(DescribeScenes(Show, NewlyStale)));
    Info.bFireAndForget = false;
    Info.bUseLargeFont = false;
    Info.ExpireDuration = 2.0f;

    const TSharedRef<TWeakPtr<SNotificationItem>> Holder = MakeShared<TWeakPtr<SNotificationItem>>();
    const TWeakObjectPtr<UInfinityStageShowAsset> WeakShow(&Show);
    const TWeakObjectPtr<UInfinityStageHandoffWatchSubsystem> WeakThis(this);
    const TArray<FGuid> Scenes = NewlyStale;
    Info.ButtonDetails.Add(FNotificationButtonInfo(
        NSLOCTEXT("InfinityStage", "HandoffWatchMatch", "Match"),
        NSLOCTEXT(
            "InfinityStage",
            "HandoffWatchMatchTip",
            "Re-take these Scenes' handoff cameras from the current Passage endpoints. Writes the level and the Scene sequences; undoable."),
        FSimpleDelegate::CreateLambda([Holder, WeakShow, WeakThis, Scenes]()
        {
            UInfinityStageShowAsset* TargetShow = WeakShow.Get();
            UWorld* World = GetHandoffWatchEditorWorld();
            bool bMatched = false;
            if (TargetShow && World && GEditor && !GEditor->PlayWorld)
            {
                FString Report;
                {
                    const FScopedTransaction Transaction(NSLOCTEXT(
                        "InfinityStage", "HandoffWatchMatchTransaction", "Match Stale Scene Camera Handoffs"));
                    bMatched = FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*TargetShow, *World, Scenes, Report);
                }
                UE_LOG(
                    LogInfinityStageHandoffWatch,
                    Display,
                    TEXT("INFINITY_HANDOFF_WATCH_MATCHED|show=%s|scenes=%d|ok=%d|report=%s"),
                    *TargetShow->GetName(),
                    Scenes.Num(),
                    bMatched ? 1 : 0,
                    *Report);
                if (UInfinityStageHandoffWatchSubsystem* Watch = WeakThis.Get())
                {
                    Watch->CaptureBaseline(*TargetShow, *World);
                }
            }
            FadeNotification(Holder, bMatched ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
        }),
        SNotificationItem::CS_Pending));
    Info.ButtonDetails.Add(FNotificationButtonInfo(
        NSLOCTEXT("InfinityStage", "HandoffWatchKeep", "Keep the Cut"),
        NSLOCTEXT(
            "InfinityStage",
            "HandoffWatchKeepTip",
            "The jump is deliberate. These Scenes will not be raised again unless they are matched and later drift."),
        FSimpleDelegate::CreateLambda([Holder]()
        {
            FadeNotification(Holder, SNotificationItem::CS_None);
        }),
        SNotificationItem::CS_Pending));

    const TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info);
    if (Item)
    {
        Item->SetCompletionState(SNotificationItem::CS_Pending);
        *Holder = Item;
    }
}
