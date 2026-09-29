#include "InfinityStageCameraRig.h"

#include "Components/SpotLightComponent.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
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

void ApplyDirectShadowCatAnimation(
    USkeletalMeshComponent* CatMesh,
    UAnimationAsset* Animation,
    const float PlayRate)
{
    if (!CatMesh || !Animation)
    {
        return;
    }

    if (CatMesh->GetAnimationMode() != EAnimationMode::AnimationSingleNode)
    {
        CatMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
    }

    UAnimSingleNodeInstance* SingleNode = CatMesh->GetSingleNodeInstance();
    if (!SingleNode || SingleNode->GetAnimationAsset() != Animation)
    {
        CatMesh->PlayAnimation(Animation, true);
        SingleNode = CatMesh->GetSingleNodeInstance();
    }

    CatMesh->SetPlayRate(PlayRate);
    if (SingleNode)
    {
        SingleNode->SetLooping(true);
        SingleNode->SetPlaying(true);
    }
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
    FollowLight->SetRelativeLocation(FollowLightOffset);
    FollowLight->SetRelativeRotation(FollowLightRotation);
    FollowLight->SetVisibility(bEnableFollowLight && bShadowFiguresLive);
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

void AInfinityStageCameraRig::ApplyShadowFigureVisibility()
{
    const bool bShowCat = bEnableShadowCat && bShadowFiguresLive;
    if (AActor* CatActor = ShadowCat ? ShadowCat->GetChildActor() : nullptr)
    {
        CatActor->SetActorHiddenInGame(!bShowCat);
        TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
        for (USkeletalMeshComponent* CatMesh : CatMeshes)
        {
            CatMesh->SetHiddenInGame(!bShowCat, true);
        }
    }
    if (FollowLight)
    {
        FollowLight->SetVisibility(bEnableFollowLight && bShadowFiguresLive);
    }
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
    // Gait bob: the cat's pose from the previous tick lifts this frame's camera.
    // The lift is applied on top of the authored camera state, never written back.
    CurrentShadowCatCameraBobCm = SampleShadowCatGaitLiftCm();
    if (!FMath::IsNearlyZero(CurrentShadowCatCameraBobCm))
    {
        CameraTransform.AddToTranslation(FVector(0.0, 0.0, CurrentShadowCatCameraBobCm));
        const FQuat Roll = FRotator(0.0, 0.0, CurrentShadowCatCameraBobCm * ShadowCatCameraBobRollDegreesPerCm).Quaternion();
        CameraTransform.SetRotation((CameraTransform.GetRotation() * Roll).GetNormalized());
    }

    SetActorTransform(CameraTransform);
    Camera->SetCurrentFocalLength(static_cast<float>(CameraEvaluation.FocalLengthMm));
    Camera->FocusSettings.FocusMethod = ECameraFocusMethod::Manual;
    Camera->FocusSettings.ManualFocusDistance = static_cast<float>(CameraEvaluation.FocusDistanceCm);

    // The cat rides the rig, so counter the lift here or it would bob twice.
    const FVector ShadowFigureWorldOffset = GetActorTransform().TransformVectorNoScale(ShadowFigureOffset);
    ShadowFigureRoot->SetWorldLocation(
        GetActorLocation() + ShadowFigureWorldOffset - FVector(0.0, 0.0, CurrentShadowCatCameraBobCm));
    ShadowFigureRoot->SetWorldScale3D(FVector::OneVector);
    if (bKeepShadowFiguresWorldUpright)
    {
        const FRotator CameraRotation = GetActorRotation();
        ShadowFigureRoot->SetWorldRotation(FRotator(0.0, CameraRotation.Yaw, 0.0));
    }

    UpdateShadowCatAtMasterFrame(MasterFrame, CameraTransform, *Passage);

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
        if (bShadowCatUseDirectWalkAnimation && GetWorld() && GetWorld()->IsGameWorld())
        {
            const bool bIsMoving = CurrentShadowCatCameraSpeedCmPerSecond > KINDA_SMALL_NUMBER;
            ApplyDirectShadowCatAnimation(
                CatMesh,
                bIsMoving ? GetShadowCatWalkAnimation() : GetShadowCatIdleAnimation(),
                bIsMoving ? static_cast<float>(CurrentShadowCatPlayRate) : 1.0f);
        }

        CatMesh->SetActive(bEnableShadowCat, true);
        CatMesh->SetComponentTickEnabled(bEnableShadowCat);
        CatMesh->bPauseAnims = false;
        CatMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        CatMesh->SetVisibility(bEnableShadowCat, true);
        CatMesh->SetHiddenInGame(!(bEnableShadowCat && bShadowFiguresLive), true);
        CatMesh->SetCastShadow(bShadowCatCastShadow);
        CatMesh->SetRenderInMainPass(bShadowCatRenderInMainPass);
        CatMesh->SetVisibleInRayTracing(bShadowCatVisibleInReflections);
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
        return;
    }

    CurrentShadowCatCameraSpeedCmPerSecond = CalculateCameraSpeedAtMasterFrame(
        MasterFrame,
        CameraTransform,
        Passage);
    const double ReferenceSpeed = FMath::Max(1.0, ShadowCatReferenceWalkSpeedCmPerSecond);
    CurrentShadowCatPlayRate = FMath::Clamp(
        (CurrentShadowCatCameraSpeedCmPerSecond / ReferenceSpeed)
            * FMath::Max(0.0, ShadowCatAnimationSpeedMultiplier),
        FMath::Max(0.0, ShadowCatMinPlayRate),
        FMath::Max(ShadowCatMinPlayRate, ShadowCatMaxPlayRate));

    const bool bIsMoving = CurrentShadowCatCameraSpeedCmPerSecond > KINDA_SMALL_NUMBER;
    if (bShadowCatUseDirectWalkAnimation)
    {
        TInlineComponentArray<USkeletalMeshComponent*> CatMeshes(CatActor);
        for (USkeletalMeshComponent* CatMesh : CatMeshes)
        {
            ApplyDirectShadowCatAnimation(
                CatMesh,
                bIsMoving ? GetShadowCatWalkAnimation() : GetShadowCatIdleAnimation(),
                bIsMoving ? static_cast<float>(CurrentShadowCatPlayRate) : 1.0f);
        }
    }
}

