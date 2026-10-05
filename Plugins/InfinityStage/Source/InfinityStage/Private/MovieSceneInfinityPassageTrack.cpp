#include "MovieSceneInfinityPassageTrack.h"

#include "Camera/PlayerCameraManager.h"
#include "Channels/MovieSceneChannelProxy.h"
#include "EngineUtils.h"
#include "Evaluation/MovieSceneExecutionTokens.h"
#include "GameFramework/PlayerController.h"
#include "IMovieScenePlayer.h"
#include "InfinityStageArrival.h"
#include "InfinityStageCameraRig.h"
#include "InfinityStageCelestialRig.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageTransportController.h"

namespace
{
double EvaluateChannel(const FMovieSceneDoubleChannel& Channel, const FFrameTime Time, const double Fallback)
{
    double Value = Fallback;
    Channel.Evaluate(Time, Value);
    return FMath::IsFinite(Value) ? Value : Fallback;
}

double EvaluateNonNegative(
    const FMovieSceneDoubleChannel& Channel,
    const double DecimalFrame,
    const double Fallback)
{
    return FMath::Max(0.0, EvaluateChannel(Channel, FFrameTime::FromDecimal(DecimalFrame), Fallback));
}

/**
 * Fixed-grid integration makes direct seek, reverse and sequential evaluation
 * history-independent. The grid is anchored at SpanStart and its bucket count is
 * fixed, so integrating to two different points and subtracting gives the same
 * answer as integrating the interval between them.
 */
double IntegrateNonNegative(
    const FMovieSceneDoubleChannel& Channel,
    const double SpanStart,
    const double SpanEnd,
    const double Until,
    const double Fallback)
{
    const double ClampedUntil = FMath::Clamp(Until, SpanStart, SpanEnd);
    const double SpanLength = SpanEnd - SpanStart;
    if (SpanLength <= UE_DOUBLE_SMALL_NUMBER || ClampedUntil <= SpanStart)
    {
        return 0.0;
    }

    constexpr int32 BucketCount = 256;
    const double BucketWidth = SpanLength / BucketCount;
    const double BucketPosition = (ClampedUntil - SpanStart) / BucketWidth;
    const int32 FullBuckets = FMath::Clamp(FMath::FloorToInt(BucketPosition), 0, BucketCount);
    double Integral = 0.0;
    for (int32 Bucket = 0; Bucket < FullBuckets; ++Bucket)
    {
        const double A = SpanStart + Bucket * BucketWidth;
        const double B = A + BucketWidth;
        Integral += 0.5
            * (EvaluateNonNegative(Channel, A, Fallback) + EvaluateNonNegative(Channel, B, Fallback))
            * BucketWidth;
    }
    if (FullBuckets < BucketCount)
    {
        const double A = SpanStart + FullBuckets * BucketWidth;
        const double B = ClampedUntil;
        Integral += 0.5
            * (EvaluateNonNegative(Channel, A, Fallback) + EvaluateNonNegative(Channel, B, Fallback))
            * (B - A);
    }
    return Integral;
}

double EvaluateRate(const FMovieSceneDoubleChannel& Channel, const double DecimalFrame)
{
    return EvaluateNonNegative(Channel, DecimalFrame, 1.0);
}

double IntegrateRate(
    const FMovieSceneDoubleChannel& Channel,
    const double SpanStart,
    const double SpanEnd,
    const double Until)
{
    return IntegrateNonNegative(Channel, SpanStart, SpanEnd, Until, 1.0);
}

/**
 * Integral of the route rate times the crossing settle envelope over
 * [WindowStart, Until]. Its own fixed grid is anchored at WindowStart, so this
 * stays history-independent exactly like IntegrateNonNegative. bUseChannel=false
 * integrates the envelope alone, for the invalid-speed fallback.
 */
double IntegrateSettledRate(
    const FMovieSceneDoubleChannel& Channel,
    const double WindowStart,
    const double WindowEnd,
    const double Until,
    const bool bUseChannel)
{
    const double ClampedUntil = FMath::Clamp(Until, WindowStart, WindowEnd);
    const double WindowLength = WindowEnd - WindowStart;
    if (WindowLength <= UE_DOUBLE_SMALL_NUMBER || ClampedUntil <= WindowStart)
    {
        return 0.0;
    }
    const auto Sample = [&Channel, WindowStart, WindowEnd, bUseChannel](const double Frame)
    {
        const double Rate = bUseChannel ? EvaluateRate(Channel, Frame) : 1.0;
        return Rate * UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(Frame, WindowStart, WindowEnd);
    };

    constexpr int32 BucketCount = 64;
    const double BucketWidth = WindowLength / BucketCount;
    const double BucketPosition = (ClampedUntil - WindowStart) / BucketWidth;
    const int32 FullBuckets = FMath::Clamp(FMath::FloorToInt(BucketPosition), 0, BucketCount);
    double Integral = 0.0;
    for (int32 Bucket = 0; Bucket < FullBuckets; ++Bucket)
    {
        const double A = WindowStart + Bucket * BucketWidth;
        const double B = A + BucketWidth;
        Integral += 0.5 * (Sample(A) + Sample(B)) * BucketWidth;
    }
    if (FullBuckets < BucketCount)
    {
        const double A = WindowStart + FullBuckets * BucketWidth;
        const double B = ClampedUntil;
        Integral += 0.5 * (Sample(A) + Sample(B)) * (B - A);
    }
    return Integral;
}

struct FInfinityPassageExecutionToken final : IMovieSceneExecutionToken
{
    FGuid PassageGuid;

