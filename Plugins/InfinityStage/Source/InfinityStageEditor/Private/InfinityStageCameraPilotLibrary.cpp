#include "InfinityStageCameraPilotLibrary.h"

#include "CineCameraComponent.h"
#include "Components/SplineComponent.h"
#include "Editor.h"
#include "EngineUtils.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStageMusicAnalysisImporter.h"
#include "InfinityStagePassageActor.h"
#include "Misc/Paths.h"
#include "InfinityStageSceneHandoffBuilder.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "Math/RotationMatrix.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "ScopedTransaction.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageCameraPilot, Log, All);

namespace
{
constexpr double PilotPositionToleranceCm = 0.01;
constexpr double PilotRotationToleranceDegrees = 0.01;
constexpr double PilotLensRelativeTolerance = 0.001;

UWorld* GetEditorWorld()
{
    return GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
}

FTransform WithoutScale(FTransform Transform)
{
    Transform.SetScale3D(FVector::OneVector);
    return Transform;
}

/** The Camera component's offset from the rig root, so a view can be mapped back to the root the channels place. */
FTransform GetCameraRelativeTransform(const AInfinityStageCameraRig& Rig)
{
    return Rig.Camera ? WithoutScale(Rig.Camera->GetRelativeTransform()) : FTransform::Identity;
}

double UnwindNear(const double Degrees, const double ReferenceDegrees)
{
    return ReferenceDegrees + FMath::UnwindDegrees(Degrees - ReferenceDegrees);
}

double AngularErrorDegrees(const FQuat& A, const FQuat& B)
{
    return FMath::RadiansToDegrees(A.AngularDistance(B));
}

bool PosesMatch(const FTransform& A, const FTransform& B)
{
    return FVector::Distance(A.GetLocation(), B.GetLocation()) <= PilotPositionToleranceCm
        && AngularErrorDegrees(A.GetRotation(), B.GetRotation()) <= PilotRotationToleranceDegrees;
}

bool LensValueMatches(const double Actual, const double Expected)
{
    return FMath::Abs(Actual - Expected) <= PilotLensRelativeTolerance * FMath::Max(1.0, FMath::Abs(Expected));
}

FString DescribePassage(const UInfinityStageShowAsset& Show, const FGuid& PassageGuid)
{
    const FInfinityPassageSettings* Settings = Show.PassageSettings.FindByPredicate(
        [&PassageGuid](const FInfinityPassageSettings& Candidate) { return Candidate.PassageGuid == PassageGuid; });
    return Settings && !Settings->Label.IsEmpty()
        ? Settings->Label.ToString()
        : PassageGuid.ToString(EGuidFormats::DigitsWithHyphens);
}

struct FPilotKey
{
    EInfinityPassageCameraChannel Channel;
    double Value;
};

/** Keys as they were before a write, so a failed read-back restores them exactly. */
struct FChannelSnapshot
{
    FMovieSceneDoubleChannel* Channel = nullptr;
    TArray<FFrameNumber> Times;
    TArray<FMovieSceneDoubleValue> Values;
};
}

AInfinityStageCameraRig* UInfinityStageCameraPilotLibrary::FindCameraRig(
    UWorld& World,
    const UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid)
{
    for (TActorIterator<AInfinityStageCameraRig> It(&World); It; ++It)
    {
        if (It->PassageActor
            && It->PassageActor->ShowAsset == &Show
            && It->PassageActor->PassageGuid == PassageGuid)
        {
            return *It;
        }
    }
    return nullptr;
}

UMovieSceneInfinityPassageSection* UInfinityStageCameraPilotLibrary::FindPassageSection(
    const UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid)
{
    ULevelSequence* Master = Show.ManagedMasterSequence.LoadSynchronous();
    UMovieScene* MovieScene = Master ? Master->GetMovieScene() : nullptr;
    UMovieSceneInfinityPassageTrack* Track = MovieScene
        ? MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>()
        : nullptr;
    if (!Track)
    {
        return nullptr;
    }
    for (UMovieSceneSection* RawSection : Track->GetAllSections())
    {
        UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(RawSection);
        if (Section && Section->PassageGuid == PassageGuid)
        {
            return Section;
        }
    }
    return nullptr;
}