double AInfinityStageCameraRig::SampleShadowCatGaitLiftCm() const
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

    // Rest height comes from the reference pose, so the lift is zero-centred
    // regardless of which clip is playing and needs no running average.
    TArray<FTransform> RestComponentSpace;
    FAnimationRuntime::FillUpComponentSpaceTransforms(RefSkeleton, RefSkeleton.GetRefBonePose(), RestComponentSpace);
    if (!RestComponentSpace.IsValidIndex(BoneIndex))
    {
        return 0.0;
    }
    const double RestZ = RestComponentSpace[BoneIndex].GetTranslation().Z;
    const double PoseZ = CatMesh->GetSocketTransform(ShadowCatBobReferenceBone, RTS_Component).GetTranslation().Z;
    const double WorldScaleZ = CatMesh->GetComponentScale().Z;
    const double LiftCm = (PoseZ - RestZ) * WorldScaleZ * ShadowCatCameraBobGain;

    if (!bShadowCatBobReported)
    {
        const_cast<AInfinityStageCameraRig*>(this)->bShadowCatBobReported = true;
        UE_LOG(
            LogInfinityStageShadowCat,
            Display,
            TEXT("SHADOW_CAT_BOB_READY|rig=%s|bone=%s|rest_z=%.3f|pose_z=%.3f|scale_z=%.3f|gain=%.3f|lift_cm=%.3f"),
            *GetName(),
            *ShadowCatBobReferenceBone.ToString(),
            RestZ,
            PoseZ,
            WorldScaleZ,
            ShadowCatCameraBobGain,
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
                        Section->EvaluateCamera(*Passage, FFrameTime(MasterFrame), OutEvaluation);
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
