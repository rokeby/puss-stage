#include "InfinityStageSceneHandoffBuilder.h"

#include "CineCameraActor.h"
#include "CineCameraComponent.h"
#include "Camera/CameraComponent.h"
#include "EngineUtils.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneObjectBindingID.h"
#include "Sections/MovieSceneCameraCutSection.h"
#include "Tracks/MovieSceneCameraCutTrack.h"
#include "Tracks/MovieScene3DTransformTrack.h"
#include "Sections/MovieScene3DTransformSection.h"
#include "Channels/MovieSceneDoubleChannel.h"
#include "UniversalObjectLocatorResolveParams.h"

namespace
{
ACineCameraActor* ResolveCutCamera(
    ULevelSequence& Sequence,
    UWorld& World,
    const UMovieSceneCameraCutSection& Cut)
{
    if (!Cut.GetCameraBindingID().IsValid())
    {
        return nullptr;
    }
    TArray<UObject*, TInlineAllocator<1>> BoundObjects;
    Sequence.LocateBoundObjects(
        Cut.GetCameraBindingID().GetGuid(),
        UE::UniversalObjectLocator::FResolveParams(&World),
        nullptr,
        BoundObjects);
    for (UObject* Object : BoundObjects)
    {
        if (ACineCameraActor* Camera = Cast<ACineCameraActor>(Object))
        {
            return Camera;
        }
        if (const UCameraComponent* Component = Cast<UCameraComponent>(Object))
        {
            if (ACineCameraActor* Camera = Cast<ACineCameraActor>(Component->GetOwner()))
            {
                return Camera;
            }
        }
    }
    return nullptr;
}

FGuid BindCamera(ULevelSequence& Sequence, UWorld& World, ACineCameraActor& Camera)
{
    UMovieScene* MovieScene = Sequence.GetMovieScene();
    const FGuid Guid = MovieScene->AddPossessable(Camera.GetActorLabel(), Camera.GetClass());
    Sequence.BindPossessableObject(Guid, Camera, &World);
    return Guid;
}

ACineCameraActor* SpawnHandoffCamera(
    UWorld& World,
    const FTransform& Transform,
    const FString& Label,
    const TCHAR* RoleTag)
{
    ACineCameraActor* Camera = World.SpawnActor<ACineCameraActor>(
        Transform.GetLocation(),
        Transform.Rotator());
    if (Camera)
    {
        Camera->SetActorScale3D(Transform.GetScale3D());
        Camera->SetActorLabel(Label);
        Camera->Tags.AddUnique(TEXT("InfinityStage.SceneHandoff"));
        Camera->Tags.AddUnique(FName(RoleTag));
        Camera->Modify();
    }
    return Camera;
}

bool HasCameraTag(const ACineCameraActor* Camera, const FName Tag)
{
    return Camera && Camera->Tags.Contains(Tag);
}

bool LooksLikeHandoffCamera(const ACineCameraActor* Camera, const TCHAR* Role, const FString& CueLabel)
{
    if (!Camera)
    {
        return false;
    }

    const FName SceneEntryTag = TEXT("InfinityStage.SceneEntry");
    const FName SceneExitTag = TEXT("InfinityStage.SceneExit");
    const bool bIsEntry = FCString::Strcmp(Role, TEXT("Entry")) == 0;
    const FName SceneHandoffTag = TEXT("InfinityStage.SceneHandoff");
    if (Camera->Tags.Contains(SceneHandoffTag)
        && (Camera->Tags.Contains(bIsEntry ? SceneEntryTag : SceneExitTag)))
    {
        return true;
    }

    const FString Label = Camera->GetActorLabel();
    const FString Needle = FString::Printf(TEXT("%s — %s Handoff Camera"), *CueLabel, Role);
    return Label.Contains(Needle)
        || ((FCString::Strcmp(Role, TEXT("Entry")) == 0) && Label.Contains(TEXT("Entry Handoff Camera")))
        || ((FCString::Strcmp(Role, TEXT("Exit")) == 0) && Label.Contains(TEXT("Exit Handoff Camera")));
}

void CopyCameraView(
    const AInfinityStageCameraRig& Source,
    const FTransform& SourceTransform,
    const float FocalLengthMm,
    const float FocusDistanceCm,
    ACineCameraActor& Destination)
{
    Destination.Modify();
    Destination.SetActorTransform(SourceTransform);
    const UCineCameraComponent* SourceCamera = Source.Camera;
    UCineCameraComponent* DestinationCamera = Destination.GetCineCameraComponent();
    if (!SourceCamera || !DestinationCamera)
    {
        return;
    }
    DestinationCamera->Modify();
    DestinationCamera->SetFilmback(SourceCamera->Filmback);
    DestinationCamera->SetLensSettings(SourceCamera->LensSettings);
    FCameraFocusSettings FocusSettings = SourceCamera->FocusSettings;
    FocusSettings.FocusMethod = ECameraFocusMethod::Manual;
    FocusSettings.ManualFocusDistance = FocusDistanceCm;
    DestinationCamera->SetFocusSettings(FocusSettings);
    DestinationCamera->SetCurrentFocalLength(FocalLengthMm);
    DestinationCamera->SetCurrentAperture(SourceCamera->CurrentAperture);
}

void CopyCameraView(const ACineCameraActor& Source, ACineCameraActor& Destination)
{
    Destination.Modify();
    Destination.SetActorTransform(Source.GetActorTransform());
    const UCineCameraComponent* SourceCamera = Source.GetCineCameraComponent();
    UCineCameraComponent* DestinationCamera = Destination.GetCineCameraComponent();
    if (!SourceCamera || !DestinationCamera)
    {
        return;
    }
    DestinationCamera->Modify();
    DestinationCamera->SetFilmback(SourceCamera->Filmback);
    DestinationCamera->SetLensSettings(SourceCamera->LensSettings);
    DestinationCamera->SetFocusSettings(SourceCamera->FocusSettings);
    DestinationCamera->SetCurrentFocalLength(SourceCamera->CurrentFocalLength);
    DestinationCamera->SetCurrentAperture(SourceCamera->CurrentAperture);
}

AInfinityStageCameraRig* FindPassageCamera(UWorld& World, const FGuid PassageGuid)
{
    for (TActorIterator<AInfinityStageCameraRig> It(&World); It; ++It)
    {
        if (It->PassageActor && It->PassageActor->PassageGuid == PassageGuid)
        {
            return *It;
        }
    }
    return nullptr;
}

bool MatchOneScene(
    UInfinityStageShowAsset& Show,
    UWorld& World,
    FInfinityShowCue& Cue,
    const FInfinityCompileResult& Compiled,
    int32& OutCreatedCameras,
    FString& OutError)
{
    const int32 SegmentIndex = Compiled.Segments.IndexOfByPredicate([&Cue](const FInfinityCompiledSegment& Segment)
    {
        return Segment.SegmentGuid == Cue.CueGuid;
    });
    if (!Compiled.Segments.IsValidIndex(SegmentIndex - 1)
        || Compiled.Segments[SegmentIndex - 1].Type != EInfinityCueType::WingPair)
    {
        OutError = FString::Printf(TEXT("%s has no incoming Passage."), *Cue.Label.ToString());
        return false;
    }

    const FInfinityCompiledSegment& IncomingSegment = Compiled.Segments[SegmentIndex - 1];
    bool bRetainedExit = false;
    const FInfinityCompiledSegment* OutgoingSegment = nullptr;
    if (Compiled.Segments.IsValidIndex(SegmentIndex + 1))
    {
        const FInfinityCompiledSegment& Following = Compiled.Segments[SegmentIndex + 1];
        if (Following.Type == EInfinityCueType::WingPair)
        {
            OutgoingSegment = &Following;
        }
        else if (Show.Cues.IsValidIndex(Following.FirstCueIndex)
            && Show.Cues[Following.FirstCueIndex].Scene.bRetainPreviousCamera)
        {
            bRetainedExit = true;
            if (Compiled.Segments.IsValidIndex(SegmentIndex + 2)
                && Compiled.Segments[SegmentIndex + 2].Type == EInfinityCueType::WingPair)
            {
                OutgoingSegment = &Compiled.Segments[SegmentIndex + 2];
            }
        }
    }
    if (!bRetainedExit && !OutgoingSegment)
    {
        OutError = FString::Printf(TEXT("%s has neither an outgoing Passage nor a retained-camera interstitial."), *Cue.Label.ToString());
        return false;
    }

    AInfinityStageCameraRig* IncomingCamera = FindPassageCamera(World, IncomingSegment.SegmentGuid);
    AInfinityStageCameraRig* OutgoingCamera = OutgoingSegment
        ? FindPassageCamera(World, OutgoingSegment->SegmentGuid)
        : nullptr;
    FTransform IncomingTransform;
    FTransform OutgoingTransform;
    float IncomingFocalLength = 35.0f;
    float IncomingFocusDistance = 100000.0f;
    float OutgoingFocalLength = 35.0f;
    float OutgoingFocusDistance = 100000.0f;
    if (!IncomingCamera
        || !IncomingCamera->GetCameraViewAtMasterFrame(
            IncomingSegment.EndFrame, IncomingTransform, IncomingFocalLength, IncomingFocusDistance))
    {
        OutError = FString::Printf(TEXT("%s cannot resolve its incoming Passage camera."), *Cue.Label.ToString());
        return false;
    }
    if (!bRetainedExit
        && (!OutgoingCamera
            || !OutgoingCamera->GetCameraViewAtMasterFrame(
                OutgoingSegment->StartFrame, OutgoingTransform, OutgoingFocalLength, OutgoingFocusDistance)))
    {
        OutError = FString::Printf(TEXT("%s cannot resolve its outgoing Passage camera."), *Cue.Label.ToString());
        return false;
    }

    ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    if (!Sequence || !MovieScene)
    {
        OutError = FString::Printf(TEXT("%s has no usable Level Sequence."), *Cue.Label.ToString());
        return false;
    }
    Sequence->Modify();
    MovieScene->Modify();
    const FFrameNumber SceneStart = MovieScene->GetPlaybackRange().GetLowerBoundValue();
    const FFrameNumber SceneEnd = MovieScene->GetPlaybackRange().GetUpperBoundValue();
    if (SceneEnd <= SceneStart)
    {
        OutError = FString::Printf(TEXT("%s has an empty playback range."), *Cue.Label.ToString());
        return false;
    }

    UMovieSceneCameraCutTrack* CutTrack = Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack());
    if (!CutTrack)
    {
        CutTrack = Cast<UMovieSceneCameraCutTrack>(
            MovieScene->AddCameraCutTrack(UMovieSceneCameraCutTrack::StaticClass()));
    }
    if (!CutTrack)
    {
        OutError = FString::Printf(TEXT("%s cannot create a Camera Cut Track."), *Cue.Label.ToString());
        return false;
    }
    CutTrack->Modify();
    CutTrack->SetIsAutoManagingSections(false);
    CutTrack->bCanBlend = false;