bool UInfinityStageCameraPilotLibrary::ResolveAnchor(
    UWorld& World,
    const UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid,
    const FFrameNumber MasterFrame,
    FInfinityCameraPilotAnchor& OutAnchor,
    FString& OutError)
{
    OutAnchor = FInfinityCameraPilotAnchor();
    OutAnchor.MasterFrame = MasterFrame;
    const FString PassageName = DescribePassage(Show, PassageGuid);

    AInfinityStageCameraRig* Rig = FindCameraRig(World, Show, PassageGuid);
    if (!Rig || !Rig->PassageActor || !Rig->PassageActor->Route)
    {
        OutError = FString::Printf(
            TEXT("No Infinity Stage Camera Rig in world '%s' drives Passage '%s' of this Show."),
            *World.GetName(),
            *PassageName);
        return false;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(Show);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
        [&PassageGuid](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == PassageGuid; });
    if (!Passage)
    {
        OutError = FString::Printf(TEXT("Passage '%s' does not compile, so it has no camera to key."), *PassageName);
        return false;
    }
    if (MasterFrame < Passage->SegmentStartFrame || MasterFrame > Passage->SegmentEndFrame)
    {
        OutError = FString::Printf(
            TEXT("Master frame %d is outside Passage '%s' (%d to %d)."),
            MasterFrame.Value,
            *PassageName,
            Passage->SegmentStartFrame.Value,
            Passage->SegmentEndFrame.Value);
        return false;
    }

    UMovieSceneInfinityPassageSection* Section = FindPassageSection(Show, PassageGuid);
    if (!Section)
    {
        OutError = FString::Printf(
            TEXT("The managed Master has no Passage section for '%s'. Rebuild the Master before keying its camera."),
            *PassageName);
        return false;
    }

    FInfinityPassageCameraEvaluation Evaluation;
    Evaluation.DistanceMasterFrame = FFrameTime(MasterFrame);
    if (!Section->EvaluateCamera(*Passage, FFrameTime(MasterFrame), Evaluation))
    {
        OutError = FString::Printf(TEXT("Passage '%s' camera does not evaluate at frame %d."), *PassageName, MasterFrame.Value);
        return false;
    }

    OutAnchor.Rig = Rig;
    OutAnchor.Section = Section;
    OutAnchor.PassageStartFrame = Passage->SegmentStartFrame;
    OutAnchor.PassageEndFrame = Passage->SegmentEndFrame;
    OutAnchor.RouteDistanceCm = FInfinityStageCompiler::EvaluateDistanceAtFrame(*Passage, Evaluation.DistanceMasterFrame);
    OutAnchor.LookAheadDistanceCm = Evaluation.LookAheadDistanceCm;
    OutAnchor.CurrentLocalOffsetCm = Evaluation.LocalOffsetCm;
    OutAnchor.CurrentLocalRotation = Evaluation.LocalRotation;
    OutAnchor.CurrentFocalLengthMm = Evaluation.FocalLengthMm;
    OutAnchor.CurrentFocusDistanceCm = Evaluation.FocusDistanceCm;
    return true;
}

