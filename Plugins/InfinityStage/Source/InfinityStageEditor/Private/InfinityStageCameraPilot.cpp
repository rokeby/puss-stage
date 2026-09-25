#include "InfinityStageCameraPilot.h"

#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Editor.h"
#include "Framework/MultiBox/MultiBoxBuilder.h"
#include "Framework/Notifications/NotificationManager.h"
#include "InfinityStageCameraPilotLibrary.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageShowAsset.h"
#include "LevelEditorViewport.h"
#include "Widgets/Notifications/SNotificationList.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageCameraPilotSession, Log, All);

namespace
{
struct FPilotSession
{
    TWeakObjectPtr<ACineCameraActor> Proxy;
    TWeakObjectPtr<UInfinityStageShowAsset> Show;
    FGuid PassageGuid;
    FFrameNumber MasterFrame = 0;
    double SecondsIntoPassage = 0.0;
    FString PassageName;
    bool bPreviousLockedCameraView = true;
    FDelegateHandle PreBeginPIEHandle;
};

FPilotSession GPilot;

UWorld* GetPilotEditorWorld()
{
    return GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
}

void NotifyPilot(const FString& Message, const bool bSucceeded)
{
    FNotificationInfo Info(FText::FromString(Message));
    Info.ExpireDuration = bSucceeded ? 5.0f : 8.0f;
    Info.bUseLargeFont = false;
    const TSharedPtr<SNotificationItem> Item = FSlateNotificationManager::Get().AddNotification(Info);
    if (Item)
    {
        Item->SetCompletionState(bSucceeded ? SNotificationItem::CS_Success : SNotificationItem::CS_Fail);
    }
}

FString DescribePilotPassage(const UInfinityStageShowAsset& Show, const FGuid& PassageGuid)
{
    const FInfinityPassageSettings* Settings = Show.PassageSettings.FindByPredicate(
        [&PassageGuid](const FInfinityPassageSettings& Candidate) { return Candidate.PassageGuid == PassageGuid; });
    return Settings && !Settings->Label.IsEmpty() ? Settings->Label.ToString() : TEXT("Passage");
}

/** The viewport currently looking through the pilot camera, if any. A Camera View scrub or Sequencer can take it away. */
FLevelEditorViewportClient* FindPilotViewport()
{
    ACineCameraActor* Proxy = GPilot.Proxy.Get();
    if (!Proxy || !GEditor)
    {
        return nullptr;
    }
    for (FLevelEditorViewportClient* Client : GEditor->GetLevelViewportClients())
    {
        if (Client && Client->IsLockedToActor(Proxy))
        {
            return Client;
        }
    }
    return nullptr;
}

FLevelEditorViewportClient* ChooseViewportToPilot()
{
    if (GCurrentLevelEditingViewportClient && GCurrentLevelEditingViewportClient->IsPerspective())
    {
        return GCurrentLevelEditingViewportClient;
    }
    if (GEditor)
    {
        for (FLevelEditorViewportClient* Client : GEditor->GetLevelViewportClients())
        {
            if (Client && Client->IsPerspective())
            {
                return Client;
            }
        }
    }
    return nullptr;
}

/** Gives the pilot camera the rig's optics, so the viewport frames exactly what the Passage camera will. */
void CopyRigOptics(const AInfinityStageCameraRig& Rig, UCineCameraComponent& PilotLens, const float FocalLengthMm, const float FocusDistanceCm)
{
    if (const UCineCameraComponent* RigLens = Rig.Camera)
    {
        PilotLens.SetFilmback(RigLens->Filmback);
        PilotLens.SetLensSettings(RigLens->LensSettings);
        PilotLens.SetCropSettings(RigLens->CropSettings);
        PilotLens.SetCurrentAperture(RigLens->CurrentAperture);
        PilotLens.bConstrainAspectRatio = RigLens->bConstrainAspectRatio;
        PilotLens.PostProcessSettings = RigLens->PostProcessSettings;
        PilotLens.PostProcessBlendWeight = RigLens->PostProcessBlendWeight;
    }
    PilotLens.SetCurrentFocalLength(FocalLengthMm);
    FCameraFocusSettings Focus = PilotLens.FocusSettings;
    Focus.FocusMethod = ECameraFocusMethod::Manual;
    Focus.ManualFocusDistance = FocusDistanceCm;
    PilotLens.SetFocusSettings(Focus);
}
}

