#include "InfinityStageCameraRig.h"

#include "Components/SpotLightComponent.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "AnimCustomInstanceHelper.h"
#include "AnimSequencerInstance.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "CineCameraComponent.h"
#include "CineCameraSettings.h"
#include "Components/ChildActorComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShadowCatComponent.h"
#include "AnimationRuntime.h"
#include "Engine/SkeletalMesh.h"
#include "InfinityStageShowAsset.h"
#include "LevelSequence.h"
#include "MovieScene.h"
#include "MovieSceneInfinityPassageTrack.h"
#include "Math/RotationMatrix.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageShadowCat, Log, All);

namespace
{
UAnimSequence* GetShadowCatWalkAnimation()
{
    static UAnimSequence* WalkAnimation = LoadObject<UAnimSequence>(
        nullptr,
        TEXT("/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Move/A_Cat_Move_Walk_F.A_Cat_Move_Walk_F"));
    return WalkAnimation;
}

UAnimSequence* GetShadowCatIdleAnimation()
{
    static UAnimSequence* IdleAnimation = LoadObject<UAnimSequence>(
        nullptr,
        TEXT("/Game/CharacterPacks/AnimX/_Common/CatMannequin/Anim/Idle/A_Cat_Idle_Base.A_Cat_Idle_Base"));
    return IdleAnimation;
}

void ApplyMasterTimedShadowCatAnimation(
    USkeletalMeshComponent* CatMesh,
    UAnimSequence* GaitAnimation,
    const double GaitPositionSeconds,
    UAnimSequence* ActionAnimation,
    const double ActionPositionSeconds,
    const double ActionWeight)
{
    if (!CatMesh || !GaitAnimation)
    {
        return;
    }

    // The no-action gait stays on the existing single-node instance exactly
    // as required: stopped, explicitly positioned, and never wall-time played.
    if (!ActionAnimation || ActionWeight <= UE_DOUBLE_SMALL_NUMBER)
    {
        if (CatMesh->GetAnimationMode() != EAnimationMode::AnimationSingleNode)
        {
            CatMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        }
        UAnimSingleNodeInstance* SingleNode = CatMesh->GetSingleNodeInstance();
        if (SingleNode)
        {
            SingleNode->SetAnimationAsset(GaitAnimation, true, 0.0f);
            SingleNode->SetLooping(true);
            SingleNode->SetPlaying(false);
            SingleNode->SetPosition(static_cast<float>(GaitPositionSeconds), false);
        }
        CatMesh->TickAnimation(0.0f, false);
        CatMesh->RefreshBoneTransforms();
        return;
    }

    bool bWasCreated = false;
    UAnimSequencerInstance* Sequencer =
        FAnimCustomInstanceHelper::BindToSkeletalMeshComponent<UAnimSequencerInstance>(CatMesh, bWasCreated);
    if (!Sequencer)
    {
        // Defensive fallback only. The normal path above is the weighted
        // Sequencer evaluator; this at least remains Master-time locked.
        CatMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
        UAnimSingleNodeInstance* SingleNode = CatMesh->GetSingleNodeInstance();
        UAnimSequence* FallbackAnimation = ActionAnimation && ActionWeight >= 0.5
            ? ActionAnimation
            : GaitAnimation;
        const double FallbackPosition = FallbackAnimation == ActionAnimation
            ? ActionPositionSeconds
            : GaitPositionSeconds;
        if (SingleNode)
        {
            SingleNode->SetAnimationAsset(FallbackAnimation, true, 0.0f);
            SingleNode->SetPlaying(false);
            SingleNode->SetPosition(static_cast<float>(FallbackPosition), false);
        }
        return;
    }

    constexpr int32 GaitSequenceId = 1;
    constexpr int32 ActionSequenceId = 2;
    const float BlendWeight = static_cast<float>(FMath::Clamp(ActionWeight, 0.0, 1.0));
    Sequencer->ResetNodes();
    if (BlendWeight < 1.0f)
    {
        Sequencer->UpdateAnimTrack(
            GaitAnimation,
            GaitSequenceId,
            static_cast<float>(GaitPositionSeconds),
            1.0f - BlendWeight,
            false);
    }
    if (ActionAnimation && BlendWeight > 0.0f)
    {
        Sequencer->UpdateAnimTrack(
            ActionAnimation,
            ActionSequenceId,
            static_cast<float>(ActionPositionSeconds),
            BlendWeight,
            false);
    }

    // Evaluation happens before the bob sample in EvaluateAtMasterFrame, so
    // refresh now rather than letting wall-time component ticking choose when
    // this Master pose reaches the bones.
    CatMesh->TickAnimation(0.0f, false);
    CatMesh->RefreshBoneTransforms();
}

double WrapAnimationPosition(const double PositionSeconds, const UAnimSequence* Animation)
{
    const double Length = Animation ? Animation->GetPlayLength() : 0.0;
    if (Length <= UE_DOUBLE_SMALL_NUMBER)
    {
        return 0.0;
    }
    double Wrapped = FMath::Fmod(PositionSeconds, Length);
    if (Wrapped < 0.0)
    {
        Wrapped += Length;
    }
    return Wrapped;
}

double SmoothUnit(const double Alpha)
{
    const double Clamped = FMath::Clamp(Alpha, 0.0, 1.0);
    return Clamped * Clamped * (3.0 - 2.0 * Clamped);
}

double SeededSignedUnit(const int32 Seed, const int32 Salt)
{
    FRandomStream Stream(Seed ^ Salt);
    const float Draw = Stream.FRand();
    return static_cast<double>(Draw) * 2.0 - 1.0;
}

struct FResolvedShadowCatAction
{
    UAnimSequence* Animation = nullptr;
    FInfinityShadowCatActionTiming Timing;
    EInfinityShadowCatCameraMode CameraMode = EInfinityShadowCatCameraMode::Route;
    EInfinityShadowCatBodyVisibility BodyVisibility = EInfinityShadowCatBodyVisibility::ShadowOnly;
    FName HeadPOVBone = TEXT("Head");
    FVector HeadPOVOffsetCm = FVector(12.0, 0.0, 3.0);
    int32 StartFrame = INDEX_NONE;
};

FResolvedShadowCatAction ResolveShadowCatAction(
    const FInfinityPassageSettings* Settings,
    const double PassageSeconds,
    const double PassageDurationSeconds,
    const double TickRate)
{
    FResolvedShadowCatAction Result;
    if (!Settings || TickRate <= UE_DOUBLE_SMALL_NUMBER)
    {
        return Result;
    }

    for (const FInfinityShadowCatAction& Action : Settings->ShadowCatActions)
    {
        if (Action.Animation.IsNull() || Action.StartFrame.Value < 0
            || Action.StartFrame.Value < Result.StartFrame)
        {
            continue;
        }
        UAnimSequence* Animation = Action.Animation.LoadSynchronous();
        if (!Animation || Animation->GetPlayLength() <= UE_DOUBLE_SMALL_NUMBER)
        {
            continue;
        }
        const double ActionStartSeconds = static_cast<double>(Action.StartFrame.Value) / TickRate;
        const FInfinityShadowCatActionTiming Timing =
            AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
                PassageSeconds,
                PassageDurationSeconds,
                ActionStartSeconds,
                Animation->GetPlayLength(),
                Action.PlayRate,
                Action.BlendInSeconds,
                Action.BlendOutSeconds,
                Action.bHoldLastFrame);
        if (Timing.bActive)
        {
            Result.Animation = Animation;
            Result.Timing = Timing;
            Result.CameraMode = Action.CameraMode;
            Result.BodyVisibility = Action.BodyVisibility;
            Result.HeadPOVBone = Action.HeadPOVBone;
            Result.HeadPOVOffsetCm = Action.HeadPOVOffsetCm;
            Result.StartFrame = Action.StartFrame.Value;
        }
    }
    return Result;
}

const FInfinityCompiledPassage* FindCompiledPassage(const FInfinityCompileResult& Compiled, const FGuid& PassageGuid)
{
    return Compiled.Passages.FindByPredicate([&PassageGuid](const FInfinityCompiledPassage& Candidate)
    {
        return Candidate.PassageGuid == PassageGuid;
    });
}

}