    explicit FInfinityPassageExecutionToken(const FGuid& InPassageGuid)
        : PassageGuid(InPassageGuid)
    {
    }

    virtual void Execute(
        const FMovieSceneContext& Context,
        const FMovieSceneEvaluationOperand& Operand,
        FPersistentEvaluationData& PersistentData,
        IMovieScenePlayer& Player) override
    {
        UObject* PlaybackContext = Player.GetPlaybackContext();
        UWorld* World = PlaybackContext ? PlaybackContext->GetWorld() : nullptr;
        if (!World)
        {
            return;
        }

        // One authority owns the view target. When a transport is driving this
        // world it issues every handover, with the blend the seam asks for, and
        // it remembers what it asked for - which is the only way a blend can
        // ever complete. A claim from here would restart that blend on every
        // evaluated frame, because a blend in flight leaves GetViewTarget()
        // still reporting the outgoing camera.
        UInfinityStageTransportController* Transport =
            UInfinityStageTransportController::FindForWorld(World);

        // The cached lookup replaces a full actor walk on every evaluated frame.
        AInfinityStageCameraRig* CameraRig =
            Transport ? Transport->FindCameraRigForPassage(PassageGuid) : nullptr;
        if (!CameraRig)
        {
            for (TActorIterator<AInfinityStageCameraRig> It(World); It; ++It)
            {
                AInfinityStageCameraRig* Candidate = *It;
                if (Candidate
                    && Candidate->PassageActor
                    && Candidate->PassageActor->PassageGuid == PassageGuid)
                {
                    CameraRig = Candidate;
                    break;
                }
            }
        }

        UInfinityStageShowAsset* ActiveShowAsset = nullptr;
        if (CameraRig && CameraRig->PassageActor)
        {
            ActiveShowAsset = CameraRig->PassageActor->ShowAsset;
            CameraRig->EvaluateAtMasterFrame(Context.GetTime().FloorToFrame());

            // IMovieScenePlayer::UpdateCameraCut is a deprecated compatibility hook and is
            // intentionally a no-op for ULevelSequencePlayer in UE 5.8. Passage cameras are
            // resolved dynamically by Passage GUID, so they cannot use a conventional fixed
            // possessable Camera Cut binding. With no transport registered - a Passage
            // previewed on its own, or a show whose transport failed to initialize - this
            // remains the only thing that can claim the viewport, so it still does.
            if (World->IsGameWorld() && !Transport)
            {
                if (APlayerController* PlayerController = World->GetFirstPlayerController())
                {
                    if (PlayerController->GetViewTarget() != CameraRig)
                    {
                        UE_LOG(LogInfinityStageTransport, Verbose,
                            TEXT("INFINITY_PASSAGE_CLAIM frame=%d target=%s previous=%s (no transport)"),
                            Context.GetTime().FloorToFrame().Value,
                            *GetNameSafe(CameraRig),
                            *GetNameSafe(PlayerController->GetViewTarget()));
                        PlayerController->SetViewTarget(CameraRig);
                    }
                }
            }
        }

        // A jump has no in-between frames whoever owns the view, so the renderer
        // is told to drop its temporal history either way. This is a render hint,
        // not a view-target change, so it does not contend for the camera.
        if (World->IsGameWorld() && Context.HasJumped())
        {
            if (APlayerController* PlayerController = World->GetFirstPlayerController())
            {
                if (PlayerController->PlayerCameraManager)
                {
                    PlayerController->PlayerCameraManager->SetGameCameraCutThisFrame();
                }
            }
        }

        if (ActiveShowAsset)
        {
            for (TActorIterator<AInfinityStageCelestialRig> It(World); It; ++It)
            {
                It->EvaluateAtMasterFrame(
                    ActiveShowAsset,
                    PassageGuid,
                    Context.GetTime().FloorToFrame());
            }
            // Added 30 Sep 2026 by the Rig & atmosphere stream (Scene arrivals), approved by the
            // conductor while this file's owner (Director & transitions) was not live: the Scene
            // track has no execution token, so Passage frames are the only clean per-frame hook
            // for a motion that begins before its Scene does. Director should review.
            for (TActorIterator<AInfinityStageArrival> It(World); It; ++It)
            {
                It->EvaluateAtMasterFrame(ActiveShowAsset, Context.GetTime());
            }
        }
    }
};
}