bool FInfinityStageCameraPilot::IsPiloting()
{
    return GPilot.Proxy.IsValid();
}

bool FInfinityStageCameraPilot::Begin(
    UInfinityStageShowAsset* Show,
    const FGuid& PassageGuid,
    const FFrameNumber MasterFrame,
    FString& OutReport)
{
    End();
    UWorld* World = GetPilotEditorWorld();
    if (!Show || !World || !GEditor)
    {
        OutReport = TEXT("Piloting needs an open Show and editor world.");
        return false;
    }
    if (GEditor->PlayWorld)
    {
        OutReport = TEXT("Stop PIE before piloting the Passage camera.");
        return false;
    }

    // Resolving the full anchor up front means a pilot never starts on a
    // Passage it could not key: no rig, no Master section, or a frame outside it.
    FInfinityCameraPilotAnchor Anchor;
    if (!UInfinityStageCameraPilotLibrary::ResolveAnchor(*World, *Show, PassageGuid, MasterFrame, Anchor, OutReport))
    {
        return false;
    }
    FTransform CameraWorld;
    float FocalLengthMm = 35.0f;
    float FocusDistanceCm = 100000.0f;
    if (!UInfinityStageCameraPilotLibrary::GetCameraView(*Anchor.Rig, MasterFrame, CameraWorld, FocalLengthMm, FocusDistanceCm))
    {
        OutReport = TEXT("The Passage camera does not evaluate at the playhead.");
        return false;
    }
    FLevelEditorViewportClient* Viewport = ChooseViewportToPilot();
    if (!Viewport)
    {
        OutReport = TEXT("Open a perspective Level Viewport to pilot from.");
        return false;
    }
    if (Viewport->IsLockedToCinematic())
    {
        OutReport = TEXT("Sequencer is driving this viewport through a Camera Cut. Turn off its camera-cut lock, then pilot again.");
        return false;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.ObjectFlags = RF_Transient | RF_Transactional;
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ACineCameraActor* Proxy = World->SpawnActor<ACineCameraActor>(
        CameraWorld.GetLocation(),
        CameraWorld.Rotator(),
        SpawnParameters);
    if (!Proxy || !Proxy->GetCineCameraComponent())
    {
        OutReport = TEXT("Could not spawn the pilot camera.");
        return false;
    }
    CopyRigOptics(*Anchor.Rig, *Proxy->GetCineCameraComponent(), FocalLengthMm, FocusDistanceCm);

    const double TickRate = Show->TickResolution.IsValid() ? Show->TickResolution.AsDecimal() : 24000.0;
    GPilot.Proxy = Proxy;
    GPilot.Show = Show;
    GPilot.PassageGuid = PassageGuid;
    GPilot.MasterFrame = MasterFrame;
    GPilot.SecondsIntoPassage = (MasterFrame.Value - Anchor.PassageStartFrame.Value) / TickRate;
    GPilot.PassageName = DescribePilotPassage(*Show, PassageGuid);
    Proxy->SetActorLabel(FString::Printf(TEXT("PILOT %s @ %.2fs"), *GPilot.PassageName, GPilot.SecondsIntoPassage));

    // The stage stands at the piloted moment: wings, shadow cat and follow light.
    Anchor.Rig->EvaluateAtMasterFrame(MasterFrame);

    GPilot.bPreviousLockedCameraView = Viewport->bLockedCameraView;
    Viewport->SetActorLock(Proxy);
    Viewport->bLockedCameraView = true;
    Viewport->MoveCameraToLockedActor();
    Viewport->Invalidate();

    // Selected so its Details panel is the lens control for Key Pose and Lens.
    GEditor->SelectNone(false, true, false);
    GEditor->SelectActor(Proxy, true, true, true, true);

    GPilot.PreBeginPIEHandle = FEditorDelegates::PreBeginPIE.AddLambda([](const bool)
    {
        FInfinityStageCameraPilot::End();
    });

    OutReport = FString::Printf(
        TEXT("Piloting '%s' at %.2f s. Fly the Level Viewport, then Key Piloted Pose. Nothing is written until you key."),
        *GPilot.PassageName,
        GPilot.SecondsIntoPassage);
    UE_LOG(
        LogInfinityStageCameraPilotSession,
        Display,
        TEXT("INFINITY_CAMERA_PILOT_BEGIN|passage=%s|label=%s|frame=%d|proxy=%s|viewport_locked=%d"),
        *PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
        *GPilot.PassageName,
        MasterFrame.Value,
        *Proxy->GetName(),
        FindPilotViewport() != nullptr ? 1 : 0);
    return true;
}

bool FInfinityStageCameraPilot::KeyPilotedPose(const bool bIncludeLens, FString& OutReport)
{
    ACineCameraActor* Proxy = GPilot.Proxy.Get();
    UInfinityStageShowAsset* Show = GPilot.Show.Get();
    UWorld* World = GetPilotEditorWorld();
    UCineCameraComponent* PilotLens = Proxy ? Proxy->GetCineCameraComponent() : nullptr;
    if (!PilotLens || !Show || !World)
    {
        OutReport = TEXT("Not piloting. Choose Pilot Camera at Playhead first.");
        return false;
    }
    // Refuse rather than key a pose the artist is no longer looking at.
    if (!FindPilotViewport())
    {
        OutReport = TEXT("The viewport is no longer looking through the pilot camera (a Camera View scrub or Sequencer took it). Nothing was keyed; pilot again.");
        return false;
    }

    FInfinityCameraPilotLens Lens;
    Lens.FocalLengthMm = PilotLens->CurrentFocalLength;
    Lens.FocusDistanceCm = PilotLens->FocusSettings.ManualFocusDistance;
    return UInfinityStageCameraPilotLibrary::KeyPose(
        *World,
        *Show,
        GPilot.PassageGuid,
        GPilot.MasterFrame,
        PilotLens->GetComponentTransform(),
        bIncludeLens ? &Lens : nullptr,
        OutReport);
}

bool FInfinityStageCameraPilot::SnapToAuthoredCamera(FString& OutReport)
{
    ACineCameraActor* Proxy = GPilot.Proxy.Get();
    UInfinityStageShowAsset* Show = GPilot.Show.Get();
    UWorld* World = GetPilotEditorWorld();
    AInfinityStageCameraRig* Rig = (Show && World)
        ? UInfinityStageCameraPilotLibrary::FindCameraRig(*World, *Show, GPilot.PassageGuid)
        : nullptr;
    FTransform CameraWorld;
    float FocalLengthMm = 35.0f;
    float FocusDistanceCm = 100000.0f;
    if (!Proxy || !Proxy->GetCineCameraComponent() || !Rig
        || !UInfinityStageCameraPilotLibrary::GetCameraView(*Rig, GPilot.MasterFrame, CameraWorld, FocalLengthMm, FocusDistanceCm))
    {
        OutReport = TEXT("Not piloting a Passage camera that still evaluates.");
        return false;
    }
    Proxy->SetActorLocationAndRotation(CameraWorld.GetLocation(), CameraWorld.GetRotation());
    CopyRigOptics(*Rig, *Proxy->GetCineCameraComponent(), FocalLengthMm, FocusDistanceCm);
    if (FLevelEditorViewportClient* Viewport = FindPilotViewport())
    {
        Viewport->MoveCameraToLockedActor();
        Viewport->Invalidate();
    }
    OutReport = FString::Printf(TEXT("Pilot camera back on the authored view of '%s' at %.2f s."), *GPilot.PassageName, GPilot.SecondsIntoPassage);
    return true;
}

void FInfinityStageCameraPilot::End()
{
    if (FLevelEditorViewportClient* Viewport = FindPilotViewport())
    {
        Viewport->SetActorLock(nullptr);
        Viewport->bLockedCameraView = GPilot.bPreviousLockedCameraView;
        Viewport->Invalidate();
    }
    if (ACineCameraActor* Proxy = GPilot.Proxy.Get())
    {
        if (GEditor)
        {
            GEditor->SelectActor(Proxy, false, true);
        }
        Proxy->Destroy();
        UE_LOG(
            LogInfinityStageCameraPilotSession,
            Display,
            TEXT("INFINITY_CAMERA_PILOT_END|passage=%s|frame=%d"),
            *GPilot.PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
            GPilot.MasterFrame.Value);
    }
    if (GPilot.PreBeginPIEHandle.IsValid())
    {
        FEditorDelegates::PreBeginPIE.Remove(GPilot.PreBeginPIEHandle);
    }
    GPilot = FPilotSession();
}

void FInfinityStageCameraPilot::BuildMenu(
    FMenuBuilder& MenuBuilder,
    UInfinityStageShowAsset* Show,
    const FGuid& PassageGuid,
    const FFrameNumber PlayheadFrame)
{
    const TWeakObjectPtr<UInfinityStageShowAsset> WeakShow(Show);
    const bool bPiloting = IsPiloting();
    const FText Moment = bPiloting
        ? FText::FromString(FString::Printf(TEXT("%s @ %.2f s"), *GPilot.PassageName, GPilot.SecondsIntoPassage))
        : FText::GetEmpty();

    MenuBuilder.AddMenuEntry(
        bPiloting
            ? NSLOCTEXT("InfinityStage", "RepilotCamera", "Pilot Again at Playhead")
            : NSLOCTEXT("InfinityStage", "PilotCamera", "Pilot Camera at Playhead"),
        NSLOCTEXT(
            "InfinityStage",
            "PilotCameraTip",
            "Look through this Passage's camera at the Music Timeline playhead in the Level Viewport, with its filmback and lens. "
            "Fly it with the ordinary viewport controls. Nothing is written until you key."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([WeakShow, PassageGuid, PlayheadFrame]()
            {
                FString Report;
                const bool bStarted = FInfinityStageCameraPilot::Begin(WeakShow.Get(), PassageGuid, PlayheadFrame, Report);
                NotifyPilot(Report, bStarted);
            }),
            FCanExecuteAction::CreateLambda([WeakShow, PassageGuid]()
            {
                return WeakShow.IsValid() && PassageGuid.IsValid();
            })));

    const auto AddKeyEntry = [&MenuBuilder, &Moment, bPiloting](const FText& Label, const FText& Tip, const bool bIncludeLens)
    {
        MenuBuilder.AddMenuEntry(
            bPiloting ? FText::Format(NSLOCTEXT("InfinityStage", "PilotKeyAtMoment", "{0} ({1})"), Label, Moment) : Label,
            Tip,
            FSlateIcon(),
            FUIAction(
                FExecuteAction::CreateLambda([bIncludeLens]()
                {
                    FString Report;
                    const bool bKeyed = FInfinityStageCameraPilot::KeyPilotedPose(bIncludeLens, Report);
                    NotifyPilot(Report, bKeyed);
                }),
                FCanExecuteAction::CreateStatic(&FInfinityStageCameraPilot::IsPiloting)));
    };
    AddKeyEntry(
        NSLOCTEXT("InfinityStage", "KeyPilotedPose", "Key Piloted Pose"),
        NSLOCTEXT(
            "InfinityStage",
            "KeyPilotedPoseTip",
            "Key position and rotation so the Passage camera sees exactly the piloted view at the moment piloting began, "
            "then verify through the camera rig. Writes the managed Master sequence only, never the Show."),
        false);
    AddKeyEntry(
        NSLOCTEXT("InfinityStage", "KeyPilotedPoseAndLens", "Key Piloted Pose and Lens"),
        NSLOCTEXT(
            "InfinityStage",
            "KeyPilotedPoseAndLensTip",
            "As Key Piloted Pose, and also key Focal Length and Focus Distance from the pilot camera's Current Focal Length "
            "and Manual Focus Distance (change them on its Details panel while piloting)."),
        true);

    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "SnapPilotToAuthored", "Snap Back to Authored Camera"),
        NSLOCTEXT("InfinityStage", "SnapPilotToAuthoredTip", "Discard the unkeyed flight and look through the authored camera at the piloted moment again."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateLambda([]()
            {
                FString Report;
                const bool bSnapped = FInfinityStageCameraPilot::SnapToAuthoredCamera(Report);
                NotifyPilot(Report, bSnapped);
            }),
            FCanExecuteAction::CreateStatic(&FInfinityStageCameraPilot::IsPiloting)));
    MenuBuilder.AddMenuEntry(
        NSLOCTEXT("InfinityStage", "StopPiloting", "Stop Piloting"),
        NSLOCTEXT("InfinityStage", "StopPilotingTip", "Release the viewport and remove the transient pilot camera. Unkeyed flight is discarded."),
        FSlateIcon(),
        FUIAction(
            FExecuteAction::CreateStatic(&FInfinityStageCameraPilot::End),
            FCanExecuteAction::CreateStatic(&FInfinityStageCameraPilot::IsPiloting)));
}
