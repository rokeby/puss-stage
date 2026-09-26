#include "InfinityStageEffectLibrary.h"
#include "InfinityStageEffectSource.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "Algo/Reverse.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LocalFogVolumeComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
/** Consecutive Wing Pair cues split into Passages of the given sizes. */
UInfinityStageShowAsset* MakeEffectShow(const TArray<int32>& PassageSizes, TArray<TArray<FGuid>>& OutCuesByPassage)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    for (int32 PassageIndex = 0; PassageIndex < PassageSizes.Num(); ++PassageIndex)
    {
        TArray<FGuid>& PassageCues = OutCuesByPassage.AddDefaulted_GetRef();
        for (int32 Index = 0; Index < PassageSizes[PassageIndex]; ++Index)
        {
            FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
            Cue.Type = EInfinityCueType::WingPair;
            Cue.CueGuid = FGuid::NewGuid();
            Cue.Label = FText::FromString(FString::Printf(TEXT("P%02d Wing %03d"), PassageIndex + 1, Index + 1));
            Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
            PassageCues.Add(Cue.CueGuid);
        }
        FInfinityPassageSettings& Passage = Show->PassageSettings.AddDefaulted_GetRef();
        Passage.PassageGuid = FGuid::NewGuid();
        Passage.FirstCueGuid = PassageCues[0];
        Passage.LastCueGuid = PassageCues.Last();
    }
    return Show;
}

FInfinityShowCue& FindCue(UInfinityStageShowAsset& Show, const FGuid& CueGuid)
{
    return *Show.Cues.FindByPredicate(
        [CueGuid](const FInfinityShowCue& Candidate) { return Candidate.CueGuid == CueGuid; });
}

FGuid AddTestLight(FInfinityShowCue& Cue, const float VolumetricScattering, const bool bVolumetricShadow = true)
{
    FInfinityCueAttachment& Light = Cue.WingPair.Attachments.AddDefaulted_GetRef();
    Light.AttachmentGuid = FGuid::NewGuid();
    Light.Kind = EInfinityAttachmentKind::Light;
    Light.Lighting.VolumetricScatteringIntensity = VolumetricScattering;
    Light.Lighting.bCastVolumetricShadow = bVolumetricShadow;
    return Light.AttachmentGuid;
}