UMovieSceneInfinityPassageSection::UMovieSceneInfinityPassageSection(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    EvalOptions.CompletionMode = EMovieSceneCompletionMode::KeepState;
    SpeedMultiplier.SetDefault(1.0);
    LongitudinalOffsetCm.SetDefault(0.0);
    LateralOffsetCm.SetDefault(0.0);
    HeightOffsetCm.SetDefault(0.0);
    PitchDegrees.SetDefault(0.0);
    YawDegrees.SetDefault(0.0);
    RollDegrees.SetDefault(0.0);
    LookAheadDistanceCm.SetDefault(0.0);
    FocalLengthMm.SetDefault(35.0);
    FocusDistanceCm.SetDefault(100000.0);
    WingInwardTravelScale.SetDefault(1.0);
    WingCycleRateScale.SetDefault(1.0);
    WingPhaseBiasCycles.SetDefault(0.0);
}

FMovieSceneDoubleChannel* UMovieSceneInfinityPassageSection::GetCameraChannel(
    const EInfinityPassageCameraChannel Channel)
{
    return const_cast<FMovieSceneDoubleChannel*>(
        static_cast<const UMovieSceneInfinityPassageSection*>(this)->GetCameraChannel(Channel));
}

const FMovieSceneDoubleChannel* UMovieSceneInfinityPassageSection::GetCameraChannel(
    const EInfinityPassageCameraChannel Channel) const
{
    switch (Channel)
    {
    case EInfinityPassageCameraChannel::SpeedMultiplier: return &SpeedMultiplier;
    case EInfinityPassageCameraChannel::LongitudinalOffsetCm: return &LongitudinalOffsetCm;
    case EInfinityPassageCameraChannel::LateralOffsetCm: return &LateralOffsetCm;
    case EInfinityPassageCameraChannel::HeightOffsetCm: return &HeightOffsetCm;
    case EInfinityPassageCameraChannel::PitchDegrees: return &PitchDegrees;
    case EInfinityPassageCameraChannel::YawDegrees: return &YawDegrees;
    case EInfinityPassageCameraChannel::RollDegrees: return &RollDegrees;
    case EInfinityPassageCameraChannel::LookAheadDistanceCm: return &LookAheadDistanceCm;
    case EInfinityPassageCameraChannel::FocalLengthMm: return &FocalLengthMm;
    case EInfinityPassageCameraChannel::FocusDistanceCm: return &FocusDistanceCm;
    case EInfinityPassageCameraChannel::WingInwardTravelScale: return &WingInwardTravelScale;
    case EInfinityPassageCameraChannel::WingCycleRateScale: return &WingCycleRateScale;
    case EInfinityPassageCameraChannel::WingPhaseBiasCycles: return &WingPhaseBiasCycles;
    default: return nullptr;
    }
}

bool UMovieSceneInfinityPassageSection::HasWingModulation() const
{
    const auto IsActive = [](const FMovieSceneDoubleChannel& Channel, const double NeutralValue)
    {
        if (Channel.GetNumKeys() > 0)
        {
            return true;
        }
        // Resetting a curve clears its keys and restores a default, so a
        // non-neutral default is still authored modulation.
        const TOptional<double> Default = Channel.GetDefault();
        return Default.IsSet() && !FMath::IsNearlyEqual(Default.GetValue(), NeutralValue);
    };

    return IsActive(WingInwardTravelScale, 1.0)
        || IsActive(WingCycleRateScale, 1.0)
        || IsActive(WingPhaseBiasCycles, 0.0);
}