AInfinityStageCameraRig::AInfinityStageCameraRig()
{
    // Ticks in game worlds only (actors do not tick in the editor), and last in
    // the frame, so the figures' visibility follows a view-target change made
    // earlier in the same frame instead of flashing for one frame in the next shot.
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_LastDemotable;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SetRootComponent(SceneRoot);

    Camera = CreateDefaultSubobject<UCineCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(SceneRoot);

    ShadowFigureRoot = CreateDefaultSubobject<USceneComponent>(TEXT("ShadowFigureRoot"));
    ShadowFigureRoot->SetupAttachment(SceneRoot);
    ShadowFigureRoot->SetAbsolute(false, false, true);
    ShadowFigureRoot->SetRelativeLocation(ShadowFigureOffset);

    ShadowCat = CreateDefaultSubobject<UInfinityStageShadowCatComponent>(TEXT("ShadowCat"));
    ShadowCat->SetupAttachment(ShadowFigureRoot);

    // Behind the camera and pointing forward, so the shadow figure reads as a
    // silhouette thrown onto the stage rather than a lit object in frame.
    FollowLight = CreateDefaultSubobject<USpotLightComponent>(TEXT("FollowLight"));
    FollowLight->SetupAttachment(SceneRoot);
    FollowLight->SetRelativeLocation(FollowLightOffset);
    FollowLight->SetRelativeRotation(FollowLightRotation);
    FollowLight->SetVisibility(bEnableFollowLight);
    FollowLight->SetOuterConeAngle(42.0f);
    FollowLight->SetInnerConeAngle(18.0f);
    FollowLight->SetAttenuationRadius(6000.0f);
    FollowLight->SetCastShadows(true);
    ShadowCat->SetRelativeTransform(BuildShadowCatRelativeTransform());

    ShadowCat->SetChildActorClass(AInfinityStageShadowCatActor::StaticClass());
}

void AInfinityStageCameraRig::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
    ConfigureShadowCat();
    ConfigureFollowLight();
}

void AInfinityStageCameraRig::ConfigureFollowLight()
{
    if (!FollowLight)
    {
        return;
    }
    // Driven from properties on construction so Details edits apply live, rather
    // than only at spawn.
    ApplyFollowLightState();
}

double AInfinityStageCameraRig::EvaluateShadowSpot(
    const TArray<FInfinityShadowSpotCue>& Cues,
    const double PassageSeconds,
    float& OutIntensity)
{
    double BestWeight = 0.0;
    OutIntensity = 0.0f;
    for (const FInfinityShadowSpotCue& Cue : Cues)
    {
        const double Attack = FMath::Max(0.0, Cue.AttackSeconds);
        const double Hold = FMath::Max(0.0, Cue.HoldSeconds);
        const double Release = FMath::Max(0.0, Cue.ReleaseSeconds);
        const double Local = PassageSeconds - Cue.PassageSeconds;
        double Weight = 0.0;
        if (Local < 0.0 || Local >= Attack + Hold + Release)
        {
            Weight = 0.0;
        }
        else if (Local < Attack)
        {
            Weight = FMath::SmoothStep(0.0, 1.0, Local / Attack);
        }
        else if (Local <= Attack + Hold)
        {
            Weight = 1.0;
        }
        else
        {
            Weight = 1.0 - FMath::SmoothStep(0.0, 1.0, (Local - Attack - Hold) / Release);
        }
        BestWeight = FMath::Max(BestWeight, Weight);
        OutIntensity = FMath::Max(
            OutIntensity,
            static_cast<float>(Weight) * FMath::Max(0.0f, Cue.Intensity));
    }
    return FMath::Clamp(BestWeight, 0.0, 1.0);
}

bool AInfinityStageCameraRig::ShouldShowFollowLight(
    const bool bEnableFollowLightIn,
    const bool bLive,
    const bool bHasShadowSpotCues,
    const double ShadowSpotWeight)
{
    if (!bLive)
    {
        return false;
    }
    return bHasShadowSpotCues ? ShadowSpotWeight > 0.0 : bEnableFollowLightIn;
}

void AInfinityStageCameraRig::ApplyFollowLightState()
{
    if (!FollowLight)
    {
        return;
    }
    const bool bHasCues = !ShadowSpotCues.IsEmpty();
    if (bHasCues)
    {
        // The schedule owns the light's placement, shadows and intensity; its
        // units, cone, colour and radii stay as set on the component.
        FollowLight->SetRelativeLocation(ShadowSpotOffset);
        FollowLight->SetRelativeRotation(ShadowSpotRotation);
        FollowLight->SetCastShadows(true);
        if (!FMath::IsNearlyEqual(FollowLight->Intensity, CurrentShadowSpotIntensity))
        {
            FollowLight->SetIntensity(CurrentShadowSpotIntensity);
        }
    }
    else
    {
        FollowLight->SetRelativeLocation(FollowLightOffset);
        FollowLight->SetRelativeRotation(FollowLightRotation);
    }
    FollowLight->SetVisibility(ShouldShowFollowLight(
        bEnableFollowLight, bShadowFiguresLive, bHasCues, CurrentShadowSpotWeight));
}

void AInfinityStageCameraRig::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateShadowFigureVisibility();
}

void AInfinityStageCameraRig::UpdateShadowFigureVisibility()
{
    const UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld())
    {
        return;
    }
    bool bLive = false;
    if (const APlayerController* PlayerController = World->GetFirstPlayerController())
    {
        // Mid-blend, GetViewTarget() already reports the INCOMING camera in UE
        // 5.8, so also wait for the blend to finish. Otherwise a stalls-to-rig
        // blend would fly the view past the cat while it is being shown.
        const APlayerCameraManager* CameraManager = PlayerController->PlayerCameraManager;
        bLive = PlayerController->GetViewTarget() == this
            && (!CameraManager || CameraManager->BlendTimeToGo <= 0.0f);
    }
    if (bLive != bShadowFiguresLive)
    {
        bShadowFiguresLive = bLive;
        ApplyShadowFigureVisibility();
    }
}

bool AInfinityStageCameraRig::ShouldDrawShadowCatBody() const
{
    const UWorld* World = GetWorld();
    return bShadowCatRenderInMainPass && !(World && World->IsGameWorld());
}

static void ApplyShadowCatBodyRendering(
    USkeletalMeshComponent* CatMesh,
    const bool bDrawBody,
    const bool bGameWorld,
    const bool bVisibleInReflections,
    const EInfinityShadowCatBodyVisibility BodyVisibility)
{
    if (!CatMesh)
    {
        return;
    }

    const bool bPOVBody = bGameWorld && BodyVisibility == EInfinityShadowCatBodyVisibility::POVBody;
    const bool bReflectionOnly = bGameWorld
        && BodyVisibility == EInfinityShadowCatBodyVisibility::ReflectionOnly;
    CatMesh->SetRenderInMainPass(bPOVBody || (!bGameWorld && bDrawBody));
    CatMesh->SetVisibleInRayTracing(
        bVisibleInReflections && (!bGameWorld || bPOVBody || bReflectionOnly));
    CatMesh->SetVisibleInSceneCaptureOnly(false);
    CatMesh->SetHiddenInSceneCapture(false);
    if (!bGameWorld)
    {
        return;
    }

    const bool bCaptureVisible = bVisibleInReflections && (bPOVBody || bReflectionOnly);
    bool bCaptureVisibilityChanged = false;
    if (CatMesh->bVisibleInReflectionCaptures != bCaptureVisible)
    {
        CatMesh->bVisibleInReflectionCaptures = bCaptureVisible;
        bCaptureVisibilityChanged = true;
    }
    if (CatMesh->bVisibleInRealTimeSkyCaptures != bCaptureVisible)
    {
        CatMesh->bVisibleInRealTimeSkyCaptures = bCaptureVisible;
        bCaptureVisibilityChanged = true;
    }
    if (CatMesh->bVisibleInReflections != bVisibleInReflections)
    {
        CatMesh->bVisibleInReflections = bVisibleInReflections;
        bCaptureVisibilityChanged = true;
    }
    if (bCaptureVisibilityChanged)
    {
        CatMesh->MarkRenderStateDirty();
    }
    CatMesh->SetRenderInDepthPass(false);
}