    TArray<UMovieSceneCameraCutSection*> Cuts;
    for (UMovieSceneSection* Section : CutTrack->GetAllSections())
    {
        if (UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(Section))
        {
            Cuts.Add(Cut);
        }
    }
    Cuts.Sort([](const UMovieSceneCameraCutSection& A, const UMovieSceneCameraCutSection& B)
    {
        return A.GetInclusiveStartFrame() < B.GetInclusiveStartFrame();
    });

    ACineCameraActor* EntryCamera = nullptr;
    ACineCameraActor* ExitCamera = nullptr;
    UMovieSceneCameraCutSection* EntryCut = nullptr;
    UMovieSceneCameraCutSection* ExitCut = nullptr;
    const FString CueLabel = Cue.Label.ToString();
    for (UMovieSceneCameraCutSection* Section : Cuts)
    {
        ACineCameraActor* CutCamera = ResolveCutCamera(*Sequence, World, *Section);
        if (LooksLikeHandoffCamera(CutCamera, TEXT("Entry"), CueLabel))
        {
            EntryCamera = CutCamera;
            EntryCut = Section;
        }
        else if (LooksLikeHandoffCamera(CutCamera, TEXT("Exit"), CueLabel))
        {
            ExitCamera = CutCamera;
            ExitCut = Section;
        }
    }

