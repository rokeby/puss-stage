#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Docking/TabManager.h"
#include "ISequencerModule.h"
#include "Modules/ModuleManager.h"
#include "Styling/AppStyle.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"

#include "PropertyEditorModule.h"

#include "SInfinityStageCueDesk.h"
#include "SInfinityStageWingAudit.h"
#include "InfinityStageDevFixtureBuilder.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStagePassageActorDetails.h"
#include "InfinityStageMusicBindingCustomization.h"
#include "InfinityStageSequencerBridge.h"
#include "InfinityStageAttachmentBinding.h"
#include "InfinityStageShadowCatComponent.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTrackEditor.h"
#include "InfinityStageWingAssetAuditor.h"
#include "InfinityStageWingLibraryAsset.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/IConsoleManager.h"

namespace
{
const FName InfinityStageCueDeskTabName(TEXT("InfinityStageCueDesk"));
const FName InfinityStageWingAuditTabName(TEXT("InfinityStageWingAudit"));

void CleanupEditorShadowCatChildren(const TCHAR* Reason)
{
    UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!EditorWorld || EditorWorld->IsGameWorld())
    {
        return;
    }

    TSet<AActor*> ClaimedCats;
    for (TActorIterator<AInfinityStageCameraRig> RigIt(EditorWorld); RigIt; ++RigIt)
    {
        if (RigIt->ShadowCat)
        {
            if (AActor* ClaimedCat = RigIt->ShadowCat->GetChildActor())
            {
                ClaimedCats.Add(ClaimedCat);
            }
        }
    }

    TArray<AActor*> OrphanedCats;
    int32 AttachedAdapterCount = 0;
    for (TActorIterator<AActor> ActorIt(EditorWorld); ActorIt; ++ActorIt)
    {
        AActor* Candidate = *ActorIt;
        const bool bIsScopedAdapter = Candidate
            && Candidate->IsA<AInfinityStageShadowCatActor>();
        const bool bIsAttachedToCameraRig = Candidate
            && Cast<AInfinityStageCameraRig>(Candidate->GetAttachParentActor()) != nullptr;
        if (!bIsScopedAdapter || !bIsAttachedToCameraRig)
        {
            continue;
        }

        ++AttachedAdapterCount;
        if (!ClaimedCats.Contains(Candidate))
        {
            OrphanedCats.Add(Candidate);
        }
    }

    int32 RemovedCount = 0;
    for (AActor* OrphanedCat : OrphanedCats)
    {
        if (IsValid(OrphanedCat) && EditorWorld->DestroyActor(OrphanedCat, false, false))
        {
            ++RemovedCount;
        }
    }

    // Do not auto-save authoring data. If stale children were serialized into
    // the map, expose the cleanup as a normal dirty-level change so the user
    // can review it and save only this level once.
    const bool bMarkedLevelDirty = RemovedCount > 0
        && EditorWorld->GetPackage()->MarkPackageDirty();

    UE_LOG(
        LogTemp,
        Display,
        TEXT("SHADOW_CAT_EDITOR_CLEANUP|reason=%s|removed=%d|claimed=%d|attached_adapters=%d|level_dirty=%d"),
        Reason,
        RemovedCount,
        ClaimedCats.Num(),
        AttachedAdapterCount,
        bMarkedLevelDirty);
}
}

class FInfinityStageEditorModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        ISequencerModule& SequencerModule = FModuleManager::LoadModuleChecked<ISequencerModule>(TEXT("Sequencer"));
        TrackEditorHandle = SequencerModule.RegisterTrackEditor(
            FOnCreateTrackEditor::CreateStatic(&FInfinityStageTrackEditor::CreateTrackEditor));

        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
            InfinityStageCueDeskTabName,
            FOnSpawnTab::CreateRaw(this, &FInfinityStageEditorModule::SpawnCueDeskTab))
            .SetDisplayName(NSLOCTEXT("InfinityStage", "CueDeskTabTitle", "Infinity Stage Cue Desk"))
            .SetTooltipText(NSLOCTEXT("InfinityStage", "CueDeskTabTooltip", "Open the finite, music-led show cue list."))
            .SetIcon(FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("LevelEditor.Tabs.Sequencer")));
        FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
            InfinityStageWingAuditTabName,
            FOnSpawnTab::CreateRaw(this, &FInfinityStageEditorModule::SpawnWingAuditTab))
            .SetDisplayName(NSLOCTEXT("InfinityStage", "WingAuditTabTitle", "Infinity Stage Wing Assets"))
            .SetTooltipText(NSLOCTEXT("InfinityStage", "WingAuditTabTooltip", "Audit, classify and canonicalise stage-wing mesh assets."))
            .SetIcon(FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("ClassIcon.StaticMesh")));

        FPropertyEditorModule& PropertyEditor =
            FModuleManager::LoadModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
        PropertyEditor.RegisterCustomClassLayout(
            AInfinityStagePassageActor::StaticClass()->GetFName(),
            FOnGetDetailCustomizationInstance::CreateStatic(&FInfinityStagePassageActorDetails::MakeInstance));
        PropertyEditor.RegisterCustomPropertyTypeLayout(
            TEXT("InfinitySectionMusicBinding"),
            FOnGetPropertyTypeCustomizationInstance::CreateStatic(
                &FInfinityStageMusicBindingCustomization::MakeInstance));

        FInfinityStageSequencerBridge::Register();

        UToolMenus::RegisterStartupCallback(
            FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FInfinityStageEditorModule::RegisterMenus));

        CreateFixtureCommand = MakeUnique<FAutoConsoleCommand>(
            TEXT("InfinityStage.CreateVerticalSlice"),
            TEXT("Create the six-Passage development fixture using -InfinityStageMusicRoot=<directory>."),
            FConsoleCommandDelegate::CreateRaw(this, &FInfinityStageEditorModule::CreateVerticalSlice));
        OpenCueDeskCommand = MakeUnique<FAutoConsoleCommand>(
            TEXT("InfinityStage.OpenCueDesk"),
            TEXT("Open the Infinity Stage Cue Desk. Use -InfinityStageCueDeskShow=/Game/... to select a Show Asset."),
            FConsoleCommandDelegate::CreateLambda([]()
            {
                FGlobalTabmanager::Get()->TryInvokeTab(InfinityStageCueDeskTabName);
            }));
        AuditWingAssetsCommand = MakeUnique<FAutoConsoleCommand>(
            TEXT("InfinityStage.AuditWingAssets"),
            TEXT("Scan stage-wing Static Meshes and update the persistent Wing Asset Library."),
            FConsoleCommandDelegate::CreateRaw(this, &FInfinityStageEditorModule::AuditWingAssets));
        ApplyWingCorrectionsCommand = MakeUnique<FAutoConsoleCommand>(
            TEXT("InfinityStage.ApplySafeWingAssetCorrections"),
            TEXT("Apply and save every deterministic correction proposed by the Wing Asset audit."),
            FConsoleCommandDelegate::CreateRaw(this, &FInfinityStageEditorModule::ApplyWingCorrections));

        ActorsMovedHandle = GEditor
            ? GEditor->OnActorsMoved().AddRaw(this, &FInfinityStageEditorModule::HandleActorsMoved)
            : FDelegateHandle();
        ObjectPropertyChangedHandle = FCoreUObjectDelegates::OnObjectPropertyChanged.AddRaw(
            this, &FInfinityStageEditorModule::HandleObjectPropertyChanged);
        LevelActorDeletedHandle = GEngine
            ? GEngine->OnLevelActorDeleted().AddRaw(this, &FInfinityStageEditorModule::HandleLevelActorDeleted)
            : FDelegateHandle();

        EndPIEHandle = FEditorDelegates::EndPIE.AddRaw(
            this,
            &FInfinityStageEditorModule::HandleEndPIE);
        MapOpenedHandle = FEditorDelegates::OnMapOpened.AddRaw(
            this,
            &FInfinityStageEditorModule::HandleMapOpened);
    }

    virtual void ShutdownModule() override
    {
        if (GEditor && ActorsMovedHandle.IsValid())
        {
            GEditor->OnActorsMoved().Remove(ActorsMovedHandle);
        }
        FCoreUObjectDelegates::OnObjectPropertyChanged.Remove(ObjectPropertyChangedHandle);
        if (GEngine && LevelActorDeletedHandle.IsValid())
        {
            GEngine->OnLevelActorDeleted().Remove(LevelActorDeletedHandle);
        }
        FEditorDelegates::EndPIE.Remove(EndPIEHandle);
        FEditorDelegates::OnMapOpened.Remove(MapOpenedHandle);
        if (TrackEditorHandle.IsValid() && FModuleManager::Get().IsModuleLoaded(TEXT("Sequencer")))
        {
            FModuleManager::GetModuleChecked<ISequencerModule>(TEXT("Sequencer"))
                .UnRegisterTrackEditor(TrackEditorHandle);
            TrackEditorHandle.Reset();
        }
        FInfinityStageSequencerBridge::Unregister();

        if (FModuleManager::Get().IsModuleLoaded(TEXT("PropertyEditor")))
        {
            FPropertyEditorModule& PropertyEditor =
                FModuleManager::GetModuleChecked<FPropertyEditorModule>(TEXT("PropertyEditor"));
            PropertyEditor.UnregisterCustomClassLayout(AInfinityStagePassageActor::StaticClass()->GetFName());
            PropertyEditor.UnregisterCustomPropertyTypeLayout(TEXT("InfinitySectionMusicBinding"));
        }
        UToolMenus::UnRegisterStartupCallback(this);
        UToolMenus::UnregisterOwner(this);
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(InfinityStageCueDeskTabName);
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(InfinityStageWingAuditTabName);
        ApplyWingCorrectionsCommand.Reset();
        AuditWingAssetsCommand.Reset();
        OpenCueDeskCommand.Reset();
        CreateFixtureCommand.Reset();
    }