void AInfinityStageCameraRig::ApplyShadowFigureVisibility()
{
    // Live: the cat is present for its SHADOW (the follow light throws it
    // ahead); in a game world its body stays out of the main pass, so no camera
    // ever sees a cat in front of it. Not live: neither body nor shadow.
    const bool bShowCat = bEnableShadowCat && bShadowFiguresLive;
    if (AActor* CatActor = ShadowCat ? ShadowCat->GetChildActor() : nullptr)
    {
        CatActor->SetActorHiddenInGame(!bShowCat);
        TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
        for (USkeletalMeshComponent* CatMesh : CatMeshes)
        {
            CatMesh->SetHiddenInGame(!bShowCat, true);
            ApplyShadowCatBodyRendering(
                CatMesh,
                ShouldDrawShadowCatBody(),
                GetWorld() && GetWorld()->IsGameWorld(),
                bShadowCatVisibleInReflections,
                CurrentShadowCatBodyVisibility);
            CatMesh->SetCastShadow(bShadowCatCastShadow);
        }
    }
    ApplyFollowLightState();
}

void AInfinityStageCameraRig::BeginPlay()
{
    Super::BeginPlay();

    // Recompiling the scoped adapter while ChildActorComponents are present can
    // leave old preview children in the editor world. PIE duplicates those
    // orphans alongside the component-owned cat, producing one still cat and
    // one animated cat. Remove only unclaimed instances of our scoped adapter.
    DestroyOrphanedShadowCats();

    // PIE duplicates can restore Blueprint tick defaults after construction.
    // Reassert the camera-driven configuration once the game world is live.
    // A rig is not live until the player is looking through it: while the
    // Opening's stalls cut is up, the P01 rig is never evaluated, and its cat
    // would otherwise stand wherever the last level save left it, in shot.
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        bShadowFiguresLive = false;
        HideCameraBodyInGame();
    }
    ConfigureShadowCat();
    ApplyShadowFigureVisibility();
    UpdateShadowFigureVisibility();
}

void AInfinityStageCameraRig::HideCameraBodyInGame()
{
    if (!Camera)
    {
        return;
    }
#if WITH_EDITORONLY_DATA
    Camera->bCameraMeshHiddenInGame = true;
#endif
    // The proxy already exists by now (the camera builds it on register, from
    // the flag as saved), so hide it directly. Only editor-only meshes hung on
    // the camera: that is the proxy, never a real prop.
    TInlineComponentArray<UStaticMeshComponent*> Meshes(this);
    for (UStaticMeshComponent* Mesh : Meshes)
    {
        if (Mesh && Mesh->GetAttachParent() == Camera && Mesh->IsEditorOnly())
        {
            Mesh->SetHiddenInGame(true);
        }
    }
}

FTransform AInfinityStageCameraRig::BuildShadowCatRelativeTransform() const
{
    FTransform Result = ShadowCatRelativeTransform;
    Result.AddToTranslation(ShadowCatPositionOffset);
    Result.ConcatenateRotation(ShadowCatRotationOffset.Quaternion());
    Result.SetScale3D(Result.GetScale3D() * FMath::Max(0.01, ShadowCatUniformScale));
    Result.NormalizeRotation();
    return Result;
}

void AInfinityStageCameraRig::DestroyOrphanedShadowCats()
{
    UWorld* World = GetWorld();
    if (!World || !World->IsGameWorld())
    {
        return;
    }

    // One pass is enough for a PIE world. All ChildActorComponents have created
    // their current children before Actor BeginPlay is dispatched.
    static TWeakObjectPtr<UWorld> LastCleanedWorld;
    if (LastCleanedWorld.Get() == World)
    {
        return;
    }
    LastCleanedWorld = World;

    TSet<AActor*> ClaimedCats;
    for (TActorIterator<AInfinityStageCameraRig> RigIt(World); RigIt; ++RigIt)
    {
        if (RigIt->ShadowCat)
        {
            if (AActor* ClaimedCat = RigIt->ShadowCat->GetChildActor())
            {
                ClaimedCats.Add(ClaimedCat);
            }
        }
    }

    int32 RemovedCount = 0;
    for (TActorIterator<AActor> ActorIt(World); ActorIt; ++ActorIt)
    {
        AActor* Candidate = *ActorIt;
        const bool bIsScopedAdapter = Candidate
            && Candidate->IsA<AInfinityStageShadowCatActor>();
        if (!bIsScopedAdapter || ClaimedCats.Contains(Candidate))
        {
            continue;
        }

        Candidate->SetActorHiddenInGame(true);
        Candidate->SetActorEnableCollision(false);
        Candidate->Destroy();
        ++RemovedCount;
    }

    UE_LOG(
        LogInfinityStageShadowCat,
        Display,
        TEXT("SHADOW_CAT_ORPHAN_CLEANUP|world=%s|removed=%d|claimed=%d"),
        *World->GetName(),
        RemovedCount,
        ClaimedCats.Num());
}

bool AInfinityStageCameraRig::EvaluateAtMasterFrame(const FFrameNumber MasterFrame)
{
    if (!PassageActor || !PassageActor->ShowAsset)
    {
        return false;
    }
    // One compile serves this frame's pose and the neighbouring speed samples
    // below. This only removes a redundant recompute; compile cost is not a
    // problem. Measured 2026-09-25 on the production Show (274 cues): 0.047 ms
    // per compile, about five per playback frame across the rig, the Passage
    // mechanisms and AInfinityStageShowRoot's camera-owner and curtain queries.
    // Those per-call compiles are deliberately NOT cached: the Show is mutated
    // without Modify() (EnsureStableIds and ReconcilePassageSettings inside
    // InitializeTransport; tests edit fixtures and evaluate in one frame), so a
    // cache would serve a stale segment table, meaning a wrong camera owner or
    // curtain state with the dog driving.
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*PassageActor->ShowAsset);
    const FInfinityCompiledPassage* Passage = FindCompiledPassage(Compiled, PassageActor->PassageGuid);
    FTransform CameraTransform;
    FInfinityPassageCameraEvaluation CameraEvaluation;
    if (!Passage || !GetCameraStateForCompiledPassage(*Passage, MasterFrame, CameraTransform, CameraEvaluation))
    {
        return false;
    }
    // Establish this master frame's speed before sampling or applying its gait
    // lift, so no weight can leak in from a previous play of this rig.
    UpdateShadowCatAtMasterFrame(MasterFrame, CameraTransform, *Passage);
    const FFrameRate& TickResolution = PassageActor->ShowAsset->TickResolution;
    const double TickRate = TickResolution.IsValid() ? TickResolution.AsDecimal() : 0.0;
    const double MasterSeconds = TickRate > UE_DOUBLE_SMALL_NUMBER
        ? static_cast<double>(MasterFrame.Value) / TickRate
        : 0.0;
    // Puss shadow spot (PS): Passage-relative, so it travels with the Passage.
    if (!ShadowSpotCues.IsEmpty())
    {
        const double PassageSeconds = TickRate > UE_DOUBLE_SMALL_NUMBER
            ? static_cast<double>(MasterFrame.Value - Passage->SegmentStartFrame.Value) / TickRate
            : 0.0;
        CurrentShadowSpotWeight = EvaluateShadowSpot(ShadowSpotCues, PassageSeconds, CurrentShadowSpotIntensity);
    }
    else
    {
        CurrentShadowSpotWeight = 0.0;
        CurrentShadowSpotIntensity = 0.0f;
    }
    ApplyFollowLightState();
    const double RawLiftCm = SampleShadowCatGaitLiftCm(CurrentShadowCatBobGainScale);
    // The walk weight already follows speed; the crossing settle weight is the
    // settle's own share of that speed, a pure function of Master time, so the
    // bob and its roll are exactly 0 at the Passage end whatever the history.
    CurrentCrossingSettleWeight = CameraEvaluation.SettleWeight;
    const FInfinityGaitBob GaitBob = SettleGaitBob(
        SettleGaitBob(
            StepGaitBob(
                ShadowCatGaitBobState,
                MasterSeconds,
                RawLiftCm,
                CurrentShadowCatCameraSpeedCmPerSecond,
                ShadowCatReferenceWalkSpeedCmPerSecond,
                ShadowCatCameraBobRollMeanSeconds,
                ShadowCatBobFadeSeconds,
                ShadowCatCameraBobRollDegreesPerCm),
            CurrentCrossingSettleWeight),
        1.0 - CurrentShadowCatActionWeight);
    CurrentShadowCatBobWalkWeight = ShadowCatGaitBobState.WalkWeight;
    CurrentShadowCatCameraBobCm = GaitBob.HeightCm;
    if (!FMath::IsNearlyZero(CurrentShadowCatCameraBobCm))
    {
        CameraTransform.AddToTranslation(FVector(0.0, 0.0, CurrentShadowCatCameraBobCm));
    }
    if (!FMath::IsNearlyZero(GaitBob.RollDeg))
    {
        const FQuat Roll = FRotator(0.0, 0.0, GaitBob.RollDeg).Quaternion();
        CameraTransform.SetRotation((CameraTransform.GetRotation() * Roll).GetNormalized());
    }

    SetActorTransform(CameraTransform);
    Camera->SetCurrentFocalLength(static_cast<float>(CameraEvaluation.FocalLengthMm));
    Camera->FocusSettings.FocusMethod = ECameraFocusMethod::Manual;
    Camera->FocusSettings.ManualFocusDistance = static_cast<float>(CameraEvaluation.FocusDistanceCm);

    // The cat rides the rig, so counter the lift here or it would bob twice,
    // and counter the keyed eye height (Camera.HeightOffsetCm) or a lowered
    // eye would sink the cat into the floor.
    const FVector ShadowFigureWorldOffset = GetActorTransform().TransformVectorNoScale(ShadowFigureOffset);
    ShadowFigureRoot->SetWorldLocation(
        GetActorLocation() + ShadowFigureWorldOffset - FVector(0.0, 0.0, CurrentShadowCatCameraBobCm)
        - CameraEvaluation.HeightOffsetWorldCm);
    ShadowFigureRoot->SetWorldScale3D(FVector::OneVector);
    if (bKeepShadowFiguresWorldUpright)
    {
        const FRotator CameraRotation = GetActorRotation();
        ShadowFigureRoot->SetWorldRotation(FRotator(0.0, CameraRotation.Yaw, 0.0));
    }
    ApplyShadowCatActionRendering();
    ApplyShadowCatPOVCamera(CameraTransform);

    CurrentCameraDistanceCm = CameraEvaluation.DistanceCm;
    PassageActor->EvaluateMechanismsAtCameraDistance(MasterFrame, CameraEvaluation.DistanceCm);
    return true;
}