double UMovieSceneInfinityPassageSection::GetWingCycleRateIntegralFrames(
    const FInfinityCompiledPassage& Passage,
    const double UntilFrame) const
{
    return IntegrateNonNegative(
        WingCycleRateScale,
        Passage.SegmentStartFrame.Value,
        Passage.SegmentEndFrame.Value,
        UntilFrame,
        1.0);
}

bool UMovieSceneInfinityPassageSection::EvaluateWingModulation(
    const FInfinityCompiledPassage& Passage,
    const FFrameTime MasterTime,
    FInfinityPassageWingEvaluation& OutEvaluation) const
{
    const double MasterFrame = MasterTime.AsDecimal();
    const double PassageStart = Passage.SegmentStartFrame.Value;
    const double PassageEnd = Passage.SegmentEndFrame.Value;
    if (MasterFrame < PassageStart || MasterFrame > PassageEnd || PassageEnd < PassageStart)
    {
        return false;
    }

    OutEvaluation.InwardTravelScale = FMath::Max(
        0.0,
        EvaluateChannel(WingInwardTravelScale, MasterTime, 1.0));
    OutEvaluation.PhaseBiasCycles = EvaluateChannel(WingPhaseBiasCycles, MasterTime, 0.0);
    OutEvaluation.CycleRateIntegralFrames = GetWingCycleRateIntegralFrames(Passage, MasterFrame);
    return true;
}

double UMovieSceneInfinityPassageSection::CrossingSettleEnvelope(
    const double Frame,
    const double WindowStart,
    const double WindowEnd)
{
    const double WindowLength = WindowEnd - WindowStart;
    if (!(WindowLength > UE_DOUBLE_SMALL_NUMBER))
    {
        return 1.0;
    }
    // U runs 1 -> 0 across the window. Smoothstep has zero slope at both ends:
    // no velocity step where the settle begins, and a soft stop at the end.
    const double U = FMath::Clamp((WindowEnd - Frame) / WindowLength, 0.0, 1.0);
    return U * U * (3.0 - 2.0 * U);
}