void UInfinityStageCameraPilotLibrary::SolveRigPose(
    const USplineComponent& Route,
    const double RouteDistanceCm,
    const FVector& CameraOffset,
    const double LookAheadDistanceCm,
    const FTransform& DesiredRigWorld,
    const FRotator& ReferenceRotation,
    FVector& OutLocalOffsetCm,
    FRotator& OutLocalRotation)
{
    // Mirrors AInfinityStageCameraRig::GetCameraStateAtMasterFrame. The route
    // frame is taken at the un-offset distance and the offset is applied in its
    // rotation only, so position inverts directly.
    const FTransform RouteTransform = Route.GetTransformAtDistanceAlongSpline(
        RouteDistanceCm,
        ESplineCoordinateSpace::World,
        true);
    OutLocalOffsetCm = RouteTransform.InverseTransformVectorNoScale(
        DesiredRigWorld.GetLocation() - RouteTransform.GetLocation()) - CameraOffset;

    // With look-ahead the base rotation aims from the offset position at a
    // point further along the route, so it can only be rebuilt once the offset
    // is known.
    FQuat BaseRotation = RouteTransform.GetRotation();
    if (LookAheadDistanceCm > UE_DOUBLE_SMALL_NUMBER)
    {
        const double TargetDistanceCm = FMath::Clamp(
            RouteDistanceCm + CameraOffset.X + OutLocalOffsetCm.X + LookAheadDistanceCm,
            0.0,
            static_cast<double>(Route.GetSplineLength()));
        const FVector LookTarget = Route.GetLocationAtDistanceAlongSpline(
            TargetDistanceCm,
            ESplineCoordinateSpace::World);
        const FVector CameraLocation = RouteTransform.GetLocation()
            + RouteTransform.TransformVectorNoScale(CameraOffset + OutLocalOffsetCm);
        const FVector LookDirection = (LookTarget - CameraLocation).GetSafeNormal();
        if (!LookDirection.IsNearlyZero())
        {
            BaseRotation = FRotationMatrix::MakeFromXZ(
                LookDirection,
                RouteTransform.GetUnitAxis(EAxis::Z)).ToQuat();
        }
    }

    // Forward is Final = Base * Local, so Local = Base^-1 * Final.
    const FRotator Local = (BaseRotation.Inverse() * DesiredRigWorld.GetRotation()).GetNormalized().Rotator();
    OutLocalRotation = FRotator(
        UnwindNear(Local.Pitch, ReferenceRotation.Pitch),
        UnwindNear(Local.Yaw, ReferenceRotation.Yaw),
        UnwindNear(Local.Roll, ReferenceRotation.Roll));
}

bool UInfinityStageCameraPilotLibrary::Solve(
    const FInfinityCameraPilotAnchor& Anchor,
    const FTransform& CameraWorldTransform,
    FInfinityCameraPilotSolution& OutSolution,
    FString& OutError)
{
    if (!Anchor.Rig || !Anchor.Rig->PassageActor || !Anchor.Rig->PassageActor->Route)
    {
        OutError = TEXT("The camera anchor has no rig or route.");
        return false;
    }
    if (CameraWorldTransform.ContainsNaN())
    {
        OutError = TEXT("The requested camera pose is not finite.");
        return false;
    }

    OutSolution.RigWorldTransform = GetCameraRelativeTransform(*Anchor.Rig).Inverse() * WithoutScale(CameraWorldTransform);
    OutSolution.RigWorldTransform.NormalizeRotation();
    SolveRigPose(
        *Anchor.Rig->PassageActor->Route,
        Anchor.RouteDistanceCm,
        Anchor.Rig->CameraOffset,
        Anchor.LookAheadDistanceCm,
        OutSolution.RigWorldTransform,
        Anchor.CurrentLocalRotation,
        OutSolution.LocalOffsetCm,
        OutSolution.LocalRotation);
    if (OutSolution.LocalOffsetCm.ContainsNaN() || OutSolution.LocalRotation.ContainsNaN())
    {
        OutError = TEXT("The pose did not solve to finite channel values.");
        return false;
    }
    return true;
}

bool UInfinityStageCameraPilotLibrary::GetCameraView(
    const AInfinityStageCameraRig& Rig,
    const FFrameNumber MasterFrame,
    FTransform& OutCameraWorldTransform,
    float& OutFocalLengthMm,
    float& OutFocusDistanceCm)
{
    FTransform RigWorld;
    if (!Rig.GetCameraViewAtMasterFrame(MasterFrame, RigWorld, OutFocalLengthMm, OutFocusDistanceCm))
    {
        return false;
    }
    OutCameraWorldTransform = GetCameraRelativeTransform(Rig) * WithoutScale(RigWorld);
    return true;
}