void AInfinityStageCameraRig::ConfigureShadowCat()
{
    if (!ShadowCat)
    {
        return;
    }

    const FVector ShadowFigureWorldOffset = GetActorTransform().TransformVectorNoScale(ShadowFigureOffset);
    ShadowFigureRoot->SetWorldLocation(GetActorLocation() + ShadowFigureWorldOffset);
    ShadowFigureRoot->SetWorldScale3D(FVector::OneVector);

    // Existing level instances may still serialize the old vendor-derived
    // Blueprint class. Override it in memory so no authoring-data resave is
    // required and the HUD/character-control dependency tree is never loaded.
    UClass* ShadowCatActorClass = AInfinityStageShadowCatActor::StaticClass();
    if (ShadowCat->GetChildActorClass() != ShadowCatActorClass)
    {
        ShadowCat->SetChildActorClass(ShadowCatActorClass);
    }

    ShadowCat->SetRelativeTransform(BuildShadowCatRelativeTransform());
    AActor* CatActor = ShadowCat->GetChildActor();
    if (!CatActor)
    {
        return;
    }

    CatActor->SetActorHiddenInGame(!(bEnableShadowCat && bShadowFiguresLive));
    CatActor->SetActorEnableCollision(false);
    CatActor->SetActorTickEnabled(false);

    TInlineComponentArray<UPrimitiveComponent*> CatPrimitives(CatActor);
    for (UPrimitiveComponent* Primitive : CatPrimitives)
    {
        Primitive->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }

    static USkeletalMesh* ShadowCatSkeletalMesh = LoadObject<USkeletalMesh>(
        nullptr,
        TEXT("/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R.SK_Cat_R"));

    TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
    for (USkeletalMeshComponent* CatMesh : CatMeshes)
    {
        // The scoped adapter intentionally bypasses AnimX's gameplay BeginPlay.
        // Do not rely on that event to assign or reveal the selected style mesh.
        if (!CatMesh->GetSkeletalMeshAsset() && ShadowCatSkeletalMesh)
        {
            CatMesh->SetSkeletalMeshAsset(ShadowCatSkeletalMesh);
        }
        CatMesh->SetActive(bEnableShadowCat, true);
        CatMesh->SetComponentTickEnabled(bEnableShadowCat);
        CatMesh->bPauseAnims = false;
        CatMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        CatMesh->SetVisibility(bEnableShadowCat, true);
        CatMesh->SetHiddenInGame(!(bEnableShadowCat && bShadowFiguresLive), true);
        CatMesh->SetCastShadow(bShadowCatCastShadow);
        ApplyShadowCatBodyRendering(
            CatMesh,
            ShouldDrawShadowCatBody(),
            GetWorld() && GetWorld()->IsGameWorld(),
            bShadowCatVisibleInReflections,
            CurrentShadowCatBodyVisibility);
    }

    const FName ReadyTag(TEXT("InfinityStageShadowCatReady"));
    if (!CatActor->Tags.Contains(ReadyTag))
    {
        CatActor->Tags.Add(ReadyTag);
        const USkeletalMeshComponent* PrimaryCatMesh = CatMeshes.IsEmpty() ? nullptr : CatMeshes[0];
        UE_LOG(
            LogInfinityStageShadowCat,
            Display,
            TEXT("SHADOW_CAT_READY|rig=%s|actor=%s|rig_location=%s|cat_location=%s|requested_offset=%s|actual_world_offset=%s|cat_scale=%s|force_walk=%d|direct_walk=%d|walk_blend_speed=%.2f|max_play_rate=%.2f|mesh=%s|animation=%s|visible=%d|hidden_in_game=%d|registered=%d"),
            *GetName(),
            *CatActor->GetName(),
            *GetActorLocation().ToCompactString(),
            *CatActor->GetActorLocation().ToCompactString(),
            *ShadowFigureOffset.ToCompactString(),
            *(CatActor->GetActorLocation() - GetActorLocation()).ToCompactString(),
            *CatActor->GetActorScale3D().ToCompactString(),
            bShadowCatForceWalk,
            bShadowCatUseDirectWalkAnimation,
            ShadowCatWalkBlendSpeedCmPerSecond,
            ShadowCatMaxPlayRate,
            PrimaryCatMesh && PrimaryCatMesh->GetSkeletalMeshAsset()
                ? *PrimaryCatMesh->GetSkeletalMeshAsset()->GetPathName()
                : TEXT("None"),
            PrimaryCatMesh && PrimaryCatMesh->GetSingleNodeInstance()
                && PrimaryCatMesh->GetSingleNodeInstance()->GetAnimationAsset()
                ? *PrimaryCatMesh->GetSingleNodeInstance()->GetAnimationAsset()->GetPathName()
                : TEXT("None"),
            PrimaryCatMesh ? PrimaryCatMesh->IsVisible() : false,
            CatActor->IsHidden(),
            PrimaryCatMesh ? PrimaryCatMesh->IsRegistered() : false);
    }

}

void AInfinityStageCameraRig::ApplyShadowCatActionRendering()
{
    AActor* CatActor = ShadowCat ? ShadowCat->GetChildActor() : nullptr;
    if (!CatActor)
    {
        return;
    }

    TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
    const FName PreviouslyHiddenBone = ShadowCatLastHiddenPOVBone;
    const bool bHidePOVHead = CurrentShadowCatBodyVisibility
        == EInfinityShadowCatBodyVisibility::POVBody;
    for (USkeletalMeshComponent* CatMesh : CatMeshes)
    {
        if (!PreviouslyHiddenBone.IsNone())
        {
            CatMesh->UnHideBoneByName(PreviouslyHiddenBone);
        }

        if (bHidePOVHead
            && CatMesh->GetBoneIndex(CurrentShadowCatHeadPOVBone) != INDEX_NONE)
        {
            // UE 5.8 HideBoneByName scales this bone (and therefore its children)
            // to zero. This is not view-specific: the POV body keeps casting a
            // body shadow, but the hidden head is absent from that shadow too.
            CatMesh->HideBoneByName(CurrentShadowCatHeadPOVBone, PBO_None);
        }

        ApplyShadowCatBodyRendering(
            CatMesh,
            ShouldDrawShadowCatBody(),
            GetWorld() && GetWorld()->IsGameWorld(),
            bShadowCatVisibleInReflections,
            CurrentShadowCatBodyVisibility);
        CatMesh->SetCastShadow(bShadowCatCastShadow);
    }
    ShadowCatLastHiddenPOVBone = bHidePOVHead ? CurrentShadowCatHeadPOVBone : NAME_None;
}