    const FString FallbackEntryName = FString::Printf(TEXT("%s — Entry Handoff Camera"), *CueLabel);
    const FString FallbackExitName = FString::Printf(TEXT("%s — Exit Handoff Camera"), *CueLabel);
    if (!EntryCamera)
    {
        EntryCamera = SpawnHandoffCamera(
            World,
            IncomingTransform,
            FallbackEntryName,
            TEXT("InfinityStage.SceneEntry"));
        if (!EntryCamera)
        {
            OutError = FString::Printf(TEXT("%s cannot create its Entry camera."), *Cue.Label.ToString());
            return false;
        }
        ++OutCreatedCameras;
        const FGuid EntryGuid = BindCamera(*Sequence, World, *EntryCamera);
        EntryCut = CutTrack->AddNewCameraCut(
            FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(EntryGuid)),
            SceneStart);
        Cuts.Reset();
        for (UMovieSceneSection* Section : CutTrack->GetAllSections())
        {
            if (UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(Section)) Cuts.Add(Cut);
        }
        Cuts.Sort([](const UMovieSceneCameraCutSection& A, const UMovieSceneCameraCutSection& B)
        {
            return A.GetInclusiveStartFrame() < B.GetInclusiveStartFrame();
        });
    }

    if (!ExitCamera || ExitCamera == EntryCamera)
    {
        ExitCamera = SpawnHandoffCamera(
            World,
            bRetainedExit ? IncomingTransform : OutgoingTransform,
            FallbackExitName,
            TEXT("InfinityStage.SceneExit"));
        if (!ExitCamera)
        {
            OutError = FString::Printf(TEXT("%s cannot create its Exit camera."), *Cue.Label.ToString());
            return false;
        }
        ++OutCreatedCameras;
        const FGuid ExitGuid = BindCamera(*Sequence, World, *ExitCamera);
        const int32 AvailableFrames = SceneEnd.Value - SceneStart.Value;
        const int32 RequestedHold = FMath::Max(1, Cue.Scene.ExitHandoffHoldFrames.Value);
        const FFrameNumber ExitStart(SceneEnd.Value - FMath::Min(RequestedHold, FMath::Max(1, AvailableFrames - 1)));
        ExitCut = CutTrack->AddNewCameraCut(
            FMovieSceneObjectBindingID(UE::MovieScene::FRelativeObjectBindingID(ExitGuid)),
            ExitStart);
    }

    EntryCamera->Tags.AddUnique(TEXT("InfinityStage.SceneHandoff"));
    ExitCamera->Tags.AddUnique(TEXT("InfinityStage.SceneHandoff"));
    EntryCamera->Tags.AddUnique(TEXT("InfinityStage.SceneEntry"));
    ExitCamera->Tags.AddUnique(TEXT("InfinityStage.SceneExit"));
    EntryCamera->SetActorLabel(FString::Printf(TEXT("%s — Entry Handoff Camera"), *Cue.Label.ToString()));
    ExitCamera->SetActorLabel(FString::Printf(TEXT("%s — Exit Handoff Camera"), *Cue.Label.ToString()));
    if (bRetainedExit)
    {
        ExitCamera->Tags.AddUnique(TEXT("InfinityStage.SceneRetainedHold"));
    }
    else
    {
        ExitCamera->Tags.Remove(TEXT("InfinityStage.SceneRetainedHold"));
    }

    const int32 SceneStartValue = SceneStart.Value;
    const int32 SceneEndValue = SceneEnd.Value;
    const int32 SceneLength = FMath::Max(1, SceneEndValue - SceneStartValue);
    int32 FirstInteriorStart = SceneEndValue;
    int32 LastInteriorEnd = SceneStartValue;
    int32 LastInteriorStart = SceneStartValue - 1;
    ACineCameraActor* LastInteriorCamera = nullptr;

    for (UMovieSceneSection* Section : CutTrack->GetAllSections())
    {
        UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(Section);
        if (!Cut || Cut == EntryCut || Cut == ExitCut)
        {
            continue;
        }
        ACineCameraActor* CutCamera = ResolveCutCamera(*Sequence, World, *Cut);
        if (LooksLikeHandoffCamera(CutCamera, TEXT("Entry"), CueLabel)
            || LooksLikeHandoffCamera(CutCamera, TEXT("Exit"), CueLabel))
        {
            continue;
        }
        const int32 CutStart = Cut->GetInclusiveStartFrame().Value;
        const int32 CutEnd = Cut->GetExclusiveEndFrame().Value;
        if (CutEnd <= SceneStartValue || CutStart >= SceneEndValue)
        {
            continue;
        }
        FirstInteriorStart = FMath::Min(FirstInteriorStart, FMath::Max(CutStart, SceneStartValue));
        LastInteriorEnd = FMath::Max(LastInteriorEnd, FMath::Min(CutEnd, SceneEndValue));
        if (CutCamera && CutStart >= LastInteriorStart)
        {
            LastInteriorStart = CutStart;
            LastInteriorCamera = CutCamera;
        }
    }

    CopyCameraView(*IncomingCamera, IncomingTransform, IncomingFocalLength, IncomingFocusDistance, *EntryCamera);
    if (bRetainedExit)
    {
        CopyCameraView(LastInteriorCamera ? *LastInteriorCamera : *EntryCamera, *ExitCamera);
    }
    else
    {
        CopyCameraView(*OutgoingCamera, OutgoingTransform, OutgoingFocalLength, OutgoingFocusDistance, *ExitCamera);
    }

    if (ExitCut)
    {
        ExitCut->Modify();
        const int32 RequestedHold = FMath::Max(1, Cue.Scene.ExitHandoffHoldFrames.Value);
        int32 ExitStart = SceneEndValue - FMath::Min(RequestedHold, FMath::Max(1, SceneLength - 1));
        if (LastInteriorEnd > SceneStartValue && LastInteriorEnd < SceneEndValue)
        {
            ExitStart = FMath::Max(ExitStart, LastInteriorEnd);
        }
        ExitStart = FMath::Min(SceneEndValue - 1, FMath::Max(SceneStartValue, ExitStart));
        ExitCut->SetStartFrame(FFrameNumber(ExitStart));
        ExitCut->SetEndFrame(SceneEnd);
    }

    if (EntryCut)
    {
        EntryCut->Modify();
        EntryCut->SetStartFrame(SceneStart);
        const int32 ExitStart = ExitCut ? ExitCut->GetInclusiveStartFrame().Value : (SceneEndValue - 1);
        int32 EntryEnd = FMath::Min(FirstInteriorStart, ExitStart);
        if (FirstInteriorStart == SceneEndValue && LastInteriorEnd == SceneStartValue)
        {
            EntryEnd = ExitStart;
        }
        EntryEnd = FMath::Clamp(EntryEnd, SceneStartValue + 1, SceneEndValue);
        EntryCut->SetEndFrame(FFrameNumber(EntryEnd));
    }
    Sequence->MarkPackageDirty();
    World.MarkPackageDirty();
    return true;
}
}