bool UInfinityStageCameraPilotLibrary::KeyPose(
    UWorld& World,
    UInfinityStageShowAsset& Show,
    const FGuid& PassageGuid,
    const FFrameNumber MasterFrame,
    const FTransform& CameraWorldTransform,
    const FInfinityCameraPilotLens* Lens,
    FString& OutReport)
{
    const FString PassageName = DescribePassage(Show, PassageGuid);
    const auto Refuse = [&OutReport, &PassageName, MasterFrame](const FString& Reason)
    {
        OutReport = Reason;
        UE_LOG(
            LogInfinityStageCameraPilot,
            Warning,
            TEXT("INFINITY_CAMERA_PILOT_REFUSED|passage=%s|frame=%d|reason=%s"),
            *PassageName,
            MasterFrame.Value,
            *Reason);
        return false;
    };

    FInfinityCameraPilotAnchor Anchor;
    FInfinityCameraPilotSolution Solution;
    FString Error;
    if (!ResolveAnchor(World, Show, PassageGuid, MasterFrame, Anchor, Error)
        || !Solve(Anchor, CameraWorldTransform, Solution, Error))
    {
        return Refuse(Error);
    }
    if (Lens && (!FMath::IsFinite(Lens->FocalLengthMm) || Lens->FocalLengthMm < 1.0
        || !FMath::IsFinite(Lens->FocusDistanceCm) || Lens->FocusDistanceCm < 0.0))
    {
        return Refuse(TEXT("Lens values must be finite, with focal length at least 1 mm and focus distance not negative."));
    }

    AInfinityStageCameraRig& Rig = *Anchor.Rig;
    UMovieSceneInfinityPassageSection& Section = *Anchor.Section;

    // Scene handoff cameras are snapshots of the Passage endpoints. A key can
    // move an endpoint even when it is nowhere near one (curves hold their
    // outermost key), so compare rather than guess.
    FTransform StartBefore;
    FTransform EndBefore;
    const bool bHaveStartBefore = Rig.GetCameraTransformAtMasterFrame(Anchor.PassageStartFrame, StartBefore);
    const bool bHaveEndBefore = Rig.GetCameraTransformAtMasterFrame(Anchor.PassageEndFrame, EndBefore);

    TArray<FPilotKey, TInlineAllocator<8>> Keys;
    Keys.Add({ EInfinityPassageCameraChannel::LongitudinalOffsetCm, Solution.LocalOffsetCm.X });
    Keys.Add({ EInfinityPassageCameraChannel::LateralOffsetCm, Solution.LocalOffsetCm.Y });
    Keys.Add({ EInfinityPassageCameraChannel::HeightOffsetCm, Solution.LocalOffsetCm.Z });
    Keys.Add({ EInfinityPassageCameraChannel::PitchDegrees, Solution.LocalRotation.Pitch });
    Keys.Add({ EInfinityPassageCameraChannel::YawDegrees, Solution.LocalRotation.Yaw });
    Keys.Add({ EInfinityPassageCameraChannel::RollDegrees, Solution.LocalRotation.Roll });
    if (Lens)
    {
        Keys.Add({ EInfinityPassageCameraChannel::FocalLengthMm, Lens->FocalLengthMm });
        Keys.Add({ EInfinityPassageCameraChannel::FocusDistanceCm, Lens->FocusDistanceCm });
    }

    FScopedTransaction Transaction(NSLOCTEXT("InfinityStage", "KeyPilotedCameraPose", "Key Piloted Passage Camera"));
    Section.Modify();
    TArray<FChannelSnapshot, TInlineAllocator<8>> Snapshots;
    const auto RestoreChannels = [&Snapshots]()
    {
        for (FChannelSnapshot& Snapshot : Snapshots)
        {
            Snapshot.Channel->Set(Snapshot.Times, Snapshot.Values);
            Snapshot.Channel->PostEditChange();
        }
    };

    for (const FPilotKey& Key : Keys)
    {
        FMovieSceneDoubleChannel* Channel = Section.GetCameraChannel(Key.Channel);
        if (!Channel)
        {
            RestoreChannels();
            Transaction.Cancel();
            return Refuse(TEXT("The Passage section is missing a camera channel."));
        }
        FChannelSnapshot& Snapshot = Snapshots.AddDefaulted_GetRef();
        Snapshot.Channel = Channel;
        Snapshot.Times.Append(Channel->GetTimes().GetData(), Channel->GetTimes().Num());
        Snapshot.Values.Append(Channel->GetValues().GetData(), Channel->GetValues().Num());
        Channel->GetData().UpdateOrAddKey(MasterFrame, FMovieSceneDoubleValue(Key.Value));
        Channel->AutoSetTangents();
        Channel->PostEditChange();
    }

    // Verify through the rig's own evaluation path, never from the piloted
    // actor: a camera that only looks right because it was moved there proves
    // nothing about what the Master will play.
    FTransform RigAfter;
    float FocalAfter = 0.0f;
    float FocusAfter = 0.0f;
    const bool bEvaluated = Rig.GetCameraViewAtMasterFrame(MasterFrame, RigAfter, FocalAfter, FocusAfter);
    const double PositionError = bEvaluated
        ? FVector::Distance(RigAfter.GetLocation(), Solution.RigWorldTransform.GetLocation())
        : TNumericLimits<double>::Max();
    const double RotationError = bEvaluated
        ? AngularErrorDegrees(RigAfter.GetRotation(), Solution.RigWorldTransform.GetRotation())
        : TNumericLimits<double>::Max();
    const bool bLensMatches = !Lens
        || (LensValueMatches(FocalAfter, Lens->FocalLengthMm) && LensValueMatches(FocusAfter, Lens->FocusDistanceCm));
    if (!bEvaluated
        || PositionError > PilotPositionToleranceCm
        || RotationError > PilotRotationToleranceDegrees
        || !bLensMatches)
    {
        RestoreChannels();
        Transaction.Cancel();
        Rig.EvaluateAtMasterFrame(MasterFrame);
        return Refuse(FString::Printf(
            TEXT("Read-back missed the piloted pose (%.4f cm, %.4f deg, lens %s), so the keys were restored. Nothing was written."),
            PositionError,
            RotationError,
            bLensMatches ? TEXT("ok") : TEXT("mismatch")));
    }

    Section.MarkPackageDirty();

    FTransform StartAfter;
    FTransform EndAfter;
    const bool bStartChanged = bHaveStartBefore
        && Rig.GetCameraTransformAtMasterFrame(Anchor.PassageStartFrame, StartAfter)
        && !PosesMatch(StartBefore, StartAfter);
    const bool bEndChanged = bHaveEndBefore
        && Rig.GetCameraTransformAtMasterFrame(Anchor.PassageEndFrame, EndAfter)
        && !PosesMatch(EndBefore, EndAfter);

    // Wings, shadow cat and follow light follow the new camera at this moment.
    Rig.EvaluateAtMasterFrame(MasterFrame);

    const double TickRate = Show.TickResolution.IsValid() ? Show.TickResolution.AsDecimal() : 24000.0;
    const double SecondsIntoPassage = (MasterFrame.Value - Anchor.PassageStartFrame.Value) / TickRate;
    const FString PackageName = Section.GetPackage()->GetName();
    OutReport = FString::Printf(
        TEXT("Keyed %d camera channel(s) on '%s' at %.2f s into the Passage. Offset %s cm, rotation %s. ")
        TEXT("Read-back error %.4f cm / %.4f deg.%s Save %s to keep it."),
        Keys.Num(),
        *PassageName,
        SecondsIntoPassage,
        *Solution.LocalOffsetCm.ToCompactString(),
        *Solution.LocalRotation.ToCompactString(),
        PositionError,
        RotationError,
        (bStartChanged || bEndChanged)
            ? TEXT(" This moved the Passage's start or end camera, so Scene handoff cameras may now be stale: run Scene Camera Handoff > Check All Scenes.")
            : TEXT(""),
        *PackageName);
    UE_LOG(
        LogInfinityStageCameraPilot,
        Display,
        TEXT("INFINITY_CAMERA_PILOT_KEYED|passage=%s|label=%s|frame=%d|channels=%d|offset=%s|rotation=%s|pos_err_cm=%.5f|rot_err_deg=%.5f|lens=%d|start_changed=%d|end_changed=%d|package=%s"),
        *PassageGuid.ToString(EGuidFormats::DigitsWithHyphens),
        *PassageName,
        MasterFrame.Value,
        Keys.Num(),
        *Solution.LocalOffsetCm.ToCompactString(),
        *Solution.LocalRotation.ToCompactString(),
        PositionError,
        RotationError,
        Lens ? 1 : 0,
        bStartChanged ? 1 : 0,
        bEndChanged ? 1 : 0,
        *PackageName);
    return true;
}