void AInfinityStageCameraRig::ApplyShadowCatPOVCamera(const FTransform& RouteCameraTransform)
{
    if (!Camera)
    {
        return;
    }
    if (!bShadowCatRouteNearClipCached)
    {
        bShadowCatRouteNearClipCached = true;
        bShadowCatRouteNearClipOverride = Camera->bOverride_CustomNearClippingPlane;
        ShadowCatRouteNearClipCm = Camera->CustomNearClippingPlane;
    }

    const bool bWantsHeadPOV = CurrentShadowCatCameraMode == EInfinityShadowCatCameraMode::HeadPOV;
    const bool bNearClipSafe = IsShadowCatHeadPOVNearClipSafe(
        CurrentShadowCatHeadPOVOffsetCm,
        ShadowCatHeadPOVNearClipCm,
        ShadowCatHeadPOVNearClipClearanceCm);
    AActor* CatActor = ShadowCat ? ShadowCat->GetChildActor() : nullptr;
    USkeletalMeshComponent* CatMesh = nullptr;
    if (CatActor)
    {
        TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
        CatMesh = CatMeshes.IsEmpty() ? nullptr : CatMeshes[0];
    }
    const bool bBoneExists = CatMesh
        && CatMesh->GetBoneIndex(CurrentShadowCatHeadPOVBone) != INDEX_NONE;

    if (!bWantsHeadPOV || !bNearClipSafe || !bBoneExists)
    {
        ensureAlwaysMsgf(
            !bWantsHeadPOV || (bNearClipSafe && bBoneExists),
            TEXT("SHADOW_CAT_HEAD_POV_REFUSED|rig=%s|bone=%s|offset_x=%.3f|near=%.3f|clearance=%.3f|bone_exists=%d"),
            *GetName(),
            *CurrentShadowCatHeadPOVBone.ToString(),
            CurrentShadowCatHeadPOVOffsetCm.X,
            ShadowCatHeadPOVNearClipCm,
            ShadowCatHeadPOVNearClipClearanceCm,
            bBoneExists);
        Camera->bOverride_CustomNearClippingPlane = bShadowCatRouteNearClipOverride;
        Camera->SetCustomNearClippingPlane(ShadowCatRouteNearClipCm);
        Camera->SetRelativeTransform(FTransform::Identity);
        return;
    }

    Camera->bOverride_CustomNearClippingPlane = true;
    Camera->SetCustomNearClippingPlane(static_cast<float>(ShadowCatHeadPOVNearClipCm));
    const FTransform HeadTransform = CatMesh->GetSocketTransform(CurrentShadowCatHeadPOVBone, RTS_World);
    Camera->SetWorldTransform(BlendShadowCatCameraTransform(
        RouteCameraTransform,
        HeadTransform,
        CurrentShadowCatHeadPOVOffsetCm,
        CurrentShadowCatActionWeight));
}

void AInfinityStageCameraRig::UpdateShadowCatAtMasterFrame(
    const FFrameNumber MasterFrame,
    const FTransform& CameraTransform,
    const FInfinityCompiledPassage& Passage)
{
    ConfigureShadowCat();
    AActor* CatActor = ShadowCat ? ShadowCat->GetChildActor() : nullptr;
    if (!CatActor || !bEnableShadowCat)
    {
        CurrentShadowCatCameraSpeedCmPerSecond = 0.0;
        CurrentShadowCatPlayRate = 0.0;
        CurrentShadowCatActionWeight = 0.0;
        CurrentShadowCatBobGainScale = 1.0;
        CurrentShadowCatCameraMode = EInfinityShadowCatCameraMode::Route;
        CurrentShadowCatBodyVisibility = EInfinityShadowCatBodyVisibility::ShadowOnly;
        return;
    }

    CurrentShadowCatCameraSpeedCmPerSecond = CalculateCameraSpeedAtMasterFrame(
        MasterFrame,
        CameraTransform,
        Passage);
    const double ReferenceSpeed = FMath::Max(1.0, ShadowCatReferenceWalkSpeedCmPerSecond);
    const double BasePlayRate = FMath::Clamp(
        (CurrentShadowCatCameraSpeedCmPerSecond / ReferenceSpeed)
            * FMath::Max(0.0, ShadowCatAnimationSpeedMultiplier),
        FMath::Max(0.0, ShadowCatMinPlayRate),
        FMath::Max(ShadowCatMinPlayRate, ShadowCatMaxPlayRate));

    const FFrameRate& TickResolution = PassageActor->ShowAsset->TickResolution;
    const double TickRate = TickResolution.IsValid() ? TickResolution.AsDecimal() : 0.0;
    const double PassageSeconds = PassageSecondsAtMasterFrame(
        MasterFrame, Passage.SegmentStartFrame, TickResolution);
    const double PassageDurationSeconds = TickRate > UE_DOUBLE_SMALL_NUMBER
        ? static_cast<double>(Passage.SegmentEndFrame.Value - Passage.SegmentStartFrame.Value) / TickRate
        : 0.0;
    const FInfinityShadowCatVariation Variation = bShadowCatBobVariation
        ? EvaluateShadowCatVariation(
            ShadowCatVariationSeed,
            PassageSeconds,
            ShadowCatVariationDriftSeconds,
            ShadowCatPlayRateDriftAmplitude,
            ShadowCatBobGainDriftAmplitude,
            ShadowCatPerStrideVariationAmplitude,
            ShadowCatVariationStrideSeconds,
            ShadowCatPerStrideVariationChance)
        : FInfinityShadowCatVariation{};
    CurrentShadowCatPlayRate = FMath::Clamp(
        BasePlayRate * Variation.PlayRateScale,
        FMath::Max(0.0, ShadowCatMinPlayRate),
        FMath::Max(ShadowCatMinPlayRate, ShadowCatMaxPlayRate));
    CurrentShadowCatBobGainScale = Variation.BobGainScale;

    const bool bIsMoving = CurrentShadowCatCameraSpeedCmPerSecond > KINDA_SMALL_NUMBER;
    if (bShadowCatUseDirectWalkAnimation)
    {
        const FInfinityPassageSettings* Settings = PassageActor->ShowAsset->PassageSettings.FindByPredicate(
            [this](const FInfinityPassageSettings& Candidate)
            {
                return PassageActor && Candidate.PassageGuid == PassageActor->PassageGuid;
            });
        const FResolvedShadowCatAction ResolvedAction = ResolveShadowCatAction(
            Settings,
            PassageSeconds,
            PassageDurationSeconds,
            TickRate);
        CurrentShadowCatActionWeight = ResolvedAction.Timing.Weight;
        CurrentShadowCatCameraMode = ResolvedAction.Timing.bActive
            ? ResolvedAction.CameraMode
            : EInfinityShadowCatCameraMode::Route;
        CurrentShadowCatBodyVisibility = ResolveShadowCatBodyVisibility(
            ResolvedAction.Timing,
            ResolvedAction.BodyVisibility);
        CurrentShadowCatHeadPOVBone = ResolvedAction.HeadPOVBone;
        CurrentShadowCatHeadPOVOffsetCm = ResolvedAction.HeadPOVOffsetCm;
        UAnimSequence* GaitAnimation = bIsMoving
            ? GetShadowCatWalkAnimation()
            : GetShadowCatIdleAnimation();
        const double GaitPositionSeconds = bIsMoving
            ? WrapAnimationPosition(EvaluateShadowCatGaitPhaseSeconds(MasterFrame, Passage), GaitAnimation)
            : WrapAnimationPosition(PassageSeconds, GaitAnimation);
        TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
        for (USkeletalMeshComponent* CatMesh : CatMeshes)
        {
            ApplyMasterTimedShadowCatAnimation(
                CatMesh,
                GaitAnimation,
                GaitPositionSeconds,
                ResolvedAction.Animation,
                ResolvedAction.Timing.PositionSeconds,
                ResolvedAction.Timing.Weight);
        }
    }
    else
    {
        CurrentShadowCatActionWeight = 0.0;
        CurrentShadowCatCameraMode = EInfinityShadowCatCameraMode::Route;
        CurrentShadowCatBodyVisibility = EInfinityShadowCatBodyVisibility::ShadowOnly;
    }
}