namespace
{
/** Read-only staleness comparison for one Scene. Never calls Modify(). */
bool CheckOneScene(
    const UInfinityStageShowAsset& Show,
    UWorld& World,
    const FInfinityShowCue& Cue,
    const FInfinityCompileResult& Compiled,
    FString& OutDetail)
{
    const int32 SegmentIndex = Compiled.Segments.IndexOfByPredicate([&Cue](const FInfinityCompiledSegment& Segment)
    {
        return Segment.SegmentGuid == Cue.CueGuid;
    });
    if (!Compiled.Segments.IsValidIndex(SegmentIndex - 1)
        || Compiled.Segments[SegmentIndex - 1].Type != EInfinityCueType::WingPair)
    {
        return false;
    }

    bool bRetainedExit = false;
    const FInfinityCompiledSegment* OutgoingSegment = nullptr;
    if (Compiled.Segments.IsValidIndex(SegmentIndex + 1))
    {
        const FInfinityCompiledSegment& Following = Compiled.Segments[SegmentIndex + 1];
        if (Following.Type == EInfinityCueType::WingPair)
        {
            OutgoingSegment = &Following;
        }
        else if (Show.Cues.IsValidIndex(Following.FirstCueIndex)
            && Show.Cues[Following.FirstCueIndex].Scene.bRetainPreviousCamera)
        {
            bRetainedExit = true;
        }
    }
    if (!bRetainedExit && !OutgoingSegment)
    {
        return false;
    }

    const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
    const UMovieScene* MovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
    const UMovieSceneCameraCutTrack* CutTrack = MovieScene
        ? Cast<UMovieSceneCameraCutTrack>(MovieScene->GetCameraCutTrack())
        : nullptr;
    if (!CutTrack)
    {
        return false;
    }

    // Compare the first and last cuts against the neighbouring Passage endpoints.
    TArray<UMovieSceneCameraCutSection*> Cuts;
    for (UMovieSceneSection* Section : CutTrack->GetAllSections())
    {
        if (UMovieSceneCameraCutSection* Cut = Cast<UMovieSceneCameraCutSection>(Section))
        {
            Cuts.Add(Cut);
        }
    }
    if (Cuts.IsEmpty())
    {
        return false;
    }
    Cuts.Sort([](const UMovieSceneCameraCutSection& A, const UMovieSceneCameraCutSection& B)
    {
        return A.GetInclusiveStartFrame() < B.GetInclusiveStartFrame();
    });

    struct FBoundaryCheck
    {
        const TCHAR* Role;
        UMovieSceneCameraCutSection* Cut;
        FFrameNumber PassageFrame;
        FGuid PassageGuid;
    };
    TArray<FBoundaryCheck> Boundaries;
    Boundaries.Add({
        TEXT("Entry"),
        Cuts[0],
        Compiled.Segments[SegmentIndex - 1].EndFrame,
        Compiled.Segments[SegmentIndex - 1].SegmentGuid });
    // A retained interstitial deliberately keeps the final Scene view. Its Exit
    // camera is compared when matching runs, not against the later Passage.
    if (!bRetainedExit && OutgoingSegment)
    {
        Boundaries.Add({
            TEXT("Exit"),
            Cuts.Last(),
            OutgoingSegment->StartFrame,
            OutgoingSegment->SegmentGuid });
    }

    TArray<FString> Differences;
    for (const FBoundaryCheck& Boundary : Boundaries)
    {
        ACineCameraActor* HandoffCamera = ResolveCutCamera(
            *const_cast<ULevelSequence*>(Sequence), World, *Boundary.Cut);
        if (!LooksLikeHandoffCamera(HandoffCamera, Boundary.Role, Cue.Label.ToString()))
        {
            // An artist-authored camera on that boundary is a deliberate choice,
            // not a stale handoff. Say nothing about it.
            continue;
        }
        AInfinityStageCameraRig* PassageCamera = FindPassageCamera(World, Boundary.PassageGuid);
        FTransform ExpectedTransform;
        float ExpectedFocalLength = 35.0f;
        float ExpectedFocusDistance = 100000.0f;
        if (!PassageCamera
            || !PassageCamera->GetCameraViewAtMasterFrame(
                Boundary.PassageFrame, ExpectedTransform, ExpectedFocalLength, ExpectedFocusDistance))
        {
            continue;
        }
        const UCineCameraComponent* Component = HandoffCamera->GetCineCameraComponent();
        if (!Component)
        {
            continue;
        }

        // Location and aim are compared separately. FTransform::Equals applies
        // one tolerance to translation AND to quaternion components, so the
        // former 0.5 let a handoff camera be re-aimed by up to about 60 degrees
        // without moving and still count as matched.
        const double PositionErrorCm = FVector::Distance(
            HandoffCamera->GetActorLocation(), ExpectedTransform.GetLocation());
        const double AimErrorDegrees = FMath::RadiansToDegrees(
            HandoffCamera->GetActorQuat().AngularDistance(ExpectedTransform.GetRotation()));
        if (PositionErrorCm > 0.5 || AimErrorDegrees > 0.05)
        {
            Differences.Add(FString::Printf(
                TEXT("%s transform (%.2f cm, %.2f deg)"),
                Boundary.Role,
                PositionErrorCm,
                AimErrorDegrees));
        }
        if (!FMath::IsNearlyEqual(Component->CurrentFocalLength, ExpectedFocalLength, 0.01f))
        {
            Differences.Add(FString::Printf(
                TEXT("%s focal length %.1fmm vs Passage %.1fmm"),
                Boundary.Role,
                Component->CurrentFocalLength,
                ExpectedFocalLength));
        }
        if (!FMath::IsNearlyEqual(
            Component->FocusSettings.ManualFocusDistance, ExpectedFocusDistance, 1.0f))
        {
            Differences.Add(FString::Printf(TEXT("%s focus distance"), Boundary.Role));
        }
    }

    if (Differences.IsEmpty())
    {
        return false;
    }
    OutDetail = FString::Printf(
        TEXT("%s: %s"),
        *Cue.Label.ToString(),
        *FString::Join(Differences, TEXT(", ")));
    return true;
}
}