private:
    /**
     * Writes a dragged attachment's new position back to its cue as a relative
     * offset.
     *
     * Direct manipulation rather than a separate edit mode: the attachment actor
     * is already in the level, so moving it is the natural gesture. Storing the
     * offset rather than the world position is what makes it survive a later
     * re-space or re-fit.
     */
    void HandleActorsMoved(TArray<AActor*>& MovedActors)
    {
        UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
        if (!EditorWorld || EditorWorld->IsGameWorld() || MovedActors.IsEmpty())
        {
            return;
        }

        int32 Updated = 0;
        for (AActor* Moved : MovedActors)
        {
            if (!IsValid(Moved))
            {
                continue;
            }
            AInfinityStagePassageActor* Owner =
                Cast<AInfinityStagePassageActor>(Moved->GetAttachParentActor());
            if (!Owner || !Owner->ShowAsset)
            {
                continue;
            }
            FGuid CueGuid;
            FGuid AttachmentGuid;
            if (!Owner->FindAttachmentByActor(Moved, CueGuid, AttachmentGuid))
            {
                continue;
            }
            // A transform keyed by an open sequence is a performance, not authoring.
            {
                TSet<FName> AnimatedProperties;
                bool bTransformAnimated = false;
                FInfinityStageSequencerBridge::CollectAnimatedInOpenSequencers(
                    Moved, InfinityStageAttachmentBinding::GetAttachmentTag(Moved), AnimatedProperties, bTransformAnimated);
                if (bTransformAnimated)
                {
                    UE_LOG(LogTemp, Display,
                        TEXT("INFINITY_CAPTURE_SKIPPED_SEQUENCER actor=%s field=Transform: an open sequence keys its transform; the move is not written to the Show."),
                        *Moved->GetName());
                    continue;
                }
            }
            FTransform AnchorWorld;
            if (!Owner->GetAttachmentAnchorWorldTransform(CueGuid, AttachmentGuid, AnchorWorld))
            {
                continue;
            }

            FInfinityShowCue* Cue = Owner->ShowAsset->Cues.FindByPredicate(
                [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
            FInfinityCueAttachment* Attachment = Cue
                ? Cue->WingPair.Attachments.FindByPredicate(
                    [AttachmentGuid](const FInfinityCueAttachment& Candidate)
                    { return Candidate.AttachmentGuid == AttachmentGuid; })
                : nullptr;
            if (!Attachment)
            {
                continue;
            }
            Owner->ShowAsset->Modify();
            Attachment->RelativeTransform = Moved->GetActorTransform().GetRelativeTransform(AnchorWorld);
            ++Updated;
        }

        if (Updated > 0)
        {
            UE_LOG(
                LogTemp,
                Display,
                TEXT("INFINITY_STAGE_ATTACHMENT_MOVED updated=%d; offsets written to the Show, save it intentionally."),
                Updated);
        }
    }

    /**
     * Writes a Details-panel edit on a placed attachment light back to its cue:
     * the light settings (strength, colour, cones, shadows, light function...)
     * and, for values typed into Transform, the relative offset as well. Gizmo
     * drags already arrive through HandleActorsMoved; this covers everything
     * that does not move the actor.
     */
    void HandleObjectPropertyChanged(UObject* Object, FPropertyChangedEvent& Event)
    {
        if (!Object || Event.ChangeType == EPropertyChangeType::Interactive)
        {
            return;
        }
        AActor* Actor = Cast<AActor>(Object);
        if (!Actor)
        {
            if (const UActorComponent* Component = Cast<UActorComponent>(Object))
            {
                Actor = Component->GetOwner();
            }
        }
        if (!Actor || !Actor->GetWorld() || Actor->GetWorld()->IsGameWorld())
        {
            return;
        }
        AInfinityStagePassageActor* Owner = Cast<AInfinityStagePassageActor>(Actor->GetAttachParentActor());
        if (!Owner || !Owner->ShowAsset)
        {
            return;
        }
        FGuid CueGuid;
        FGuid AttachmentGuid;
        if (!Owner->FindAttachmentByActor(Actor, CueGuid, AttachmentGuid))
        {
            return;
        }
        FInfinityShowCue* Cue = Owner->ShowAsset->Cues.FindByPredicate(
            [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
        FInfinityCueAttachment* Attachment = Cue
            ? Cue->WingPair.Attachments.FindByPredicate(
                [AttachmentGuid](const FInfinityCueAttachment& Candidate)
                { return Candidate.AttachmentGuid == AttachmentGuid; })
            : nullptr;
        if (!Attachment || Attachment->Kind != EInfinityAttachmentKind::Light)
        {
            return;
        }

        // Cueing plan, Part 4: a lamp keyed by an open sequence shows KEYED values.
        // Hand edits must still author the Show, but a keyed value must never be
        // written as authored, so each animated setting keeps its authored value.
        TSet<FName> AnimatedProperties;
        bool bTransformAnimated = false;
        const bool bSequencerBound = FInfinityStageSequencerBridge::CollectAnimatedInOpenSequencers(
            Actor, InfinityStageAttachmentBinding::GetAttachmentTag(Actor), AnimatedProperties, bTransformAnimated);

        FInfinityStageLightSettings Captured = Attachment->Lighting;
        if (!AInfinityStagePassageActor::CaptureAttachmentLightSettings(*Actor, Captured))
        {
            return;
        }
        if (bSequencerBound)
        {
            FString Unmapped;
            if (!InfinityStageAttachmentBinding::RestoreAnimatedLightFields(Captured, Attachment->Lighting, AnimatedProperties, Unmapped))
            {
                UE_LOG(LogTemp, Display,
                    TEXT("INFINITY_CAPTURE_SKIPPED_SEQUENCER actor=%s unmapped=%s: an open sequence keys a setting the capture cannot separate; nothing written. Close that sequence to author this lamp."),
                    *Actor->GetName(), *Unmapped);
                return;
            }
            if (!AnimatedProperties.IsEmpty() || bTransformAnimated)
            {
                TArray<FString> Withheld;
                for (const FName& Name : AnimatedProperties)
                {
                    Withheld.Add(Name.ToString());
                }
                if (bTransformAnimated)
                {
                    Withheld.Add(TEXT("Transform"));
                }
                UE_LOG(LogTemp, Display,
                    TEXT("INFINITY_CAPTURE_WITHHELD actor=%s fields=%s: keyed by an open sequence, these keep their authored Show values; everything else below is written."),
                    *Actor->GetName(), *FString::Join(Withheld, TEXT(",")));
            }
        }
        FTransform AnchorWorld;
        const bool bHaveAnchor = !bTransformAnimated
            && Owner->GetAttachmentAnchorWorldTransform(CueGuid, AttachmentGuid, AnchorWorld);

        Owner->ShowAsset->Modify();
        Attachment->Lighting = Captured;
        if (bHaveAnchor)
        {
            Attachment->RelativeTransform = Actor->GetActorTransform().GetRelativeTransform(AnchorWorld);
        }
        UE_LOG(
            LogTemp,
            Display,
            TEXT("INFINITY_STAGE_ATTACHMENT_LIGHT_UPDATED cue=%s attachment='%s' property=%s intensity=%.3f; written to the Show, save it intentionally."),
            *Cue->Label.ToString(),
            *Attachment->Label.ToString(),
            Event.Property ? *Event.Property->GetName() : TEXT("?"),
            Captured.Intensity);
    }

    /**
     * A generated attachment actor is a direct editor representation of its Show
     * record. Deleting a generated light therefore removes that one Light
     * attachment from the authoritative Show, just as moving or editing it writes
     * its changed values back. Passage rematerialization strips the identity tag
     * before its own internal destroys, so only an artist deletion reaches here.
     */
    void HandleLevelActorDeleted(AActor* Actor)
    {
        UWorld* World = Actor ? Actor->GetWorld() : nullptr;
        if (!Actor || !World || World->IsGameWorld())
        {
            return;
        }

        AInfinityStagePassageActor* Owner =
            Cast<AInfinityStagePassageActor>(Actor->GetAttachParentActor());
        if (!Owner)
        {
            // Some editor deletion paths detach first and broadcast second. The
            // Passage's ownership array still identifies the authoritative owner.
            for (TActorIterator<AInfinityStagePassageActor> It(World); It; ++It)
            {
                if (It->ManagedAttachmentActors.Contains(Actor))
                {
                    Owner = *It;
                    break;
                }
            }
        }
        if (!Owner || Owner->IsActorBeingDestroyed() || !Owner->ShowAsset)
        {
            return;
        }

        FGuid CueGuid;
        FGuid AttachmentGuid;
        if (!Owner->FindAttachmentByActor(Actor, CueGuid, AttachmentGuid))
        {
            return;
        }
        FInfinityShowCue* Cue = Owner->ShowAsset->Cues.FindByPredicate(
            [CueGuid](const FInfinityShowCue& Candidate)
            { return Candidate.CueGuid == CueGuid; });
        if (!Cue || Cue->Type != EInfinityCueType::WingPair)
        {
            return;
        }
        const int32 AttachmentIndex = Cue->WingPair.Attachments.IndexOfByPredicate(
            [AttachmentGuid](const FInfinityCueAttachment& Candidate)
            { return Candidate.AttachmentGuid == AttachmentGuid; });
        if (!Cue->WingPair.Attachments.IsValidIndex(AttachmentIndex)
            || Cue->WingPair.Attachments[AttachmentIndex].Kind != EInfinityAttachmentKind::Light)
        {
            return;
        }

        const FString CueLabel = Cue->Label.ToString();
        const FString AttachmentLabel = Cue->WingPair.Attachments[AttachmentIndex].Label.ToString();
        Owner->ShowAsset->Modify();
        Owner->Modify();
        Cue->WingPair.Attachments.RemoveAt(AttachmentIndex);
        Owner->ManagedAttachmentActors.Remove(Actor);
        UE_LOG(
            LogTemp,
            Display,
            TEXT("INFINITY_STAGE_ATTACHMENT_LIGHT_DELETED cue='%s' attachment='%s'; removed from the Show, save it intentionally."),
            *CueLabel,
            *AttachmentLabel);
    }

    void HandleEndPIE(bool bWasSimulatingInEditor)
    {
        CleanupEditorShadowCatChildren(TEXT("EndPIE"));
    }

    void HandleMapOpened(const FString& Filename, bool bAsTemplate)
    {
        CleanupEditorShadowCatChildren(TEXT("MapOpened"));
    }

    void CreateVerticalSlice()
    {
        FString MusicRoot;
        FParse::Value(FCommandLine::Get(), TEXT("InfinityStageMusicRoot="), MusicRoot);
        FString Report;
        if (!FInfinityStageDevFixtureBuilder::Build(MusicRoot, Report))
        {
            UE_LOG(LogTemp, Error, TEXT("Infinity Stage fixture failed: %s"), *Report);
            return;
        }
        UE_LOG(LogTemp, Display, TEXT("Infinity Stage fixture: %s"), *Report);
    }

    TSharedRef<SDockTab> SpawnCueDeskTab(const FSpawnTabArgs& Args)
    {
        FString InitialShowPath;
        UInfinityStageShowAsset* InitialShow = nullptr;
        if (FParse::Value(FCommandLine::Get(), TEXT("InfinityStageCueDeskShow="), InitialShowPath))
        {
            InitialShow = LoadObject<UInfinityStageShowAsset>(nullptr, *InitialShowPath);
        }
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
            [
                SNew(SInfinityStageCueDesk)
                .InitialShowAsset(InitialShow)
            ];
    }

    TSharedRef<SDockTab> SpawnWingAuditTab(const FSpawnTabArgs& Args)
    {
        return SNew(SDockTab)
            .TabRole(ETabRole::NomadTab)
            [
                SNew(SInfinityStageWingAudit)
            ];
    }

    void AuditWingAssets()
    {
        UInfinityStageWingLibraryAsset* Library = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
        FInfinityWingAuditSummary Summary;
        FString Error;
        const bool bSucceeded = Library && FInfinityStageWingAssetAuditor::Scan(*Library, Summary, Error);
        UE_LOG(LogTemp, Display, TEXT("Infinity Stage Wing Audit: %s · %s"), *Summary.ToString(), *Error);
        if (!bSucceeded)
        {
            UE_LOG(LogTemp, Error, TEXT("Infinity Stage Wing Audit failed: %s"), *Error);
        }
    }

    void ApplyWingCorrections()
    {
        UInfinityStageWingLibraryAsset* Library = FInfinityStageWingAssetAuditor::LoadOrCreateDefaultLibrary();
        FInfinityWingAuditSummary Summary;
        FString Error;
        if (!Library || !FInfinityStageWingAssetAuditor::Scan(*Library, Summary, Error)
            || !FInfinityStageWingAssetAuditor::ApplySafeCorrections(*Library, Summary, Error))
        {
            UE_LOG(LogTemp, Error, TEXT("Infinity Stage Wing correction failed: %s"), *Error);
            return;
        }
        UE_LOG(LogTemp, Display, TEXT("Infinity Stage Wing correction complete: %s"), *Summary.ToString());
    }

    void RegisterMenus()
    {
        FToolMenuOwnerScoped OwnerScoped(this);
        UToolMenu* Menu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Window"));
        FToolMenuSection& Section = Menu->FindOrAddSection(TEXT("InfinityStage"));
        Section.AddMenuEntry(
            TEXT("OpenInfinityStageCueDesk"),
            NSLOCTEXT("InfinityStage", "OpenCueDeskMenu", "Infinity Stage Cue Desk"),
            NSLOCTEXT("InfinityStage", "OpenCueDeskMenuTooltip", "Open the resizable Infinity Stage cueing workspace."),
            FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("LevelEditor.Tabs.Sequencer")),
            FUIAction(FExecuteAction::CreateLambda([]()
            {
                FGlobalTabmanager::Get()->TryInvokeTab(InfinityStageCueDeskTabName);
            }))); 
        Section.AddMenuEntry(
            TEXT("OpenInfinityStageWingAudit"),
            NSLOCTEXT("InfinityStage", "OpenWingAuditMenu", "Infinity Stage Wing Assets"),
            NSLOCTEXT("InfinityStage", "OpenWingAuditMenuTooltip", "Open the resizable wing asset audit and correction library."),
            FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("ClassIcon.StaticMesh")),
            FUIAction(FExecuteAction::CreateLambda([]()
            {
                FGlobalTabmanager::Get()->TryInvokeTab(InfinityStageWingAuditTabName);
            })));
    }

    TUniquePtr<FAutoConsoleCommand> CreateFixtureCommand;
    TUniquePtr<FAutoConsoleCommand> OpenCueDeskCommand;
    TUniquePtr<FAutoConsoleCommand> AuditWingAssetsCommand;
    TUniquePtr<FAutoConsoleCommand> ApplyWingCorrectionsCommand;
    FDelegateHandle TrackEditorHandle;
    FDelegateHandle ActorsMovedHandle;
    FDelegateHandle ObjectPropertyChangedHandle;
    FDelegateHandle LevelActorDeletedHandle;
    FDelegateHandle EndPIEHandle;
    FDelegateHandle MapOpenedHandle;
};

IMPLEMENT_MODULE(FInfinityStageEditorModule, InfinityStageEditor)