bool UInfinityStageCameraPilotLibrary::KeyPassageCameraPose(
    UInfinityStageShowAsset* Show,
    const FGuid PassageGuid,
    const int32 MasterFrame,
    const FTransform CameraWorldTransform,
    const bool bKeyLens,
    const float FocalLengthMm,
    const float FocusDistanceCm,
    FString& OutReport)
{
    UWorld* World = GetEditorWorld();
    if (!Show || !World)
    {
        OutReport = TEXT("Needs a Show asset and an open editor world.");
        return false;
    }
    if (GEditor && GEditor->PlayWorld)
    {
        OutReport = TEXT("Stop PIE before keying the Passage camera.");
        return false;
    }
    FInfinityCameraPilotLens Lens;
    Lens.FocalLengthMm = FocalLengthMm;
    Lens.FocusDistanceCm = FocusDistanceCm;
    return KeyPose(*World, *Show, PassageGuid, FFrameNumber(MasterFrame), CameraWorldTransform, bKeyLens ? &Lens : nullptr, OutReport);
}

bool UInfinityStageCameraPilotLibrary::SolvePassageCameraPose(
    UInfinityStageShowAsset* Show,
    const FGuid PassageGuid,
    const int32 MasterFrame,
    const FTransform CameraWorldTransform,
    FVector& OutLocalOffsetCm,
    FRotator& OutLocalRotation,
    FVector& OutCurrentLocalOffsetCm,
    FRotator& OutCurrentLocalRotation,
    FString& OutReport)
{
    UWorld* World = GetEditorWorld();
    if (!Show || !World)
    {
        OutReport = TEXT("Needs a Show asset and an open editor world.");
        return false;
    }
    FInfinityCameraPilotAnchor Anchor;
    FInfinityCameraPilotSolution Solution;
    if (!ResolveAnchor(*World, *Show, PassageGuid, FFrameNumber(MasterFrame), Anchor, OutReport)
        || !Solve(Anchor, CameraWorldTransform, Solution, OutReport))
    {
        return false;
    }
    OutLocalOffsetCm = Solution.LocalOffsetCm;
    OutLocalRotation = Solution.LocalRotation;
    OutCurrentLocalOffsetCm = Anchor.CurrentLocalOffsetCm;
    OutCurrentLocalRotation = Anchor.CurrentLocalRotation;
    OutReport = FString::Printf(
        TEXT("Would key offset %s cm and rotation %s (currently %s cm and %s). Nothing was written."),
        *Solution.LocalOffsetCm.ToCompactString(),
        *Solution.LocalRotation.ToCompactString(),
        *Anchor.CurrentLocalOffsetCm.ToCompactString(),
        *Anchor.CurrentLocalRotation.ToCompactString());
    return true;
}