bool UMovieSceneInfinityPassageSection::EvaluateCamera(
    const FInfinityCompiledPassage& Passage,
    const FFrameTime MasterTime,
    FInfinityPassageCameraEvaluation& OutEvaluation,
    const double SettleFrames) const
{
    const double MasterFrame = MasterTime.AsDecimal();
    const double PassageStart = Passage.SegmentStartFrame.Value;
    const double PassageEnd = Passage.SegmentEndFrame.Value;
    if (MasterFrame < PassageStart || MasterFrame > PassageEnd || PassageEnd < PassageStart)
    {
        return false;
    }
    OutEvaluation.SettleWeight = 1.0;

    TArray<double, TInlineAllocator<32>> PinnedFrames;
    PinnedFrames.Add(PassageStart);
    for (const FInfinityCompiledWing& Wing : Passage.Wings)
    {
        if (PinnedWingCueGuids.Contains(Wing.CueGuid))
        {
            PinnedFrames.Add(Wing.PassFrame.Value);
        }
    }
    for (const FFrameNumber RelativeFrame : PinnedPassageFrames)
    {
        const double AbsoluteFrame = PassageStart + RelativeFrame.Value;
        if (AbsoluteFrame > PassageStart && AbsoluteFrame < PassageEnd)
        {
            PinnedFrames.Add(AbsoluteFrame);
        }
    }
    PinnedFrames.Add(PassageEnd);
    PinnedFrames.Sort();
    for (int32 Index = PinnedFrames.Num() - 1; Index > 0; --Index)
    {
        if (FMath::IsNearlyEqual(PinnedFrames[Index], PinnedFrames[Index - 1]))
        {
            PinnedFrames.RemoveAt(Index);
        }
    }

    double SpanStart = PassageStart;
    double SpanEnd = PassageEnd;
    for (int32 Index = 1; Index < PinnedFrames.Num(); ++Index)
    {
        if (MasterFrame <= PinnedFrames[Index])
        {
            SpanStart = PinnedFrames[Index - 1];
            SpanEnd = PinnedFrames[Index];
            break;
        }
    }

    // The crossing settle only ever touches the span that ends at the Passage
    // end, and is never longer than that span, so the envelope is still 1 at the
    // span's opening pin. Both span ends stay pinned: the rate is renormalized
    // over the span exactly as SpeedMultiplier is, which is what keeps every pin
    // (and the Passage end) at its absolute frame.
    const bool bSettle = SettleFrames > 0.0
        && SpanEnd > SpanStart
        && FMath::IsNearlyEqual(SpanEnd, PassageEnd, 0.5);
    double SpanAlpha = 0.0;
    if (!bSettle)
    {
        const double FullIntegral = IntegrateRate(SpeedMultiplier, SpanStart, SpanEnd, SpanEnd);
        if (FullIntegral > UE_DOUBLE_SMALL_NUMBER)
        {
            SpanAlpha = IntegrateRate(SpeedMultiplier, SpanStart, SpanEnd, MasterFrame) / FullIntegral;
        }
        else
        {
            OutEvaluation.bUsedInvalidSpeedFallback = true;
            SpanAlpha = (SpanEnd > SpanStart) ? (MasterFrame - SpanStart) / (SpanEnd - SpanStart) : 0.0;
        }
    }
    else
    {
        const double SettleStart = FMath::Max(SpanStart, SpanEnd - SettleFrames);
        // Before the window the existing span grid is used unchanged, so the
        // walk's own shape there is untouched; only the normalization differs.
        const auto SettledIntegral = [this, SpanStart, SpanEnd, SettleStart](const double Until, const bool bUseChannel)
        {
            const double PreUntil = FMath::Min(Until, SettleStart);
            const double Before = bUseChannel
                ? IntegrateRate(SpeedMultiplier, SpanStart, SpanEnd, PreUntil)
                : FMath::Max(0.0, PreUntil - SpanStart);
            return Before + IntegrateSettledRate(SpeedMultiplier, SettleStart, SpanEnd, Until, bUseChannel);
        };
        const double FullIntegral = SettledIntegral(SpanEnd, true);
        if (FullIntegral > UE_DOUBLE_SMALL_NUMBER)
        {
            SpanAlpha = SettledIntegral(MasterFrame, true) / FullIntegral;
        }
        else
        {
            OutEvaluation.bUsedInvalidSpeedFallback = true;
            const double FullFallback = SettledIntegral(SpanEnd, false);
            SpanAlpha = FullFallback > UE_DOUBLE_SMALL_NUMBER
                ? SettledIntegral(MasterFrame, false) / FullFallback
                : 0.0;
        }
        OutEvaluation.SettleWeight = CrossingSettleEnvelope(MasterFrame, SettleStart, SpanEnd);
    }

    OutEvaluation.DistanceMasterFrame = FFrameTime::FromDecimal(FMath::Lerp(SpanStart, SpanEnd, SpanAlpha));
    OutEvaluation.SpeedMultiplier = EvaluateRate(SpeedMultiplier, MasterFrame);
    OutEvaluation.LocalOffsetCm = FVector(
        EvaluateChannel(LongitudinalOffsetCm, MasterTime, 0.0),
        EvaluateChannel(LateralOffsetCm, MasterTime, 0.0),
        EvaluateChannel(HeightOffsetCm, MasterTime, 0.0));
    OutEvaluation.LocalRotation = FRotator(
        EvaluateChannel(PitchDegrees, MasterTime, 0.0),
        EvaluateChannel(YawDegrees, MasterTime, 0.0),
        EvaluateChannel(RollDegrees, MasterTime, 0.0));
    OutEvaluation.LookAheadDistanceCm = FMath::Max(
        0.0,
        EvaluateChannel(LookAheadDistanceCm, MasterTime, 0.0));
    OutEvaluation.FocalLengthMm = FMath::Max(1.0, EvaluateChannel(FocalLengthMm, MasterTime, 35.0));
    OutEvaluation.FocusDistanceCm = FMath::Max(0.0, EvaluateChannel(FocusDistanceCm, MasterTime, 100000.0));
    return true;
}