TArray<const FInfinityCueAttachment*> EffectCopies(const FInfinityShowCue& Cue)
{
    TArray<const FInfinityCueAttachment*> Result;
    for (const FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
    {
        if (Attachment.Kind == EInfinityAttachmentKind::Effect && Attachment.Effect.ReplicatedFromAttachmentGuid.IsValid())
        {
            Result.Add(&Attachment);
        }
    }
    return Result;
}

int32 CountHandPlacedEffects(const FInfinityShowCue& Cue)
{
    int32 Count = 0;
    for (const FInfinityCueAttachment& Attachment : Cue.WingPair.Attachments)
    {
        Count += Attachment.Kind == EInfinityAttachmentKind::Effect
            && !Attachment.Effect.ReplicatedFromAttachmentGuid.IsValid() ? 1 : 0;
    }
    return Count;
}

bool SameGuids(const TArray<FGuid>& Actual, const TArray<FGuid>& Expected)
{
    return Actual == Expected;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectBurnProgressTest,
    "InfinityStage.Effects.BurnProgressFollowsCameraTravel",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectBurnProgressTest::RunTest(const FString& Parameters)
{
    // Takes hold 3000 cm before the camera reaches the wing, consumed 4000 cm later.
    TestEqual(TEXT("Intact while the wing is far ahead"),
        AInfinityStageEffectSource::ComputeBurnProgress(8000.0, 3000.0f, 4000.0f), 0.0f);
    TestEqual(TEXT("Intact at the start line"),
        AInfinityStageEffectSource::ComputeBurnProgress(3000.0, 3000.0f, 4000.0f), 0.0f);
    TestEqual(TEXT("Half consumed halfway through the span"),
        AInfinityStageEffectSource::ComputeBurnProgress(1000.0, 3000.0f, 4000.0f), 0.5f, 1.0e-5f);
    TestEqual(TEXT("Consumed at the end of the span"),
        AInfinityStageEffectSource::ComputeBurnProgress(-1000.0, 3000.0f, 4000.0f), 1.0f);
    TestEqual(TEXT("Stays consumed once the camera has passed"),
        AInfinityStageEffectSource::ComputeBurnProgress(-20000.0, 3000.0f, 4000.0f), 1.0f);
    TestEqual(TEXT("A zero span cannot divide by zero"),
        AInfinityStageEffectSource::ComputeBurnProgress(2999.0, 3000.0f, 0.0f), 1.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectBurnFrontTest,
    "InfinityStage.Effects.BurnFrontFollowsTheWingMastersContract",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectBurnFrontTest::RunTest(const FString& Parameters)
{
    // A 733 x 1000 cm UV square (SM_R__1_roccoco's span), U running right to
    // left and V down, as on most wings: V = 1 at Z = 0, V = 0 at Z = 1000.
    FInfinityStageEffectSettings Settings =
        UInfinityStageEffectLibrary::MakeDefaultEffectSettings(EInfinityStageEffectType::WingBurn);
    FVector Ignition;
    float Radius = 0.0f;
    TestFalse(TEXT("No front before the UV mapping is measured"),
        AInfinityStageEffectSource::ComputeBurnFront(Settings, 0.5f, Ignition, Radius));

    Settings.BurnUAxis = FVector2D(-1.0 / 733.0, 0.5);
    Settings.BurnVAxis = FVector2D(-1.0 / 1000.0, 1.0);
    TestTrue(TEXT("A measured mapping gives a front"),
        AInfinityStageEffectSource::ComputeBurnFront(Settings, 1.0f, Ignition, Radius));
    TestTrue(TEXT("Default ignition is bottom centre of the UV square"),
        Ignition.Equals(FVector::ZeroVector, 0.01));
    const double FarthestCorner = FMath::Sqrt(FMath::Square(0.5 * 733.0) + FMath::Square(1000.0));
    TestEqual(TEXT("Progress 1 reaches the farthest corner plus the master's pad"),
        Radius, static_cast<float>(FarthestCorner + InfinityStageWingBurn::FrontPadCm), 0.01f);
    AInfinityStageEffectSource::ComputeBurnFront(Settings, 0.5f, Ignition, Radius);
    TestEqual(TEXT("The front grows linearly with progress"),
        Radius, static_cast<float>(0.5 * (FarthestCorner + InfinityStageWingBurn::FrontPadCm)), 0.01f);
    AInfinityStageEffectSource::ComputeBurnFront(Settings, 0.0f, Ignition, Radius);
    TestEqual(TEXT("An intact wing has no front"), Radius, 0.0f);

    // The U sign differs between meshes and must never be assumed.
    Settings.IgnitionUV = FVector2D(0.0, 0.0);
    AInfinityStageEffectSource::ComputeBurnFront(Settings, 1.0f, Ignition, Radius);
    TestTrue(TEXT("U = 0 lies at +Y when U runs right to left"),
        Ignition.Equals(FVector(0.0, 366.5, 1000.0), 0.01));
    Settings.BurnUAxis = FVector2D(1.0 / 733.0, 0.5);
    AInfinityStageEffectSource::ComputeBurnFront(Settings, 1.0f, Ignition, Radius);
    TestTrue(TEXT("U = 0 lies at -Y when U runs left to right"),
        Ignition.Equals(FVector(0.0, -366.5, 1000.0), 0.01));
    TestEqual(TEXT("A corner ignition reaches across the whole square"),
        Radius, static_cast<float>(FMath::Sqrt(FMath::Square(733.0) + FMath::Square(1000.0))
            + InfinityStageWingBurn::FrontPadCm), 0.01f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectPumpTest,
    "InfinityStage.Effects.PumpIsSoftEdgedPhasedAndBounded",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectPumpTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("A zero period pumps steadily"),
        AInfinityStageEffectSource::ComputePump(12.3, 0.0f, 0.35f, 0.0f), 1.0f);
    TestEqual(TEXT("Full duty pumps steadily"),
        AInfinityStageEffectSource::ComputePump(12.3, 6.0f, 1.0f, 0.0f), 1.0f);
    // Period 10 s, duty 0.4: a full stroke inside the duty, silence after it.
    TestEqual(TEXT("Full stroke inside the duty"),
        AInfinityStageEffectSource::ComputePump(2.0, 10.0f, 0.4f, 0.0f), 1.0f, 1.0e-5f);
    TestEqual(TEXT("Silent after the duty"),
        AInfinityStageEffectSource::ComputePump(7.0, 10.0f, 0.4f, 0.0f), 0.0f, 1.0e-5f);
    const float Swell = AInfinityStageEffectSource::ComputePump(0.5, 10.0f, 0.4f, 0.0f);
    TestTrue(TEXT("The stroke swells rather than switching"), Swell > 0.05f && Swell < 0.95f);
    TestEqual(TEXT("Phase shifts the cycle"),
        AInfinityStageEffectSource::ComputePump(7.0, 10.0f, 0.4f, 0.5f), 1.0f, 1.0e-5f);

    bool bBounded = true;
    for (int32 Step = 0; Step <= 400; ++Step)
    {
        const double Time = Step * 0.05;
        const float Pump = AInfinityStageEffectSource::ComputePump(Time, 6.0f, 0.35f, 0.37f);
        const float Flicker = AInfinityStageEffectSource::ComputeFlicker(Time, 0.37f);
        bBounded &= Pump >= 0.0f && Pump <= 1.0f && FMath::Abs(Flicker) <= 1.0f + 1.0e-5f;
    }
    TestTrue(TEXT("Pump stays in 0..1 and flicker in -1..1"), bBounded);

    const FGuid CueGuid = FGuid::NewGuid();
    const FGuid AttachmentGuid = FGuid::NewGuid();
    const float Phase = AInfinityStageEffectSource::ComputePhase(CueGuid, AttachmentGuid);
    TestEqual(TEXT("Phase is stable for an identity"),
        AInfinityStageEffectSource::ComputePhase(CueGuid, AttachmentGuid), Phase);
    TestTrue(TEXT("Phase is a fraction of a cycle"), Phase >= 0.0f && Phase < 1.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectStrideSelectionTest,
    "InfinityStage.Effects.StrideCountsAfreshWithinEachPassage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectStrideSelectionTest::RunTest(const FString& Parameters)
{
    TArray<TArray<FGuid>> Cues;
    UInfinityStageShowAsset* Show = MakeEffectShow({ 7, 5 }, Cues);
    TArray<FGuid> All = Cues[0];
    All.Append(Cues[1]);

    TestTrue(TEXT("Stride 3 restarts at each Passage"),
        SameGuids(UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, All, 3, 0),
            { Cues[0][0], Cues[0][3], Cues[0][6], Cues[1][0], Cues[1][3] }));
    TestTrue(TEXT("Phase offsets within each Passage"),
        SameGuids(UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, All, 3, 1),
            { Cues[0][1], Cues[0][4], Cues[1][1], Cues[1][4] }));
    TestEqual(TEXT("Stride 1 keeps everything"),
        UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, All, 1, 0).Num(), All.Num());
    TestEqual(TEXT("Stride 0 selects nothing"),
        UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, All, 0, 0).Num(), 0);

    TArray<FGuid> Reversed = All;
    Algo::Reverse(Reversed);
    TestTrue(TEXT("Selection follows Show order, not argument order"),
        SameGuids(UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, Reversed, 3, 0),
            UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, All, 3, 0)));

    // Counting is among the given cues: every other one of a sparse set.
    const TArray<FGuid> Sparse = { Cues[0][1], Cues[0][2], Cues[0][4], Cues[0][5], Cues[0][6] };
    TestTrue(TEXT("Counts among the given cues"),
        SameGuids(UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, Sparse, 2, 0),
            { Cues[0][1], Cues[0][4], Cues[0][6] }));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectBeamBayTest,
    "InfinityStage.Effects.BeamBaysAreThoseWithVolumetricFixtures",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectBeamBayTest::RunTest(const FString& Parameters)
{
    TArray<TArray<FGuid>> Cues;
    UInfinityStageShowAsset* Show = MakeEffectShow({ 7 }, Cues);
    AddTestLight(FindCue(*Show, Cues[0][0]), 9.0f);
    AddTestLight(FindCue(*Show, Cues[0][2]), 0.6f);
    AddTestLight(FindCue(*Show, Cues[0][4]), 0.6f);
    AddTestLight(FindCue(*Show, Cues[0][4]), 9.0f);
    AddTestLight(FindCue(*Show, Cues[0][5]), 9.0f);
    FindCue(*Show, Cues[0][5]).WingPair.Attachments.Last().bEnabled = false;
    AddTestLight(FindCue(*Show, Cues[0][6]), 9.0f, false);

    TestTrue(TEXT("Only enabled volumetric beams make a beam bay"),
        SameGuids(UInfinityStageEffectLibrary::SelectBeamBays(Show, Cues[0], 5.0f), { Cues[0][0], Cues[0][4] }));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectReplicationOwnershipTest,
    "InfinityStage.Effects.ReplicationOwnsOnlyItsCopies",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectReplicationOwnershipTest::RunTest(const FString& Parameters)
{
    TArray<TArray<FGuid>> Cues;
    UInfinityStageShowAsset* Show = MakeEffectShow({ 9 }, Cues);
    const TArray<FGuid>& Scope = Cues[0];
    const FGuid SourceCueGuid = Scope[0];

    // Source: a light, a haze pot, and a fire flickering that light.
    const FGuid SourceLight = AddTestLight(FindCue(*Show, SourceCueGuid), 0.6f);
    const FGuid Haze = UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, SourceCueGuid, EInfinityStageEffectType::Haze, EInfinityAttachmentAnchor::Station,
        FTransform(FVector(0.0, -600.0, 0.0)), FText::FromString(TEXT("P01 Wing 001 Haze")));
    const FGuid Fire = UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, SourceCueGuid, EInfinityStageEffectType::Fire, EInfinityAttachmentAnchor::Station,
        FTransform::Identity, FText::FromString(TEXT("P01 Wing 001 Fire")));
    FindCue(*Show, SourceCueGuid).WingPair.Attachments.FindByPredicate(
        [Fire](const FInfinityCueAttachment& Candidate) { return Candidate.AttachmentGuid == Fire; })
        ->Effect.LinkedLightAttachmentGuid = SourceLight;
    TestTrue(TEXT("Hand-placed effects are added"), Haze.IsValid() && Fire.IsValid());

    // A hand-placed accident elsewhere, and bays with and without a light.
    const FGuid Accident = UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, Scope[4], EInfinityStageEffectType::Fire, EInfinityAttachmentAnchor::Station,
        FTransform::Identity, FText::FromString(TEXT("Dropped brazier")));
    FInfinityCueAttachment& Prop = FindCue(*Show, Scope[4]).WingPair.Attachments.AddDefaulted_GetRef();
    Prop.AttachmentGuid = FGuid::NewGuid();
    Prop.Kind = EInfinityAttachmentKind::Prop;
    const FGuid TargetLight = AddTestLight(FindCue(*Show, Scope[2]), 0.6f);

    FInfinityEffectReplicationVariation Variation;
    Variation.Seed = 11;
    TestEqual(TEXT("Two sources onto three bays"),
        UInfinityStageEffectLibrary::ReplicateEffectAttachments(
            Show, SourceCueGuid, Scope, { Scope[2], Scope[4], Scope[6] }, Variation),
        6);

    const TArray<const FInfinityCueAttachment*> OnTwo = EffectCopies(FindCue(*Show, Scope[2]));
    TestEqual(TEXT("Each target carries one copy per source"), OnTwo.Num(), 2);
    for (const FInfinityCueAttachment* Copy : OnTwo)
    {
        if (Copy->Effect.ReplicatedFromAttachmentGuid == Fire)
        {
            TestTrue(TEXT("A copied fire flickers its own pair's light"),
                Copy->Effect.LinkedLightAttachmentGuid == TargetLight);
            TestTrue(TEXT("Copy labels follow their cue"),
                Copy->Label.ToString() == TEXT("P01 Wing 003 Fire"));
        }
    }
    for (const FInfinityCueAttachment* Copy : EffectCopies(FindCue(*Show, Scope[6])))
    {
        if (Copy->Effect.ReplicatedFromAttachmentGuid == Fire)
        {
            TestFalse(TEXT("With no light to flicker the link is cleared"),
                Copy->Effect.LinkedLightAttachmentGuid.IsValid());
        }
    }
    TestEqual(TEXT("The hand-placed accident survives beside the copies"),
        CountHandPlacedEffects(FindCue(*Show, Scope[4])), 1);
    TestEqual(TEXT("The source cue is untouched"), FindCue(*Show, SourceCueGuid).WingPair.Attachments.Num(), 3);

    TSet<FGuid> FirstIdentities;
    for (const FGuid& CueGuid : Scope)
    {
        for (const FInfinityCueAttachment* Copy : EffectCopies(FindCue(*Show, CueGuid)))
        {
            FirstIdentities.Add(Copy->AttachmentGuid);
        }
    }
    UInfinityStageEffectLibrary::ReplicateEffectAttachments(
        Show, SourceCueGuid, Scope, { Scope[2], Scope[4], Scope[6] }, Variation);
    TSet<FGuid> SecondIdentities;
    int32 CopyCount = 0;
    for (const FGuid& CueGuid : Scope)
    {
        for (const FInfinityCueAttachment* Copy : EffectCopies(FindCue(*Show, CueGuid)))
        {
            SecondIdentities.Add(Copy->AttachmentGuid);
            ++CopyCount;
        }
    }
    TestEqual(TEXT("Re-replicating does not duplicate"), CopyCount, 6);
    TestTrue(TEXT("Copy identities are deterministic"),
        FirstIdentities.Num() == SecondIdentities.Num() && FirstIdentities.Includes(SecondIdentities));

    // A new stride removes the old copies wherever they were.
    UInfinityStageEffectLibrary::ReplicateEffectAttachments(
        Show, SourceCueGuid, Scope, { Scope[3], Scope[6] }, Variation);
    TestEqual(TEXT("Dropped bays lose their copies"), EffectCopies(FindCue(*Show, Scope[2])).Num(), 0);
    TestEqual(TEXT("The accident's bay keeps only the accident"), EffectCopies(FindCue(*Show, Scope[4])).Num(), 0);
    TestEqual(TEXT("The accident is still there"), CountHandPlacedEffects(FindCue(*Show, Scope[4])), 1);
    TestTrue(TEXT("The prop is still there"),
        FindCue(*Show, Scope[4]).WingPair.Attachments.ContainsByPredicate(
            [](const FInfinityCueAttachment& Candidate) { return Candidate.Kind == EInfinityAttachmentKind::Prop; }));
    TestEqual(TEXT("New bays gain copies"), EffectCopies(FindCue(*Show, Scope[3])).Num(), 2);

    TestEqual(TEXT("Clearing every copy removes exactly the copies"),
        UInfinityStageEffectLibrary::ClearReplicatedEffects(Show, FGuid(), Scope), 4);
    TestEqual(TEXT("Hand-placed sources remain"), CountHandPlacedEffects(FindCue(*Show, SourceCueGuid)), 2);
    TestTrue(TEXT("The accident remains"),
        FindCue(*Show, Scope[4]).WingPair.Attachments.ContainsByPredicate(
            [Accident](const FInfinityCueAttachment& Candidate) { return Candidate.AttachmentGuid == Accident; }));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectVariationTest,
    "InfinityStage.Effects.VariationIsSeededAndBounded",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectVariationTest::RunTest(const FString& Parameters)
{
    TArray<TArray<FGuid>> Cues;
    UInfinityStageShowAsset* Show = MakeEffectShow({ 12 }, Cues);
    const TArray<FGuid>& Scope = Cues[0];
    UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, Scope[0], EInfinityStageEffectType::Haze, EInfinityAttachmentAnchor::Station,
        FTransform::Identity, FText::FromString(TEXT("Haze")));
    const TArray<FGuid> Targets = UInfinityStageEffectLibrary::SelectEveryNthPerPassage(Show, Scope, 2, 1);

    FInfinityEffectReplicationVariation Variation;
    Variation.Seed = 7;
    Variation.OutputJitterFraction = 0.9f;
    Variation.PositionJitterCm = 50.0f;
    Variation.RotationJitterDegrees = 10.0f;

    const auto Snapshot = [&Show, &Scope]()
    {
        TArray<FString> Values;
        for (const FGuid& CueGuid : Scope)
        {
            for (const FInfinityCueAttachment* Copy : EffectCopies(FindCue(*Show, CueGuid)))
            {
                Values.Add(FString::Printf(TEXT("%.6f %s"),
                    Copy->Effect.Output, *Copy->RelativeTransform.ToString()));
            }
        }
        return Values;
    };

    UInfinityStageEffectLibrary::ReplicateEffectAttachments(Show, Scope[0], Scope, Targets, Variation);
    const TArray<FString> First = Snapshot();
    UInfinityStageEffectLibrary::ReplicateEffectAttachments(Show, Scope[0], Scope, Targets, Variation);
    TestTrue(TEXT("The same seed yields the same corridor"), Snapshot() == First);

    bool bBounded = true;
    for (const FGuid& CueGuid : Scope)
    {
        for (const FInfinityCueAttachment* Copy : EffectCopies(FindCue(*Show, CueGuid)))
        {
            bBounded &= Copy->Effect.Output >= 0.0f && Copy->Effect.Output <= 1.0f;
        }
    }
    TestTrue(TEXT("Jittered output stays in 0..1"), bBounded);

    Variation.Seed = 8;
    UInfinityStageEffectLibrary::ReplicateEffectAttachments(Show, Scope[0], Scope, Targets, Variation);
    TestTrue(TEXT("Another seed yields another corridor"), Snapshot() != First);

    const FInfinityStageEffectSettings FireDefaults =
        UInfinityStageEffectLibrary::MakeDefaultEffectSettings(EInfinityStageEffectType::Fire);
    TestTrue(TEXT("Fire defaults to Fire"), FireDefaults.Type == EInfinityStageEffectType::Fire);
    TestFalse(TEXT("Fire leaves no medium of its own"), FireDefaults.bFeedsLocalMedium);
    TestTrue(TEXT("Haze feeds the medium"),
        UInfinityStageEffectLibrary::MakeDefaultEffectSettings(EInfinityStageEffectType::Haze).bFeedsLocalMedium);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageEffectMaterializeTest,
    "InfinityStage.Effects.MaterializeSpawnsAndTracksEffectSources",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageEffectMaterializeTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
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
    Show->ReconcilePassageSettings();
    const FGuid CueGuid = Show->Cues[1].CueGuid;
    const FGuid HazeGuid = UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, CueGuid, EInfinityStageEffectType::Haze, EInfinityAttachmentAnchor::Station,
        FTransform(FVector(0.0, -700.0, 0.0)), FText::FromString(TEXT("Haze pot")));
    const FGuid BurnGuid = UInfinityStageEffectLibrary::AddEffectAttachment(
        Show, CueGuid, EInfinityStageEffectType::WingBurn, EInfinityAttachmentAnchor::LeftPanel,
        FTransform::Identity, FText::FromString(TEXT("Burning wing")));
    // The engine cube spans -50..50 cm; map it as a wing would be, V down.
    TestTrue(TEXT("The burn's UV mapping is recorded"),
        UInfinityStageEffectLibrary::SetWingBurnUVMapping(
            Show, CueGuid, BurnGuid, FVector2D(-0.01, 0.5), FVector2D(-0.01, 0.5), Cube));
    TestFalse(TEXT("A haze pot takes no UV mapping"),
        UInfinityStageEffectLibrary::SetWingBurnUVMapping(
            Show, CueGuid, HazeGuid, FVector2D(-0.01, 0.5), FVector2D(-0.01, 0.5), Cube));

    AInfinityStagePassageActor* Passage = World->SpawnActor<AInfinityStagePassageActor>();
    Passage->ShowAsset = Show;
    TestTrue(TEXT("Passage materializes"), Passage->MaterializePassage());

    AInfinityStageEffectSource* Haze = nullptr;
    AInfinityStageEffectSource* Burn = nullptr;
    for (AActor* Actor : Passage->ManagedAttachmentActors)
    {
        AInfinityStageEffectSource* Effect = Cast<AInfinityStageEffectSource>(Actor);
        if (Effect && Effect->AttachmentGuid == HazeGuid)
        {
            Haze = Effect;
        }
        if (Effect && Effect->AttachmentGuid == BurnGuid)
        {
            Burn = Effect;
        }
    }
    TestNotNull(TEXT("An Effect attachment spawns an Effect Source"), Haze);
    TestNotNull(TEXT("A Wing Burn spawns an Effect Source"), Burn);
    if (!Haze || !Burn)
    {
        World->DestroyWorld(false);
        return false;
    }

    TestTrue(TEXT("Identity comes from the cue"), Haze->CueGuid == CueGuid);
    TestTrue(TEXT("Settings come from the Show"), Haze->Settings.Type == EInfinityStageEffectType::Haze);
    TestTrue(TEXT("A haze pot shows its apparatus"), Haze->Apparatus->IsVisible());
    TestEqual(TEXT("A haze pot feeds its medium"),
        Haze->Medium->RadialFogExtinction, Haze->Settings.MediumDensity);
    TestFalse(TEXT("A burning wing has no apparatus"), Burn->Apparatus->IsVisible());
    TestEqual(TEXT("A burning wing leaves no medium"), Burn->Medium->RadialFogExtinction, 0.0f);

    // Move the wing inward: the burn follows it, the station-anchored pot does not.
    const FInfinityMaterializedPanelRef* Left = Passage->MaterializedPanels.FindByPredicate(
        [CueGuid](const FInfinityMaterializedPanelRef& Ref)
        { return Ref.CueGuid == CueGuid && Ref.Side == EInfinityPanelSide::Left; });
    TestNotNull(TEXT("The burning wing's panel exists"), Left);
    if (Left && Left->Component)
    {
        FTransform Moved = Left->BaseWorldTransform;
        Moved.AddToTranslation(FVector(0.0, 150.0, 0.0));
        Left->Component->UpdateInstanceTransform(Left->InstanceIndex, Moved, true, false, true);
        const FVector BurnBefore = Burn->TrackingRoot->GetComponentLocation();
        const FVector HazeBefore = Haze->TrackingRoot->GetComponentLocation();
        Burn->Tick(0.0f);
        Haze->Tick(0.0f);
        TestTrue(TEXT("The burn rides the wing's travel"),
            Burn->TrackingRoot->GetComponentLocation().Equals(BurnBefore + FVector(0.0, 150.0, 0.0), 0.1));
        TestTrue(TEXT("The station pot stays put"),
            Haze->TrackingRoot->GetComponentLocation().Equals(HazeBefore, 0.1));

        // A drag in the viewport moves the actor; tracking keeps the new offset.
        Burn->SetActorLocation(Burn->GetActorLocation() + FVector(0.0, 0.0, 80.0));
        Burn->Tick(0.0f);
        TestTrue(TEXT("A dragged burn keeps its new offset on the moving wing"),
            Burn->TrackingRoot->GetComponentLocation().Equals(BurnBefore + FVector(0.0, 150.0, 80.0), 0.1));
    }

    World->DestroyWorld(false);
    return true;
}

#endif