/**
 * Whether a Scene's cut cameras carry keyed rotation.
 *
 * Reported, never enforced: a Scene with authored camera rotation and dog look
 * enabled means two things writing the same orientation. Usually a mistake, but
 * the artist may know better, so this informs rather than blocks.
 */
bool SceneHasKeyedCameraRotation(const UMovieScene& MovieScene)
{
    const UMovieSceneCameraCutTrack* CutTrack =
        Cast<UMovieSceneCameraCutTrack>(MovieScene.GetCameraCutTrack());
    if (!CutTrack)
    {
        return false;
    }
    TSet<FGuid> CameraBindings;
    for (const UMovieSceneSection* Section : CutTrack->GetAllSections())
    {
        if (const UMovieSceneCameraCutSection* Cut = Cast<const UMovieSceneCameraCutSection>(Section))
        {
            CameraBindings.Add(Cut->GetCameraBindingID().GetGuid());
        }
    }

    for (const FMovieSceneBinding& Binding : MovieScene.GetBindings())
    {
        if (!CameraBindings.Contains(Binding.GetObjectGuid()))
        {
            continue;
        }
        for (const UMovieSceneTrack* Track : Binding.GetTracks())
        {
            const UMovieScene3DTransformTrack* TransformTrack =
                Cast<const UMovieScene3DTransformTrack>(Track);
            if (!TransformTrack)
            {
                continue;
            }
            for (const UMovieSceneSection* Section : TransformTrack->GetAllSections())
            {
                const UMovieScene3DTransformSection* Transform =
                    Cast<const UMovieScene3DTransformSection>(Section);
                if (!Transform)
                {
                    continue;
                }
                const FMovieSceneChannelProxy& Proxy = Transform->GetChannelProxy();
                // Channels 3, 4, 5 are rotation X/Y/Z on a transform section.
                for (int32 ChannelIndex = 3; ChannelIndex <= 5; ++ChannelIndex)
                {
                    const FMovieSceneDoubleChannel* Channel =
                        Proxy.GetChannel<FMovieSceneDoubleChannel>(ChannelIndex);
                    if (Channel && Channel->GetNumKeys() > 0)
                    {
                        return true;
                    }
                }
            }
        }
    }
    return false;
}