EMovieSceneChannelProxyType UMovieSceneInfinityPassageSection::CacheChannelProxy()
{
    FMovieSceneChannelProxyData Channels;
#if WITH_EDITOR
    auto AddChannel = [&Channels](FMovieSceneDoubleChannel& Channel, const TCHAR* Name, const FText& Label, const FText& Group, const int32 SortOrder, const FLinearColor Color)
    {
        FMovieSceneChannelMetaData MetaData(FName(Name), Label, Group);
        MetaData.SortOrder = SortOrder;
        MetaData.bCanCollapseToTrack = false;
        MetaData.Color = Color;
        Channels.Add(Channel, MetaData, TMovieSceneExternalValue<double>());
    };
    AddChannel(SpeedMultiplier, TEXT("Camera.SpeedMultiplier"), NSLOCTEXT("InfinityStage", "CameraSpeedMultiplier", "Speed Multiplier"), NSLOCTEXT("InfinityStage", "CameraTimingGroup", "Camera Timing"), 0, FLinearColor(1.0f, 0.55f, 0.12f));
    AddChannel(LongitudinalOffsetCm, TEXT("Camera.LongitudinalOffsetCm"), NSLOCTEXT("InfinityStage", "CameraLongitudinal", "Longitudinal Offset (cm)"), NSLOCTEXT("InfinityStage", "CameraPositionGroup", "Camera Position"), 10, FLinearColor::Red);
    AddChannel(LateralOffsetCm, TEXT("Camera.LateralOffsetCm"), NSLOCTEXT("InfinityStage", "CameraLateral", "Lateral Offset (cm)"), NSLOCTEXT("InfinityStage", "CameraPositionGroup", "Camera Position"), 11, FLinearColor::Green);
    AddChannel(HeightOffsetCm, TEXT("Camera.HeightOffsetCm"), NSLOCTEXT("InfinityStage", "CameraHeight", "Height Offset (cm)"), NSLOCTEXT("InfinityStage", "CameraPositionGroup", "Camera Position"), 12, FLinearColor::Blue);
    AddChannel(PitchDegrees, TEXT("Camera.PitchDegrees"), NSLOCTEXT("InfinityStage", "CameraPitch", "Pitch (deg)"), NSLOCTEXT("InfinityStage", "CameraRotationGroup", "Camera Rotation"), 20, FLinearColor::Red);
    AddChannel(YawDegrees, TEXT("Camera.YawDegrees"), NSLOCTEXT("InfinityStage", "CameraYaw", "Yaw (deg)"), NSLOCTEXT("InfinityStage", "CameraRotationGroup", "Camera Rotation"), 21, FLinearColor::Green);
    AddChannel(RollDegrees, TEXT("Camera.RollDegrees"), NSLOCTEXT("InfinityStage", "CameraRoll", "Roll (deg)"), NSLOCTEXT("InfinityStage", "CameraRotationGroup", "Camera Rotation"), 22, FLinearColor::Blue);
    AddChannel(LookAheadDistanceCm, TEXT("Camera.LookAheadDistanceCm"), NSLOCTEXT("InfinityStage", "CameraLookAhead", "Route Look Ahead (cm)"), NSLOCTEXT("InfinityStage", "CameraRotationGroup", "Camera Rotation"), 23, FLinearColor(0.95f, 0.72f, 0.20f));
    AddChannel(FocalLengthMm, TEXT("Camera.FocalLengthMm"), NSLOCTEXT("InfinityStage", "CameraFocalLength", "Focal Length (mm)"), NSLOCTEXT("InfinityStage", "CameraLensGroup", "Camera Lens"), 30, FLinearColor(0.75f, 0.35f, 1.0f));
    AddChannel(FocusDistanceCm, TEXT("Camera.FocusDistanceCm"), NSLOCTEXT("InfinityStage", "CameraFocusDistance", "Focus Distance (cm)"), NSLOCTEXT("InfinityStage", "CameraLensGroup", "Camera Lens"), 31, FLinearColor(0.35f, 0.9f, 0.9f));
    AddChannel(WingInwardTravelScale, TEXT("Wing.InwardTravelScale"), NSLOCTEXT("InfinityStage", "WingTravelScale", "Inward Travel Scale"), NSLOCTEXT("InfinityStage", "WingMovementGroup", "Wing Movement"), 40, FLinearColor(0.40f, 0.95f, 0.55f));
    AddChannel(WingCycleRateScale, TEXT("Wing.CycleRateScale"), NSLOCTEXT("InfinityStage", "WingRateScale", "Cycle Rate Scale"), NSLOCTEXT("InfinityStage", "WingMovementGroup", "Wing Movement"), 41, FLinearColor(0.95f, 0.45f, 0.75f));
    AddChannel(WingPhaseBiasCycles, TEXT("Wing.PhaseBiasCycles"), NSLOCTEXT("InfinityStage", "WingPhaseBias", "Phase Bias (cycles)"), NSLOCTEXT("InfinityStage", "WingMovementGroup", "Wing Movement"), 42, FLinearColor(0.60f, 0.70f, 1.0f));
#else
    Channels.Add(SpeedMultiplier);
    Channels.Add(LongitudinalOffsetCm);
    Channels.Add(LateralOffsetCm);
    Channels.Add(HeightOffsetCm);
    Channels.Add(PitchDegrees);
    Channels.Add(YawDegrees);
    Channels.Add(RollDegrees);
    Channels.Add(LookAheadDistanceCm);
    Channels.Add(FocalLengthMm);
    Channels.Add(FocusDistanceCm);
    Channels.Add(WingInwardTravelScale);
    Channels.Add(WingCycleRateScale);
    Channels.Add(WingPhaseBiasCycles);
#endif
    ChannelProxy = MakeShared<FMovieSceneChannelProxy>(MoveTemp(Channels));
    return EMovieSceneChannelProxyType::Static;
}

