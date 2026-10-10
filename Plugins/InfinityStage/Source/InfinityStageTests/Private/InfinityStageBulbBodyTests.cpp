#include "InfinityStageBulbBody.h"

#include "Components/LightComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageTypes.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Bulb glass follows its light (patch BG, 6 Oct). Off by default; with
 * Body.bFollowLight the glass's emissive scalar is Full x the light's drama level
 * x the glass's own flicker (Stable / Slight / Fail), in game worlds only.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBulbBodyFlickerTest,
    "InfinityStage.BulbBody.FlickerModes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBulbBodyFlickerTest::RunTest(const FString& Parameters)
{
    using namespace InfinityStageBulbBody;
    const FInfinityBulbBodySettings Defaults;
    TestFalse(TEXT("Off by default"), Defaults.bFollowLight);
    TestEqual(TEXT("Stable by default"), Defaults.Flicker, EInfinityBulbBodyFlicker::Stable);
    TestEqual(TEXT("The M_UP_TubeEmissive parameter by default"), Defaults.IntensityParameter, FName(TEXT("Intensity")));

    const FGuid Bulb = FGuid::NewGuid();
    FInfinityBulbBodySettings Settings;
    bool bStable = true;
    for (double Seconds = 0.0; Seconds < 5.0; Seconds += 0.013)
    {
        bStable &= FlickerScale(Settings, Bulb, Seconds, -9000.0) == 1.0f;
    }
    TestTrue(TEXT("Stable never flickers"), bStable);

    Settings.Flicker = EInfinityBulbBodyFlicker::Slight;
    float Low = 1.0f;
    float High = 0.0f;
    bool bRepeat = true;
    for (double Seconds = 0.0; Seconds < 5.0; Seconds += 0.013)
    {
        const float Value = FlickerScale(Settings, Bulb, Seconds, 0.0);
        Low = FMath::Min(Low, Value);
        High = FMath::Max(High, Value);
        bRepeat &= Value == FlickerScale(Settings, Bulb, Seconds, 0.0);
    }
    TestTrue(TEXT("Slight stays within its depth"), Low >= 1.0f - Settings.SlightDepth - 1.0e-5f && High <= 1.0f);
    TestTrue(TEXT("Slight does move"), High - Low > 0.02f);
    TestTrue(TEXT("Slight replays identically (Master time)"), bRepeat);

    Settings.Flicker = EInfinityBulbBodyFlicker::Fail;
    Settings.FailAtCm = 0.0;
    Settings.FailWindowCm = 1500.0;
    TestEqual(TEXT("Fail: dead once the camera reaches the death point"), FlickerScale(Settings, Bulb, 1.0, 0.0), 0.0f);
    TestEqual(TEXT("Fail: stays dead past it"), FlickerScale(Settings, Bulb, 2.0, 5000.0), 0.0f);
    int32 FarDrops = 0;
    int32 NearDrops = 0;
    for (int32 Step = 0; Step < 400; ++Step)
    {
        const double Seconds = Step / 14.0 + 0.01;
        FarDrops += FlickerScale(Settings, Bulb, Seconds, -5000.0) == 0.0f ? 1 : 0;
        NearDrops += FlickerScale(Settings, Bulb, Seconds, -100.0) == 0.0f ? 1 : 0;
    }
    TestEqual(TEXT("Fail: steady (no drop-outs) far before its window"), FarDrops, 0);
    TestTrue(TEXT("Fail: drops out often just before it dies"), NearDrops > 100);

    Settings.Flicker = EInfinityBulbBodyFlicker::Slight;
    FInfinityBulbBodySettings Reseeded = Settings;
    Reseeded.Seed = 7;
    bool bDiffers = false;
    for (double Seconds = 0.0; Seconds < 2.0; Seconds += 0.07)
    {
        bDiffers |= FlickerScale(Settings, Bulb, Seconds, 0.0) != FlickerScale(Reseeded, Bulb, Seconds, 0.0);
    }
    TestTrue(TEXT("The seed re-rolls a bulb's flicker"), bDiffers);

    TestEqual(TEXT("Body = full x drama x flicker"), BodyIntensity(6.0f, 0.5f, 0.5f), 1.5f);
    TestEqual(TEXT("An unstruck lamp's glass is dark"), BodyIntensity(6.0f, 0.0f, 1.0f), 0.0f);
    TestEqual(TEXT("Never negative"), BodyIntensity(-1.0f, 1.0f, 1.0f), 0.0f);

    Settings.bSwingOnCord = true;
    Settings.SwingYawAmplitudeDegrees = 3.0f;
    Settings.SwingPitchAmplitudeDegrees = 2.0f;
    Settings.SwingPeriodSeconds = 8.0f;
    const FRotator Swing0 = CordSwingRotation(Settings, Bulb, 1.25);
    const FRotator SwingRepeat = CordSwingRotation(Settings, Bulb, 1.25);
    const FRotator SwingCycle = CordSwingRotation(Settings, Bulb, 9.25);
    TestTrue(TEXT("Cord sway is deterministic"), Swing0.Equals(SwingRepeat, 1.0e-6f));
    TestTrue(TEXT("Cord sway repeats exactly once per period"), Swing0.Equals(SwingCycle, 1.0e-4f));
    TestTrue(TEXT("Cord sway stays within authored amplitudes"),
        FMath::Abs(Swing0.Yaw) <= Settings.SwingYawAmplitudeDegrees + 1.0e-4f
        && FMath::Abs(Swing0.Pitch) <= Settings.SwingPitchAmplitudeDegrees + 1.0e-4f);
    FInfinityBulbBodySettings Still = Settings;
    Still.bSwingOnCord = false;
    TestTrue(TEXT("Cord sway is opt-in"), CordSwingRotation(Still, Bulb, 1.25).IsNearlyZero());

    // Compatibility gate: an empty kick score takes the exact established path,
    // not merely a numerically close rewrite of it.
    const FRotator BeforeKickFeature = CordSwingRotation(Settings, Bulb, 1.25);
    Settings.KickAmplitudeDegrees = 8.0f;
    const FRotator NoKickNow = CordSwingRotation(Settings, Bulb, 1.25, {});
    TestTrue(TEXT("No cue kick is bit-identical to the 9 Oct sway"),
        BeforeKickFeature.Pitch == NoKickNow.Pitch && BeforeKickFeature.Yaw == NoKickNow.Yaw);

    TArray<double> Resolved;
    FString ResolveError;
    TestFalse(TEXT("A kick without a Show cue id is refused"),
        ResolveCordSwingKickTimes(Settings, {}, Resolved, ResolveError));
    TestTrue(TEXT("The missing-cue refusal explains the cue-id contract"), ResolveError.Contains(TEXT("cue id")));
    const FGuid KickCue = FGuid::NewGuid();
    Settings.KickCueIds = { KickCue };
    const TArray<TPair<FGuid, double>> Available = { TPair<FGuid, double>(KickCue, 3.0) };
    TestTrue(TEXT("A Show cue id resolves to compiled Show time"),
        ResolveCordSwingKickTimes(Settings, Available, Resolved, ResolveError));
    TestEqual(TEXT("Exactly one kick time resolved"), Resolved.Num(), 1);
    TestEqual(TEXT("The resolved time came from compiled Show data"), Resolved[0], 3.0);
    const FRotator AtImpulse = CordSwingRotation(Settings, Bulb, 3.0, Resolved);
    const FRotator QuarterKick = CordSwingRotation(Settings, Bulb, 3.0 + Settings.SwingPeriodSeconds * 0.25, Resolved);
    const FRotator LateKick = CordSwingRotation(Settings, Bulb, 3.0 + Settings.SwingPeriodSeconds * 4.0, Resolved);
    const FRotator LateIdle = CordSwingRotation(FInfinityBulbBodySettings(Settings), Bulb,
        3.0 + Settings.SwingPeriodSeconds * 4.0, {});
    TestTrue(TEXT("An impulse starts without an angle discontinuity"), AtImpulse.Equals(CordSwingRotation(Settings, Bulb, 3.0, {}), 1.0e-6f));
    TestTrue(TEXT("A cue kick adds a dramatic quarter-cycle displacement"),
        FMath::Abs(QuarterKick.Yaw - CordSwingRotation(Settings, Bulb, 3.0 + Settings.SwingPeriodSeconds * 0.25, {}).Yaw) > 1.0f);
    TestTrue(TEXT("Cue kick decay returns toward idle sway"), FMath::Abs(LateKick.Yaw - LateIdle.Yaw) < 0.01f);
    TestTrue(TEXT("Cue kick is deterministic under scrub/jump"),
        QuarterKick.Equals(CordSwingRotation(Settings, Bulb, 3.0 + Settings.SwingPeriodSeconds * 0.25, Resolved), 1.0e-6f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageBulbBodyFollowsLightTest,
    "InfinityStage.BulbBody.GlassFollowsTheStrikeInGameOnly",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageBulbBodyFollowsLightTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 Index = 0; Index < 3; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetLocation(FVector(0.0, -400.0, 0.0));
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Right.LocalTransform.SetLocation(FVector(0.0, 400.0, 0.0));
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    FInfinityShowCue& Host = Show->Cues[1];
    FInfinityCueAttachment& Lamp = Host.WingPair.Attachments.AddDefaulted_GetRef();
    Lamp.AttachmentGuid = FGuid::NewGuid();
    Lamp.Kind = EInfinityAttachmentKind::Light;
    Lamp.Lighting.Type = EInfinityStageLightType::Point;
    Lamp.Lighting.Intensity = 40.0f;
    Lamp.Lighting.Drama.bStrikeOnApproach = true;
    Lamp.Lighting.Drama.StrikeDistanceCm = 2500.0;
    Lamp.Lighting.Drama.StrikeRampCm = 250.0;
    Lamp.Lighting.Drama.IgnitionStutter = 0.0f;
    Lamp.RelativeTransform.SetLocation(FVector(0.0, 0.0, 300.0));
    FInfinityCueAttachment& Glass = Host.WingPair.Attachments.AddDefaulted_GetRef();
    Glass.AttachmentGuid = FGuid::NewGuid();
    Glass.Kind = EInfinityAttachmentKind::Prop;
    Glass.Mesh = Cube;
    Glass.RelativeTransform.SetLocation(FVector(0.0, 0.0, 300.0));
    Glass.Body.bFollowLight = true;
    Glass.Body.LightAttachmentGuid = Lamp.AttachmentGuid;
    Glass.Body.FullIntensity = 6.0f;
    Glass.Body.bEmitPointLight = true;
    Glass.Body.PointLightLumens = 24.0f;
    FInfinityCueAttachment& Plain = Host.WingPair.Attachments.AddDefaulted_GetRef();
    Plain.AttachmentGuid = FGuid::NewGuid();
    Plain.Kind = EInfinityAttachmentKind::Prop;
    Plain.Mesh = Cube;
    const FGuid GlassGuid = Glass.AttachmentGuid;
    const FGuid PlainGuid = Plain.AttachmentGuid;
    Show->ReconcilePassageSettings();

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Show);
    const double LampCm = Compiled.Passages.Num() == 1 && Compiled.Passages[0].Wings.Num() == 3
        ? Compiled.Passages[0].Wings[1].DistanceCm
        : -1.0;
    if (!TestTrue(TEXT("Fixture compiles to one Passage of three wings"), LampCm >= 0.0))
    {
        return false;
    }
    const FFrameNumber Frame = Compiled.Passages[0].SegmentStartFrame;

    const auto FindBody = [](const AInfinityStagePassageActor& Passage, const FGuid& Wanted) -> AActor*
    {
        for (AActor* Actor : Passage.ManagedAttachmentActors)
        {
            FGuid Cue;
            FGuid Attachment;
            if (Actor && Passage.FindAttachmentByActor(Actor, Cue, Attachment) && Attachment == Wanted)
            {
                return Actor;
            }
        }
        return nullptr;
    };

    // MaterializePassage refuses game worlds by design ("editor authoring only";
    // PassageActor.cpp:716-718): stage content is built in the editor and PIE gets
    // a copy. So build in an editor-type world, check nothing is driven there, then
    // retype the same world as Game - what PIE's duplicate is - and evaluate.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    Passage->MaterializePassage();
    AActor* Body = FindBody(*Passage, GlassGuid);
    AActor* PlainBody = FindBody(*Passage, PlainGuid);
    if (!TestNotNull(TEXT("The glass is placed"), Body) || !TestNotNull(TEXT("The plain prop is placed"), PlainBody))
    {
        World->DestroyWorld(false);
        return false;
    }
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 3000.0);
    TestEqual(TEXT("Editor world: the glass is never driven"), Passage->GetBulbBodyLevelForTests(Body), -1.0f);

    World->WorldType = EWorldType::Game;
    TestTrue(TEXT("Fixture: the world now reads as a game world"), World->IsGameWorld());
    TestTrue(TEXT("The glass is a static mesh prop"), Body->IsA<AStaticMeshActor>());

    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 3000.0);
    TestEqual(TEXT("Unstruck lamp: the glass is dark"), Passage->GetBulbBodyLevelForTests(Body), 0.0f);
    UPointLightComponent* BulbPoint = Body->FindComponentByClass<UPointLightComponent>();
    TestTrue(TEXT("A bulb-owned point light is created only in the game-world evaluation"), BulbPoint != nullptr);
    TestTrue(TEXT("Unstruck bulb-owned point light is hidden"), BulbPoint && !BulbPoint->IsVisible());
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 2375.0);
    TestTrue(TEXT("Half way up the strike: the glass is half lit"),
        FMath::IsNearlyEqual(Passage->GetBulbBodyLevelForTests(Body), 3.0f, 0.01f));
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm - 1000.0);
    TestEqual(TEXT("Struck: the glass is at full"), Passage->GetBulbBodyLevelForTests(Body), 6.0f);
    TestTrue(TEXT("Struck bulb-owned point light reaches its authored dim lumens"),
        BulbPoint && BulbPoint->IsVisible() && FMath::IsNearlyEqual(BulbPoint->Intensity, 24.0f, 0.01f));
    TestEqual(TEXT("A prop without bFollowLight is never touched"), Passage->GetBulbBodyLevelForTests(PlainBody), -1.0f);

    // Fail mode with the light following: dies at the lamp, light switched off.
    Show->Cues[1].WingPair.Attachments[1].Body.Flicker = EInfinityBulbBodyFlicker::Fail;
    Show->Cues[1].WingPair.Attachments[1].Body.bFlickerAlsoDrivesLight = true;
    Passage->EvaluateMechanismsAtCameraDistance(Frame, LampCm + 10.0);
    TestEqual(TEXT("Fail: the glass is dead past the lamp"), Passage->GetBulbBodyLevelForTests(Body), 0.0f);
    AActor* LampActor = FindBody(*Passage, Show->Cues[1].WingPair.Attachments[0].AttachmentGuid);
    const ULightComponent* Light = LampActor ? LampActor->FindComponentByClass<ULightComponent>() : nullptr;
    TestTrue(TEXT("Fail + drives light: the lamp is switched off with its glass"), Light && !Light->IsVisible());
    World->WorldType = EWorldType::EditorPreview;
    World->DestroyWorld(false);
    return true;
}

#endif