double AInfinityStageCameraRig::IntegrateShadowCatPlayRates(
    const TArray<double>& IntervalPlayRates,
    const double IntervalSeconds)
{
    if (!(IntervalSeconds > 0.0) || !FMath::IsFinite(IntervalSeconds))
    {
        return 0.0;
    }
    double PhaseSeconds = 0.0;
    for (const double PlayRate : IntervalPlayRates)
    {
        if (FMath::IsFinite(PlayRate))
        {
            PhaseSeconds += FMath::Max(0.0, PlayRate) * IntervalSeconds;
        }
    }
    return PhaseSeconds;
}

FTransform AInfinityStageCameraRig::BlendShadowCatCameraTransform(
    const FTransform& RouteCameraTransform,
    const FTransform& HeadBoneTransform,
    const FVector& HeadLocalOffsetCm,
    const double Weight)
{
    const double Alpha = FMath::Clamp(Weight, 0.0, 1.0);
    FTransform HeadCameraTransform = HeadBoneTransform;
    HeadCameraTransform.SetLocation(HeadBoneTransform.TransformPosition(HeadLocalOffsetCm));
    FTransform Result;
    Result.SetLocation(FMath::Lerp(
        RouteCameraTransform.GetLocation(),
        HeadCameraTransform.GetLocation(),
        Alpha));
    Result.SetRotation(FQuat::Slerp(
        RouteCameraTransform.GetRotation(),
        HeadCameraTransform.GetRotation(),
        Alpha).GetNormalized());
    Result.SetScale3D(FVector::OneVector);
    return Result;
}

bool AInfinityStageCameraRig::IsShadowCatHeadPOVNearClipSafe(
    const FVector& HeadLocalOffsetCm,
    const double NearClipCm,
    const double ClearanceCm)
{
    return FMath::IsFinite(HeadLocalOffsetCm.X)
        && FMath::IsFinite(NearClipCm)
        && FMath::IsFinite(ClearanceCm)
        && NearClipCm > 0.0
        && ClearanceCm >= 0.0
        && HeadLocalOffsetCm.X >= NearClipCm + ClearanceCm;
}

EInfinityShadowCatBodyVisibility AInfinityStageCameraRig::ResolveShadowCatBodyVisibility(
    const FInfinityShadowCatActionTiming& Timing,
    const EInfinityShadowCatBodyVisibility RequestedMode)
{
    return Timing.bActive
        ? RequestedMode
        : EInfinityShadowCatBodyVisibility::ShadowOnly;
}

double AInfinityStageCameraRig::PassageSecondsAtMasterFrame(
    const FFrameNumber MasterFrame,
    const FFrameNumber PassageStartFrame,
    const FFrameRate TickResolution)
{
    const double TickRate = TickResolution.IsValid() ? TickResolution.AsDecimal() : 0.0;
    return TickRate > UE_DOUBLE_SMALL_NUMBER
        ? static_cast<double>(MasterFrame.Value - PassageStartFrame.Value) / TickRate
        : 0.0;
}

FInfinityShadowCatActionTiming AInfinityStageCameraRig::EvaluateShadowCatActionTiming(
    const double PassageSeconds,
    const double PassageDurationSeconds,
    const double ActionStartSeconds,
    const double ClipLengthSeconds,
    const double PlayRate,
    const double BlendInSeconds,
    const double BlendOutSeconds,
    const bool bHoldLastFrame)
{
    FInfinityShadowCatActionTiming Result;
    const double SafeRate = FMath::Max(PlayRate, UE_DOUBLE_SMALL_NUMBER);
    const double ActionDuration = ClipLengthSeconds / SafeRate;
    const double Elapsed = PassageSeconds - ActionStartSeconds;
    const double EndSeconds = bHoldLastFrame
        ? PassageDurationSeconds
        : ActionStartSeconds + ActionDuration;
    if (Elapsed < 0.0 || PassageSeconds > EndSeconds || ActionDuration <= UE_DOUBLE_SMALL_NUMBER)
    {
        return Result;
    }

    Result.bActive = true;
    Result.PositionSeconds = FMath::Clamp(Elapsed * SafeRate, 0.0, ClipLengthSeconds);
    const double InWeight = BlendInSeconds > UE_DOUBLE_SMALL_NUMBER
        ? SmoothUnit(Elapsed / BlendInSeconds)
        : 1.0;
    const double SecondsToEnd = EndSeconds - PassageSeconds;
    const double OutWeight = BlendOutSeconds > UE_DOUBLE_SMALL_NUMBER
        ? SmoothUnit(SecondsToEnd / BlendOutSeconds)
        : (SecondsToEnd > 0.0 ? 1.0 : 0.0);
    Result.Weight = FMath::Min(InWeight, OutWeight);
    return Result;
}

FInfinityShadowCatVariation AInfinityStageCameraRig::EvaluateShadowCatVariation(
    const int32 Seed,
    const double PassageSeconds,
    const double DriftSeconds,
    const double PlayRateDriftAmplitude,
    const double BobGainDriftAmplitude,
    const double PerStrideAmplitude,
    const double StrideSeconds,
    const double PerStrideChance)
{
    const double SafeTime = FMath::Max(0.0, PassageSeconds);
    const double SafeDriftSeconds = FMath::Max(1.0, DriftSeconds);
    const int32 DriftIndex = FMath::FloorToInt(SafeTime / SafeDriftSeconds);
    const double DriftAlpha = SmoothUnit(FMath::Fmod(SafeTime, SafeDriftSeconds) / SafeDriftSeconds);

    const double PlayA = SeededSignedUnit(Seed, DriftIndex * 7919 + 101);
    const double PlayB = SeededSignedUnit(Seed, (DriftIndex + 1) * 7919 + 101);
    const double BobA = SeededSignedUnit(Seed, DriftIndex * 7919 + 307);
    const double BobB = SeededSignedUnit(Seed, (DriftIndex + 1) * 7919 + 307);
    const double PlayDrift = FMath::Lerp(PlayA, PlayB, DriftAlpha);
    const double BobDrift = FMath::Lerp(BobA, BobB, DriftAlpha);

    const double SafeStrideSeconds = FMath::Max(0.1, StrideSeconds);
    const int32 StrideIndex = FMath::FloorToInt(SafeTime / SafeStrideSeconds);
    FRandomStream GateStream(Seed ^ (StrideIndex * 3571 + 503));
    const float GateDraw = GateStream.FRand();
    double PlayStride = 0.0;
    double BobStride = 0.0;
    if (GateDraw < FMath::Clamp(PerStrideChance, 0.0, 1.0))
    {
        PlayStride = SeededSignedUnit(Seed, StrideIndex * 3571 + 701);
        BobStride = SeededSignedUnit(Seed, StrideIndex * 3571 + 907);
    }

    const double SafePlayAmplitude = FMath::Max(0.0, PlayRateDriftAmplitude);
    const double SafeBobAmplitude = FMath::Max(0.0, BobGainDriftAmplitude);
    const double SafeStrideAmplitude = FMath::Max(0.0, PerStrideAmplitude);
    FInfinityShadowCatVariation Result;
    Result.PlayRateScale = 1.0 + FMath::Clamp(
        PlayDrift * SafePlayAmplitude + PlayStride * SafeStrideAmplitude,
        -(SafePlayAmplitude + SafeStrideAmplitude),
        SafePlayAmplitude + SafeStrideAmplitude);
    Result.BobGainScale = 1.0 + FMath::Clamp(
        BobDrift * SafeBobAmplitude + BobStride * SafeStrideAmplitude,
        -(SafeBobAmplitude + SafeStrideAmplitude),
        SafeBobAmplitude + SafeStrideAmplitude);
    return Result;
}