bool UInfinityStageCameraPilotLibrary::MatchNamedSceneHandoffs(
    UInfinityStageShowAsset* Show,
    const TArray<FGuid>& SceneCueGuids,
    const int32 ExpectedSceneCount,
    FString& OutReport)
{
    UWorld* World = GetEditorWorld();
    if (!Show || !World || !GEditor)
    {
        OutReport = TEXT("Needs a Show asset and an open editor world.");
        return false;
    }
    if (GEditor->PlayWorld)
    {
        OutReport = TEXT("Stop PIE before matching Scene handoffs.");
        return false;
    }
    if (SceneCueGuids.IsEmpty() || SceneCueGuids.Num() != ExpectedSceneCount)
    {
        OutReport = FString::Printf(
            TEXT("Refused: name the Scenes to match and state how many (got %d GUIDs, expected count %d). An empty list would match every Scene."),
            SceneCueGuids.Num(),
            ExpectedSceneCount);
        return false;
    }
    TArray<FString> Labels;
    for (const FGuid& SceneGuid : SceneCueGuids)
    {
        const FInfinityShowCue* Cue = Show->Cues.FindByPredicate(
            [&SceneGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == SceneGuid; });
        if (!Cue || !Cue->bEnabled || Cue->Type != EInfinityCueType::Scene)
        {
            OutReport = FString::Printf(
                TEXT("Refused: %s is not an enabled Scene cue of this Show."),
                *SceneGuid.ToString(EGuidFormats::DigitsWithHyphens));
            return false;
        }
        Labels.Add(Cue->Label.ToString());
    }

    TArray<FGuid> StaleBefore;
    FString CheckBefore;
    FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(*Show, *World, SceneCueGuids, StaleBefore, CheckBefore);

    FString MatchReport;
    bool bMatched = false;
    {
        const FScopedTransaction Transaction(NSLOCTEXT(
            "InfinityStage", "MatchNamedSceneHandoffsTransaction", "Match Named Scene Camera Handoffs"));
        bMatched = FInfinityStageSceneHandoffBuilder::MatchSceneHandoffs(*Show, *World, SceneCueGuids, MatchReport);
    }

    TArray<FGuid> StaleAfter;
    FString CheckAfter;
    FInfinityStageSceneHandoffBuilder::CheckSceneHandoffs(*Show, *World, SceneCueGuids, StaleAfter, CheckAfter);

    OutReport = FString::Printf(
        TEXT("%s %s. Stale before: %d, after: %d. %s"),
        bMatched ? TEXT("Matched") : TEXT("Match FAILED for"),
        *FString::Join(Labels, TEXT(", ")),
        StaleBefore.Num(),
        StaleAfter.Num(),
        *MatchReport);
    UE_LOG(
        LogInfinityStageCameraPilot,
        Display,
        TEXT("INFINITY_SCENE_HANDOFF_MATCHED|scenes=%s|ok=%d|stale_before=%d|stale_after=%d|report=%s"),
        *FString::Join(Labels, TEXT(", ")),
        bMatched ? 1 : 0,
        StaleBefore.Num(),
        StaleAfter.Num(),
        *MatchReport);
    return bMatched && StaleAfter.IsEmpty();
}