bool FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(
    UInfinityStageShowAsset& Show,
    UWorld& World,
    const TArray<FGuid>& SceneCueGuids,
    TArray<FGuid>& OutStaleSceneGuids,
    FString& OutReport)
{
    OutStaleSceneGuids.Reset();
    OutReport.Reset();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(Show);
    if (Compiled.HasErrors())
    {
        OutReport = TEXT("The Show must compile before camera handoffs can be checked.");
        return false;
    }

    int32 CheckedScenes = 0;
    TArray<FString> Details;
    for (const FInfinityShowCue& Cue : Show.Cues)
    {
        if (!Cue.bEnabled || Cue.Type != EInfinityCueType::Scene
            || (!SceneCueGuids.IsEmpty() && !SceneCueGuids.Contains(Cue.CueGuid)))
        {
            continue;
        }
        ++CheckedScenes;
        FString Detail;
        if (CheckOneScene(Show, World, Cue, Compiled, Detail))
        {
            OutStaleSceneGuids.Add(Cue.CueGuid);
            Details.Add(Detail);
        }

        // Advisory only: two things writing one orientation is usually a
        // mistake, but the artist decides.
        if (Cue.Scene.CameraOwner != EInfinityCameraOwner::Timeline)
        {
            const ULevelSequence* Sequence = Cue.Scene.Sequence.LoadSynchronous();
            const UMovieScene* SceneMovieScene = Sequence ? Sequence->GetMovieScene() : nullptr;
            if (SceneMovieScene && SceneHasKeyedCameraRotation(*SceneMovieScene))
            {
                Details.Add(FString::Printf(
                    TEXT("%s: dog look is enabled and its cut camera also has keyed rotation — they will fight unless the "
                         "rotation is meant as a base the dog looks around from"),
                    *Cue.Label.ToString()));
            }
        }
    }

    OutReport = OutStaleSceneGuids.IsEmpty()
        ? FString::Printf(TEXT("All %d checked Scene handoff camera(s) match their authored boundary policy."), CheckedScenes)
        : FString::Printf(
            TEXT("%d of %d Scene(s) no longer match their authored boundary policy — %s. Run Match to resync, or keep the difference if the cut is deliberate."),
            OutStaleSceneGuids.Num(),
            CheckedScenes,
            *FString::Join(Details, TEXT("; ")));
    return true;
}