FInfinityGaitBob AInfinityStageCameraRig::StepGaitBob(
    FInfinityGaitBobState& State,
    const double MasterSeconds,
    const double RawLiftCm,
    const double SpeedCmPerSecond,
    const double ReferenceSpeed,
    const double RollMeanSeconds,
    const double FadeSeconds,
    const double RollDegPerCm,
    const double MaxGapSeconds)
{
    const double DeltaSeconds = MasterSeconds - State.LastMasterSeconds;
    if (!State.bPrimed || DeltaSeconds < 0.0 || DeltaSeconds > MaxGapSeconds)
    {
        State.bPrimed = true;
        State.LastMasterSeconds = MasterSeconds;
        State.LiftMeanCm = RawLiftCm;
        State.WalkWeight = 0.0;
        return FInfinityGaitBob{};
    }

    if (DeltaSeconds == 0.0)
    {
        const double CentredLiftCm = RawLiftCm - State.LiftMeanCm;
        return {
            State.WalkWeight * CentredLiftCm,
            State.WalkWeight * CentredLiftCm * RollDegPerCm};
    }

    State.LastMasterSeconds = MasterSeconds;
    const double MeanAlpha = RollMeanSeconds > UE_DOUBLE_SMALL_NUMBER
        ? 1.0 - FMath::Exp(-DeltaSeconds / RollMeanSeconds)
        : 1.0;
    State.LiftMeanCm += (RawLiftCm - State.LiftMeanCm) * MeanAlpha;

    const double TargetWeight = FMath::Clamp(
        SpeedCmPerSecond / FMath::Max(1.0, ReferenceSpeed),
        0.0,
        1.0);
    const double WeightAlpha = FadeSeconds > UE_DOUBLE_SMALL_NUMBER
        ? 1.0 - FMath::Exp(-DeltaSeconds / FadeSeconds)
        : 1.0;
    State.WalkWeight += (TargetWeight - State.WalkWeight) * WeightAlpha;

    const double CentredLiftCm = RawLiftCm - State.LiftMeanCm;
    return {
        State.WalkWeight * CentredLiftCm,
        State.WalkWeight * CentredLiftCm * RollDegPerCm};
}

FInfinityGaitBob AInfinityStageCameraRig::SettleGaitBob(const FInfinityGaitBob& Bob, const double SettleWeight)
{
    const double Weight = FMath::Clamp(SettleWeight, 0.0, 1.0);
    return {Bob.HeightCm * Weight, Bob.RollDeg * Weight};
}

double AInfinityStageCameraRig::GetCrossingSettleFrames() const
{
    if (!(CrossingSettleSeconds > 0.0) || !PassageActor || !PassageActor->ShowAsset
        || !PassageActor->ShowAsset->TickResolution.IsValid())
    {
        return 0.0;
    }
    return CrossingSettleSeconds * PassageActor->ShowAsset->TickResolution.AsDecimal();
}

double AInfinityStageCameraRig::EvaluateShadowCatGaitPhaseSeconds(
    const FFrameNumber MasterFrame,
    const FInfinityCompiledPassage& Passage) const
{
    if (!PassageActor || !PassageActor->ShowAsset
        || !PassageActor->ShowAsset->TickResolution.IsValid()
        || !PassageActor->ShowAsset->DisplayRate.IsValid())
    {
        return 0.0;
    }

    const double TickRate = PassageActor->ShowAsset->TickResolution.AsDecimal();
    const double DisplayRate = PassageActor->ShowAsset->DisplayRate.AsDecimal();
    const int32 StepTicks = FMath::Max(1, FMath::RoundToInt(TickRate / DisplayRate));
    const int32 TargetFrame = FMath::Clamp(
        MasterFrame.Value,
        Passage.SegmentStartFrame.Value,
        Passage.SegmentEndFrame.Value);
    double PhaseSeconds = 0.0;
    FTransform FromTransform;
    FInfinityPassageCameraEvaluation FromEvaluation;
    if (!GetCameraStateForCompiledPassage(
        Passage, Passage.SegmentStartFrame, FromTransform, FromEvaluation))
    {
        return 0.0;
    }

    int32 FromFrame = Passage.SegmentStartFrame.Value;
    while (FromFrame < TargetFrame)
    {
        const int32 ToFrame = FMath::Min(FromFrame + StepTicks, TargetFrame);
        FTransform ToTransform;
        FInfinityPassageCameraEvaluation ToEvaluation;
        if (!GetCameraStateForCompiledPassage(
            Passage, FFrameNumber(ToFrame), ToTransform, ToEvaluation))
        {
            break;
        }
        const double IntervalSeconds = static_cast<double>(ToFrame - FromFrame) / TickRate;
        const double Speed = IntervalSeconds > UE_DOUBLE_SMALL_NUMBER
            ? FVector::Distance(FromTransform.GetLocation(), ToTransform.GetLocation()) / IntervalSeconds
            : 0.0;
        const double ReferenceSpeed = FMath::Max(1.0, ShadowCatReferenceWalkSpeedCmPerSecond);
        double PlayRate = FMath::Clamp(
            (Speed / ReferenceSpeed) * FMath::Max(0.0, ShadowCatAnimationSpeedMultiplier),
            FMath::Max(0.0, ShadowCatMinPlayRate),
            FMath::Max(ShadowCatMinPlayRate, ShadowCatMaxPlayRate));
        if (bShadowCatBobVariation)
        {
            const double MidPassageSeconds =
                (0.5 * (FromFrame + ToFrame) - Passage.SegmentStartFrame.Value) / TickRate;
            const FInfinityShadowCatVariation Variation = EvaluateShadowCatVariation(
                ShadowCatVariationSeed,
                MidPassageSeconds,
                ShadowCatVariationDriftSeconds,
                ShadowCatPlayRateDriftAmplitude,
                ShadowCatBobGainDriftAmplitude,
                ShadowCatPerStrideVariationAmplitude,
                ShadowCatVariationStrideSeconds,
                ShadowCatPerStrideVariationChance);
            PlayRate = FMath::Clamp(
                PlayRate * Variation.PlayRateScale,
                FMath::Max(0.0, ShadowCatMinPlayRate),
                FMath::Max(ShadowCatMinPlayRate, ShadowCatMaxPlayRate));
        }
        PhaseSeconds += PlayRate * IntervalSeconds;
        FromFrame = ToFrame;
        FromTransform = ToTransform;
    }
    return PhaseSeconds;
}

double AInfinityStageCameraRig::SampleShadowCatGaitLiftCm(const double VariationGainScale) const
{
    if (!bShadowCatCameraBob || !bEnableShadowCat || ShadowCatCameraBobGain <= 0.0 || !ShadowCat)
    {
        return 0.0;
    }
    const AActor* CatActor = ShadowCat->GetChildActor();
    if (!CatActor)
    {
        return 0.0;
    }
    TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
    const USkeletalMeshComponent* CatMesh = CatMeshes.IsEmpty() ? nullptr : CatMeshes[0];
    const USkeletalMesh* SkeletalMesh = CatMesh ? CatMesh->GetSkeletalMeshAsset() : nullptr;
    if (!SkeletalMesh)
    {
        return 0.0;
    }
    const FReferenceSkeleton& RefSkeleton = SkeletalMesh->GetRefSkeleton();
    const int32 BoneIndex = RefSkeleton.FindBoneIndex(ShadowCatBobReferenceBone);
    if (BoneIndex == INDEX_NONE)
    {
        return 0.0;
    }

    // The bind pose is only the stable measurement reference. A walking cat sits
    // lower than that pose, so RawLiftCm carries a persistent negative bias.
    // StepGaitBob removes its running mean from BOTH height and roll: only the
    // gait excursion moves the camera, never the walk-vs-bind pose difference.
    TArray<FTransform> RestComponentSpace;
    FAnimationRuntime::FillUpComponentSpaceTransforms(RefSkeleton, RefSkeleton.GetRefBonePose(), RestComponentSpace);
    if (!RestComponentSpace.IsValidIndex(BoneIndex))
    {
        return 0.0;
    }
    const double RestZ = RestComponentSpace[BoneIndex].GetTranslation().Z;
    const double PoseZ = CatMesh->GetSocketTransform(ShadowCatBobReferenceBone, RTS_Component).GetTranslation().Z;
    const double WorldScaleZ = CatMesh->GetComponentScale().Z;
    const double LiftCm = (PoseZ - RestZ) * WorldScaleZ * ShadowCatCameraBobGain
        * FMath::Max(0.0, VariationGainScale);

    if (!bShadowCatBobReported)
    {
        const_cast<AInfinityStageCameraRig*>(this)->bShadowCatBobReported = true;
        UE_LOG(
            LogInfinityStageShadowCat,
            Display,
            TEXT("SHADOW_CAT_BOB_READY|rig=%s|bone=%s|rest_z=%.3f|pose_z=%.3f|scale_z=%.3f|gain=%.3f|variation_gain=%.3f|lift_cm=%.3f"),
            *GetName(),
            *ShadowCatBobReferenceBone.ToString(),
            RestZ,
            PoseZ,
            WorldScaleZ,
            ShadowCatCameraBobGain,
            VariationGainScale,
            LiftCm);
    }
    return LiftCm;
}