UMovieSceneInfinityPassageTrack::UMovieSceneInfinityPassageTrack(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    OwnerGuid = FGuid::NewGuid();
}

UMovieSceneSection* UMovieSceneInfinityPassageTrack::CreateNewSection()
{
    return NewObject<UMovieSceneInfinityPassageSection>(this, NAME_None, RF_Transactional);
}

bool UMovieSceneInfinityPassageTrack::IsEmpty() const
{
    return Sections.IsEmpty();
}

bool UMovieSceneInfinityPassageTrack::SupportsType(const TSubclassOf<UMovieSceneSection> SectionClass) const
{
    return SectionClass == UMovieSceneInfinityPassageSection::StaticClass();
}

void UMovieSceneInfinityPassageTrack::AddSection(UMovieSceneSection& Section)
{
    Sections.AddUnique(&Section);
}

const TArray<UMovieSceneSection*>& UMovieSceneInfinityPassageTrack::GetAllSections() const
{
    return Sections;
}

bool UMovieSceneInfinityPassageTrack::HasSection(const UMovieSceneSection& Section) const
{
    return Sections.Contains(&Section);
}

void UMovieSceneInfinityPassageTrack::RemoveSection(UMovieSceneSection& Section)
{
    Sections.Remove(&Section);
}

void UMovieSceneInfinityPassageTrack::RemoveSectionAt(const int32 SectionIndex)
{
    Sections.RemoveAt(SectionIndex);
}

FMovieSceneEvalTemplatePtr UMovieSceneInfinityPassageTrack::CreateTemplateForSection(const UMovieSceneSection& InSection) const
{
    return FMovieSceneInfinityPassageSectionTemplate(*CastChecked<const UMovieSceneInfinityPassageSection>(&InSection));
}

#if WITH_EDITORONLY_DATA
FText UMovieSceneInfinityPassageTrack::GetDisplayName() const
{
    return NSLOCTEXT("InfinityStage", "PassageTrackName", "Infinity Stage Passages");
}
#endif

FMovieSceneInfinityPassageSectionTemplate::FMovieSceneInfinityPassageSectionTemplate(const UMovieSceneInfinityPassageSection& Section)
    : PassageGuid(Section.PassageGuid)
    , EvaluationStart(Section.HasStartFrame() ? Section.GetInclusiveStartFrame() : FFrameNumber(MIN_int32))
    , EvaluationEnd(Section.HasEndFrame() ? Section.GetExclusiveEndFrame() : FFrameNumber(MAX_int32))
{
}

void FMovieSceneInfinityPassageSectionTemplate::Evaluate(
    const FMovieSceneEvaluationOperand& Operand,
    const FMovieSceneContext& Context,
    const FPersistentEvaluationData& PersistentData,
    FMovieSceneExecutionTokens& ExecutionTokens) const
{
    // A swept evaluation can include the outgoing section even when its final
    // context time belongs to the next Scene. Never issue a Passage camera or
    // mechanism token outside this section's half-open interval.
    const FFrameTime Time = Context.GetTime();
    if (Time < EvaluationStart || Time >= EvaluationEnd)
    {
        return;
    }
    ExecutionTokens.Add(FInfinityPassageExecutionToken(PassageGuid));
}