bool FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(
    UInfinityStageShowAsset& Show,
    UWorld& World,
    const TArray<FGuid>& SceneCueGuids,
    FString& OutReport)
{
    OutReport.Reset();
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(Show);
    if (Compiled.HasErrors())
    {
        OutReport = TEXT("The Show must compile before camera handoffs can be matched.");
        return false;
    }

    int32 MatchedScenes = 0;
    int32 CreatedCameras = 0;
    TArray<FString> Errors;
    for (FInfinityShowCue& Cue : Show.Cues)
    {
        if (!Cue.bEnabled || Cue.Type != EInfinityCueType::Scene
            || (!SceneCueGuids.IsEmpty() && !SceneCueGuids.Contains(Cue.CueGuid)))
        {
            continue;
        }
        FString Error;
        if (MatchOneScene(Show, World, Cue, Compiled, CreatedCameras, Error))
        {
            ++MatchedScenes;
        }
        else
        {
            Errors.Add(Error);
        }
    }

    OutReport = FString::Printf(
        TEXT("Matched %d Scene camera handoff(s), created %d missing boundary camera(s)"),
        MatchedScenes,
        CreatedCameras);
    if (!Errors.IsEmpty())
    {
        OutReport += TEXT(". ");
        OutReport += FString::Join(Errors, TEXT(" "));
    }
    else
    {
        OutReport += TEXT(". Entry views match incoming Passage endpoints; normal Exits match outgoing Passage starts; retained Exits hold the final designed Scene shot.");
    }
    return MatchedScenes > 0 && Errors.IsEmpty();
}