double AInfinityStageCameraRig::CalculateCameraSpeedAtMasterFrame(
    const FFrameNumber MasterFrame,
    const FTransform& CameraTransform,
    const FInfinityCompiledPassage& Passage) const
{
    if (!PassageActor || !PassageActor->ShowAsset
        || !PassageActor->ShowAsset->TickResolution.IsValid()
        || !PassageActor->ShowAsset->DisplayRate.IsValid())
    {
        return 0.0;
    }

    const double TickRate = PassageActor->ShowAsset->TickResolution.AsDecimal();
    const double DisplayRate = PassageActor->ShowAsset->DisplayRate.AsDecimal();
    const int32 SampleFrameDelta = FMath::Max(
        1,
        FMath::RoundToInt(TickRate / DisplayRate));
    const double SampleSeconds = SampleFrameDelta / TickRate;

    FInfinityPassageCameraEvaluation SampleEvaluation;
    FTransform SampleTransform;
    if (GetCameraStateForCompiledPassage(
        Passage,
        FFrameNumber(MasterFrame.Value - SampleFrameDelta),
        SampleTransform,
        SampleEvaluation))
    {
        return FVector::Distance(CameraTransform.GetLocation(), SampleTransform.GetLocation())
            / SampleSeconds;
    }

    if (GetCameraStateForCompiledPassage(
        Passage,
        FFrameNumber(MasterFrame.Value + SampleFrameDelta),
        SampleTransform,
        SampleEvaluation))
    {
        return FVector::Distance(SampleTransform.GetLocation(), CameraTransform.GetLocation())
            / SampleSeconds;
    }

    return 0.0;
}

bool AInfinityStageCameraRig::GetCameraTransformAtMasterFrame(
    const FFrameNumber MasterFrame,
    FTransform& OutWorldTransform) const
{
    FInfinityPassageCameraEvaluation CameraEvaluation;
    return GetCameraStateAtMasterFrame(MasterFrame, OutWorldTransform, CameraEvaluation);
}

bool AInfinityStageCameraRig::GetCameraViewAtMasterFrame(
    const FFrameNumber MasterFrame,
    FTransform& OutWorldTransform,
    float& OutFocalLengthMm,
    float& OutFocusDistanceCm) const
{
    FInfinityPassageCameraEvaluation CameraEvaluation;
    if (!GetCameraStateAtMasterFrame(MasterFrame, OutWorldTransform, CameraEvaluation))
    {
        return false;
    }
    OutFocalLengthMm = static_cast<float>(CameraEvaluation.FocalLengthMm);
    OutFocusDistanceCm = static_cast<float>(CameraEvaluation.FocusDistanceCm);
    return true;
}

bool AInfinityStageCameraRig::GetCameraStateAtMasterFrame(
    const FFrameNumber MasterFrame,
    FTransform& OutWorldTransform,
    FInfinityPassageCameraEvaluation& OutEvaluation) const
{
    if (!PassageActor || !PassageActor->ShowAsset || !PassageActor->Route)
    {
        return false;
    }
    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*PassageActor->ShowAsset);
    const FInfinityCompiledPassage* Passage = FindCompiledPassage(Compiled, PassageActor->PassageGuid);
    return Passage && GetCameraStateForCompiledPassage(*Passage, MasterFrame, OutWorldTransform, OutEvaluation);
}

bool AInfinityStageCameraRig::GetCameraStateForCompiledPassage(
    const FInfinityCompiledPassage& CompiledPassage,
    const FFrameNumber MasterFrame,
    FTransform& OutWorldTransform,
    FInfinityPassageCameraEvaluation& OutEvaluation) const
{
    if (!PassageActor || !PassageActor->ShowAsset || !PassageActor->Route
        || MasterFrame < CompiledPassage.SegmentStartFrame || MasterFrame > CompiledPassage.SegmentEndFrame)
    {
        return false;
    }
    const FInfinityCompiledPassage* Passage = &CompiledPassage;

    OutEvaluation.DistanceMasterFrame = FFrameTime(MasterFrame);
    OutEvaluation.FocalLengthMm = Camera ? Camera->CurrentFocalLength : 35.0;
    OutEvaluation.FocusDistanceCm = Camera ? Camera->FocusSettings.ManualFocusDistance : 100000.0;

    if (ULevelSequence* MasterSequence = PassageActor->ShowAsset->ManagedMasterSequence.LoadSynchronous())
    {
        if (UMovieScene* MovieScene = MasterSequence->GetMovieScene())
        {
            if (UMovieSceneInfinityPassageTrack* Track = MovieScene->FindTrack<UMovieSceneInfinityPassageTrack>())
            {
                for (UMovieSceneSection* RawSection : Track->GetAllSections())
                {
                    const UMovieSceneInfinityPassageSection* Section = Cast<UMovieSceneInfinityPassageSection>(RawSection);
                    if (Section && Section->PassageGuid == PassageActor->PassageGuid)
                    {
                        Section->EvaluateCamera(
                            *Passage, FFrameTime(MasterFrame), OutEvaluation, GetCrossingSettleFrames());
                        break;
                    }
                }
            }
        }
    }

    const double DistanceCm = FInfinityStageCompiler::EvaluateDistanceAtFrame(
        *Passage,
        OutEvaluation.DistanceMasterFrame);
    // The reveal follows the optical camera station, including authored
    // longitudinal framing offsets, rather than the un-offset Passage root.
    OutEvaluation.DistanceCm = DistanceCm + CameraOffset.X + OutEvaluation.LocalOffsetCm.X;
    FTransform RouteTransform = PassageActor->Route->GetTransformAtDistanceAlongSpline(
        DistanceCm,
        ESplineCoordinateSpace::World,
        true);
    RouteTransform.AddToTranslation(RouteTransform.TransformVectorNoScale(CameraOffset + OutEvaluation.LocalOffsetCm));
    OutEvaluation.HeightOffsetWorldCm =
        RouteTransform.TransformVectorNoScale(FVector(0.0, 0.0, OutEvaluation.LocalOffsetCm.Z));
    FQuat RouteRotation = RouteTransform.GetRotation();
    if (OutEvaluation.LookAheadDistanceCm > UE_DOUBLE_SMALL_NUMBER)
    {
        const double TargetDistanceCm = FMath::Clamp(
            DistanceCm + CameraOffset.X + OutEvaluation.LocalOffsetCm.X + OutEvaluation.LookAheadDistanceCm,
            0.0,
            static_cast<double>(PassageActor->Route->GetSplineLength()));
        const FVector LookTarget = PassageActor->Route->GetLocationAtDistanceAlongSpline(
            TargetDistanceCm,
            ESplineCoordinateSpace::World);
        const FVector LookDirection = (LookTarget - RouteTransform.GetLocation()).GetSafeNormal();
        if (!LookDirection.IsNearlyZero())
        {
            RouteRotation = FRotationMatrix::MakeFromXZ(
                LookDirection,
                RouteTransform.GetUnitAxis(EAxis::Z)).ToQuat();
        }
    }
    RouteTransform.SetRotation((RouteRotation * OutEvaluation.LocalRotation.Quaternion()).GetNormalized());
    OutWorldTransform = RouteTransform;
    return true;
}