bool UInfinityStageCameraPilotLibrary::ImportMusicAnalysis(UInfinityStageShowAsset* Show, FString& OutReport)
{
    if (!Show || !GEditor)
    {
        OutReport = TEXT("Needs a Show asset and the editor.");
        return false;
    }
    if (GEditor->PlayWorld)
    {
        OutReport = TEXT("Stop PIE before importing music analysis.");
        return false;
    }
    const FString AnalysisDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("InfinityStage/MusicAnalysis"));
    bool bImported = false;
    {
        const FScopedTransaction Transaction(NSLOCTEXT(
            "InfinityStage", "ScriptedMusicAnalysisImport", "Link Infinity Stage Music Analysis"));
        bImported = FInfinityStageMusicAnalysisImporter::ImportDirectory(AnalysisDirectory, Show, OutReport);
    }
    UE_LOG(
        LogInfinityStageCameraPilot,
        Display,
        TEXT("INFINITY_MUSIC_ANALYSIS_IMPORTED|ok=%d|report=%s"),
        bImported ? 1 : 0,
        *OutReport);
    return bImported;
}

bool UInfinityStageCameraPilotLibrary::GetPassageFrameRange(
    UInfinityStageShowAsset* Show,
    const FGuid PassageGuid,
    int32& OutStartFrame,
    int32& OutEndFrame)
{
    if (!Show)
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    const FInfinityCompiledPassage* Passage = Compiled.Passages.FindByPredicate(
        [&PassageGuid](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == PassageGuid; });
    if (!Passage)
    {
        return false;
    }
    OutStartFrame = Passage->SegmentStartFrame.Value;
    OutEndFrame = Passage->SegmentEndFrame.Value;
    return true;
}

bool UInfinityStageCameraPilotLibrary::GetPassageCameraPose(
    UInfinityStageShowAsset* Show,
    const FGuid PassageGuid,
    const int32 MasterFrame,
    FTransform& OutCameraWorldTransform,
    float& OutFocalLengthMm,
    float& OutFocusDistanceCm)
{
    UWorld* World = GetEditorWorld();
    const AInfinityStageCameraRig* Rig = (Show && World) ? FindCameraRig(*World, *Show, PassageGuid) : nullptr;
    return Rig && GetCameraView(*Rig, FFrameNumber(MasterFrame), OutCameraWorldTransform, OutFocalLengthMm, OutFocusDistanceCm);
}
