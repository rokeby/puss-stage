#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageStructureActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/RectLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
constexpr double FixtureHalfWidthCm = 400.0;

/** A materialized Passage of cube wing pairs, 800 cm apart across the route. */
AInfinityStagePassageActor* SpawnMaterializedPassage(
    UWorld& World,
    const int32 PairCount,
    const FRotator& Rotation = FRotator::ZeroRotator,
    const double LeftLateralCm = -FixtureHalfWidthCm,
    const double RightLateralCm = FixtureHalfWidthCm)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    for (int32 Index = 0; Index < PairCount; ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetLocation(FVector(0.0, LeftLateralCm, 0.0));
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Right.LocalTransform.SetLocation(FVector(0.0, RightLateralCm, 0.0));
        Cue.WingPair.GapToNextCm = 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    Show->ReconcilePassageSettings();

    AInfinityStagePassageActor* Passage = World.SpawnActor<AInfinityStagePassageActor>(
        FVector::ZeroVector, Rotation);
    Passage->ShowAsset = Show;
    Passage->MaterializePassage();
    return Passage;
}

AInfinityStageStructureActor* SpawnMachinedStructure(UWorld& World, AInfinityStagePassageActor& Passage)
{
    AInfinityStageStructureActor* Structure = World.SpawnActor<AInfinityStageStructureActor>();
    Structure->Passage = &Passage;
    // Exact geometry for assertions; the wear settings and the ground are
    // covered by their own tests.
    Structure->Gridiron.SectionVariation = 0.0;
    Structure->Gridiron.TwistDegrees = 0.0;
    Structure->Ground.bEnabled = false;
    return Structure;
}

int32 CountStructureComponents(const AActor& Actor)
{
    TInlineComponentArray<UInstancedStaticMeshComponent*> Components(&Actor);
    int32 Count = 0;
    for (const UInstancedStaticMeshComponent* Component : Components)
    {
        Count += Component->ComponentTags.Contains(TEXT("InfinityStage.Structure")) ? 1 : 0;
    }
    return Count;
}

UInstancedStaticMeshComponent* FindLayer(const AInfinityStageStructureActor& Structure, const TCHAR* Tag)
{
    for (UInstancedStaticMeshComponent* Component : Structure.ManagedComponents)
    {
        if (Component && Component->ComponentTags.Contains(FName(Tag)))
        {
            return Component;
        }
    }
    return nullptr;
}

TArray<FTransform> ReadInstances(const UInstancedStaticMeshComponent& Component)
{
    TArray<FTransform> Transforms;
    for (int32 Index = 0; Index < Component.GetInstanceCount(); ++Index)
    {
        Component.GetInstanceTransform(Index, Transforms.AddDefaulted_GetRef(), true);
    }
    return Transforms;
}

bool InstanceTransformsBitIdentical(const TArray<FTransform>& A, const TArray<FTransform>& B)
{
    if (A.Num() != B.Num())
    {
        return false;
    }
    for (int32 Index = 0; Index < A.Num(); ++Index)
    {
        const FVector ALocation = A[Index].GetLocation();
        const FVector BLocation = B[Index].GetLocation();
        const FQuat ARotation = A[Index].GetRotation();
        const FQuat BRotation = B[Index].GetRotation();
        const FVector AScale = A[Index].GetScale3D();
        const FVector BScale = B[Index].GetScale3D();
        if (FMemory::Memcmp(&ALocation, &BLocation, sizeof(FVector)) != 0
            || FMemory::Memcmp(&ARotation, &BRotation, sizeof(FQuat)) != 0
            || FMemory::Memcmp(&AScale, &BScale, sizeof(FVector)) != 0)
        {
            return false;
        }
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageGridironFollowsStationsTest,
    "InfinityStage.Structure.GridironFollowsCompiledStations",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageGridironFollowsStationsTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);

    UFunction* Button = Structure->FindFunction(
        GET_FUNCTION_NAME_CHECKED(AInfinityStageStructureActor, MaterializeStructureInEditor));
    TestTrue(TEXT("Materialize Structure is a Call In Editor button"),
        Button && Button->HasMetaData(TEXT("CallInEditor")));
    TestTrue(TEXT("Structure materializes"), Structure->MaterializeStructure());
    TestEqual(TEXT("One bay per wing station"), Structure->StationCount, 3);
    TestEqual(TEXT("A cross beam on every station"), Structure->CrossBeamCount, 3);
    TestEqual(TEXT("Two rails between each pair of stations"), Structure->RailSegmentCount, 4);
    TestEqual(TEXT("One component for the gridiron layer"), Structure->ManagedComponents.Num(), 1);
    const double ExpectedHalfSpan = FixtureHalfWidthCm + Structure->Gridiron.OverhangCm;
    TestTrue(TEXT("Grid spans the widest panel plus the overhang"),
        FMath::IsNearlyEqual(Structure->GridHalfWidthCm, ExpectedHalfSpan, 0.01));
    TestTrue(TEXT("A fresh build reports its stations as current"), Structure->IsStructureCurrent());

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    TestTrue(TEXT("Stations gather"), Structure->GatherStations(Stations, Error));
    UInstancedStaticMeshComponent* Grid =
        Structure->ManagedComponents.IsEmpty() ? nullptr : Structure->ManagedComponents[0].Get();
    TestNotNull(TEXT("Gridiron component exists"), Grid);
    TestEqual(TEXT("Three stations"), Stations.Num(), 3);
    if (!Grid || Stations.Num() != 3 || Grid->GetInstanceCount() != 7)
    {
        AddError(TEXT("Gridiron fixture did not build seven timbers over three stations."));
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Layer is tagged for ownership"),
        Grid->ComponentTags.Contains(TEXT("InfinityStage.Structure.Gridiron")));
    TestEqual(TEXT("Every timber carries four custom floats"), Grid->PerInstanceSMCustomData.Num(), 7 * 4);
    TestTrue(TEXT("Stations are in route order"),
        Stations[0].DistanceCm < Stations[1].DistanceCm && Stations[1].DistanceCm < Stations[2].DistanceCm);
    TestTrue(TEXT("Station width is read from the placed panels"),
        FMath::IsNearlyEqual(Stations[1].HalfWidthCm, FixtureHalfWidthCm, 0.01));

    // Instance order per station: the cross beam, then the two rails to the next station.
    const TArray<FTransform> Timbers = ReadInstances(*Grid);
    const FVector Station0 = Stations[0].StationWorld.GetLocation();
    const FVector Station1 = Stations[1].StationWorld.GetLocation();
    TestTrue(TEXT("Cross beam hangs at gridiron height over its station"),
        Timbers[0].GetLocation().Equals(Station0 + FVector(0.0, 0.0, Structure->Gridiron.HeightCm), 0.1));
    TestTrue(TEXT("Cross beam length runs across the route"),
        FMath::Abs(Timbers[0].GetRotation().GetAxisX().Y) > 0.999);
    TestTrue(TEXT("Cross beam spans the whole grid"),
        FMath::IsNearlyEqual(Timbers[0].GetScale3D().X * 100.0, ExpectedHalfSpan * 2.0, 0.1));
    const FVector RailCentre = (Station0 + Station1) * 0.5
        + FVector(0.0, -ExpectedHalfSpan, Structure->Gridiron.HeightCm + Structure->Gridiron.BeamDepthCm);
    TestTrue(TEXT("Rail rests on the crosses at the grid edge"),
        Timbers[1].GetLocation().Equals(RailCentre, 0.1));
    TestTrue(TEXT("Rail runs along the route"),
        FMath::Abs(Timbers[1].GetRotation().GetAxisX().X) > 0.999);
    TestTrue(TEXT("Rail spans one bay"),
        FMath::IsNearlyEqual(Timbers[1].GetScale3D().X * 100.0, FVector::Distance(Station0, Station1), 0.1));
    TestTrue(TEXT("Custom data carries the true beam length for the material"),
        FMath::IsNearlyEqual(Grid->PerInstanceSMCustomData[1], static_cast<float>(ExpectedHalfSpan * 2.0), 0.1f));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureOwnsOnlyItsOwnTest,
    "InfinityStage.Structure.RegenerationOwnsOnlyItsOwn",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureOwnsOnlyItsOwnTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 4);
    AInfinityStageStructureActor* Structure = World->SpawnActor<AInfinityStageStructureActor>();
    Structure->Passage = Passage;
    Structure->Ground.bEnabled = false;
    TestTrue(TEXT("Worn structure materializes"), Structure->MaterializeStructure());
    if (Structure->ManagedComponents.Num() != 1)
    {
        AddError(TEXT("Expected one gridiron component."));
        World->DestroyWorld(false);
        return false;
    }
    const TArray<FTransform> FirstBuild = ReadInstances(*Structure->ManagedComponents[0]);
    const TArray<float> FirstData = Structure->ManagedComponents[0]->PerInstanceSMCustomData;
    TestTrue(TEXT("Wear varies the timbers"),
        FirstBuild.Num() > 3
        && !FMath::IsNearlyEqual(FirstBuild[0].GetScale3D().Y, FirstBuild[3].GetScale3D().Y, 1.0e-6));

    // Evidence of use, placed by hand: a separate actor, and a component the
    // artist added to the structure actor itself.
    AActor* Sandbag = World->SpawnActor<AActor>();
    UInstancedStaticMeshComponent* HandRope = NewObject<UInstancedStaticMeshComponent>(Structure, TEXT("HandRope"));
    HandRope->SetupAttachment(Structure->GetRootComponent());
    Structure->AddInstanceComponent(HandRope);
    HandRope->RegisterComponent();

    // Undo can drop the ownership record while the component lives on.
    UInstancedStaticMeshComponent* Orphan = Structure->ManagedComponents[0];
    Structure->ManagedComponents.Reset();
    TestTrue(TEXT("Rebuild succeeds"), Structure->MaterializeStructure());
    TInlineComponentArray<UInstancedStaticMeshComponent*> Remaining(Structure);
    TestEqual(TEXT("Rebuild never stacks a second grid"), CountStructureComponents(*Structure), 1);
    TestFalse(TEXT("The orphaned grid was destroyed"), Remaining.Contains(Orphan));
    TestTrue(TEXT("A hand-placed actor survives regeneration"), IsValid(Sandbag));
    TestTrue(TEXT("A hand-added component survives regeneration"), Remaining.Contains(HandRope));

    const TArray<FTransform> SecondBuild = ReadInstances(*Structure->ManagedComponents[0]);
    bool bSameTimbers = SecondBuild.Num() == FirstBuild.Num();
    for (int32 Index = 0; bSameTimbers && Index < SecondBuild.Num(); ++Index)
    {
        bSameTimbers = SecondBuild[Index].Equals(FirstBuild[Index], 1.0e-4);
    }
    TestTrue(TEXT("Regeneration reproduces the same worn timbers"), bSameTimbers);
    TestTrue(TEXT("Regeneration reproduces the same custom data"),
        Structure->ManagedComponents[0]->PerInstanceSMCustomData == FirstData);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureRefitTest,
    "InfinityStage.Structure.RefitsAndRefusesStalePassage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureRefitTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);

    AInfinityStageStructureActor* Unassigned = World->SpawnActor<AInfinityStageStructureActor>();
    AddExpectedError(TEXT("Structure has no Passage"), EAutomationExpectedErrorFlags::Contains, 1);
    TestFalse(TEXT("A structure with no Passage refuses"), Unassigned->MaterializeStructure());

    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    TestTrue(TEXT("Initial build"), Structure->MaterializeStructure());
    if (Structure->ManagedComponents.Num() != 1)
    {
        AddError(TEXT("Expected one gridiron component."));
        World->DestroyWorld(false);
        return false;
    }
    const FVector FirstCross = ReadInstances(*Structure->ManagedComponents[0])[0].GetLocation();

    // Re-placing the wings changes the stations the building must fit.
    Passage->SetActorLocation(FVector(1000.0, 0.0, 0.0));
    TestTrue(TEXT("Wings re-materialize"), Passage->MaterializePassage());
    TestFalse(TEXT("Moved wings leave the structure stale"), Structure->IsStructureCurrent());
    TestTrue(TEXT("Structure re-fits"), Structure->MaterializeStructure());
    TestTrue(TEXT("Re-fitted structure is current"), Structure->IsStructureCurrent());
    TestTrue(TEXT("Re-fit follows the wings"),
        ReadInstances(*Structure->ManagedComponents[0])[0].GetLocation().Equals(
            FirstCross + FVector(1000.0, 0.0, 0.0), 0.1));

    // A cleared Passage no longer matches its compile; building on it would fit
    // the wrong wings, so the last good structure must stay standing.
    const int32 TimbersBefore = Structure->ManagedComponents[0]->GetInstanceCount();
    Passage->ClearMaterializedPassage();
    AddExpectedError(TEXT("is stale"), EAutomationExpectedErrorFlags::Contains, 1);
    TestFalse(TEXT("A stale Passage is refused"), Structure->MaterializeStructure());
    TestEqual(TEXT("Refusal keeps the previous structure"),
        Structure->ManagedComponents.Num() == 1 ? Structure->ManagedComponents[0]->GetInstanceCount() : 0,
        TimbersBefore);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureRouteFrameTest,
    "InfinityStage.Structure.FollowsRouteFrame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureRouteFrameTest::RunTest(const FString& Parameters)
{
    // A Passage turned a quarter: the route runs along world Y, so the building
    // must turn with it rather than assume the route is world X.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3, FRotator(0.0, 90.0, 0.0));
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    TestTrue(TEXT("Turned structure materializes"), Structure->MaterializeStructure());
    TestTrue(TEXT("Width is measured across the turned route"),
        FMath::IsNearlyEqual(Structure->GridHalfWidthCm, FixtureHalfWidthCm + Structure->Gridiron.OverhangCm, 0.01));
    if (Structure->ManagedComponents.Num() != 1 || Structure->ManagedComponents[0]->GetInstanceCount() < 2)
    {
        AddError(TEXT("Expected a gridiron with at least one cross beam and rail."));
        World->DestroyWorld(false);
        return false;
    }
    const TArray<FTransform> Timbers = ReadInstances(*Structure->ManagedComponents[0]);
    TestTrue(TEXT("Cross beam turns to span world X"),
        FMath::Abs(Timbers[0].GetRotation().GetAxisX().X) > 0.999);
    TestTrue(TEXT("Rail turns to run along world Y"),
        FMath::Abs(Timbers[1].GetRotation().GetAxisX().Y) > 0.999);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureFixturesTest,
    "InfinityStage.Structure.FixturesHangFromTheGrid",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureFixturesTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 2);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;

    const auto MakeLight = [](const FTransform& Offset)
    {
        FInfinityCueAttachment Light;
        Light.AttachmentGuid = FGuid::NewGuid();
        Light.Kind = EInfinityAttachmentKind::Light;
        Light.RelativeTransform = Offset;
        return Light;
    };
    // A lamp hung under the grid, thrown forward and down.
    const FInfinityCueAttachment Hung = MakeLight(FTransform(FRotator(-50.0, 0.0, 0.0), FVector(0.0, 200.0, 1000.0)));
    // Beyond the grid's span: a housing, but nothing overhead to hang from.
    const FInfinityCueAttachment Outside = MakeLight(FTransform(FVector(0.0, 2000.0, 800.0)));
    FInfinityCueAttachment Off = MakeLight(FTransform(FVector(0.0, -200.0, 1000.0)));
    Off.bEnabled = false;
    FInfinityCueAttachment Riding = MakeLight(FTransform(FVector(0.0, -200.0, 1000.0)));
    Riding.Anchor = EInfinityAttachmentAnchor::LeftPanel;
    FInfinityCueAttachment Suppressed = MakeLight(FTransform(FVector(0.0, 50.0, 900.0)));
    Suppressed.bSuppressFixtureBody = true;
    TArray<FInfinityCueAttachment>& Attachments = Passage->ShowAsset->Cues[0].WingPair.Attachments;
    Attachments.Append({ Hung, Outside, Off, Riding, Suppressed });

    TestTrue(TEXT("Structure with lights materializes"), Structure->MaterializeStructure());
    TestEqual(TEXT("A housing for each enabled station light"), Structure->FixtureBodyCount, 2);
    TestTrue(TEXT("Fixture suppression defaults off"), !Hung.bSuppressFixtureBody);
    TestTrue(TEXT("A suppressed station light gets no additional housing"), Suppressed.bSuppressFixtureBody);
    TestEqual(TEXT("A line only where the grid is overhead"), Structure->HangingLineCount, 1);
    TestEqual(TEXT("A panel-riding light is reported, not housed"), Structure->MovingLightsWithoutHousing, 1);
    TestTrue(TEXT("Gridiron, ground, grooves, understage, housings and lines are separate layers"),
        Structure->ManagedComponents.Num() >= 6);

    UInstancedStaticMeshComponent* Housings = FindLayer(*Structure, TEXT("InfinityStage.Structure.Fixtures"));
    UInstancedStaticMeshComponent* Lines = FindLayer(*Structure, TEXT("InfinityStage.Structure.Lines"));
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    if (!Housings || !Lines || Housings->GetInstanceCount() != 2 || Lines->GetInstanceCount() != 1 || Stations.IsEmpty())
    {
        AddError(TEXT("Expected two housings and one line over a gathered station."));
        World->DestroyWorld(false);
        return false;
    }
    TestFalse(TEXT("Housings cast no shadow"), Housings->CastShadow);

    const FTransform LightWorld = Hung.RelativeTransform * Stations[0].StationWorld;
    const FVector Throw = LightWorld.GetUnitAxis(EAxis::X);
    const double HousingLength = Structure->Fixtures.BodySizeCm.X;
    const FTransform Housing = ReadInstances(*Housings)[0];
    TestTrue(TEXT("The housing sits behind its source"),
        Housing.GetLocation().Equals(LightWorld.GetLocation() - Throw * (HousingLength * 0.5), 0.1));
    TestTrue(TEXT("The housing points along the throw"),
        FVector::DotProduct(Housing.GetRotation().GetAxisX(), Throw) > 0.999);
    const FTransform SuppressedWorld = Suppressed.RelativeTransform * Stations[0].StationWorld;
    const FVector SuppressedCentre = SuppressedWorld.GetLocation()
        - SuppressedWorld.GetUnitAxis(EAxis::X) * (HousingLength * 0.5);
    bool bFoundSuppressedHousing = false;
    for (const FTransform& Candidate : ReadInstances(*Housings))
    {
        bFoundSuppressedHousing |= Candidate.GetLocation().Equals(SuppressedCentre, 0.1);
    }
    TestFalse(TEXT("A suppressed attachment has no body instance"), bFoundSuppressedHousing);

    const FTransform Line = ReadInstances(*Lines)[0];
    const double GridTopZ = Stations[0].StationWorld.GetLocation().Z
        + Structure->Gridiron.HeightCm + Structure->Gridiron.BeamDepthCm * 1.5;
    TestTrue(TEXT("The line hangs plumb"), FMath::Abs(Line.GetRotation().GetAxisX().Z) > 0.999);
    TestTrue(TEXT("The line reaches the top of the grid"),
        FMath::IsNearlyEqual(Line.GetLocation().Z + Line.GetScale3D().X * 50.0, GridTopZ, 0.1));
    TestTrue(TEXT("The line starts on the housing"),
        FMath::IsNearlyEqual(Line.GetLocation().X, Housing.GetLocation().X, 0.1)
        && FMath::IsNearlyEqual(Line.GetLocation().Y, Housing.GetLocation().Y, 0.1));

    TestTrue(TEXT("A fresh build with lights is current"), Structure->IsStructureCurrent());
    TMap<UInstancedStaticMeshComponent*, TArray<FTransform>> OtherLayersBefore;
    for (UInstancedStaticMeshComponent* Component : Structure->ManagedComponents)
    {
        if (Component
            && !Component->ComponentTags.Contains(TEXT("InfinityStage.Structure.Fixtures"))
            && !Component->ComponentTags.Contains(TEXT("InfinityStage.Structure.Lines")))
        {
            OtherLayersBefore.Add(Component, ReadInstances(*Component));
        }
    }
    TestTrue(TEXT("Fixture test covers multiple non-fixture layers"), OtherLayersBefore.Num() >= 4);
    const FVector HousingBefore = Housing.GetLocation();
    Attachments[0].RelativeTransform.AddToTranslation(FVector(0.0, 0.0, -50.0));
    TestFalse(TEXT("Moving a light in the Show leaves its housing stale"), Structure->IsStructureCurrent());
    TestTrue(TEXT("Fixture-only rebuild succeeds"), Structure->RebuildFixturesOnly());
    UInstancedStaticMeshComponent* HousingsAfter = FindLayer(*Structure, TEXT("InfinityStage.Structure.Fixtures"));
    TestNotNull(TEXT("Fixture-only rebuild creates housings"), HousingsAfter);
    bool bOtherLayersUntouched = true;
    for (const TPair<UInstancedStaticMeshComponent*, TArray<FTransform>>& Pair : OtherLayersBefore)
    {
        const bool bStillManaged = Structure->ManagedComponents.ContainsByPredicate(
            [&Pair](const TObjectPtr<UInstancedStaticMeshComponent>& Candidate)
            {
                return Candidate.Get() == Pair.Key;
            });
        bOtherLayersUntouched &= bStillManaged
            && InstanceTransformsBitIdentical(Pair.Value, ReadInstances(*Pair.Key));
    }
    TestTrue(TEXT("Every other layer component and its instance transforms are bit-identical"),
        bOtherLayersUntouched);
    const TArray<FTransform> HousingsAfterTransforms = HousingsAfter
        ? ReadInstances(*HousingsAfter)
        : TArray<FTransform>();
    TestTrue(TEXT("Fixture-only rebuild makes the housing follow the moved light"),
        !HousingsAfterTransforms.IsEmpty() && HousingsAfterTransforms[0].GetLocation().Equals(
            HousingBefore + FVector(0.0, 0.0, -50.0), 0.1));
    TestEqual(TEXT("Suppression still omits one body after a rebuild"), Structure->FixtureBodyCount, 2);
    TestTrue(TEXT("Fixture-only rebuild refreshes the structure signature"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageFixtureOnlyRebuildRefusesPIETest,
    "InfinityStage.Structure.FixtureOnlyRebuildRefusesPIE",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageFixtureOnlyRebuildRefusesPIETest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::PIE, false);
    AInfinityStageStructureActor* Structure = World->SpawnActor<AInfinityStageStructureActor>();
    Structure->FixtureBodyCount = 17;
    AddExpectedError(TEXT("RebuildFixturesOnly is editor authoring only"), EAutomationExpectedErrorFlags::Contains, 1);
    TestFalse(TEXT("Fixture-only rebuild refuses in PIE"), Structure->RebuildFixturesOnly());
    TestEqual(TEXT("PIE refusal leaves the fixture layer untouched"), Structure->FixtureBodyCount, 17);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureGroundTest,
    "InfinityStage.Structure.GroundSlotsKeepTheCatLineClear",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureGroundTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;
    TestTrue(TEXT("Structure with ground materializes"), Structure->MaterializeStructure());
    TestEqual(TEXT("A slot each side of every station"), Structure->SlotCount, 6);

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    UInstancedStaticMeshComponent* Boards = FindLayer(*Structure, TEXT("InfinityStage.Structure.Ground"));
    UInstancedStaticMeshComponent* Understage = FindLayer(*Structure, TEXT("InfinityStage.Structure.Understage"));
    if (!Boards || !Understage || Stations.Num() != 3 || Boards->GetInstanceCount() == 0)
    {
        AddError(TEXT("Expected boards and an understage over three stations."));
        World->DestroyWorld(false);
        return false;
    }
    TestEqual(TEXT("Board count is reported"), Structure->BoardCount, Boards->GetInstanceCount());
    TestTrue(TEXT("Boards cast shadow, so the understage stays dark"), static_cast<bool>(Boards->CastShadow));

    const FInfinityStageGroundSettings& Ground = Structure->Ground;
    const double SlotInnerCm = FixtureHalfWidthCm - Ground.SlotInboardCm;
    const double HalfSlotCm = Ground.SlotWidthCm * 0.5;
    const double HalfBoardCm = Ground.BoardWidthCm * 0.5;
    const TArray<FTransform> Planks = ReadInstances(*Boards);
    bool bSlotsOpen = true;
    bool bCentreRunsThrough = false;
    bool bFlushTop = true;
    const double MiddleStationCm = Stations[1].StationWorld.GetLocation().X;
    for (const FTransform& Plank : Planks)
    {
        const FVector Centre = Plank.GetLocation();
        const double HalfLengthCm = Plank.GetScale3D().X * 50.0;
        const double FromCm = Centre.X - HalfLengthCm;
        const double ToCm = Centre.X + HalfLengthCm;
        bFlushTop &= FMath::IsNearlyEqual(Centre.Z + Plank.GetScale3D().Z * 50.0, Ground.FloorHeightCm, 0.01);
        if (FMath::Abs(Centre.Y) + HalfBoardCm > SlotInnerCm)
        {
            for (const FInfinityStructureStation& Station : Stations)
            {
                const double SlotCm = Station.StationWorld.GetLocation().X;
                bSlotsOpen &= !(FromCm < SlotCm + HalfSlotCm - 0.01 && ToCm > SlotCm - HalfSlotCm + 0.01);
            }
        }
        if (FMath::Abs(Centre.Y) + HalfBoardCm <= Ground.CatClearanceCm)
        {
            bCentreRunsThrough |= FromCm < MiddleStationCm && ToCm > MiddleStationCm;
        }
    }
    TestTrue(TEXT("No board bridges a chariot slot"), bSlotsOpen);
    TestTrue(TEXT("Boards run unbroken across a station on the cat's line"), bCentreRunsThrough);
    TestTrue(TEXT("Every board top sits at floor height"), bFlushTop);
    TestTrue(TEXT("The understage lies well below the boards"),
        ReadInstances(*Understage)[0].GetLocation().Z < Ground.FloorHeightCm - Ground.UnderstageDepthCm);

    // Steel grooves: every slot lined by two walls and a bottom, all inside the
    // gap, between the boards' underside and the floor, reaching the floor's edge.
    UInstancedStaticMeshComponent* Grooves = FindLayer(*Structure, TEXT("InfinityStage.Structure.Grooves"));
    TestTrue(TEXT("Slots are lined with steel grooves"), Grooves != nullptr);
    if (Grooves)
    {
        TestEqual(TEXT("Three plates per slot"), Structure->GroovePieceCount, Structure->SlotCount * 3);
        TestEqual(TEXT("Groove pieces are counted"), Structure->GroovePieceCount, Grooves->GetInstanceCount());
        TestFalse(TEXT("Groove plates cast no shadow"), static_cast<bool>(Grooves->CastShadow));
        const FBox MeshBounds = Grooves->GetStaticMesh()->GetBoundingBox();
        const double PitchCm = Ground.BoardWidthCm + Ground.BoardGapCm;
        const int32 Lanes = FMath::FloorToInt32((Structure->GridHalfWidthCm * 2.0 + Ground.BoardGapCm) / PitchCm);
        const double FloorOuterCm = (Lanes * PitchCm - Ground.BoardGapCm) * 0.5;
        bool bInsideGaps = true;
        bool bBetweenFloorAndUnderside = true;
        double OuterReachCm = 0.0;
        for (const FTransform& Piece : ReadInstances(*Grooves))
        {
            const FBox Box = MeshBounds.TransformBy(Piece);
            bool bInSomeGap = false;
            for (const FInfinityStructureStation& Station : Stations)
            {
                const double SlotCm = Station.StationWorld.GetLocation().X;
                bInSomeGap |= Box.Min.X >= SlotCm - HalfSlotCm - 0.01 && Box.Max.X <= SlotCm + HalfSlotCm + 0.01;
            }
            bInsideGaps &= bInSomeGap;
            bBetweenFloorAndUnderside &= Box.Max.Z <= Ground.FloorHeightCm + 0.01
                && Box.Min.Z >= Ground.FloorHeightCm - Ground.BoardThicknessCm - 0.01;
            OuterReachCm = FMath::Max(OuterReachCm, FMath::Max(FMath::Abs(Box.Min.Y), FMath::Abs(Box.Max.Y)));
        }
        TestTrue(TEXT("Every groove plate sits inside a slot's gap"), bInsideGaps);
        TestTrue(TEXT("Every groove plate lies between the boards' underside and the floor"), bBetweenFloorAndUnderside);
        TestTrue(TEXT("Grooves run out to the floor's edge"), FMath::IsNearlyEqual(OuterReachCm, FloorOuterCm, 0.05));
    }

    TestTrue(TEXT("Rebuild succeeds"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Rebuilt = FindLayer(*Structure, TEXT("InfinityStage.Structure.Ground"));
    TestTrue(TEXT("Rebuilding lays the same boards"),
        Rebuilt && Rebuilt->GetInstanceCount() == Planks.Num() && ReadInstances(*Rebuilt)[0].Equals(Planks[0], 1.0e-4));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureDrawOrderTest,
    "InfinityStage.Structure.SavedFloorsSurviveARebuild",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

/**
 * A lane's first board is two random draws multiplied. C++ leaves the order of a
 * product's operands unspecified, and the 29 Sep rebuild flipped it for the passage
 * floor, re-rolling the joints of all five saved floors (boards S01 +1, S02 -1,
 * S04 +4, S05 -1, S06 -6). The draws are now separate statements, each site in the
 * order its saved boards were laid in: the passage floor draws a lane's length
 * first, the stage front its fraction first. Both are read back from the boards.
 */
bool FInfinityStageStructureDrawOrderTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;
    TestTrue(TEXT("Structure with a floor and a stage front materializes"), Structure->MaterializeStructure());

    constexpr int32 DataFloats = 4;         // [tone, length, width, thickness]
    constexpr uint32 BoardLanePart = 4;     // ETimberPart::BoardLane
    constexpr uint32 PortalPart = 6;        // ETimberPart::Portal
    const FInfinityStageGroundSettings& Ground = Structure->Ground;
    const double MinLengthCm = FMath::Max(20.0, FMath::Min(Ground.MinBoardLengthCm, Ground.MaxBoardLengthCm));
    const double MaxLengthCm = FMath::Max(MinLengthCm, Ground.MaxBoardLengthCm);
    // A lane's first length from its two draws: Key if the length is drawn first,
    // Value if the fraction is.
    const auto FirstLengths = [MinLengthCm, MaxLengthCm](const float First, const float Second)
    {
        return TPair<double, double>(
            (MinLengthCm + (MaxLengthCm - MinLengthCm) * First) * (0.2 + (1.0 - 0.2) * Second),
            (MinLengthCm + (MaxLengthCm - MinLengthCm) * Second) * (0.2 + (1.0 - 0.2) * First));
    };
    UInstancedStaticMeshComponent* Boards = FindLayer(*Structure, TEXT("InfinityStage.Structure.Ground"));
    UInstancedStaticMeshComponent* Front = nullptr;
    for (UInstancedStaticMeshComponent* Component : Structure->ManagedComponents)
    {
        if (Component && Component->GetName().StartsWith(TEXT("StructureStageFront")))
        {
            Front = Component;
        }
    }
    if (!Boards || !Front || Boards->GetInstanceCount() == 0 || Front->GetInstanceCount() == 0)
    {
        AddError(TEXT("Expected a boarded floor and a stage front."));
        World->DestroyWorld(false);
        return false;
    }

    // The passage floor: the first board of the lane beside the route line, which no
    // slot cuts and no end clamps.
    const double PitchCm = Ground.BoardWidthCm + Ground.BoardGapCm;
    const int32 Lanes = FMath::FloorToInt32((Structure->GridHalfWidthCm * 2.0 + Ground.BoardGapCm) / PitchCm);
    const int32 Lane = (Lanes - 1) / 2;
    const double LaneCm = -(Lanes * PitchCm - Ground.BoardGapCm) * 0.5 + Ground.BoardWidthCm * 0.5 + Lane * PitchCm;
    int32 FirstBoard = INDEX_NONE;
    double FirstBoardX = TNumericLimits<double>::Max();
    for (int32 Index = 0; Index < Boards->GetInstanceCount(); ++Index)
    {
        FTransform Plank;
        Boards->GetInstanceTransform(Index, Plank, true);
        if (FMath::Abs(Plank.GetLocation().Y - LaneCm) < 1.0 && Plank.GetLocation().X < FirstBoardX)
        {
            FirstBoardX = Plank.GetLocation().X;
            FirstBoard = Index;
        }
    }
    FRandomStream LaneStream(static_cast<int32>(HashCombineFast(
        HashCombineFast(GetTypeHash(Passage->PassageGuid), ::GetTypeHash(BoardLanePart)), ::GetTypeHash(Lane))));
    const float LaneFirstDraw = LaneStream.FRand();
    const float LaneSecondDraw = LaneStream.FRand();
    const TPair<double, double> LaneWays = FirstLengths(LaneFirstDraw, LaneSecondDraw);
    TestTrue(TEXT("The two draw orders lay different first boards, so the check can tell them apart"),
        !FMath::IsNearlyEqual(LaneWays.Key, LaneWays.Value, 0.01));
    TestTrue(TEXT("The passage floor draws a lane's first length before its fraction"),
        FirstBoard != INDEX_NONE && FMath::IsNearlyEqual(
            static_cast<double>(Boards->PerInstanceSMCustomData[FirstBoard * DataFloats + 1]), LaneWays.Key, 0.01));

    // The stage front: every portal piece draws its tone from one stream, in build
    // order, so a board's tone says where it sits in that stream. A lane starts where
    // three or more draws separate two tones (the last lane's unused next length, then
    // this lane's two); within a lane only one does.
    FRandomStream PortalStream(static_cast<int32>(HashCombineFast(GetTypeHash(Passage->PassageGuid), ::GetTypeHash(PortalPart))));
    TArray<float> Draws;
    TMap<float, int32> DrawIndex;
    for (int32 Index = 0; Index < 20000; ++Index)
    {
        const float Draw = PortalStream.FRand();
        Draws.Add(Draw);
        if (!DrawIndex.Contains(Draw))
        {
            DrawIndex.Add(Draw, Index);
        }
    }
    int32 Located = 0;
    int32 LengthFirst = 0;
    int32 FractionFirst = 0;
    int32 Previous = INDEX_NONE;
    for (int32 Index = 0; Index < Front->GetInstanceCount(); ++Index)
    {
        const int32* At = DrawIndex.Find(Front->PerInstanceSMCustomData[Index * DataFloats]);
        if (!At)
        {
            Previous = INDEX_NONE;
            continue;
        }
        ++Located;
        if ((Previous == INDEX_NONE || *At - Previous >= 3) && *At >= 2)
        {
            const TPair<double, double> Ways = FirstLengths(Draws[*At - 2], Draws[*At - 1]);
            const double LengthCm = Front->PerInstanceSMCustomData[Index * DataFloats + 1];
            const bool bLengthFirst = FMath::IsNearlyEqual(LengthCm, Ways.Key, 0.01);
            const bool bFractionFirst = FMath::IsNearlyEqual(LengthCm, Ways.Value, 0.01);
            LengthFirst += bLengthFirst && !bFractionFirst ? 1 : 0;
            FractionFirst += bFractionFirst && !bLengthFirst ? 1 : 0;
        }
        Previous = *At;
    }
    TestEqual(TEXT("Every stage-front board's tone comes from the portal stream"), Located, Front->GetInstanceCount());
    TestTrue(TEXT("Some stage-front lanes start with a board no run end clamps"), LengthFirst + FractionFirst > 0);
    TestEqual(TEXT("The stage front draws a lane's first fraction before its length"), LengthFirst, 0);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureClothTest,
    "InfinityStage.Structure.ClothLiesOverTheBoards",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureClothTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 4);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    // The engine plane stands in for the Soft goods pieces: pivot centred, flat.
    Structure->Cloth.bEnabled = true;
    Structure->Cloth.Pieces = { TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Engine/BasicShapes/Plane.Plane"))) };
    Structure->Cloth.Coverage = 1.0f;
    TestTrue(TEXT("Structure with cloth materializes"), Structure->MaterializeStructure());
    TestEqual(TEXT("Full coverage lays one cloth per bay"), Structure->ClothCount, 3);

    UInstancedStaticMeshComponent* Cloths = FindLayer(*Structure, TEXT("InfinityStage.Structure.Cloth"));
    if (!Cloths || Cloths->GetInstanceCount() != 3)
    {
        AddError(TEXT("Expected three cloths on the cloth layer."));
        World->DestroyWorld(false);
        return false;
    }
    const TArray<FTransform> Laid = ReadInstances(*Cloths);
    bool bOnFloor = true;
    bool bUnscaledVertically = true;
    for (const FTransform& Piece : Laid)
    {
        bOnFloor &= FMath::IsNearlyEqual(Piece.GetLocation().Z, Structure->Ground.FloorHeightCm, 0.01);
        bUnscaledVertically &= FMath::IsNearlyEqual(Piece.GetScale3D().Z, 1.0, 1.0e-6);
    }
    TestTrue(TEXT("Cloths are pivoted at floor height"), bOnFloor);
    TestTrue(TEXT("Cloths keep their authored relief"), bUnscaledVertically);
    const float LengthCm = Cloths->PerInstanceSMCustomData[1];
    TestTrue(TEXT("Custom data carries the true length for the weave"),
        LengthCm >= 500.0f * 0.85f - 0.1f && LengthCm <= 500.0f * 1.2f + 0.1f);

    TestTrue(TEXT("Rebuild succeeds"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Rebuilt = FindLayer(*Structure, TEXT("InfinityStage.Structure.Cloth"));
    TestTrue(TEXT("Rebuilding lays the same cloths"),
        Rebuilt && Rebuilt->GetInstanceCount() == 3 && ReadInstances(*Rebuilt)[0].Equals(Laid[0], 1.0e-4));

    Structure->Cloth.Coverage = 0.0f;
    TestTrue(TEXT("Bare build succeeds"), Structure->MaterializeStructure());
    TestEqual(TEXT("No coverage lays no cloth"), Structure->ClothCount, 0);
    TestNull(TEXT("No coverage leaves no empty cloth layer"),
        FindLayer(*Structure, TEXT("InfinityStage.Structure.Cloth")));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureAsymmetricSlotsTest,
    "InfinityStage.Structure.SlotsStartUnderEachSidesOwnWing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureAsymmetricSlotsTest::RunTest(const FString& Parameters)
{
    // P01's shape: wings at -750 and +500, so each side's slots must start under
    // that side's own wing, not both under the wider one.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3, FRotator::ZeroRotator, -750.0, 500.0);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;
    TestTrue(TEXT("Asymmetric structure materializes"), Structure->MaterializeStructure());

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    UInstancedStaticMeshComponent* Boards = FindLayer(*Structure, TEXT("InfinityStage.Structure.Ground"));
    if (Stations.Num() != 3 || !Boards)
    {
        AddError(TEXT("Expected boards over three stations."));
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("The negative side reads its own wing"), FMath::IsNearlyEqual(Stations[1].NegativeSideCm, 750.0, 0.01));
    TestTrue(TEXT("The positive side reads its own wing"), FMath::IsNearlyEqual(Stations[1].PositiveSideCm, 500.0, 0.01));
    TestTrue(TEXT("Half width is still the wider side"), FMath::IsNearlyEqual(Stations[1].HalfWidthCm, 750.0, 0.01));

    const FInfinityStageGroundSettings& Ground = Structure->Ground;
    const double NegativeInnerCm = 750.0 - Ground.SlotInboardCm;   // 600
    const double PositiveInnerCm = 500.0 - Ground.SlotInboardCm;   // 350
    const double HalfBoardCm = Ground.BoardWidthCm * 0.5;
    const double StationCm = Stations[1].StationWorld.GetLocation().X;
    // Lanes wholly between the two slot starts: cut at the station on the narrow
    // (+) side, continuous across it on the wide (-) side. Before the fix both
    // sides used the wider wing, so the + side ran continuous here.
    bool bPositiveCut = true;
    bool bNegativeWhole = false;
    for (const FTransform& Plank : ReadInstances(*Boards))
    {
        const FVector Centre = Plank.GetLocation();
        const double OuterCm = FMath::Abs(Centre.Y) + HalfBoardCm;
        const double InnerCm = FMath::Abs(Centre.Y) - HalfBoardCm;
        if (InnerCm <= PositiveInnerCm || OuterCm >= NegativeInnerCm)
        {
            continue;
        }
        const double HalfLengthCm = Plank.GetScale3D().X * 50.0;
        const bool bSpansStation = Centre.X - HalfLengthCm < StationCm && Centre.X + HalfLengthCm > StationCm;
        if (Centre.Y > 0.0)
        {
            bPositiveCut &= !bSpansStation;
        }
        else
        {
            bNegativeWhole |= bSpansStation;
        }
    }
    TestTrue(TEXT("The narrow side's slot starts under its own wing"), bPositiveCut);
    TestTrue(TEXT("The wide side is not cut inside its own wing's line"), bNegativeWhole);
    TestEqual(TEXT("Still one slot per side per station"), Structure->SlotCount, 6);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructurePortalTest,
    "InfinityStage.Structure.PortalFramesTheCurtain",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructurePortalTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    TestTrue(TEXT("Without a portal the structure builds"), Structure->MaterializeStructure());
    TestNull(TEXT("The portal is off by default"), FindLayer(*Structure, TEXT("InfinityStage.Structure.Portal")));

    // No apron, so the forestage fills the floor in front of the portal line. The
    // frame on its own here; the stage front has its own test.
    Structure->Ground.bEnabled = true;
    Structure->Ground.ApronCm = 0.0;
    Structure->Portal.bEnabled = true;
    Structure->Portal.bStageFront = false;
    TestTrue(TEXT("Structure with a portal materializes"), Structure->MaterializeStructure());

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    UInstancedStaticMeshComponent* Timber = nullptr;
    UInstancedStaticMeshComponent* Forestage = nullptr;
    UInstancedStaticMeshComponent* Lines = nullptr;
    for (UInstancedStaticMeshComponent* Component : Structure->ManagedComponents)
    {
        if (!Component || !Component->ComponentTags.Contains(FName(TEXT("InfinityStage.Structure.Portal"))))
        {
            continue;
        }
        const FString Name = Component->GetName();
        if (Name.StartsWith(TEXT("StructurePortalLines"))) { Lines = Component; }
        else if (Name.StartsWith(TEXT("StructureForestage"))) { Forestage = Component; }
        else if (Name.StartsWith(TEXT("StructurePortal"))) { Timber = Component; }
    }
    if (!Timber || !Forestage || !Lines || Stations.IsEmpty())
    {
        AddError(TEXT("Expected portal timber, forestage and lines over gathered stations."));
        World->DestroyWorld(false);
        return false;
    }
    const FInfinityStagePortalSettings& Portal = Structure->Portal;
    const double PortalX = Stations[0].StationWorld.GetLocation().X + Portal.OffsetFromFirstStationCm;
    const double PostHeightCm = Portal.OpeningHeightCm + Portal.HeaderDepthCm;

    // Posts, header, trough, the grid's forward cross beam and its two rails.
    TestEqual(TEXT("Seven portal timbers"), Timber->GetInstanceCount(), 7);
    int32 Posts = 0;
    bool bPostsFrame = true;
    bool bHeaderOverOpening = false;
    for (const FTransform& Piece : ReadInstances(*Timber))
    {
        if (FMath::Abs(Piece.GetRotation().GetAxisX().Z) > 0.99)
        {
            ++Posts;
            bPostsFrame &= FMath::IsNearlyEqual(Piece.GetScale3D().X * 100.0, PostHeightCm, 0.1)
                && FMath::IsNearlyEqual(FMath::Abs(Piece.GetLocation().Y), Portal.OpeningHalfWidthCm + Portal.PostWidthCm * 0.5, 0.1)
                && FMath::IsNearlyEqual(Piece.GetLocation().X, PortalX, 0.1);
        }
        bHeaderOverOpening |= FMath::Abs(Piece.GetRotation().GetAxisX().Y) > 0.99
            && FMath::IsNearlyEqual(Piece.GetLocation().Z, Portal.OpeningHeightCm + Portal.HeaderDepthCm * 0.5, 0.1);
    }
    TestEqual(TEXT("Two posts"), Posts, 2);
    TestTrue(TEXT("Posts stand either side of the opening, on the portal line"), bPostsFrame);
    TestTrue(TEXT("A header spans the opening at its height"), bHeaderOverOpening);

    bool bForestageInFront = Forestage->GetInstanceCount() > 0;
    for (const FTransform& Board : ReadInstances(*Forestage))
    {
        const double HalfLengthCm = Board.GetScale3D().X * 50.0;
        bForestageInFront &= FMath::IsNearlyEqual(Board.GetLocation().X + HalfLengthCm, PortalX, 0.1)
            && FMath::IsNearlyEqual(HalfLengthCm * 2.0, Portal.ForestageDepthCm, 0.1)
            && FMath::IsNearlyEqual(Board.GetLocation().Z + Board.GetScale3D().Z * 50.0, Structure->Ground.FloorHeightCm, 0.01);
    }
    TestTrue(TEXT("The forestage runs from the portal line toward the audience, flush with the floor"), bForestageInFront);
    TestEqual(TEXT("One hemp line per setting"), Lines->GetInstanceCount(), Portal.HangingLines);
    TestEqual(TEXT("Portal pieces are counted"), Structure->PortalPieceCount,
        Timber->GetInstanceCount() + Forestage->GetInstanceCount() + Lines->GetInstanceCount());
    TestTrue(TEXT("A structure with a portal is current"), Structure->IsStructureCurrent());

    const FTransform FirstPiece = ReadInstances(*Timber)[0];
    TestTrue(TEXT("Rebuild succeeds"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Rebuilt = FindLayer(*Structure, TEXT("InfinityStage.Structure.Portal"));
    TestTrue(TEXT("Rebuilding places the same portal"),
        Rebuilt && Rebuilt->GetInstanceCount() > 0 && ReadInstances(*Rebuilt)[0].Equals(FirstPiece, 1.0e-4));

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructureStageFrontTest,
    "InfinityStage.Structure.StageFrontCatchesTheOverspill",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructureStageFrontTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;
    Structure->Ground.ApronCm = 0.0;
    Structure->Portal.bEnabled = true;
    TestTrue(TEXT("The stage front is on by default with the portal"), Structure->Portal.bStageFront);
    TestTrue(TEXT("Structure with a stage front materializes"), Structure->MaterializeStructure());

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    UInstancedStaticMeshComponent* Front = nullptr;
    UInstancedStaticMeshComponent* Forestage = nullptr;
    int32 PortalInstances = 0;
    for (UInstancedStaticMeshComponent* Component : Structure->ManagedComponents)
    {
        if (!Component || !Component->ComponentTags.Contains(FName(TEXT("InfinityStage.Structure.Portal"))))
        {
            continue;
        }
        PortalInstances += Component->GetInstanceCount();
        const FString Name = Component->GetName();
        if (Name.StartsWith(TEXT("StructureStageFront"))) { Front = Component; }
        else if (Name.StartsWith(TEXT("StructureForestage"))) { Forestage = Component; }
    }
    if (!Front || !Forestage || Stations.IsEmpty())
    {
        AddError(TEXT("Expected stage-front and forestage boards over gathered stations."));
        World->DestroyWorld(false);
        return false;
    }
    TestEqual(TEXT("Stage-front boards are counted as portal pieces"), Structure->PortalPieceCount, PortalInstances);

    const FInfinityStagePortalSettings& Portal = Structure->Portal;
    const double ThickCm = Structure->Ground.BoardThicknessCm;
    const double FloorCm = Structure->Ground.FloorHeightCm;
    const double MouthEndX = Stations[0].StationWorld.GetLocation().X;
    const double LipX = MouthEndX + Portal.OffsetFromFirstStationCm - Portal.ForestageDepthCm;
    const double HouseZ = FloorCm - Portal.HouseFloorDepthCm;
    const auto Boxes = [](const UInstancedStaticMeshComponent& Component)
    {
        TArray<FBox> Out;
        const FBox MeshBounds = Component.GetStaticMesh()->GetBoundingBox();
        for (const FTransform& Instance : ReadInstances(Component))
        {
            Out.Add(MeshBounds.TransformBy(Instance));
        }
        return Out;
    };
    const TArray<FBox> FrontBoxes = Boxes(*Front);
    const TArray<FBox> ForestageBoxes = Boxes(*Forestage);

    FBox Fascia(ForceInit);
    FBox HouseFloor(ForceInit);
    FBox StageLevel(ForceInit);
    FBox MouthReturn(ForceInit);
    bool bNothingAboveTheStage = true;
    for (const FBox& Board : FrontBoxes)
    {
        bNothingAboveTheStage &= Board.Max.Z <= FloorCm + 0.01;
        if (Board.Max.X <= LipX + 0.1 && Board.Min.X >= LipX - ThickCm - 0.1)
        {
            Fascia += Board;
        }
        if (FMath::IsNearlyEqual(Board.Max.Z, HouseZ, 0.1))
        {
            HouseFloor += Board;
        }
        if (FMath::IsNearlyEqual(Board.Max.Z, FloorCm, 0.1) && Board.Min.Z >= FloorCm - ThickCm - 0.1)
        {
            StageLevel += Board;
        }
        if (Board.Min.Y >= Portal.MouthHalfWidthCm - 0.1 && Board.Max.Y <= Portal.MouthHalfWidthCm + ThickCm + 0.1
            && Board.Max.Z <= FloorCm + 0.1 && Board.Min.Z < FloorCm - ThickCm - 1.0)
        {
            MouthReturn += Board;
        }
    }
    for (const FBox& Board : ForestageBoxes)
    {
        StageLevel += Board;
    }
    TestTrue(TEXT("No stage-front board rises above the stage"), bNothingAboveTheStage);
    TestTrue(TEXT("The fascia stands at the lip, from the stage down to the house floor, the mouth's width"),
        Fascia.IsValid
        && FMath::IsNearlyEqual(Fascia.Max.Z, FloorCm, 0.1) && FMath::IsNearlyEqual(Fascia.Min.Z, HouseZ, 0.1)
        && FMath::IsNearlyEqual(Fascia.Max.Y, Portal.MouthHalfWidthCm + ThickCm, 0.1)
        && FMath::IsNearlyEqual(Fascia.Min.Y, -Portal.MouthHalfWidthCm - ThickCm, 0.1));
    TestTrue(TEXT("The stage-level floor reaches the mouth's width exactly"),
        StageLevel.IsValid && FMath::IsNearlyEqual(StageLevel.Max.Y, Portal.MouthHalfWidthCm, 0.1)
        && FMath::IsNearlyEqual(StageLevel.Min.Y, -Portal.MouthHalfWidthCm, 0.1)
        && FMath::IsNearlyEqual(StageLevel.Min.X, LipX, 0.1));
    TestTrue(TEXT("The house floor runs its set distance toward the audience, its set width"),
        HouseFloor.IsValid
        && FMath::IsNearlyEqual(HouseFloor.Min.X, LipX - Portal.HouseFloorDownstageCm, 0.5)
        && FMath::IsNearlyEqual(HouseFloor.Max.Y, Portal.HouseFloorHalfWidthCm, 0.1)
        && FMath::IsNearlyEqual(HouseFloor.Min.Y, -Portal.HouseFloorHalfWidthCm, 0.1));
    TestTrue(TEXT("The house floor wraps the sides past the first station"),
        HouseFloor.IsValid && FMath::IsNearlyEqual(HouseFloor.Max.X, MouthEndX + Portal.SideRunUpstageCm, 0.5));
    TestTrue(TEXT("The mouth's side is a face from the lip to the first station, down to the house floor"),
        MouthReturn.IsValid && FMath::IsNearlyEqual(MouthReturn.Min.X, LipX, 0.5)
        && FMath::IsNearlyEqual(MouthReturn.Max.X, MouthEndX, 0.5) && FMath::IsNearlyEqual(MouthReturn.Min.Z, HouseZ, 0.1));
    TestTrue(TEXT("A structure with a stage front is current"), Structure->IsStructureCurrent());

    const FTransform FirstBoard = ReadInstances(*Front)[0];
    TestTrue(TEXT("Rebuild succeeds"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Rebuilt = nullptr;
    for (UInstancedStaticMeshComponent* Component : Structure->ManagedComponents)
    {
        if (Component && Component->GetName().StartsWith(TEXT("StructureStageFront")))
        {
            Rebuilt = Component;
        }
    }
    TestTrue(TEXT("Rebuilding lays the same stage front"),
        Rebuilt && Rebuilt->GetInstanceCount() == FrontBoxes.Num() && ReadInstances(*Rebuilt)[0].Equals(FirstBoard, 1.0e-4));

    World->DestroyWorld(false);
    return true;
}

namespace
{
/** The portal's timber component: posts, header, trough, nosing, carried-forward grid. */
UInstancedStaticMeshComponent* FindPortalTimber(const AInfinityStageStructureActor& Structure)
{
    for (UInstancedStaticMeshComponent* Component : Structure.ManagedComponents)
    {
        if (Component && Component->ComponentTags.Contains(FName(TEXT("InfinityStage.Structure.Portal")))
            && Component->GetName().StartsWith(TEXT("StructurePortal"))
            && !Component->GetName().StartsWith(TEXT("StructurePortalLines")))
        {
            return Component;
        }
    }
    return nullptr;
}

/** One built component: its layer tags, mesh, slot-0 material, instances and custom data. */
struct FBuiltLayer
{
    TArray<FName> Tags;
    const UStaticMesh* Mesh = nullptr;
    const UMaterialInterface* Material = nullptr;
    TArray<FTransform> Transforms;
    TArray<float> CustomData;
};

FBuiltLayer SnapshotLayer(const UInstancedStaticMeshComponent& Component)
{
    FBuiltLayer Layer;
    Layer.Tags = Component.ComponentTags;
    Layer.Mesh = Component.GetStaticMesh();
    Layer.Material = Component.GetMaterial(0);
    Layer.Transforms = ReadInstances(Component);
    Layer.CustomData = Component.PerInstanceSMCustomData;
    return Layer;
}

TArray<FBuiltLayer> SnapshotBuild(const AInfinityStageStructureActor& Structure)
{
    TArray<FBuiltLayer> Layers;
    for (const UInstancedStaticMeshComponent* Component : Structure.ManagedComponents)
    {
        if (Component)
        {
            Layers.Add(SnapshotLayer(*Component));
        }
    }
    return Layers;
}

bool SameLayer(const FBuiltLayer& A, const FBuiltLayer& B, FString& OutWhy)
{
    if (A.Tags != B.Tags) { OutWhy = TEXT("tags differ"); return false; }
    if (A.Mesh != B.Mesh) { OutWhy = TEXT("mesh differs"); return false; }
    if (A.Material != B.Material) { OutWhy = TEXT("material differs"); return false; }
    if (A.CustomData != B.CustomData) { OutWhy = TEXT("custom data (sizes) differ"); return false; }
    if (A.Transforms.Num() != B.Transforms.Num()) { OutWhy = TEXT("instance counts differ"); return false; }
    for (int32 Index = 0; Index < A.Transforms.Num(); ++Index)
    {
        if (!A.Transforms[Index].Equals(B.Transforms[Index], 1.0e-4))
        {
            OutWhy = FString::Printf(TEXT("instance %d moved"), Index);
            return false;
        }
    }
    return true;
}

bool SameBuild(const TArray<FBuiltLayer>& A, const TArray<FBuiltLayer>& B, FString& OutWhy)
{
    if (A.Num() != B.Num())
    {
        OutWhy = FString::Printf(TEXT("%d components != %d"), A.Num(), B.Num());
        return false;
    }
    for (int32 Index = 0; Index < A.Num(); ++Index)
    {
        FString Why;
        if (!SameLayer(A[Index], B[Index], Why))
        {
            OutWhy = FString::Printf(TEXT("component %d: %s"), Index, *Why);
            return false;
        }
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructurePortalNullTimberTest,
    "InfinityStage.Structure.PortalTimberNullFollowsTheGridiron",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructurePortalNullTimberTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UMaterialInterface> Painted(
        FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial")));
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    if (!Painted.LoadSynchronous() || !Cube.LoadSynchronous())
    {
        AddError(TEXT("Fixture: VertexColorMaterial or the engine cube does not load."));
        return false;
    }
    // Otherwise "the portal wears the gridiron's material" could pass on the mesh's own.
    TestTrue(TEXT("Fixture: the gridiron material is not the cube's own"),
        Cube.LoadSynchronous()->GetMaterial(0) != Painted.LoadSynchronous());

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    TestTrue(TEXT("A new portal has no timber of its own"),
        Structure->Portal.PortalMesh.IsNull() && Structure->Portal.PortalMaterial.IsNull());

    // Ground and stage front on, and a nosing, so every portal component and
    // every kind of portal timber is built.
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;
    Structure->Portal.NosingDepthCm = 10.0;
    Structure->Gridiron.BeamMesh = Cube;
    Structure->Gridiron.Material = Painted;
    TestTrue(TEXT("Builds with null portal timber"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> FromNull = SnapshotBuild(*Structure);
    UInstancedStaticMeshComponent* Grid = FindLayer(*Structure, TEXT("InfinityStage.Structure.Gridiron"));
    UInstancedStaticMeshComponent* Timber = FindPortalTimber(*Structure);
    if (!Grid || !Timber)
    {
        AddError(TEXT("Expected a gridiron and a portal timber component."));
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("Null portal timber is the gridiron's beam mesh"),
        Timber->GetStaticMesh() == Grid->GetStaticMesh() && Timber->GetStaticMesh() == Cube.LoadSynchronous());
    TestTrue(TEXT("Null portal material is the gridiron's material"),
        Timber->GetMaterial(0) == Painted.LoadSynchronous() && Grid->GetMaterial(0) == Painted.LoadSynchronous());
    TestTrue(TEXT("A structure with null portal timber is current"), Structure->IsStructureCurrent());

    // Pinned explicitly to the gridiron's own values, the building is identical:
    // null means exactly what the portal did before it had slots.
    Structure->Portal.PortalMesh = Structure->Gridiron.BeamMesh;
    Structure->Portal.PortalMaterial = Structure->Gridiron.Material;
    TestTrue(TEXT("Builds with portal timber pinned to the gridiron's"), Structure->MaterializeStructure());
    FString Why;
    const bool bSame = SameBuild(FromNull, SnapshotBuild(*Structure), Why);
    TestTrue(FString::Printf(TEXT("Null slots build what the gridiron's own values build (%s)"), *Why), bSame);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageStructurePortalKeepsTimberTest,
    "InfinityStage.Structure.PortalKeepsItsOwnTimber",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageStructurePortalKeepsTimberTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Sphere(FSoftObjectPath(TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    const TSoftObjectPtr<UMaterialInterface> Wood(
        FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial")));
    const TSoftObjectPtr<UMaterialInterface> Iron(
        FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/M_SimpleOpaque.M_SimpleOpaque")));
    if (!Cube.LoadSynchronous() || !Sphere.LoadSynchronous() || !Wood.LoadSynchronous() || !Iron.LoadSynchronous())
    {
        AddError(TEXT("Fixture: an engine mesh or material does not load."));
        return false;
    }
    // Every comparison below must be able to fail: two distinct meshes, two
    // distinct materials, neither material a mesh's own.
    TestTrue(TEXT("Fixture: distinct meshes and materials"),
        Cube.LoadSynchronous() != Sphere.LoadSynchronous() && Wood.LoadSynchronous() != Iron.LoadSynchronous());
    for (const UStaticMesh* Mesh : { Cube.LoadSynchronous(), Sphere.LoadSynchronous() })
    {
        TestTrue(TEXT("Fixture: neither material is a mesh's own"),
            Mesh->GetMaterial(0) != Wood.LoadSynchronous() && Mesh->GetMaterial(0) != Iron.LoadSynchronous());
    }

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 3);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;
    Structure->Portal.NosingDepthCm = 10.0;
    Structure->Gridiron.BeamMesh = Cube;
    Structure->Gridiron.Material = Wood;
    TestTrue(TEXT("The timber building materializes"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Timber = FindPortalTimber(*Structure);
    if (!Timber)
    {
        AddError(TEXT("Expected a portal timber component."));
        World->DestroyWorld(false);
        return false;
    }
    const FBuiltLayer WoodPortal = SnapshotLayer(*Timber);

    // Control: nothing pinned, so the portal turns with the gridiron. Without
    // this the assertions below could pass on a portal that never changes.
    Structure->Gridiron.BeamMesh = Sphere;
    Structure->Gridiron.Material = Iron;
    TestTrue(TEXT("The iron building materializes"), Structure->MaterializeStructure());
    Timber = FindPortalTimber(*Structure);
    TestTrue(TEXT("Control: an unpinned portal follows the gridiron's mesh and material"),
        Timber && Timber->GetStaticMesh() == Sphere.LoadSynchronous() && Timber->GetMaterial(0) == Iron.LoadSynchronous());

    // Pinned: the gridiron stays iron, the portal goes back to its timber, in
    // the same places with the same sections.
    Structure->Portal.PortalMesh = Cube;
    Structure->Portal.PortalMaterial = Wood;
    TestTrue(TEXT("The pinned building materializes"), Structure->MaterializeStructure());
    UInstancedStaticMeshComponent* Grid = FindLayer(*Structure, TEXT("InfinityStage.Structure.Gridiron"));
    Timber = FindPortalTimber(*Structure);
    if (!Grid || !Timber)
    {
        AddError(TEXT("Expected a gridiron and a portal timber component after pinning."));
        World->DestroyWorld(false);
        return false;
    }
    TestTrue(TEXT("The gridiron is iron"),
        Grid->GetStaticMesh() == Sphere.LoadSynchronous() && Grid->GetMaterial(0) == Iron.LoadSynchronous());
    TestTrue(TEXT("The pinned portal keeps its own mesh and material"),
        Timber->GetStaticMesh() == Cube.LoadSynchronous() && Timber->GetMaterial(0) == Wood.LoadSynchronous());
    FString Why;
    const bool bSame = SameLayer(WoodPortal, SnapshotLayer(*Timber), Why);
    TestTrue(FString::Printf(TEXT("The pinned portal is the timber portal it was, piece for piece (%s)"), *Why), bSame);
    TestTrue(TEXT("A pinned structure is current"), Structure->IsStructureCurrent());

    // The slots are independent: a pinned mesh with a null material wears the gridiron's.
    Structure->Portal.PortalMaterial = nullptr;
    TestTrue(TEXT("Builds with only the mesh pinned"), Structure->MaterializeStructure());
    Timber = FindPortalTimber(*Structure);
    TestTrue(TEXT("Only the mesh pinned: own mesh, the gridiron's material"),
        Timber && Timber->GetStaticMesh() == Cube.LoadSynchronous() && Timber->GetMaterial(0) == Iron.LoadSynchronous());

    World->DestroyWorld(false);
    return true;
}

namespace
{
/** The underpass layers, in the order of the parts below: columns, piers, knees, deck, catwalk. */
const TCHAR* const UnderpassTags[] = {
    TEXT("InfinityStage.Structure.Underpass.Columns"),
    TEXT("InfinityStage.Structure.Underpass.Piers"),
    TEXT("InfinityStage.Structure.Underpass.Knees"),
    TEXT("InfinityStage.Structure.Underpass.Deck"),
    TEXT("InfinityStage.Structure.Underpass.Catwalk"),
};
constexpr int32 UnderpassPartCount = 5;
static_assert(sizeof(UnderpassTags) / sizeof(UnderpassTags[0]) == UnderpassPartCount, "one tag per underpass part");

/** Every underpass part on the engine cube (100 cm, centred), catwalk included, and switched on. */
void ArmUnderpass(AInfinityStageStructureActor& Structure)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    FInfinityStageUnderpassSettings& Underpass = Structure.Underpass;
    Underpass.ColumnMesh = Cube;
    Underpass.PierMesh = Cube;
    Underpass.KneeMesh = Cube;
    Underpass.DeckMesh = Cube;
    Underpass.CatwalkMesh = Cube;
    Underpass.bCatwalk = true;
    Underpass.bEnabled = true;
}

TArray<FBuiltLayer> WithoutUnderpass(const TArray<FBuiltLayer>& Layers)
{
    TArray<FBuiltLayer> Kept;
    for (const FBuiltLayer& Layer : Layers)
    {
        bool bUnderpass = false;
        for (const TCHAR* Tag : UnderpassTags)
        {
            bUnderpass |= Layer.Tags.Contains(FName(Tag));
        }
        if (!bUnderpass)
        {
            Kept.Add(Layer);
        }
    }
    return Kept;
}

/** Every count the structure reported before the underpass existed. */
TArray<int32> ExistingCounts(const AInfinityStageStructureActor& Structure)
{
    return {
        Structure.StationCount, Structure.CrossBeamCount, Structure.RailSegmentCount, Structure.BoardCount,
        Structure.SlotCount, Structure.GroovePieceCount, Structure.ClothCount, Structure.PortalPieceCount,
        Structure.FixtureBodyCount, Structure.HangingLineCount, Structure.MovingLightsWithoutHousing,
        Structure.StationSignature, static_cast<int32>(FMath::RoundToInt64(Structure.GridHalfWidthCm * 10.0)) };
}

TArray<int32> UnderpassCounts(const AInfinityStageStructureActor& Structure)
{
    return {
        Structure.UnderpassColumnCount, Structure.UnderpassPierCount, Structure.UnderpassKneeCount,
        Structure.UnderpassDeckCount, Structure.UnderpassCatwalkCount };
}

/** Column stations: every Nth from the first, and the last. Closed form, independent of the build's loop. */
int32 ExpectedColumnStations(const int32 Stations, const int32 Every)
{
    return (Stations + Every - 1) / Every + ((Stations - 1) % Every != 0 ? 1 : 0);
}

TArray<FBox> InstanceBoxes(const UInstancedStaticMeshComponent& Component)
{
    TArray<FBox> Boxes;
    const FBox MeshBounds = Component.GetStaticMesh()->GetBoundingBox();
    for (const FTransform& Instance : ReadInstances(Component))
    {
        Boxes.Add(MeshBounds.TransformBy(Instance));
    }
    return Boxes;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassOffByDefaultTest,
    "InfinityStage.Structure.UnderpassOffByDefaultChangesNothing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassOffByDefaultTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    // Floor, grooves, understage, portal and stage front too, so every existing layer is compared.
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;

    const FInfinityStageUnderpassSettings& Defaults = Structure->Underpass;
    TestFalse(TEXT("The underpass is off by default"), Defaults.bEnabled);
    TestTrue(TEXT("No underpass part has a mesh by default"),
        Defaults.ColumnMesh.IsNull() && Defaults.PierMesh.IsNull() && Defaults.KneeMesh.IsNull()
        && Defaults.DeckMesh.IsNull() && Defaults.CatwalkMesh.IsNull());
    TestEqual(TEXT("A column pair every second station by default"), Defaults.ColumnEvery, 2);
    TestTrue(TEXT("Columns 60 cm outside the grid and the deck at 2000 cm by default"),
        FMath::IsNearlyEqual(Defaults.ColumnOutsetCm, 60.0) && FMath::IsNearlyEqual(Defaults.DeckHeightCm, 2000.0));

    TestTrue(TEXT("The default structure builds"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Baseline = SnapshotBuild(*Structure);
    const TArray<int32> BaselineCounts = ExistingCounts(*Structure);

    // The whole kit set, but the layer off: nothing may change.
    ArmUnderpass(*Structure);
    Structure->Underpass.bEnabled = false;
    TestTrue(TEXT("Builds with the kit set but the layer off"), Structure->MaterializeStructure());
    FString Why;
    const bool bSameOff = SameBuild(Baseline, SnapshotBuild(*Structure), Why);
    TestTrue(FString::Printf(TEXT("Off, every component, mesh, material, instance and custom float is unchanged (%s)"), *Why), bSameOff);
    TestTrue(TEXT("Off, every existing count is unchanged"), ExistingCounts(*Structure) == BaselineCounts);
    TestTrue(TEXT("Off, every underpass count is zero"), UnderpassCounts(*Structure) == TArray<int32>({ 0, 0, 0, 0, 0 }));

    // Control: on, the same kit adds its five layers, so the comparison above can
    // fail. Even on, it leaves every other layer exactly as it was.
    Structure->Underpass.bEnabled = true;
    TestTrue(TEXT("Builds with the layer on"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> WithUnderpass = SnapshotBuild(*Structure);
    TestEqual(TEXT("Control: on, the underpass adds one component per part"), WithUnderpass.Num(), Baseline.Num() + 5);
    const bool bSameOthers = SameBuild(Baseline, WithoutUnderpass(WithUnderpass), Why);
    TestTrue(FString::Printf(TEXT("On, every other layer is unchanged (%s)"), *Why), bSameOthers);
    TestTrue(TEXT("On, every existing count is unchanged"), ExistingCounts(*Structure) == BaselineCounts);
    TestTrue(TEXT("A structure with an underpass is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassCountsTest,
    "InfinityStage.Structure.UnderpassCountsFollowTheStations",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassCountsTest::RunTest(const FString& Parameters)
{
    struct FCase
    {
        int32 Stations;
        int32 Every;
    };
    // 5/2 ends on a column station; 4/2 and 6/3 add the last; 5/1 stands one everywhere.
    for (const FCase Case : { FCase{ 5, 2 }, FCase{ 4, 2 }, FCase{ 6, 3 }, FCase{ 5, 1 } })
    {
        const FString Label = FString::Printf(TEXT("%d stations, columns every %d"), Case.Stations, Case.Every);
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, Case.Stations);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmUnderpass(*Structure);
        Structure->Underpass.ColumnEvery = Case.Every;
        if (Case.Stations == 5 && Case.Every == 2)
        {
            // The census the conductor's tools parse: the new keys, appended.
            AddExpectedMessagePlain(
                TEXT("half_width_cm=620 underpass_columns=6 underpass_piers=6 underpass_knees=8 underpass_decks=4 underpass_catwalks=8"),
                ELogVerbosity::Display,
                EAutomationExpectedMessageFlags::Contains,
                1);
        }
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        TestEqual(*(Label + TEXT(": stations")), Structure->StationCount, Case.Stations);

        const int32 ColumnStations = ExpectedColumnStations(Case.Stations, Case.Every);
        TestEqual(*(Label + TEXT(": two columns per column station")), Structure->UnderpassColumnCount, 2 * ColumnStations);
        TestEqual(*(Label + TEXT(": a pier under every column")), Structure->UnderpassPierCount, 2 * ColumnStations);
        TestEqual(*(Label + TEXT(": two knees per column, one at each end column")),
            Structure->UnderpassKneeCount, 2 * (2 * ColumnStations - 2));
        TestEqual(*(Label + TEXT(": a deck bay per station gap")), Structure->UnderpassDeckCount, Case.Stations - 1);
        TestEqual(*(Label + TEXT(": two catwalk rails per bay")), Structure->UnderpassCatwalkCount, 2 * (Case.Stations - 1));
        if (Case.Stations == 5 && Case.Every == 2)
        {
            // Pins the formula itself: stations 0, 2 and 4.
            TestTrue(Label + TEXT(": the counts are 6, 6, 8, 4, 8"),
                UnderpassCounts(*Structure) == TArray<int32>({ 6, 6, 8, 4, 8 }));
        }
        const TArray<int32> Reported = UnderpassCounts(*Structure);
        for (int32 Part = 0; Part < UnderpassPartCount; ++Part)
        {
            const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, UnderpassTags[Part]);
            TestEqual(*(Label + TEXT(": the count is the layer's instances, ") + UnderpassTags[Part]),
                Layer ? Layer->GetInstanceCount() : 0, Reported[Part]);
        }
        TestTrue(Label + TEXT(": a structure with an underpass is current"), Structure->IsStructureCurrent());

        // Where the plan puts it: piers on the floor, columns from the pier top to
        // the deck's underside on the column line, knees under the deck.
        const FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
        const double FloorCm = Structure->Ground.FloorHeightCm;
        const double ColumnLineCm = Structure->GridHalfWidthCm + Underpass.ColumnOutsetCm;
        const UInstancedStaticMeshComponent* Columns = FindLayer(*Structure, UnderpassTags[0]);
        const UInstancedStaticMeshComponent* Piers = FindLayer(*Structure, UnderpassTags[1]);
        const UInstancedStaticMeshComponent* Knees = FindLayer(*Structure, UnderpassTags[2]);
        const UInstancedStaticMeshComponent* Decks = FindLayer(*Structure, UnderpassTags[3]);
        if (!Columns || !Piers || !Knees || !Decks)
        {
            AddError(Label + TEXT(": expected column, pier, knee and deck layers."));
            World->DestroyWorld(false);
            return false;
        }
        bool bColumnsPlaced = true;
        for (const FBox& Box : InstanceBoxes(*Columns))
        {
            bColumnsPlaced &= FMath::IsNearlyEqual(Box.Min.Z, FloorCm + Underpass.PierHeightCm, 0.1)
                && FMath::IsNearlyEqual(Box.Max.Z, Underpass.DeckHeightCm, 0.1)
                && FMath::IsNearlyEqual(FMath::Abs(Box.GetCenter().Y), ColumnLineCm, 0.1)
                && FMath::IsNearlyEqual(Box.GetSize().Y, Underpass.ColumnWidthCm, 0.1)
                && FMath::IsNearlyEqual(Box.GetSize().X, Underpass.ColumnDepthCm, 0.1);
        }
        TestTrue(Label + TEXT(": columns stand on the piers, up to the deck, on the column line"), bColumnsPlaced);
        bool bPiersPlaced = true;
        for (const FBox& Box : InstanceBoxes(*Piers))
        {
            bPiersPlaced &= FMath::IsNearlyEqual(Box.Min.Z, FloorCm, 0.1)
                && FMath::IsNearlyEqual(Box.Max.Z, FloorCm + Underpass.PierHeightCm, 0.1)
                && FMath::IsNearlyEqual(FMath::Abs(Box.GetCenter().Y), ColumnLineCm, 0.1);
        }
        TestTrue(Label + TEXT(": piers stand on the floor under the columns"), bPiersPlaced);
        bool bKneesPlaced = true;
        for (const FBox& Box : InstanceBoxes(*Knees))
        {
            bKneesPlaced &= FMath::IsNearlyEqual(Box.Max.Z, Underpass.DeckHeightCm, 0.1)
                && FMath::IsNearlyEqual(Box.GetSize().X, Underpass.KneeSizeCm, 0.1);
        }
        TestTrue(Label + TEXT(": knees sit under the deck"), bKneesPlaced);
        bool bDeckPlaced = true;
        for (const FBox& Box : InstanceBoxes(*Decks))
        {
            bDeckPlaced &= FMath::IsNearlyEqual(Box.Min.Z, Underpass.DeckHeightCm, 0.1)
                && FMath::IsNearlyEqual(Box.GetSize().Y, (ColumnLineCm + Underpass.ColumnWidthCm * 0.5) * 2.0, 0.1);
        }
        TestTrue(Label + TEXT(": the deck rests on the column heads and spans them"), bDeckPlaced);

        World->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassCleanEndsTest,
    "InfinityStage.Structure.UnderpassKeepsThePassageEndsClean",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassCleanEndsTest::RunTest(const FString& Parameters)
{
    // 5 stations end on a column station by the rhythm; 4 get one added at the end.
    for (const int32 StationTotal : { 5, 4 })
    {
        const FString Label = FString::Printf(TEXT("%d stations"), StationTotal);
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, StationTotal);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmUnderpass(*Structure);
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        TArray<FInfinityStructureStation> Stations;
        FString Error;
        Structure->GatherStations(Stations, Error);
        if (Stations.Num() != StationTotal)
        {
            AddError(Label + TEXT(": stations did not gather."));
            World->DestroyWorld(false);
            return false;
        }
        // The fixture's route runs along world +X.
        const double FirstX = Stations[0].StationWorld.GetLocation().X;
        const double LastX = Stations.Last().StationWorld.GetLocation().X;
        double MinX = TNumericLimits<double>::Max();
        double MaxX = TNumericLimits<double>::Lowest();
        int32 Pieces = 0;
        for (const TCHAR* Tag : UnderpassTags)
        {
            const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, Tag);
            if (!Layer)
            {
                AddError(Label + TEXT(": missing underpass layer ") + Tag);
                continue;
            }
            bool bInside = true;
            for (const FBox& Box : InstanceBoxes(*Layer))
            {
                bInside &= Box.Min.X >= FirstX - 0.5 && Box.Max.X <= LastX + 0.5;
                MinX = FMath::Min(MinX, Box.Min.X);
                MaxX = FMath::Max(MaxX, Box.Max.X);
                ++Pieces;
            }
            TestTrue(Label + TEXT(": nothing passes the first or last station, ") + Tag, bInside);
        }
        // Controls, so the bound above measures a real edge: the rig reaches both
        // ends exactly, and a column foot stands at the last station.
        TestTrue(Label + TEXT(": the underpass was built"), Pieces > 0);
        TestTrue(Label + TEXT(": the rig reaches the last station"), FMath::IsNearlyEqual(MaxX, LastX, 0.5));
        TestTrue(Label + TEXT(": the rig reaches the first station"), FMath::IsNearlyEqual(MinX, FirstX, 0.5));
        bool bEndColumn = false;
        if (const UInstancedStaticMeshComponent* Piers = FindLayer(*Structure, UnderpassTags[1]))
        {
            for (const FBox& Box : InstanceBoxes(*Piers))
            {
                bEndColumn |= FMath::IsNearlyEqual(Box.Max.X, LastX, 0.1);
            }
        }
        TestTrue(Label + TEXT(": a pier's face is flush with the last station"), bEndColumn);

        World->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassMaterialsTest,
    "InfinityStage.Structure.UnderpassPartsWearTheirOwnMaterials",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassMaterialsTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    // Five distinct surface materials, none the cube's own (WorldGridMaterial here).
    const TSoftObjectPtr<UMaterialInterface> Paints[] = {
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/M_SimpleOpaque.M_SimpleOpaque"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/DebugMeshMaterial.DebugMeshMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/TangentColorMaterial.TangentColorMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/LevelColorationLitMaterial.LevelColorationLitMaterial"))),
    };
    if (!Cube.LoadSynchronous())
    {
        AddError(TEXT("Fixture: the engine cube does not load."));
        return false;
    }
    for (int32 Index = 0; Index < UnderpassPartCount; ++Index)
    {
        if (!Paints[Index].LoadSynchronous())
        {
            AddError(FString::Printf(TEXT("Fixture: material %s does not load."), *Paints[Index].ToSoftObjectPath().ToString()));
            return false;
        }
        TestTrue(TEXT("Fixture: no test material is the cube's own"),
            Cube.LoadSynchronous()->GetMaterial(0) != Paints[Index].LoadSynchronous());
        for (int32 Other = Index + 1; Other < UnderpassPartCount; ++Other)
        {
            TestTrue(TEXT("Fixture: the test materials are distinct"),
                Paints[Index].LoadSynchronous() != Paints[Other].LoadSynchronous());
        }
    }

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmUnderpass(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    // Plan section 5: only the deck casts by default.
    TestTrue(TEXT("Only the deck casts shadow by default"),
        Underpass.bDeckCastShadow && !Underpass.bColumnCastShadow && !Underpass.bPierCastShadow
        && !Underpass.bKneeCastShadow && !Underpass.bCatwalkCastShadow);
    Underpass.ColumnMaterial = Paints[0];
    Underpass.PierMaterial = Paints[1];
    Underpass.KneeMaterial = Paints[2];
    Underpass.DeckMaterial = Paints[3];
    Underpass.CatwalkMaterial = Paints[4];
    // Flipped from the defaults, so each flag is shown to come from its own setting.
    const bool Shadows[] = { true, true, false, false, true };
    Underpass.bColumnCastShadow = Shadows[0];
    Underpass.bPierCastShadow = Shadows[1];
    Underpass.bKneeCastShadow = Shadows[2];
    Underpass.bDeckCastShadow = Shadows[3];
    Underpass.bCatwalkCastShadow = Shadows[4];
    TestTrue(TEXT("The painted underpass builds"), Structure->MaterializeStructure());

    for (int32 Part = 0; Part < UnderpassPartCount; ++Part)
    {
        const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, UnderpassTags[Part]);
        if (!Layer)
        {
            AddError(FString::Printf(TEXT("Missing underpass layer %s."), UnderpassTags[Part]));
            continue;
        }
        TestTrue(FString::Printf(TEXT("%s wears its own material"), UnderpassTags[Part]),
            Layer->GetMaterial(0) == Paints[Part].LoadSynchronous());
        TestTrue(FString::Printf(TEXT("%s casts shadow per its own flag"), UnderpassTags[Part]),
            static_cast<bool>(Layer->CastShadow) == Shadows[Part]);
        TestTrue(FString::Printf(TEXT("%s is built from its own mesh"), UnderpassTags[Part]),
            Layer->GetStaticMesh() == Cube.LoadSynchronous());
    }

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassNullMeshTest,
    "InfinityStage.Structure.UnderpassNullMeshSkipsOnlyThatPart",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassNullMeshTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmUnderpass(*Structure);
    TestTrue(TEXT("The full underpass builds"), Structure->MaterializeStructure());
    TArray<FBuiltLayer> Full;
    for (const TCHAR* Tag : UnderpassTags)
    {
        const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, Tag);
        if (!Layer || Layer->GetInstanceCount() == 0)
        {
            // Control: every part must be there to be missed.
            AddError(FString::Printf(TEXT("Control: the full build has no %s."), Tag));
            World->DestroyWorld(false);
            return false;
        }
        Full.Add(SnapshotLayer(*Layer));
    }
    const TArray<FBuiltLayer> FullOthers = WithoutUnderpass(SnapshotBuild(*Structure));

    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    TSoftObjectPtr<UStaticMesh>* const Slots[] = {
        &Underpass.ColumnMesh, &Underpass.PierMesh, &Underpass.KneeMesh, &Underpass.DeckMesh, &Underpass.CatwalkMesh };
    for (int32 Skipped = 0; Skipped < UnderpassPartCount; ++Skipped)
    {
        ArmUnderpass(*Structure);
        *Slots[Skipped] = nullptr;
        const FString Label = FString::Printf(TEXT("No mesh for %s"), UnderpassTags[Skipped]);
        // A null part is skipped quietly: any error logged here fails the test.
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        TestNull(*(Label + TEXT(": that part has no layer")), FindLayer(*Structure, UnderpassTags[Skipped]));
        TestEqual(*(Label + TEXT(": that part counts zero")), UnderpassCounts(*Structure)[Skipped], 0);
        for (int32 Kept = 0; Kept < UnderpassPartCount; ++Kept)
        {
            if (Kept == Skipped)
            {
                continue;
            }
            const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, UnderpassTags[Kept]);
            FString Why = TEXT("layer missing");
            const bool bSame = Layer && SameLayer(Full[Kept], SnapshotLayer(*Layer), Why);
            TestTrue(FString::Printf(TEXT("%s: %s is unchanged (%s)"), *Label, UnderpassTags[Kept], *Why), bSame);
        }
        FString Why;
        const bool bSameOthers = SameBuild(FullOthers, WithoutUnderpass(SnapshotBuild(*Structure)), Why);
        TestTrue(FString::Printf(TEXT("%s: every other layer is unchanged (%s)"), *Label, *Why), bSameOthers);
        TestTrue(Label + TEXT(": the structure is current"), Structure->IsStructureCurrent());
    }

    World->DestroyWorld(false);
    return true;
}

namespace
{
const TCHAR* const TubeTag = TEXT("InfinityStage.Structure.Underpass.Tubes");
const TCHAR* const TubeLightTag = TEXT("InfinityStage.Structure.Underpass.TubeLights");

/** The underpass armed as above, and its tubes on the engine cube. Lights stay as the caller sets them. */
void ArmTubes(AInfinityStageStructureActor& Structure)
{
    ArmUnderpass(Structure);
    Structure.Underpass.bTubes = true;
    Structure.Underpass.TubeMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
}

TArray<URectLightComponent*> TaggedTubeLights(const AActor& Actor)
{
    TInlineComponentArray<URectLightComponent*> Lights(&Actor);
    TArray<URectLightComponent*> Tagged;
    for (URectLightComponent* Light : Lights)
    {
        if (Light && Light->ComponentTags.Contains(FName(TubeLightTag)))
        {
            Tagged.Add(Light);
        }
    }
    return Tagged;
}

int32 CountRectLights(const AActor& Actor)
{
    TInlineComponentArray<URectLightComponent*> Lights(&Actor);
    return Lights.Num();
}

/** One built tube: its instance, world box and four custom floats. */
struct FTubeRead
{
    FTransform Transform;
    FBox Box = FBox(ForceInit);
    int32 Row = INDEX_NONE;
    int32 Index = INDEX_NONE;
    float Random = -1.0f;
    float Alive = -1.0f;
};

/** Every built tube, decoded. Empty if the layer is missing or its custom data is malformed. */
TArray<FTubeRead> ReadTubes(const AInfinityStageStructureActor& Structure)
{
    TArray<FTubeRead> Tubes;
    const UInstancedStaticMeshComponent* Layer = FindLayer(Structure, TubeTag);
    if (!Layer || Layer->NumCustomDataFloats < 4
        || Layer->PerInstanceSMCustomData.Num() != Layer->GetInstanceCount() * Layer->NumCustomDataFloats)
    {
        return Tubes;
    }
    const FBox MeshBounds = Layer->GetStaticMesh()->GetBoundingBox();
    const TArray<FTransform> Instances = ReadInstances(*Layer);
    for (int32 Instance = 0; Instance < Instances.Num(); ++Instance)
    {
        const float* Data = Layer->PerInstanceSMCustomData.GetData() + Instance * Layer->NumCustomDataFloats;
        FTubeRead& Tube = Tubes.AddDefaulted_GetRef();
        Tube.Transform = Instances[Instance];
        Tube.Box = MeshBounds.TransformBy(Instances[Instance]);
        Tube.Row = FMath::RoundToInt32(Data[0]);
        Tube.Index = FMath::RoundToInt32(Data[1]);
        Tube.Random = Data[2];
        Tube.Alive = Data[3];
    }
    return Tubes;
}

/** Station X along the straight fixture route (it runs along world +X). */
TArray<double> FixtureStationX(const AInfinityStageStructureActor& Structure)
{
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    TArray<double> Xs;
    if (Structure.GatherStations(Stations, Error))
    {
        for (const FInfinityStructureStation& Station : Stations)
        {
            Xs.Add(Station.StationWorld.GetLocation().X);
        }
    }
    return Xs;
}

/** Closed form: tubes of length L with a clear gap G between them that fit in the run. */
int32 ExpectedTubesPerRow(const double RunCm, const double LengthCm, const double GapCm)
{
    return RunCm >= LengthCm
        ? static_cast<int32>(FMath::FloorToDouble((RunCm + GapCm) / (LengthCm + GapCm) + 1.0e-9))
        : 0;
}

int32 ExpectedTubeRows(const FInfinityStageUnderpassSettings& Underpass)
{
    return Underpass.TubeRowsCentre + (Underpass.bTubeCornerRows ? 2 : 0);
}

int32 CeilDiv(const int32 A, const int32 B)
{
    return (A + B - 1) / B;
}

/** The tubes that should carry a light, from the read-back data: each group's
 * middle tube along its row, where that tube is alive. */
TArray<const FTubeRead*> ExpectedHosts(const TArray<FTubeRead>& Tubes, const int32 PerRow, const int32 Every)
{
    TMap<FIntPoint, const FTubeRead*> ByPlace;
    TSet<int32> Rows;
    for (const FTubeRead& Tube : Tubes)
    {
        ByPlace.Add(FIntPoint(Tube.Row, Tube.Index), &Tube);
        Rows.Add(Tube.Row);
    }
    TArray<const FTubeRead*> Hosts;
    for (const int32 Row : Rows)
    {
        for (int32 GroupStart = 0; GroupStart < PerRow; GroupStart += Every)
        {
            const int32 Host = GroupStart + (FMath::Min(Every, PerRow - GroupStart) - 1) / 2;
            const FTubeRead* const* Found = ByPlace.Find(FIntPoint(Row, Host));
            if (Found && (*Found)->Alive > 0.5f)
            {
                Hosts.Add(*Found);
            }
        }
    }
    return Hosts;
}

/** Each light on its own host's underside, and one light per host. */
bool LightsSitOnHosts(
    const TArray<URectLightComponent*>& Lights,
    const TArray<const FTubeRead*>& Hosts,
    const double DiameterCm,
    FString& OutWhy)
{
    if (Lights.Num() != Hosts.Num())
    {
        OutWhy = FString::Printf(TEXT("%d lights for %d live hosts"), Lights.Num(), Hosts.Num());
        return false;
    }
    TSet<const FTubeRead*> Used;
    for (const URectLightComponent* Light : Lights)
    {
        const FVector Location = Light->GetComponentLocation();
        const FTubeRead* Match = nullptr;
        for (const FTubeRead* Host : Hosts)
        {
            if (!Used.Contains(Host) && Location.Equals(Host->Box.GetCenter() - FVector(0.0, 0.0, DiameterCm * 0.5), 0.5))
            {
                Match = Host;
                break;
            }
        }
        if (!Match)
        {
            OutWhy = FString::Printf(TEXT("a light at %s is on no live host"), *Location.ToString());
            return false;
        }
        Used.Add(Match);
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubesOffTest,
    "InfinityStage.Structure.UnderpassTubesOffByDefaultChangeNothing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubesOffTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    // Floor, grooves, understage, portal and stage front too, so every existing layer is compared.
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;

    const FInfinityStageUnderpassSettings& Defaults = Structure->Underpass;
    TestTrue(TEXT("Tubes and their lights are off by default"), !Defaults.bTubes && !Defaults.bTubeLights);
    TestTrue(TEXT("No tube mesh, material or light function by default"),
        Defaults.TubeMesh.IsNull() && Defaults.TubeMaterial.IsNull() && Defaults.TubeLightFunctionMaterial.IsNull());
    TestTrue(TEXT("Tube defaults as briefed"),
        FMath::IsNearlyEqual(Defaults.TubeLengthCm, 150.0) && FMath::IsNearlyEqual(Defaults.TubeDiameterCm, 5.0)
        && FMath::IsNearlyEqual(Defaults.TubeGapCm, 100.0) && Defaults.TubeRowsCentre == 2
        && FMath::IsNearlyEqual(Defaults.TubeCentreRowSpacingCm, 120.0) && Defaults.bTubeCornerRows
        && FMath::IsNearlyEqual(Defaults.TubeCornerInsetCm, 0.0) && FMath::IsNearlyEqual(Defaults.TubeDropCm, 30.0)
        && !Defaults.bTubeCastShadow && Defaults.bTubeMeshAlongZ && FMath::IsNearlyEqual(Defaults.TubeDeadFraction, 0.15)
        && Defaults.TubeFromStation == 0 && Defaults.TubeToStation == -1 && Defaults.TubeSeed == 0);
    TestTrue(TEXT("Tube light defaults as briefed: every 4, cap 64, 1500 lm, 4300 K, 1500 cm, no shadow"),
        Defaults.TubeLightEvery == 4 && Defaults.TubeLightMax == 64
        && FMath::IsNearlyEqual(Defaults.TubeLightIntensity, 1500.0f)
        && FMath::IsNearlyEqual(Defaults.TubeLightTemperatureK, 4300.0f)
        && FMath::IsNearlyEqual(Defaults.TubeLightAttenuationRadius, 1500.0f) && !Defaults.bTubeLightCastShadow);
    TestTrue(TEXT("The tube light colour is a tired office green"),
        Defaults.TubeLightColor.Equals(FLinearColor(0.92f, 1.0f, 0.88f), 1.0e-4f));

    ArmUnderpass(*Structure);
    TestTrue(TEXT("The underpass builds without tubes"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Baseline = SnapshotBuild(*Structure);
    const TArray<int32> BaselineCounts = UnderpassCounts(*Structure);

    // The tube kit set, lights too, but the tubes off: nothing may change.
    ArmTubes(*Structure);
    Structure->Underpass.bTubeLights = true;
    Structure->Underpass.bTubes = false;
    TestTrue(TEXT("Builds with the tube kit set but the tubes off"), Structure->MaterializeStructure());
    FString Why;
    const bool bSameOff = SameBuild(Baseline, SnapshotBuild(*Structure), Why);
    TestTrue(FString::Printf(TEXT("Tubes off, every component is unchanged (%s)"), *Why), bSameOff);
    TestTrue(TEXT("Tubes off, every other underpass count is unchanged"), UnderpassCounts(*Structure) == BaselineCounts);
    TestTrue(TEXT("Tubes off, no tubes and no lights are counted"),
        Structure->UnderpassTubeCount == 0 && Structure->UnderpassTubeLightCount == 0);
    TestEqual(TEXT("Tubes off, the actor has no rect light"), CountRectLights(*Structure), 0);
    TestEqual(TEXT("Tubes off, no light is managed"), Structure->ManagedLights.Num(), 0);

    // Tubes on but the underpass off: still nothing.
    Structure->Underpass.bTubes = true;
    Structure->Underpass.bEnabled = false;
    TestTrue(TEXT("Builds with the tubes on and the underpass off"), Structure->MaterializeStructure());
    TestTrue(TEXT("Underpass off, no tube layer, tube or light"),
        FindLayer(*Structure, TubeTag) == nullptr && Structure->UnderpassTubeCount == 0
        && Structure->UnderpassTubeLightCount == 0 && CountRectLights(*Structure) == 0);

    // Control: on, the tubes add one layer and their lights, so the comparisons
    // above can fail. Every other layer stays exactly as it was.
    Structure->Underpass.bEnabled = true;
    TestTrue(TEXT("Builds with the tubes on"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> WithTubes = SnapshotBuild(*Structure);
    TestEqual(TEXT("Control: the tubes add one component"), WithTubes.Num(), Baseline.Num() + 1);
    TestTrue(TEXT("Control: tubes and lights are built"),
        Structure->UnderpassTubeCount > 0 && Structure->UnderpassTubeLightCount > 0
        && CountRectLights(*Structure) == Structure->UnderpassTubeLightCount);
    TArray<FBuiltLayer> Others;
    for (const FBuiltLayer& Layer : WithTubes)
    {
        if (!Layer.Tags.Contains(FName(TubeTag)))
        {
            Others.Add(Layer);
        }
    }
    const bool bSameOthers = SameBuild(Baseline, Others, Why);
    TestTrue(FString::Printf(TEXT("Tubes on, every other layer is unchanged (%s)"), *Why), bSameOthers);
    TestTrue(TEXT("Tubes on, every other underpass count is unchanged"), UnderpassCounts(*Structure) == BaselineCounts);
    TestTrue(TEXT("A structure with tubes is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeCountsTest,
    "InfinityStage.Structure.UnderpassTubeCountsFollowTheFormula",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeCountsTest::RunTest(const FString& Parameters)
{
    struct FCase
    {
        int32 Stations;
        int32 CentreRows;
        bool bCorners;
        double LengthCm;
        double GapCm;
    };
    // The briefed default; three centre rows and no corners; corners alone; no gap.
    for (const FCase Case : { FCase{ 5, 2, true, 150.0, 100.0 }, FCase{ 4, 3, false, 200.0, 50.0 },
                              FCase{ 5, 0, true, 150.0, 100.0 }, FCase{ 6, 2, true, 333.0, 0.0 } })
    {
        const FString Label = FString::Printf(TEXT("%d stations, %d centre rows%s, %.0f cm tubes, %.0f cm gaps"),
            Case.Stations, Case.CentreRows, Case.bCorners ? TEXT(" and corners") : TEXT(""), Case.LengthCm, Case.GapCm);
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, Case.Stations);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmTubes(*Structure);
        FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
        Underpass.TubeRowsCentre = Case.CentreRows;
        Underpass.bTubeCornerRows = Case.bCorners;
        Underpass.TubeLengthCm = Case.LengthCm;
        Underpass.TubeGapCm = Case.GapCm;

        const TArray<double> Xs = FixtureStationX(*Structure);
        const double RunCm = Xs.Num() == Case.Stations ? Xs.Last() - Xs[0] : 0.0;
        const int32 PerRow = ExpectedTubesPerRow(RunCm, Case.LengthCm, Case.GapCm);
        const int32 Rows = Case.CentreRows + (Case.bCorners ? 2 : 0);
        TestTrue(Label + TEXT(": fixture, the run fits several tubes"), PerRow > 1);
        // The census the conductor's tools parse: the new keys, appended after the catwalks.
        AddExpectedMessagePlain(
            *FString::Printf(TEXT("underpass_catwalks=%d underpass_tubes=%d underpass_tube_lights=0"),
                2 * (Case.Stations - 1), Rows * PerRow),
            ELogVerbosity::Display,
            EAutomationExpectedMessageFlags::Contains,
            1);
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        TestEqual(*(Label + TEXT(": rows x tubes per row")), Structure->UnderpassTubeCount, Rows * PerRow);

        const TArray<FTubeRead> Tubes = ReadTubes(*Structure);
        TestEqual(*(Label + TEXT(": the count is the layer's instances")), Tubes.Num(), Structure->UnderpassTubeCount);
        TMap<int32, TArray<int32>> IndicesByRow;
        for (const FTubeRead& Tube : Tubes)
        {
            IndicesByRow.FindOrAdd(Tube.Row).Add(Tube.Index);
        }
        TestEqual(*(Label + TEXT(": one row per row setting")), IndicesByRow.Num(), Rows);
        for (int32 Row = 0; Row < Rows; ++Row)
        {
            TArray<int32>* Indices = IndicesByRow.Find(Row);
            bool bWhole = Indices && Indices->Num() == PerRow;
            if (bWhole)
            {
                Indices->Sort();
                for (int32 Index = 0; Index < PerRow; ++Index)
                {
                    bWhole &= (*Indices)[Index] == Index;
                }
            }
            TestTrue(FString::Printf(TEXT("%s: row %d holds tubes 0..%d once each"), *Label, Row, PerRow - 1), bWhole);
        }
        World->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeRowsTest,
    "InfinityStage.Structure.UnderpassTubeRowsHangUnderTheDeck",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeRowsTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cylinder(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    if (!Cylinder.LoadSynchronous())
    {
        AddError(TEXT("Fixture: the engine cylinder does not load."));
        return false;
    }
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    // Off the defaults, so each value is shown to come from its own setting.
    Underpass.TubeCentreRowSpacingCm = 150.0;
    Underpass.TubeDropCm = 40.0;
    Underpass.TubeDiameterCm = 8.0;
    Underpass.TubeLengthCm = 120.0;
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());

    const auto CheckRows = [this, Structure](const FString& Label, const double CornerCm, const double ZCm)
    {
        const FInfinityStageUnderpassSettings& Set = Structure->Underpass;
        const double Lateral[] = { -Set.TubeCentreRowSpacingCm * 0.5, Set.TubeCentreRowSpacingCm * 0.5, -CornerCm, CornerCm };
        const TArray<FTubeRead> Tubes = ReadTubes(*Structure);
        bool bPlaced = Tubes.Num() > 0;
        TSet<int32> RowsSeen;
        for (const FTubeRead& Tube : Tubes)
        {
            const bool bRow = Tube.Row >= 0 && Tube.Row < 4;
            const FVector Centre = Tube.Box.GetCenter();
            const FVector Size = Tube.Box.GetSize();
            bPlaced &= bRow && FMath::IsNearlyEqual(Centre.Y, Lateral[bRow ? Tube.Row : 0], 0.1)
                && FMath::IsNearlyEqual(Centre.Z, ZCm, 0.1)
                && FMath::IsNearlyEqual(Size.X, Set.TubeLengthCm, 0.1)
                && FMath::IsNearlyEqual(Size.Y, Set.TubeDiameterCm, 0.1)
                && FMath::IsNearlyEqual(Size.Z, Set.TubeDiameterCm, 0.1);
            RowsSeen.Add(Tube.Row);
        }
        TestTrue(Label + TEXT(": centre rows at +-spacing/2, corners as set, centres at the hang height, tube-sized"), bPlaced);
        TestEqual(*(Label + TEXT(": all four rows are built")), RowsSeen.Num(), 4);
    };

    const double ColumnLineCm = Structure->GridHalfWidthCm + Underpass.ColumnOutsetCm;
    CheckRows(TEXT("Default inset"), ColumnLineCm, Underpass.DeckHeightCm - Underpass.TubeDropCm);
    // The corner rows stand on the line the columns stand on.
    bool bOnColumnLine = false;
    if (const UInstancedStaticMeshComponent* Columns = FindLayer(*Structure, UnderpassTags[0]))
    {
        for (const FBox& Box : InstanceBoxes(*Columns))
        {
            bOnColumnLine |= FMath::IsNearlyEqual(Box.GetCenter().Y, ColumnLineCm, 0.1);
        }
    }
    TestTrue(TEXT("A column stands on the corner row's line"), bOnColumnLine);

    // Control: an inset moves only the corners, and no drop hangs the tubes at the deck.
    Underpass.TubeCornerInsetCm = 25.0;
    Underpass.TubeDropCm = 0.0;
    TestTrue(TEXT("Builds with an inset and no drop"), Structure->MaterializeStructure());
    CheckRows(TEXT("Inset 25, no drop"), ColumnLineCm - 25.0, Underpass.DeckHeightCm);

    // The engine cylinder's length is its local Z: along the route, tube-sized.
    Underpass.TubeMesh = Cylinder;
    Underpass.bTubeMeshAlongZ = true;
    TestTrue(TEXT("Builds on the cylinder"), Structure->MaterializeStructure());
    const TArray<FTubeRead> AlongZ = ReadTubes(*Structure);
    bool bZAlong = AlongZ.Num() > 0;
    for (const FTubeRead& Tube : AlongZ)
    {
        bZAlong &= FMath::Abs(Tube.Transform.GetUnitAxis(EAxis::Z).X) > 0.9999
            && FMath::IsNearlyEqual(Tube.Box.GetSize().X, Underpass.TubeLengthCm, 0.1);
    }
    TestTrue(TEXT("Along Z: the cylinder's axis runs along the route"), bZAlong);
    // Control: a mesh authored along X turns the other way.
    Underpass.bTubeMeshAlongZ = false;
    TestTrue(TEXT("Builds on the cylinder, along X"), Structure->MaterializeStructure());
    const TArray<FTubeRead> AlongX = ReadTubes(*Structure);
    bool bXAlong = AlongX.Num() > 0;
    for (const FTubeRead& Tube : AlongX)
    {
        bXAlong &= FMath::Abs(Tube.Transform.GetUnitAxis(EAxis::X).X) > 0.9999
            && FMath::Abs(Tube.Transform.GetUnitAxis(EAxis::Z).X) < 1.0e-3;
    }
    TestTrue(TEXT("Control, along X: the mesh's X runs along the route instead"), bXAlong);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeEndsTest,
    "InfinityStage.Structure.UnderpassTubesKeepTheEndsClean",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeEndsTest::RunTest(const FString& Parameters)
{
    for (const int32 StationTotal : { 5, 4 })
    {
        const FString Label = FString::Printf(TEXT("%d stations"), StationTotal);
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, StationTotal);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmTubes(*Structure);
        FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
        const TArray<double> Xs = FixtureStationX(*Structure);
        if (Xs.Num() != StationTotal)
        {
            AddError(Label + TEXT(": stations did not gather."));
            World->DestroyWorld(false);
            return false;
        }
        const double PitchCm = Underpass.TubeLengthCm + Underpass.TubeGapCm;

        // Inside [FromX, ToX], and the spare length split evenly between the two
        // ends: the even split is the control that the bound measures a real edge.
        const auto CheckStretch = [&](const FString& Stretch, const double FromX, const double ToX)
        {
            const TArray<FTubeRead> Tubes = ReadTubes(*Structure);
            double MinX = TNumericLimits<double>::Max();
            double MaxX = TNumericLimits<double>::Lowest();
            bool bInside = Tubes.Num() > 0;
            for (const FTubeRead& Tube : Tubes)
            {
                bInside &= Tube.Box.Min.X >= FromX - 0.5 && Tube.Box.Max.X <= ToX + 0.5;
                MinX = FMath::Min(MinX, Tube.Box.Min.X);
                MaxX = FMath::Max(MaxX, Tube.Box.Max.X);
            }
            TestTrue(Stretch + TEXT(": no tube passes either end station"), bInside);
            const double Head = MinX - FromX;
            const double Tail = ToX - MaxX;
            TestTrue(FString::Printf(TEXT("%s: the spare is split between the ends (%.2f, %.2f), each under a pitch"),
                *Stretch, Head, Tail), FMath::IsNearlyEqual(Head, Tail, 0.5) && Head < PitchCm);
            TestEqual(*(Stretch + TEXT(": count")), Tubes.Num(),
                ExpectedTubeRows(Underpass) * ExpectedTubesPerRow(ToX - FromX, Underpass.TubeLengthCm, Underpass.TubeGapCm));
            return Tubes.Num();
        };
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        const int32 Whole = CheckStretch(Label + TEXT(", whole Passage"), Xs[0], Xs.Last());

        // A stretch, as the P02 breakdown wants: its own end stations are its clean ends.
        Underpass.TubeFromStation = 1;
        Underpass.TubeToStation = StationTotal - 2;
        TestTrue(Label + TEXT(": builds a stretch"), Structure->MaterializeStructure());
        const int32 Part = CheckStretch(Label + TEXT(", stations 1 to N-2"), Xs[1], Xs[StationTotal - 2]);
        TestTrue(Label + TEXT(": control, the stretch is shorter than the whole"), Part > 0 && Part < Whole);

        // An empty stretch builds nothing, and is no error.
        Underpass.TubeFromStation = 2;
        Underpass.TubeToStation = 2;
        TestTrue(Label + TEXT(": builds an empty stretch"), Structure->MaterializeStructure());
        TestTrue(Label + TEXT(": an empty stretch has no tubes"),
            Structure->UnderpassTubeCount == 0 && FindLayer(*Structure, TubeTag) == nullptr);

        World->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeSeedTest,
    "InfinityStage.Structure.UnderpassTubeCustomDataIsSeeded",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeSeedTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());
    const TArray<FTubeRead> First = ReadTubes(*Structure);
    TestTrue(TEXT("Fixture: tubes were built"), First.Num() >= 16);

    bool bWellFormed = First.Num() > 0;
    TSet<float> Distinct;
    for (const FTubeRead& Tube : First)
    {
        bWellFormed &= Tube.Random >= 0.0f && Tube.Random < 1.0f
            && Tube.Alive == (Tube.Random >= Underpass.TubeDeadFraction ? 1.0f : 0.0f);
        Distinct.Add(Tube.Random);
    }
    TestTrue(TEXT("[2] lies in 0..1 and [3] marks alive exactly where [2] >= the dead fraction"), bWellFormed);
    TestTrue(TEXT("[2] varies from tube to tube"), Distinct.Num() > First.Num() / 2);

    // The same seed rebuilds the same data.
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    const TArray<FTubeRead> Again = ReadTubes(*Structure);
    bool bSame = Again.Num() == First.Num();
    for (int32 Index = 0; bSame && Index < First.Num(); ++Index)
    {
        bSame = Again[Index].Row == First[Index].Row && Again[Index].Index == First[Index].Index
            && Again[Index].Random == First[Index].Random && Again[Index].Alive == First[Index].Alive
            && Again[Index].Transform.Equals(First[Index].Transform, 1.0e-4);
    }
    TestTrue(TEXT("The same seed rebuilds the same custom data"), bSame);

    // Another seed re-rolls the randoms and nothing else.
    Underpass.TubeSeed = 7;
    TestTrue(TEXT("Builds with seed 7"), Structure->MaterializeStructure());
    const TArray<FTubeRead> Reseeded = ReadTubes(*Structure);
    bool bSamePlaces = Reseeded.Num() == First.Num();
    int32 Changed = 0;
    for (int32 Index = 0; bSamePlaces && Index < First.Num(); ++Index)
    {
        bSamePlaces = Reseeded[Index].Row == First[Index].Row && Reseeded[Index].Index == First[Index].Index
            && Reseeded[Index].Transform.Equals(First[Index].Transform, 1.0e-4);
        Changed += Reseeded[Index].Random != First[Index].Random ? 1 : 0;
    }
    TestTrue(TEXT("Another seed keeps every tube where it was"), bSamePlaces);
    TestTrue(FString::Printf(TEXT("Another seed re-rolls the randoms (%d of %d changed)"), Changed, First.Num()),
        Changed >= First.Num() * 9 / 10);

    // The corners off never re-roll a centre row.
    Underpass.TubeSeed = 0;
    Underpass.bTubeCornerRows = false;
    TestTrue(TEXT("Builds without corners"), Structure->MaterializeStructure());
    const TArray<FTubeRead> NoCorners = ReadTubes(*Structure);
    TMap<FIntPoint, float> CentreRandoms;
    for (const FTubeRead& Tube : First)
    {
        if (Tube.Row < Underpass.TubeRowsCentre)
        {
            CentreRandoms.Add(FIntPoint(Tube.Row, Tube.Index), Tube.Random);
        }
    }
    bool bCentreKept = NoCorners.Num() == CentreRandoms.Num() && NoCorners.Num() < First.Num();
    for (const FTubeRead& Tube : NoCorners)
    {
        const float* Before = CentreRandoms.Find(FIntPoint(Tube.Row, Tube.Index));
        bCentreKept &= Before && *Before == Tube.Random;
    }
    TestTrue(TEXT("Corners off: the centre rows keep their randoms, and only the corners went"), bCentreKept);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassDeadTubesTest,
    "InfinityStage.Structure.UnderpassDeadTubesAreDarkAndUnlit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassDeadTubesTest::RunTest(const FString& Parameters)
{
    // Many short tubes, so the dead share is measured over well over a thousand.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 21);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.TubeLengthCm = 20.0;
    Underpass.TubeGapCm = 5.0;
    Underpass.bTubeLights = true;
    Underpass.TubeLightEvery = 8;
    Underpass.TubeLightMax = 100000;
    const TArray<double> Xs = FixtureStationX(*Structure);
    const int32 PerRow = ExpectedTubesPerRow(Xs.Num() == 21 ? Xs.Last() - Xs[0] : 0.0, 20.0, 5.0);
    const int32 Rows = ExpectedTubeRows(Underpass);
    const int32 Groups = Rows * CeilDiv(FMath::Max(1, PerRow), 8);

    TestTrue(TEXT("Builds at the default dead fraction"), Structure->MaterializeStructure());
    const TArray<FTubeRead> Tubes = ReadTubes(*Structure);
    TestTrue(FString::Printf(TEXT("Fixture: %d tubes, at least 1000"), Tubes.Num()), Tubes.Num() >= 1000);
    int32 Dead = 0;
    for (const FTubeRead& Tube : Tubes)
    {
        Dead += Tube.Alive < 0.5f ? 1 : 0;
    }
    const double Share = Tubes.Num() > 0 ? static_cast<double>(Dead) / Tubes.Num() : -1.0;
    // 0.04 is about four and a half standard deviations at 1600 tubes.
    TestTrue(FString::Printf(TEXT("The dead share %.3f is close to 0.15"), Share), FMath::Abs(Share - 0.15) <= 0.04);

    const TArray<const FTubeRead*> Hosts = ExpectedHosts(Tubes, PerRow, 8);
    const TArray<URectLightComponent*> Lights = TaggedTubeLights(*Structure);
    FString Why;
    const bool bOnHosts = LightsSitOnHosts(Lights, Hosts, Underpass.TubeDiameterCm, Why);
    TestTrue(FString::Printf(TEXT("A light on every live group-middle tube and nowhere else (%s)"), *Why), bOnHosts);
    TestTrue(FString::Printf(TEXT("Control: dead middles cost lights (%d of %d groups lit)"), Hosts.Num(), Groups),
        Hosts.Num() < Groups && Hosts.Num() > 0);
    bool bNoneOnDead = true;
    for (const FTubeRead& Tube : Tubes)
    {
        if (Tube.Alive > 0.5f)
        {
            continue;
        }
        for (const URectLightComponent* Light : Lights)
        {
            bNoneOnDead &= !Light->GetComponentLocation().Equals(
                Tube.Box.GetCenter() - FVector(0.0, 0.0, Underpass.TubeDiameterCm * 0.5), 1.0);
        }
    }
    TestTrue(TEXT("No light hangs on a dead tube"), bNoneOnDead);

    // Deterministic: the same build kills the same tubes.
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    const TArray<FTubeRead> Again = ReadTubes(*Structure);
    bool bSameDead = Again.Num() == Tubes.Num();
    for (int32 Index = 0; bSameDead && Index < Tubes.Num(); ++Index)
    {
        bSameDead = Again[Index].Alive == Tubes[Index].Alive;
    }
    TestTrue(TEXT("The same seed kills the same tubes"), bSameDead);
    TestEqual(TEXT("The same seed lights the same groups"), Structure->UnderpassTubeLightCount, Hosts.Num());

    // Control: fraction 0, every tube alive and every group lit.
    Underpass.TubeDeadFraction = 0.0;
    TestTrue(TEXT("Builds at fraction 0"), Structure->MaterializeStructure());
    int32 DeadAtZero = 0;
    const TArray<FTubeRead> AllAlive = ReadTubes(*Structure);
    for (const FTubeRead& Tube : AllAlive)
    {
        DeadAtZero += Tube.Alive < 0.5f ? 1 : 0;
    }
    TestTrue(TEXT("Fraction 0: no dead tubes"), DeadAtZero == 0 && AllAlive.Num() == Tubes.Num());
    TestEqual(TEXT("Fraction 0: one light per group"), Structure->UnderpassTubeLightCount, Groups);

    // And fraction 1: every tube still hangs, dark, and none is lit.
    Underpass.TubeDeadFraction = 1.0;
    TestTrue(TEXT("Builds at fraction 1"), Structure->MaterializeStructure());
    int32 AliveAtOne = 0;
    const TArray<FTubeRead> AllDead = ReadTubes(*Structure);
    for (const FTubeRead& Tube : AllDead)
    {
        AliveAtOne += Tube.Alive > 0.5f ? 1 : 0;
    }
    TestTrue(TEXT("Fraction 1: every tube hangs, dead"), AliveAtOne == 0 && AllDead.Num() == Tubes.Num());
    TestTrue(TEXT("Fraction 1: no light"), Structure->UnderpassTubeLightCount == 0 && TaggedTubeLights(*Structure).Num() == 0);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeLightCountTest,
    "InfinityStage.Structure.UnderpassTubeLightsFollowEveryAndTheCap",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeLightCountTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    // No dead tubes, so the count is the formula alone.
    Underpass.TubeDeadFraction = 0.0;
    Underpass.bTubeLights = true;
    const TArray<double> Xs = FixtureStationX(*Structure);
    const int32 PerRow = ExpectedTubesPerRow(Xs.Num() == 5 ? Xs.Last() - Xs[0] : 0.0, Underpass.TubeLengthCm, Underpass.TubeGapCm);
    const int32 Rows = ExpectedTubeRows(Underpass);
    TestTrue(TEXT("Fixture: several tubes per row"), PerRow >= 4);

    // Not 4: at 4 the count equals the thinned case's, and its census line is expected exactly once below.
    for (const int32 Every : { 1, 3, 1000 })
    {
        const FString Label = FString::Printf(TEXT("Every %d"), Every);
        Underpass.TubeLightEvery = Every;
        Underpass.TubeLightMax = 100000;
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        const int32 Expected = Rows * CeilDiv(PerRow, Every);
        TestEqual(*(Label + TEXT(": rows x groups per row")), Structure->UnderpassTubeLightCount, Expected);
        TestEqual(*(Label + TEXT(": the count is the lights on the actor")), TaggedTubeLights(*Structure).Num(), Expected);
        TestEqual(*(Label + TEXT(": the count is the managed lights")), Structure->ManagedLights.Num(), Expected);
        TestEqual(*(Label + TEXT(": built at the asked spacing")), Structure->UnderpassTubeLightEveryUsed, Every);
        FString Why;
        const bool bOnHosts = LightsSitOnHosts(TaggedTubeLights(*Structure), ExpectedHosts(ReadTubes(*Structure), PerRow, Every),
            Underpass.TubeDiameterCm, Why);
        TestTrue(FString::Printf(TEXT("%s: each light on its group's middle tube (%s)"), *Label, *Why), bOnHosts);
    }

    // Over the cap, thinned evenly: the smallest spacing whose lights fit.
    Underpass.TubeLightEvery = 1;
    Underpass.TubeLightMax = 10;
    int32 Thinned = 1;
    while (Rows * CeilDiv(PerRow, Thinned) > 10 && Thinned < PerRow)
    {
        ++Thinned;
    }
    TestTrue(TEXT("Fixture: the cap bites (one light per tube would exceed it)"), Rows * PerRow > 10 && Thinned > 1);
    AddExpectedMessagePlain(TEXT("INFINITY_STAGE_STRUCTURE_TUBE_LIGHTS_THINNED"), ELogVerbosity::Display,
        EAutomationExpectedMessageFlags::Contains, 1);
    AddExpectedMessagePlain(
        *FString::Printf(TEXT("underpass_tubes=%d underpass_tube_lights=%d"), Rows * PerRow, Rows * CeilDiv(PerRow, Thinned)),
        ELogVerbosity::Display,
        EAutomationExpectedMessageFlags::Contains,
        1);
    TestTrue(TEXT("Builds thinned"), Structure->MaterializeStructure());
    TestEqual(TEXT("Thinned: the spacing used"), Structure->UnderpassTubeLightEveryUsed, Thinned);
    TestEqual(TEXT("Thinned: the lights at that spacing"), Structure->UnderpassTubeLightCount, Rows * CeilDiv(PerRow, Thinned));
    TestTrue(TEXT("Thinned: within the cap"), Structure->UnderpassTubeLightCount <= 10 && TaggedTubeLights(*Structure).Num() <= 10);

    // Fewer allowed than there are rows: refused, the tubes still built.
    // Refused twice below: here, and at a cap of 0. One registration for both.
    Underpass.TubeLightMax = Rows - 1;
    AddExpectedMessagePlain(TEXT("INFINITY_STAGE_STRUCTURE_TUBE_LIGHTS_REFUSED"), ELogVerbosity::Warning,
        EAutomationExpectedMessageFlags::Contains, 2);
    TestTrue(TEXT("Builds with a cap under the rows"), Structure->MaterializeStructure());
    TestTrue(TEXT("A cap under the rows: no lights, tubes still built"),
        Structure->UnderpassTubeLightCount == 0 && TaggedTubeLights(*Structure).Num() == 0
        && Structure->UnderpassTubeCount == Rows * PerRow);

    // A cap of 0 is "no lights" at any spacing.
    Underpass.TubeLightMax = 0;
    TestTrue(TEXT("Builds with a cap of 0"), Structure->MaterializeStructure());
    TestEqual(TEXT("A cap of 0: no lights"), TaggedTubeLights(*Structure).Num(), 0);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeLightShadowTest,
    "InfinityStage.Structure.UnderpassTubeLightsCastNoShadowByDefault",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeLightShadowTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UMaterialInterface> Hum(
        FSoftObjectPath(TEXT("/Game/InfinityStage/Lighting/MI_LF_Flicker_Hum.MI_LF_Flicker_Hum")));
    if (!Hum.LoadSynchronous())
    {
        AddError(TEXT("Fixture: MI_LF_Flicker_Hum does not load."));
        return false;
    }
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.TubeDeadFraction = 0.0;
    Underpass.bTubeLights = true;
    TestTrue(TEXT("Builds with default lights"), Structure->MaterializeStructure());

    const auto CheckLights = [this, Structure](const FString& Label, const bool bShadow, const float Intensity,
                                               const float Kelvin, const UMaterialInterface* Function)
    {
        const FInfinityStageUnderpassSettings& Set = Structure->Underpass;
        const TArray<URectLightComponent*> Lights = TaggedTubeLights(*Structure);
        bool bAsSet = Lights.Num() > 0 && Lights.Num() == Structure->UnderpassTubeLightCount;
        bool bColour = bAsSet;
        for (const URectLightComponent* Light : Lights)
        {
            bAsSet &= static_cast<bool>(Light->CastShadows) == bShadow
                && Light->GetMobility() == EComponentMobility::Movable
                && Light->IntensityUnits == ELightUnits::Lumens
                && FMath::IsNearlyEqual(Light->Intensity, Intensity, 0.01f)
                && Light->bUseTemperature
                && FMath::IsNearlyEqual(Light->Temperature, Kelvin, 0.01f)
                && FMath::IsNearlyEqual(Light->AttenuationRadius, Set.TubeLightAttenuationRadius, 0.01f)
                && FMath::IsNearlyEqual(Light->SourceWidth, static_cast<float>(Set.TubeLengthCm), 0.01f)
                && FMath::IsNearlyEqual(Light->SourceHeight, static_cast<float>(Set.TubeDiameterCm), 0.01f)
                && Light->LightFunctionMaterial.Get() == Function
                && FVector::DotProduct(Light->GetForwardVector(), FVector::DownVector) > 0.9999
                && Light->ComponentTags.Contains(FName(TEXT("InfinityStage.Structure")));
            bColour &= Light->GetLightColor().Equals(Set.TubeLightColor, 0.01f);
        }
        TestTrue(Label + TEXT(": shadow, mobility, units, level, temperature, reach, size, function and aim as set"), bAsSet);
        TestTrue(Label + TEXT(": the colour reads back as set"), bColour);
    };
    CheckLights(TEXT("Defaults"), false, 1500.0f, 4300.0f, nullptr);
    const UInstancedStaticMeshComponent* Tubes = FindLayer(*Structure, TubeTag);
    TestTrue(TEXT("The tube meshes cast no shadow by default"), Tubes && !Tubes->CastShadow);

    // Control: every value flipped from its default reads back flipped.
    Underpass.bTubeLightCastShadow = true;
    Underpass.bTubeCastShadow = true;
    Underpass.TubeLightIntensity = 900.0f;
    Underpass.TubeLightTemperatureK = 5000.0f;
    Underpass.TubeLightColor = FLinearColor(1.0f, 0.5f, 0.25f);
    Underpass.TubeLightFunctionMaterial = Hum;
    TestTrue(TEXT("Builds with every light value changed"), Structure->MaterializeStructure());
    CheckLights(TEXT("Control, changed"), true, 900.0f, 5000.0f, Hum.LoadSynchronous());
    Tubes = FindLayer(*Structure, TubeTag);
    TestTrue(TEXT("Control: the tube meshes cast when asked"), Tubes && Tubes->CastShadow);

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassTubeLightClearTest,
    "InfinityStage.Structure.UnderpassClearRemovesTubeLights",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassTubeLightClearTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    Structure->Underpass.TubeDeadFraction = 0.0;
    Structure->Underpass.bTubeLights = true;

    // A work light the artist added to the structure by hand: not the layer's to clear.
    URectLightComponent* HandLight = NewObject<URectLightComponent>(Structure, TEXT("HandWorkLight"));
    HandLight->SetupAttachment(Structure->GetRootComponent());
    Structure->AddInstanceComponent(HandLight);
    HandLight->RegisterComponent();

    TestTrue(TEXT("Builds with lights"), Structure->MaterializeStructure());
    const int32 Built = TaggedTubeLights(*Structure).Num();
    TestTrue(TEXT("Control: lights were built"), Built > 0 && Built == Structure->UnderpassTubeLightCount);
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    TestEqual(TEXT("A rebuild never stacks lights"), TaggedTubeLights(*Structure).Num(), Built);
    TestEqual(TEXT("The managed record holds every light"), Structure->ManagedLights.Num(), Built);

    // Undo can drop the record while the light lives on: it is still cleared.
    URectLightComponent* Orphan = Structure->ManagedLights[0];
    Structure->ManagedLights.RemoveAt(0);
    Structure->ClearStructure();
    TInlineComponentArray<URectLightComponent*> Remaining(Structure);
    TestEqual(TEXT("Clear removes every tube light"), TaggedTubeLights(*Structure).Num(), 0);
    TestFalse(TEXT("Clear removes a light the record lost"), Remaining.Contains(Orphan));
    TestTrue(TEXT("Clear empties the record and the counts"),
        Structure->ManagedLights.Num() == 0 && Structure->UnderpassTubeLightCount == 0
        && Structure->UnderpassTubeCount == 0 && Structure->UnderpassTubeLightEveryUsed == 0
        && FindLayer(*Structure, TubeTag) == nullptr);
    TestTrue(TEXT("A hand-added light survives the clear"), IsValid(HandLight) && Remaining.Contains(HandLight));

    // Switching the lights off removes them on the next build.
    TestTrue(TEXT("Rebuilds with lights"), Structure->MaterializeStructure());
    TestEqual(TEXT("Control: lights are back"), TaggedTubeLights(*Structure).Num(), Built);
    Structure->Underpass.bTubeLights = false;
    TestTrue(TEXT("Rebuilds without lights"), Structure->MaterializeStructure());
    TestEqual(TEXT("Lights off: none left"), TaggedTubeLights(*Structure).Num(), 0);
    TestTrue(TEXT("Lights off: the hand light still stands"), IsValid(HandLight));

    World->DestroyWorld(false);
    return true;
}

namespace
{
const TCHAR* const FenceTag = TEXT("InfinityStage.Structure.Underpass.Fence");
const TCHAR* const FenceVariantTags[] = {
    TEXT("InfinityStage.Structure.Underpass.Fence.A"),
    TEXT("InfinityStage.Structure.Underpass.Fence.B"),
    TEXT("InfinityStage.Structure.Underpass.Fence.C"),
    TEXT("InfinityStage.Structure.Underpass.Fence.D"),
};
const TCHAR* const FenceOverlayTags[] = {
    TEXT("InfinityStage.Structure.Underpass.FenceOverlay.A"),
    TEXT("InfinityStage.Structure.Underpass.FenceOverlay.B"),
    TEXT("InfinityStage.Structure.Underpass.FenceOverlay.C"),
    TEXT("InfinityStage.Structure.Underpass.FenceOverlay.D"),
};
constexpr int32 FenceVariantTotal = 4;
static_assert(sizeof(FenceVariantTags) / sizeof(FenceVariantTags[0]) == FenceVariantTotal, "one tag per fence variant");
static_assert(FInfinityStageUnderpassSettings::FenceVariantCount == FenceVariantTotal, "the tests know four variants");
/** The engine cube's (and cylinder's) bounds: 100 cm on every axis. */
constexpr double EngineShapeCm = 100.0;

FInfinityStageFenceVariant& FenceVariant(FInfinityStageUnderpassSettings& Underpass, const int32 Index)
{
    FInfinityStageFenceVariant* const Variants[] = {
        &Underpass.FenceVariantA, &Underpass.FenceVariantB, &Underpass.FenceVariantC, &Underpass.FenceVariantD };
    return *Variants[Index];
}

/** The underpass armed as above, and its fence on with every variant on the engine
 * cube, no overlays (the preset tarps are game content), and the intended height
 * the cube's own, so Native mode has nothing to warn about. */
void ArmFence(AInfinityStageStructureActor& Structure)
{
    ArmUnderpass(Structure);
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    Structure.Underpass.bFence = true;
    Structure.Underpass.FenceHeightCm = EngineShapeCm;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Structure.Underpass, Variant).Mesh = Cube;
        FenceVariant(Structure.Underpass, Variant).OverlayMesh = nullptr;
    }
}

/** A materialized straight Passage whose station gaps are as given, along +X. */
AInfinityStagePassageActor* SpawnSpacedPassage(UWorld& World, const TArray<double>& GapsCm)
{
    UInfinityStageShowAsset* Show = NewObject<UInfinityStageShowAsset>(GetTransientPackage());
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    for (int32 Index = 0; Index <= GapsCm.Num(); ++Index)
    {
        FInfinityShowCue& Cue = Show->Cues.AddDefaulted_GetRef();
        Cue.Type = EInfinityCueType::WingPair;
        Cue.CueGuid = FGuid::NewGuid();
        Cue.WingPair.OccurrenceGuid = FGuid::NewGuid();
        Cue.WingPair.Left.Mesh = Cube;
        Cue.WingPair.Left.LocalTransform.SetLocation(FVector(0.0, -FixtureHalfWidthCm, 0.0));
        Cue.WingPair.Right.Mesh = Cube;
        Cue.WingPair.Right.LocalTransform.SetLocation(FVector(0.0, FixtureHalfWidthCm, 0.0));
        Cue.WingPair.GapToNextCm = Index < GapsCm.Num() ? GapsCm[Index] : 500.0;
        Cue.WingPair.IntervalToNext = 48000;
    }
    Show->ReconcilePassageSettings();
    AInfinityStagePassageActor* Passage = World.SpawnActor<AInfinityStagePassageActor>(FVector::ZeroVector, FRotator::ZeroRotator);
    Passage->ShowAsset = Show;
    Passage->MaterializePassage();
    return Passage;
}

/** One built panel: its variant (read from its layer), instance, world box and custom floats. */
struct FFenceRead
{
    int32 Variant = INDEX_NONE;
    FTransform Transform;
    FBox Box = FBox(ForceInit);
    float Data[4] = { -1.0f, -1.0f, -1.0f, -1.0f };
};

TArray<FFenceRead> ReadFence(const AInfinityStageStructureActor& Structure, const TCHAR* const* Tags = FenceVariantTags)
{
    TArray<FFenceRead> Panels;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        const UInstancedStaticMeshComponent* Layer = FindLayer(Structure, Tags[Variant]);
        if (!Layer)
        {
            continue;
        }
        const bool bData = Layer->NumCustomDataFloats >= 4
            && Layer->PerInstanceSMCustomData.Num() == Layer->GetInstanceCount() * Layer->NumCustomDataFloats;
        const FBox MeshBounds = Layer->GetStaticMesh()->GetBoundingBox();
        const TArray<FTransform> Instances = ReadInstances(*Layer);
        for (int32 Instance = 0; Instance < Instances.Num(); ++Instance)
        {
            FFenceRead& Panel = Panels.AddDefaulted_GetRef();
            Panel.Variant = Variant;
            Panel.Transform = Instances[Instance];
            Panel.Box = MeshBounds.TransformBy(Instances[Instance]);
            for (int32 Float = 0; bData && Float < 4; ++Float)
            {
                Panel.Data[Float] = Layer->PerInstanceSMCustomData[Instance * Layer->NumCustomDataFloats + Float];
            }
        }
    }
    return Panels;
}

/** Each panel's variant, keyed by where it stands (its plan centre to the cm), which a rebuild does not move. */
TMap<FIntPoint, int32> FenceChoices(const TArray<FFenceRead>& Panels)
{
    TMap<FIntPoint, int32> Choices;
    for (const FFenceRead& Panel : Panels)
    {
        const FVector Centre = Panel.Box.GetCenter();
        Choices.Add(FIntPoint(FMath::RoundToInt32(Centre.X), FMath::RoundToInt32(Centre.Y)), Panel.Variant);
    }
    return Choices;
}

TArray<FBuiltLayer> WithoutFence(const TArray<FBuiltLayer>& Layers)
{
    TArray<FBuiltLayer> Kept;
    for (const FBuiltLayer& Layer : Layers)
    {
        if (!Layer.Tags.Contains(FName(FenceTag)))
        {
            Kept.Add(Layer);
        }
    }
    return Kept;
}

int32 FenceLayerInstances(const AInfinityStageStructureActor& Structure)
{
    int32 Total = 0;
    for (const TCHAR* Tag : FenceVariantTags)
    {
        const UInstancedStaticMeshComponent* Layer = FindLayer(Structure, Tag);
        Total += Layer ? Layer->GetInstanceCount() : 0;
    }
    return Total;
}

/** Column centre X along the straight fixture route, sorted, from the built column layer. */
TArray<double> ColumnCentreX(const AInfinityStageStructureActor& Structure)
{
    TArray<double> Xs;
    if (const UInstancedStaticMeshComponent* Columns = FindLayer(Structure, UnderpassTags[0]))
    {
        for (const FBox& Box : InstanceBoxes(*Columns))
        {
            const double X = Box.GetCenter().X;
            if (!Xs.ContainsByPredicate([X](const double Seen) { return FMath::IsNearlyEqual(Seen, X, 0.1); }))
            {
                Xs.Add(X);
            }
        }
    }
    Xs.Sort();
    return Xs;
}

/** The brief's tiling rule, written out: n = max(1, round(gap / native width)). */
int32 ExpectedTiles(const double GapCm, const double NativeWidthCm)
{
    return FMath::Max(1, static_cast<int32>(FMath::FloorToDouble(GapCm / NativeWidthCm + 0.5)));
}

/** Tiles over every column gap, per side, on the straight fixture. */
int32 ExpectedFencePanels(const TArray<double>& ColumnXs, const double NativeWidthCm, const int32 Sides)
{
    int32 Total = 0;
    for (int32 Gap = 0; Gap + 1 < ColumnXs.Num(); ++Gap)
    {
        Total += ExpectedTiles(ColumnXs[Gap + 1] - ColumnXs[Gap], NativeWidthCm);
    }
    return Total * Sides;
}

/** Each column gap, per side, tiled exactly: its count of panels, equal widths of
 * gap / n, edge to edge from one column centre to the next. */
bool TilesFillTheGaps(const TArray<FFenceRead>& Panels, const TArray<double>& ColumnXs, const double NativeWidthCm,
    const int32 Sides, FString& OutWhy)
{
    for (const double Side : { -1.0, 1.0 })
    {
        if (Sides == 1 && Side > 0.0)
        {
            continue;
        }
        for (int32 Gap = 0; Gap + 1 < ColumnXs.Num(); ++Gap)
        {
            const double FromX = ColumnXs[Gap];
            const double ToX = ColumnXs[Gap + 1];
            const int32 Tiles = ExpectedTiles(ToX - FromX, NativeWidthCm);
            const double SlotCm = (ToX - FromX) / Tiles;
            TArray<FBox> InGap;
            for (const FFenceRead& Panel : Panels)
            {
                const FVector Centre = Panel.Box.GetCenter();
                if (Centre.Y * Side > 0.0 && Centre.X > FromX && Centre.X < ToX)
                {
                    InGap.Add(Panel.Box);
                }
            }
            if (InGap.Num() != Tiles)
            {
                OutWhy = FString::Printf(TEXT("gap %d side %+.0f: %d panels, expected %d"), Gap, Side, InGap.Num(), Tiles);
                return false;
            }
            InGap.Sort([](const FBox& A, const FBox& B) { return A.Min.X < B.Min.X; });
            for (int32 Tile = 0; Tile < Tiles; ++Tile)
            {
                if (!FMath::IsNearlyEqual(InGap[Tile].Min.X, FromX + Tile * SlotCm, 0.1)
                    || !FMath::IsNearlyEqual(InGap[Tile].Max.X, FromX + (Tile + 1) * SlotCm, 0.1))
                {
                    OutWhy = FString::Printf(TEXT("gap %d side %+.0f tile %d spans %.2f..%.2f, expected %.2f..%.2f"),
                        Gap, Side, Tile, InGap[Tile].Min.X, InGap[Tile].Max.X, FromX + Tile * SlotCm, FromX + (Tile + 1) * SlotCm);
                    return false;
                }
            }
        }
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceOffTest,
    "InfinityStage.Structure.UnderpassFenceOffByDefaultChangesNothing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceOffTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    // Floor, grooves, understage, portal and stage front too, so every existing layer is compared.
    Structure->Ground.bEnabled = true;
    Structure->Portal.bEnabled = true;

    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    TestFalse(TEXT("The fence is off by default"), Underpass.bFence);
    bool bNoBays = true;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        const FInfinityStageFenceVariant& Kind = FenceVariant(Underpass, Variant);
        bNoBays &= Kind.Mesh.IsNull() && Kind.Material.IsNull() && Kind.OverlayMaterial.IsNull();
    }
    TestTrue(TEXT("No fence variant has a bay mesh or a material by default"), bNoBays);
    TestTrue(TEXT("B and C carry the half and torn tarps as overlays by default; A and D none"),
        Underpass.FenceVariantB.OverlayMesh.ToSoftObjectPath().ToString()
            == TEXT("/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/SM_FenceTarp_tarp_half_v2.SM_FenceTarp_tarp_half_v2")
        && Underpass.FenceVariantC.OverlayMesh.ToSoftObjectPath().ToString()
            == TEXT("/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/SM_FenceTarp_tarp_torn_v2.SM_FenceTarp_tarp_torn_v2")
        && Underpass.FenceVariantA.OverlayMesh.IsNull() && Underpass.FenceVariantD.OverlayMesh.IsNull());
    TestTrue(TEXT("Fence weights default to 0.6, 0.2, 0.15, 0.05"),
        FMath::IsNearlyEqual(Underpass.FenceVariantA.Weight, 0.6) && FMath::IsNearlyEqual(Underpass.FenceVariantB.Weight, 0.2)
        && FMath::IsNearlyEqual(Underpass.FenceVariantC.Weight, 0.15) && FMath::IsNearlyEqual(Underpass.FenceVariantD.Weight, 0.05));
    TestTrue(TEXT("Fence defaults as briefed: native height, 300 intended, from the floor, 75 inside the columns, both sides, casting, seed 0"),
        Underpass.FenceHeightMode == EInfinityFenceHeightMode::Native
        && FMath::IsNearlyEqual(Underpass.FenceHeightCm, 300.0) && FMath::IsNearlyEqual(Underpass.FenceBaseCm, 0.0)
        && FMath::IsNearlyEqual(Underpass.FenceInsetCm, 75.0) && Underpass.bFenceBothSides && Underpass.bFenceCastShadow
        && Underpass.FenceSeed == 0);

    ArmUnderpass(*Structure);
    TestTrue(TEXT("The underpass builds without a fence"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Baseline = SnapshotBuild(*Structure);
    const TArray<int32> BaselineUnderpass = UnderpassCounts(*Structure);
    const TArray<int32> BaselineExisting = ExistingCounts(*Structure);

    // The whole fence kit set, an overlay too, but the fence off: nothing may change.
    ArmFence(*Structure);
    Underpass.FenceVariantB.OverlayMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    Underpass.bFence = false;
    TestTrue(TEXT("Builds with the fence kit set but the fence off"), Structure->MaterializeStructure());
    FString Why;
    const bool bSameOff = SameBuild(Baseline, SnapshotBuild(*Structure), Why);
    TestTrue(FString::Printf(TEXT("Fence off, every component is unchanged (%s)"), *Why), bSameOff);
    TestTrue(TEXT("Fence off, every other count is unchanged"),
        UnderpassCounts(*Structure) == BaselineUnderpass && ExistingCounts(*Structure) == BaselineExisting);
    TestTrue(TEXT("Fence off, no panel or overlay is counted"),
        Structure->UnderpassFencePanelCount == 0 && Structure->UnderpassFenceOverlayCount == 0);

    // The fence on but the underpass off: still no fence.
    Underpass.bFence = true;
    Underpass.bEnabled = false;
    TestTrue(TEXT("Builds with the fence on and the underpass off"), Structure->MaterializeStructure());
    TestTrue(TEXT("Underpass off: no fence layer and no panel"),
        FenceLayerInstances(*Structure) == 0 && FindLayer(*Structure, FenceTag) == nullptr
        && Structure->UnderpassFencePanelCount == 0);

    // Control: on, the fence adds its layers, so the comparisons above can fail.
    // Every other layer and count stays exactly as it was.
    Underpass.bEnabled = true;
    TestTrue(TEXT("Builds with the fence on"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> WithFence = SnapshotBuild(*Structure);
    TestTrue(TEXT("Control: the fence adds components and panels"),
        WithFence.Num() > Baseline.Num() && Structure->UnderpassFencePanelCount > 0);
    const bool bSameOthers = SameBuild(Baseline, WithoutFence(WithFence), Why);
    TestTrue(FString::Printf(TEXT("Fence on, every other layer is unchanged (%s)"), *Why), bSameOthers);
    TestTrue(TEXT("Fence on, every other count is unchanged"),
        UnderpassCounts(*Structure) == BaselineUnderpass && ExistingCounts(*Structure) == BaselineExisting);
    TestTrue(TEXT("A structure with a fence is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceCountsTest,
    "InfinityStage.Structure.UnderpassFenceCountsFollowTheColumnGaps",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceCountsTest::RunTest(const FString& Parameters)
{
    struct FCase
    {
        int32 Stations;
        int32 Every;
        bool bBothSides;
    };
    // As the column cases, and one side alone as the control on the side factor.
    for (const FCase Case : { FCase{ 5, 2, true }, FCase{ 4, 2, true }, FCase{ 6, 3, true }, FCase{ 5, 1, true },
                              FCase{ 5, 2, false } })
    {
        const FString Label = FString::Printf(TEXT("%d stations, columns every %d, %s"),
            Case.Stations, Case.Every, Case.bBothSides ? TEXT("both sides") : TEXT("one side"));
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, Case.Stations);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmFence(*Structure);
        Structure->Underpass.ColumnEvery = Case.Every;
        Structure->Underpass.bFenceBothSides = Case.bBothSides;
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        const TArray<double> ColumnXs = ColumnCentreX(*Structure);
        TestEqual(*(Label + TEXT(": the column stations")), ColumnXs.Num(), ExpectedColumnStations(Case.Stations, Case.Every));
        const int32 Sides = Case.bBothSides ? 2 : 1;
        const int32 Expected = ExpectedFencePanels(ColumnXs, EngineShapeCm, Sides);
        TestTrue(Label + TEXT(": fixture, the gaps hold several tiles"), Expected >= 3 * (ColumnXs.Num() - 1) * Sides);
        TestEqual(*(Label + TEXT(": tiles per gap x sides")), Structure->UnderpassFencePanelCount, Expected);
        TestEqual(*(Label + TEXT(": the count is the fence layers' instances")), FenceLayerInstances(*Structure), Expected);
        TestEqual(*(Label + TEXT(": no overlay without an overlay mesh")), Structure->UnderpassFenceOverlayCount, 0);
        FString Why;
        const bool bFilled = TilesFillTheGaps(ReadFence(*Structure), ColumnXs, EngineShapeCm, Sides, Why);
        TestTrue(FString::Printf(TEXT("%s: every gap is tiled edge to edge (%s)"), *Label, *Why), bFilled);
        int32 PositiveSide = 0;
        for (const FFenceRead& Panel : ReadFence(*Structure))
        {
            PositiveSide += Panel.Box.GetCenter().Y > 0.0 ? 1 : 0;
        }
        TestEqual(*(Label + TEXT(": +Y side panels")), PositiveSide, Case.bBothSides ? Expected / 2 : 0);
        TestTrue(Label + TEXT(": the structure is current"), Structure->IsStructureCurrent());
        World->DestroyWorld(false);
    }

    // The census key, appended after the tube lights. The catwalk is off here and
    // on in every case above, so this line is logged exactly once.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    Structure->Underpass.bCatwalk = false;
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    if (Stations.Num() != 5)
    {
        AddError(TEXT("Census: stations did not gather."));
        World->DestroyWorld(false);
        return false;
    }
    // Column centres at stations 0, 2 and 4, the end ones stepped 70 cm inside.
    const double EndInsetCm = FMath::Max(Structure->Underpass.PierSizeCm, Structure->Underpass.ColumnDepthCm) * 0.5;
    const TArray<double> PlannedXs = {
        Stations[0].StationWorld.GetLocation().X + EndInsetCm,
        Stations[2].StationWorld.GetLocation().X,
        Stations[4].StationWorld.GetLocation().X - EndInsetCm };
    const int32 Planned = ExpectedFencePanels(PlannedXs, EngineShapeCm, 2);
    AddExpectedMessagePlain(
        *FString::Printf(TEXT("underpass_catwalks=0 underpass_tubes=0 underpass_tube_lights=0 underpass_fence_panels=%d"), Planned),
        ELogVerbosity::Display,
        EAutomationExpectedMessageFlags::Contains,
        1);
    TestTrue(TEXT("Census: builds"), Structure->MaterializeStructure());
    TestEqual(TEXT("Census: the planned count is the built count"), Structure->UnderpassFencePanelCount, Planned);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFencePlacementTest,
    "InfinityStage.Structure.UnderpassFencePanelsStandBetweenTheColumns",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFencePlacementTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 5);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    // Off the defaults, so each value is shown to come from its own setting.
    Underpass.FenceBaseCm = 20.0;
    Underpass.FenceInsetCm = 90.0;
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());

    const double FloorCm = Structure->Ground.FloorHeightCm;
    const double ColumnLineCm = Structure->GridHalfWidthCm + Underpass.ColumnOutsetCm;
    const TArray<double> ColumnXs = ColumnCentreX(*Structure);
    TestEqual(TEXT("Fixture: three column stations"), ColumnXs.Num(), 3);

    const auto CheckPanels = [&](const FString& Label, const double LateralCm, const double HeightCm)
    {
        const FInfinityStageUnderpassSettings& Set = Structure->Underpass;
        const TArray<FFenceRead> Panels = ReadFence(*Structure);
        const int32 Expected = ExpectedFencePanels(ColumnXs, EngineShapeCm, 2);
        bool bPlaced = Panels.Num() == Expected && Expected > 0;
        bool bInward = bPlaced;
        bool bData = bPlaced;
        for (const FFenceRead& Panel : Panels)
        {
            const FVector Centre = Panel.Box.GetCenter();
            const FVector Size = Panel.Box.GetSize();
            bPlaced &= FMath::IsNearlyEqual(Panel.Box.Min.Z, FloorCm + Set.FenceBaseCm, 0.1)
                && FMath::IsNearlyEqual(Panel.Box.Max.Z, FloorCm + Set.FenceBaseCm + HeightCm, 0.1)
                && FMath::IsNearlyEqual(FMath::Abs(Centre.Y), LateralCm, 0.1)
                // The cube's own depth, unscaled.
                && FMath::IsNearlyEqual(Size.Y, EngineShapeCm, 0.1);
            // Local +Y faces the route on both sides.
            bInward &= Panel.Transform.GetUnitAxis(EAxis::Y).Y * FMath::Sign(Centre.Y) < -0.9999
                && Panel.Transform.GetUnitAxis(EAxis::Z).Z > 0.9999;
            bData &= Panel.Data[0] >= 0.0f && Panel.Data[0] < 1.0f
                && FMath::IsNearlyEqual(Panel.Data[1], static_cast<float>(Size.X), 0.01f)
                && FMath::IsNearlyEqual(Panel.Data[2], static_cast<float>(EngineShapeCm), 0.01f)
                && FMath::IsNearlyEqual(Panel.Data[3], static_cast<float>(HeightCm), 0.01f);
        }
        TestTrue(Label + TEXT(": every tile from base to base + height, on the inset line, at the mesh's own depth"), bPlaced);
        FString Why;
        const bool bFilled = TilesFillTheGaps(Panels, ColumnXs, EngineShapeCm, 2, Why);
        TestTrue(FString::Printf(TEXT("%s: each gap tiled from one column centre to the next (%s)"), *Label, *Why), bFilled);
        TestTrue(Label + TEXT(": each tile's +Y faces the route, upright"), bInward);
        TestTrue(Label + TEXT(": custom data is tone 0..1, then length, depth and height"), bData);
    };
    // Native: the cube's own 100 cm, whatever the intended height says.
    CheckPanels(TEXT("Native, inset 90, base 20"), ColumnLineCm - 90.0, EngineShapeCm);

    // Control: no inset puts the tiles on the column line itself, so the inset is
    // read; Fit builds the intended height instead of the mesh's.
    Underpass.FenceInsetCm = 0.0;
    Underpass.FenceBaseCm = 0.0;
    Underpass.FenceHeightCm = 250.0;
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Fit;
    TestTrue(TEXT("Builds fitted, with no inset"), Structure->MaterializeStructure());
    CheckPanels(TEXT("Fit 250, inset 0, base 0"), ColumnLineCm, 250.0);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceTilingTest,
    "InfinityStage.Structure.UnderpassFenceTilesFollowTheGapAndNativeWidth",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceTilingTest::RunTest(const FString& Parameters)
{
    // Gaps of 1.1 to 10.3 native widths (the cube's 100 cm), a column on each
    // station. The end gaps lose the 70 cm end inset: 430 each.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnSpacedPassage(*World, { 500.0, 110.0, 160.0, 250.0, 330.0, 1030.0, 500.0 });
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.ColumnEvery = 1;
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());
    const TArray<double> ColumnXs = ColumnCentreX(*Structure);
    TestEqual(TEXT("Fixture: a column on each of the 8 stations"), ColumnXs.Num(), 8);

    const auto CheckScales = [&](const FString& Label, const double ZScale)
    {
        const TArray<FFenceRead> Panels = ReadFence(*Structure);
        TestEqual(*(Label + TEXT(": tiles per gap x sides")), Panels.Num(), ExpectedFencePanels(ColumnXs, EngineShapeCm, 2));
        FString Why;
        const bool bFilled = TilesFillTheGaps(Panels, ColumnXs, EngineShapeCm, 2, Why);
        TestTrue(FString::Printf(TEXT("%s: each gap holds max(1, round(gap / width)) equal tiles (%s)"), *Label, *Why), bFilled);
        int32 Bounded = 0;
        for (int32 Gap = 0; Gap + 1 < ColumnXs.Num(); ++Gap)
        {
            const double GapCm = ColumnXs[Gap + 1] - ColumnXs[Gap];
            const double Ratio = GapCm / EngineShapeCm;
            const double Want = GapCm / (ExpectedTiles(GapCm, EngineShapeCm) * EngineShapeCm);
            bool bScale = true;
            for (const FFenceRead& Panel : Panels)
            {
                const double X = Panel.Box.GetCenter().X;
                if (X > ColumnXs[Gap] && X < ColumnXs[Gap + 1])
                {
                    const FVector Scale = Panel.Transform.GetScale3D();
                    bScale &= FMath::IsNearlyEqual(Scale.X, Want, 1.0e-4) && FMath::IsNearlyEqual(Scale.Y, 1.0, 1.0e-4)
                        && FMath::IsNearlyEqual(Scale.Z, ZScale, 1.0e-4);
                }
            }
            TestTrue(FString::Printf(TEXT("%s: gap %.0f cm, X scale %.3f, depth 1, Z %.3f"), *Label, GapCm, Want, ZScale), bScale);
            // The rounding rule keeps X within [0.85, 1.2] except for ratios in
            // (1.2, 1.7) (one tile, stretched) and [2.4, 2.55) (two stretched or
            // three squeezed): there no whole number of tiles can.
            const bool bReachable = Ratio >= 1.0 && !(Ratio > 1.2 && Ratio < 1.7) && !(Ratio >= 2.4 && Ratio < 2.55);
            if (bReachable)
            {
                ++Bounded;
                TestTrue(FString::Printf(TEXT("%s: gap ratio %.2f keeps X scale %.3f within [0.85, 1.2]"), *Label, Ratio, Want),
                    Want >= 0.85 && Want <= 1.2);
            }
            else
            {
                AddInfo(FString::Printf(TEXT("%s: gap ratio %.2f has X scale %.3f (outside the reachable band)"), *Label, Ratio, Want));
            }
        }
        TestTrue(FString::Printf(TEXT("%s: fixture, at least five gaps are held to the band (%d)"), *Label, Bounded), Bounded >= 5);
    };
    CheckScales(TEXT("Native"), 1.0);

    // Native leaves the mesh's height whatever the intended height, and warns once
    // per built variant when that is more than 10 % away from it.
    Underpass.FenceHeightCm = 300.0;
    AddExpectedMessagePlain(TEXT("INFINITY_STAGE_STRUCTURE_FENCE_HEIGHT_MISMATCH"), ELogVerbosity::Warning,
        EAutomationExpectedMessageFlags::Contains, FenceVariantTotal);
    TestTrue(TEXT("Builds native with 300 intended"), Structure->MaterializeStructure());
    CheckScales(TEXT("Native, 300 intended"), 1.0);
    // Within 10 %: no warning (one more would break the exact count above).
    Underpass.FenceHeightCm = 108.0;
    TestTrue(TEXT("Builds native with 108 intended"), Structure->MaterializeStructure());

    // Control: Fit stretches Z to the intended height (and does not warn), with the
    // same tiles, so the Native checks above can fail.
    Underpass.FenceHeightCm = 300.0;
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Fit;
    TestTrue(TEXT("Builds fitted to 300"), Structure->MaterializeStructure());
    CheckScales(TEXT("Control, Fit 300"), 3.0);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceEndsTest,
    "InfinityStage.Structure.UnderpassFenceKeepsThePassageEndsClean",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceEndsTest::RunTest(const FString& Parameters)
{
    // 5 stations end on a column station by the rhythm; 4 get one added at the end.
    for (const int32 StationTotal : { 5, 4 })
    {
        const FString Label = FString::Printf(TEXT("%d stations"), StationTotal);
        UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
        AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, StationTotal);
        AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
        ArmFence(*Structure);
        FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
        // Overlays on every variant, so they are held to the ends too.
        for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
        {
            FenceVariant(Underpass, Variant).OverlayMesh = FenceVariant(Underpass, Variant).Mesh;
        }
        TestTrue(Label + TEXT(": builds"), Structure->MaterializeStructure());
        const TArray<double> Xs = FixtureStationX(*Structure);
        if (Xs.Num() != StationTotal)
        {
            AddError(Label + TEXT(": stations did not gather."));
            World->DestroyWorld(false);
            return false;
        }
        const double EndInsetCm = FMath::Max(Underpass.PierSizeCm, Underpass.ColumnDepthCm) * 0.5;
        TArray<FFenceRead> Pieces = ReadFence(*Structure);
        const int32 PanelTotal = Pieces.Num();
        Pieces.Append(ReadFence(*Structure, FenceOverlayTags));
        TestTrue(Label + TEXT(": panels and as many overlays were built"),
            PanelTotal > 0 && Pieces.Num() == 2 * PanelTotal && Structure->UnderpassFenceOverlayCount == PanelTotal);
        double MinX = TNumericLimits<double>::Max();
        double MaxX = TNumericLimits<double>::Lowest();
        bool bInside = Pieces.Num() > 0;
        for (const FFenceRead& Piece : Pieces)
        {
            bInside &= Piece.Box.Min.X >= Xs[0] - 0.5 && Piece.Box.Max.X <= Xs.Last() + 0.5;
            MinX = FMath::Min(MinX, Piece.Box.Min.X);
            MaxX = FMath::Max(MaxX, Piece.Box.Max.X);
        }
        TestTrue(Label + TEXT(": no panel or overlay passes the first or last station"), bInside);
        // Controls, so the bound above measures a real edge: the fence reaches the
        // end columns, which stand stepped inside the end stations.
        TestTrue(FString::Printf(TEXT("%s: the fence starts at the first column (%.2f)"), *Label, MinX - Xs[0]),
            FMath::IsNearlyEqual(MinX, Xs[0] + EndInsetCm, 0.5));
        TestTrue(FString::Printf(TEXT("%s: the fence ends at the last column (%.2f)"), *Label, Xs.Last() - MaxX),
            FMath::IsNearlyEqual(MaxX, Xs.Last() - EndInsetCm, 0.5));
        const TArray<double> ColumnXs = ColumnCentreX(*Structure);
        TestTrue(Label + TEXT(": the end columns stand where the fence ends"),
            ColumnXs.Num() >= 2 && FMath::IsNearlyEqual(ColumnXs[0], MinX, 0.5) && FMath::IsNearlyEqual(ColumnXs.Last(), MaxX, 0.5));
        World->DestroyWorld(false);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceVariantsTest,
    "InfinityStage.Structure.UnderpassFenceVariantsAreSeededAndWeighted",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceVariantsTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Cylinder(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    if (!Cube.LoadSynchronous() || !Cylinder.LoadSynchronous())
    {
        AddError(TEXT("Fixture: the engine cube or cylinder does not load."));
        return false;
    }
    TestTrue(TEXT("Fixture: the cylinder is as wide as the cube, so swapping them keeps the tiling"),
        FMath::IsNearlyEqual(Cylinder.LoadSynchronous()->GetBoundingBox().GetSize().X, EngineShapeCm, 0.01));
    // 21 stations with a column on each: 20 gaps of several tiles a side.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 21);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.ColumnEvery = 1;
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());
    const TMap<FIntPoint, int32> First = FenceChoices(ReadFence(*Structure));
    const int32 PanelTotal = Structure->UnderpassFencePanelCount;
    TestTrue(FString::Printf(TEXT("Fixture: %d tiles, at least 150, each in its own place"), PanelTotal),
        PanelTotal >= 150 && First.Num() == PanelTotal);

    // The same seed chooses the same variant everywhere.
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    TestTrue(TEXT("The same seed rebuilds the same choices"), FenceChoices(ReadFence(*Structure)).OrderIndependentCompareEqual(First));

    // Another seed re-rolls the choices and moves nothing. About 0.575 of tiles
    // change for these weights; 0.3 is far below that and far above zero.
    Underpass.FenceSeed = 7;
    TestTrue(TEXT("Builds with seed 7"), Structure->MaterializeStructure());
    const TMap<FIntPoint, int32> Reseeded = FenceChoices(ReadFence(*Structure));
    int32 Changed = 0;
    bool bSamePlaces = Reseeded.Num() == First.Num();
    for (const TPair<FIntPoint, int32>& Pair : First)
    {
        const int32* After = Reseeded.Find(Pair.Key);
        bSamePlaces &= After != nullptr;
        Changed += After && *After != Pair.Value ? 1 : 0;
    }
    TestTrue(TEXT("Another seed keeps every tile where it was"), bSamePlaces);
    TestTrue(FString::Printf(TEXT("Another seed re-rolls the choices (%d of %d changed)"), Changed, PanelTotal),
        Changed >= PanelTotal * 3 / 10);
    // Neighbouring tiles of one gap draw independently: the gaps are not all one variant each.
    Underpass.FenceSeed = 0;

    // Changing one variant's mesh re-rolls nothing.
    Underpass.FenceVariantB.Mesh = Cylinder;
    TestTrue(TEXT("Builds with variant B on the cylinder"), Structure->MaterializeStructure());
    TestTrue(TEXT("A new mesh for B keeps every tile's choice"), FenceChoices(ReadFence(*Structure)).OrderIndependentCompareEqual(First));
    const UInstancedStaticMeshComponent* LayerB = FindLayer(*Structure, FenceVariantTags[1]);
    TestTrue(TEXT("Control: B's layer now wears the cylinder"), LayerB && LayerB->GetStaticMesh() == Cylinder.LoadSynchronous());
    Underpass.FenceVariantB.Mesh = Cube;

    // A null variant is skipped, and only the tiles that drew it are re-dealt.
    Underpass.FenceVariantC.Mesh = nullptr;
    TestTrue(TEXT("Builds with variant C null"), Structure->MaterializeStructure());
    const TMap<FIntPoint, int32> Nulled = FenceChoices(ReadFence(*Structure));
    int32 FormerC = 0;
    bool bOthersKept = Nulled.Num() == PanelTotal;
    bool bRedealt = true;
    for (const TPair<FIntPoint, int32>& Pair : First)
    {
        const int32* After = Nulled.Find(Pair.Key);
        if (Pair.Value == 2)
        {
            ++FormerC;
            bRedealt &= After && *After != 2;
        }
        else
        {
            bOthersKept &= After && *After == Pair.Value;
        }
    }
    TestTrue(TEXT("C null: no C layer and the count unchanged"),
        FindLayer(*Structure, FenceVariantTags[2]) == nullptr && Structure->UnderpassFencePanelCount == PanelTotal);
    TestTrue(TEXT("C null: every tile that did not draw C keeps its variant"), bOthersKept);
    TestTrue(FString::Printf(TEXT("C null: C's %d tiles went to the other variants"), FormerC), bRedealt && FormerC > 0);
    TestTrue(TEXT("Rebuilds with C null"), Structure->MaterializeStructure());
    TestTrue(TEXT("C null: the re-deal is deterministic"), FenceChoices(ReadFence(*Structure)).OrderIndependentCompareEqual(Nulled));

    // The mix over thousands of tiles, the full kit and with C null: each share
    // within 4.5 standard deviations of its weight's share (of the built weights).
    constexpr int32 Seeds = 12;
    int32 Full[FenceVariantTotal] = {};
    int32 WithoutC[FenceVariantTotal] = {};
    bool bAllBuilt = true;
    for (int32 Seed = 0; Seed < Seeds; ++Seed)
    {
        Underpass.FenceSeed = 1000 + Seed;
        Underpass.FenceVariantC.Mesh = Cube;
        bAllBuilt &= Structure->MaterializeStructure();
        for (const FFenceRead& Panel : ReadFence(*Structure))
        {
            ++Full[Panel.Variant];
        }
        Underpass.FenceVariantC.Mesh = nullptr;
        bAllBuilt &= Structure->MaterializeStructure();
        for (const FFenceRead& Panel : ReadFence(*Structure))
        {
            ++WithoutC[Panel.Variant];
        }
    }
    TestTrue(TEXT("Every seeded build succeeded"), bAllBuilt);
    const double Weights[FenceVariantTotal] = { 0.6, 0.2, 0.15, 0.05 };
    const double Samples = static_cast<double>(Seeds * PanelTotal);
    TestEqual(TEXT("Control: every full build was counted"), Full[0] + Full[1] + Full[2] + Full[3], Seeds * PanelTotal);
    TestEqual(TEXT("Control: every C-null build was counted"),
        WithoutC[0] + WithoutC[1] + WithoutC[2] + WithoutC[3], Seeds * PanelTotal);
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        const double Want = Weights[Variant];
        const double Share = Full[Variant] / Samples;
        const double Tolerance = 4.5 * FMath::Sqrt(Want * (1.0 - Want) / Samples);
        TestTrue(FString::Printf(TEXT("Full kit: %s's share %.3f is within %.3f of %.3f"),
            FenceVariantTags[Variant], Share, Tolerance, Want), FMath::Abs(Share - Want) <= Tolerance);
        const double WantNull = Variant == 2 ? 0.0 : Want / (1.0 - Weights[2]);
        const double ShareNull = WithoutC[Variant] / Samples;
        const double ToleranceNull = Variant == 2 ? 0.0 : 4.5 * FMath::Sqrt(WantNull * (1.0 - WantNull) / Samples);
        TestTrue(FString::Printf(TEXT("C null: %s's share %.3f is within %.3f of %.3f"),
            FenceVariantTags[Variant], ShareNull, ToleranceNull, WantNull), FMath::Abs(ShareNull - WantNull) <= ToleranceNull + 1.0e-12);
    }
    // Control: the two mixes are told apart, so the share checks can fail.
    TestTrue(TEXT("Control: A's share with C null differs from the full kit's by more than the tolerance"),
        FMath::Abs(0.6 / 0.85 - 0.6) > 4.5 * FMath::Sqrt(0.6 * 0.4 / Samples));

    // Every variant null: no fence, and no error.
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).Mesh = nullptr;
    }
    TestTrue(TEXT("Builds with every variant null"), Structure->MaterializeStructure());
    TestTrue(TEXT("Every variant null: no tile"),
        Structure->UnderpassFencePanelCount == 0 && FindLayer(*Structure, FenceTag) == nullptr);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageUnderpassFenceMaterialsTest,
    "InfinityStage.Structure.UnderpassFenceVariantsWearTheirOwnMaterials",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageUnderpassFenceMaterialsTest::RunTest(const FString& Parameters)
{
    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Cylinder(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    // Five distinct surface materials, none the cube's own (WorldGridMaterial here).
    const TSoftObjectPtr<UMaterialInterface> Paints[] = {
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/M_SimpleOpaque.M_SimpleOpaque"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/DebugMeshMaterial.DebugMeshMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/TangentColorMaterial.TangentColorMaterial"))),
        TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Engine/EngineDebugMaterials/LevelColorationLitMaterial.LevelColorationLitMaterial"))),
    };
    constexpr int32 PaintTotal = UE_ARRAY_COUNT(Paints);
    if (!Cube.LoadSynchronous() || !Cylinder.LoadSynchronous())
    {
        AddError(TEXT("Fixture: the engine cube or cylinder does not load."));
        return false;
    }
    for (int32 Index = 0; Index < PaintTotal; ++Index)
    {
        if (!Paints[Index].LoadSynchronous())
        {
            AddError(FString::Printf(TEXT("Fixture: material %s does not load."), *Paints[Index].ToSoftObjectPath().ToString()));
            return false;
        }
        TestTrue(TEXT("Fixture: no test material is the cube's or the cylinder's own"),
            Cube.LoadSynchronous()->GetMaterial(0) != Paints[Index].LoadSynchronous()
            && Cylinder.LoadSynchronous()->GetMaterial(0) != Paints[Index].LoadSynchronous());
        for (int32 Other = Index + 1; Other < PaintTotal; ++Other)
        {
            TestTrue(TEXT("Fixture: the test materials are distinct"),
                Paints[Index].LoadSynchronous() != Paints[Other].LoadSynchronous());
        }
    }

    // 11 stations, a column on each: dozens of tiles at equal weights, so every
    // variant is drawn.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 11);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.ColumnEvery = 1;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).Weight = 0.25;
        FenceVariant(Underpass, Variant).Material = Paints[Variant];
    }
    // D on its own mesh, and A with an overlay in a fifth material.
    Underpass.FenceVariantD.Mesh = Cylinder;
    Underpass.FenceVariantA.OverlayMesh = Cylinder;
    Underpass.FenceVariantA.OverlayMaterial = Paints[4];
    TestTrue(TEXT("Builds"), Structure->MaterializeStructure());

    const auto CheckLayers = [&](const FString& Label, const bool bShadow, const bool bPainted)
    {
        for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
        {
            const UInstancedStaticMeshComponent* Layer = FindLayer(*Structure, FenceVariantTags[Variant]);
            if (!Layer)
            {
                AddError(FString::Printf(TEXT("%s: fixture, no tile drew %s."), *Label, FenceVariantTags[Variant]));
                continue;
            }
            const UStaticMesh* Mesh = (Variant == 3 ? Cylinder : Cube).LoadSynchronous();
            const UMaterialInterface* Expected = bPainted || Variant != 0 ? Paints[Variant].LoadSynchronous() : Mesh->GetMaterial(0);
            TestTrue(FString::Printf(TEXT("%s: %s wears its own material"), *Label, FenceVariantTags[Variant]),
                Layer->GetMaterial(0) == Expected);
            TestTrue(FString::Printf(TEXT("%s: %s is built from its own mesh"), *Label, FenceVariantTags[Variant]),
                Layer->GetStaticMesh() == Mesh);
            TestTrue(FString::Printf(TEXT("%s: %s casts shadow as set"), *Label, FenceVariantTags[Variant]),
                static_cast<bool>(Layer->CastShadow) == bShadow);
            TestTrue(FString::Printf(TEXT("%s: %s carries the fence tag"), *Label, FenceVariantTags[Variant]),
                Layer->ComponentTags.Contains(FName(FenceTag)));
        }
        const UInstancedStaticMeshComponent* PanelsA = FindLayer(*Structure, FenceVariantTags[0]);
        const UInstancedStaticMeshComponent* OverlayA = FindLayer(*Structure, FenceOverlayTags[0]);
        bool bRides = PanelsA && OverlayA && OverlayA->GetInstanceCount() == PanelsA->GetInstanceCount();
        if (bRides)
        {
            const TArray<FTransform> Under = ReadInstances(*PanelsA);
            const TArray<FTransform> Over = ReadInstances(*OverlayA);
            for (int32 Index = 0; bRides && Index < Under.Num(); ++Index)
            {
                bRides = Over[Index].Equals(Under[Index], 1.0e-4);
            }
        }
        TestTrue(Label + TEXT(": A's overlay rides A's tiles, transform for transform"), bRides);
        TestTrue(Label + TEXT(": the overlay count is A's tiles"),
            PanelsA && Structure->UnderpassFenceOverlayCount == PanelsA->GetInstanceCount());
        TestTrue(Label + TEXT(": the overlay wears its own material and mesh, and casts as set"),
            OverlayA && OverlayA->GetMaterial(0) == Paints[4].LoadSynchronous()
            && OverlayA->GetStaticMesh() == Cylinder.LoadSynchronous() && static_cast<bool>(OverlayA->CastShadow) == bShadow);
        bool bNoOtherOverlay = true;
        for (int32 Variant = 1; Variant < FenceVariantTotal; ++Variant)
        {
            bNoOtherOverlay &= FindLayer(*Structure, FenceOverlayTags[Variant]) == nullptr;
        }
        TestTrue(Label + TEXT(": no overlay where none is set"), bNoOtherOverlay);
    };
    TestTrue(TEXT("The fence casts shadow by default"), Underpass.bFenceCastShadow);
    CheckLayers(TEXT("Painted"), true, true);

    // Control: no shadow and no material for A read back as set, so each value
    // comes from its own setting.
    Underpass.bFenceCastShadow = false;
    Underpass.FenceVariantA.Material = nullptr;
    TestTrue(TEXT("Builds without shadows, A unpainted"), Structure->MaterializeStructure());
    CheckLayers(TEXT("Control, no shadow, A unpainted"), false, false);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());

    World->DestroyWorld(false);
    return true;
}

// ---------------------------------------------------------------------------
// Tubes everywhere (patch TU, 6 Oct): fence-top rows, per-row light switches, a
// low-glow level, and a deterministic blinking share. Every new field defaults
// to the 5 Oct behaviour, which the first test proves byte for byte.
// ---------------------------------------------------------------------------
namespace
{
struct FEverywhereTube
{
    int32 Row = INDEX_NONE;
    int32 Index = INDEX_NONE;
    float Random = -1.0f;
    float Level = -1.0f;
    FVector Centre = FVector::ZeroVector;
    bool bBlinkComponent = false;
};

/** Every tube in every tube-tagged component (the steady one and the blinkers'). */
TArray<FEverywhereTube> ReadEveryTube(const AInfinityStageStructureActor& Structure)
{
    TArray<FEverywhereTube> Tubes;
    for (const UInstancedStaticMeshComponent* Layer : Structure.ManagedComponents)
    {
        if (!Layer || !Layer->ComponentTags.Contains(FName(TubeTag)) || Layer->NumCustomDataFloats < 4)
        {
            continue;
        }
        const FBox MeshBounds = Layer->GetStaticMesh()->GetBoundingBox();
        const TArray<FTransform> Instances = ReadInstances(*Layer);
        for (int32 Instance = 0; Instance < Instances.Num(); ++Instance)
        {
            const float* Data = Layer->PerInstanceSMCustomData.GetData() + Instance * Layer->NumCustomDataFloats;
            FEverywhereTube& Tube = Tubes.AddDefaulted_GetRef();
            Tube.Row = FMath::RoundToInt32(Data[0]);
            Tube.Index = FMath::RoundToInt32(Data[1]);
            Tube.Random = Data[2];
            Tube.Level = Data[3];
            Tube.Centre = MeshBounds.TransformBy(Instances[Instance]).GetCenter();
            Tube.bBlinkComponent = Layer == Structure.UnderpassTubeBlinkComponent.Get();
        }
    }
    Tubes.Sort([](const FEverywhereTube& A, const FEverywhereTube& B)
        { return A.Row != B.Row ? A.Row < B.Row : A.Index < B.Index; });
    return Tubes;
}

bool SameTubeIdentity(const TArray<FEverywhereTube>& A, const TArray<FEverywhereTube>& B, const int32 MaxRow, FString& OutWhy)
{
    TArray<const FEverywhereTube*> FA;
    TArray<const FEverywhereTube*> FB;
    for (const FEverywhereTube& Tube : A) { if (Tube.Row <= MaxRow) { FA.Add(&Tube); } }
    for (const FEverywhereTube& Tube : B) { if (Tube.Row <= MaxRow) { FB.Add(&Tube); } }
    if (FA.Num() != FB.Num())
    {
        OutWhy = FString::Printf(TEXT("%d tubes != %d"), FA.Num(), FB.Num());
        return false;
    }
    for (int32 Index = 0; Index < FA.Num(); ++Index)
    {
        if (FA[Index]->Row != FB[Index]->Row || FA[Index]->Index != FB[Index]->Index
            || FA[Index]->Random != FB[Index]->Random || !FA[Index]->Centre.Equals(FB[Index]->Centre, 1.0e-3)
            || (FA[Index]->Level > 0.0f) != (FB[Index]->Level > 0.0f))
        {
            OutWhy = FString::Printf(TEXT("tube row %d index %d differs"), FA[Index]->Row, FA[Index]->Index);
            return false;
        }
    }
    return true;
}

void ArmTubesEverywhere(AInfinityStageStructureActor& Structure)
{
    ArmTubes(Structure);
    Structure.Underpass.bTubeLights = true;
    Structure.Underpass.TubeLightEvery = 1;
    Structure.Underpass.TubeLightMax = 2000;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageTubesEverywhereDefaultsTest,
    "InfinityStage.Structure.TubesEverywhere.DefaultsBuildExactlyAsBefore",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageTubesEverywhereDefaultsTest::RunTest(const FString& Parameters)
{
    const FInfinityStageUnderpassSettings Defaults;
    TestTrue(TEXT("Defaults: every row emits light, no fence-top rows, full glow, no blinking"),
        Defaults.bTubeCentreRowsEmitLight && Defaults.bTubeCornerRowsEmitLight && Defaults.bTubeFenceTopRowsEmitLight
        && !Defaults.bTubeFenceTopRows && FMath::IsNearlyEqual(Defaults.TubeGlowLevel, 1.0f)
        && FMath::IsNearlyEqual(Defaults.TubeBlinkFraction, 0.0));

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 6);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubes(*Structure);
    Structure->Underpass.bTubeLights = true;
    TestTrue(TEXT("Builds with the 5 Oct tube settings"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Before = SnapshotBuild(*Structure);
    TArray<FVector> LightsBefore;
    for (const URectLightComponent* Light : TaggedTubeLights(*Structure))
    {
        LightsBefore.Add(Light->GetComponentLocation());
    }
    const TArray<FTubeRead> TubesBefore = ReadTubes(*Structure);
    TestTrue(TEXT("Control: tubes and lights exist"), TubesBefore.Num() > 0 && LightsBefore.Num() > 0);
    TestTrue(TEXT("No blinkers and no blink component by default"),
        Structure->UnderpassTubeBlinkers.IsEmpty() && Structure->UnderpassTubeBlinkComponent == nullptr);
    bool bAliveIsOne = true;
    for (const FTubeRead& Tube : TubesBefore)
    {
        bAliveIsOne &= Tube.Alive == 0.0f || Tube.Alive == 1.0f;
    }
    TestTrue(TEXT("[3] is still exactly 1 alive / 0 dead at the default glow"), bAliveIsOne);

    // Control: a low glow changes [3] of the live tubes only, and nothing else.
    Structure->Underpass.TubeGlowLevel = 0.15f;
    TestTrue(TEXT("Builds at a low glow"), Structure->MaterializeStructure());
    const TArray<FTubeRead> Glowing = ReadTubes(*Structure);
    bool bGlowOnlyLevel = Glowing.Num() == TubesBefore.Num();
    for (int32 Index = 0; bGlowOnlyLevel && Index < Glowing.Num(); ++Index)
    {
        bGlowOnlyLevel = Glowing[Index].Transform.Equals(TubesBefore[Index].Transform, 1.0e-4)
            && Glowing[Index].Random == TubesBefore[Index].Random
            && Glowing[Index].Alive == (TubesBefore[Index].Alive > 0.5f ? 0.15f : 0.0f);
    }
    TestTrue(TEXT("Low glow: [3] = 0.15 alive, 0 dead; transforms and randoms unchanged"), bGlowOnlyLevel);
    TestEqual(TEXT("Low glow does not change the lights"), TaggedTubeLights(*Structure).Num(), LightsBefore.Num());

    // And back to the default: byte-identical to the first build.
    Structure->Underpass.TubeGlowLevel = 1.0f;
    TestTrue(TEXT("Rebuilds at the default glow"), Structure->MaterializeStructure());
    FString Why;
    TestTrue(FString::Printf(TEXT("Defaults again: every component identical (%s)"), *Why),
        SameBuild(Before, SnapshotBuild(*Structure), Why));
    TArray<URectLightComponent*> LightsAfter = TaggedTubeLights(*Structure);
    bool bSameLights = LightsAfter.Num() == LightsBefore.Num();
    for (int32 Index = 0; bSameLights && Index < LightsAfter.Num(); ++Index)
    {
        bSameLights = LightsAfter[Index]->GetComponentLocation().Equals(LightsBefore[Index], 1.0e-3);
    }
    TestTrue(TEXT("Defaults again: the same lights in the same places"), bSameLights);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageTubesEverywhereFenceRowsTest,
    "InfinityStage.Structure.TubesEverywhere.FenceTopRowsAndPerRowLight",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageTubesEverywhereFenceRowsTest::RunTest(const FString& Parameters)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 6);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubesEverywhere(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    TestTrue(TEXT("Builds the deck rows"), Structure->MaterializeStructure());
    const TArray<FEverywhereTube> DeckOnly = ReadEveryTube(*Structure);
    const int32 DeckLights = Structure->UnderpassTubeLightCount;
    double CornerY = 0.0;
    for (const FEverywhereTube& Tube : DeckOnly)
    {
        CornerY = FMath::Max(CornerY, FMath::Abs(Tube.Centre.Y));
    }

    Underpass.bTubeFenceTopRows = true;
    TestTrue(TEXT("Builds with fence-top rows"), Structure->MaterializeStructure());
    const TArray<FEverywhereTube> WithFence = ReadEveryTube(*Structure);
    const int32 DeckRows = Underpass.TubeRowsCentre + 2;
    FString Why;
    TestTrue(FString::Printf(TEXT("Adding fence-top rows re-rolls and moves no deck tube (%s)"), *Why),
        SameTubeIdentity(DeckOnly, WithFence, DeckRows - 1, Why));

    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    const double StationZ = Stations.IsEmpty() ? 0.0 : Stations[0].StationWorld.GetLocation().Z;
    const double ExpectedLineY = CornerY - Underpass.FenceInsetCm;
    const double ExpectedZ = StationZ + Structure->Ground.FloorHeightCm + Underpass.FenceBaseCm
        + Underpass.FenceHeightCm + Underpass.TubeFenceTopRaiseCm;
    int32 FenceTubes = 0;
    bool bOnLine = true;
    bool bBothSides[2] = { false, false };
    for (const FEverywhereTube& Tube : WithFence)
    {
        if (Tube.Row < DeckRows)
        {
            continue;
        }
        ++FenceTubes;
        bOnLine &= FMath::IsNearlyEqual(FMath::Abs(Tube.Centre.Y), ExpectedLineY, 0.5)
            && FMath::IsNearlyEqual(Tube.Centre.Z, ExpectedZ, 0.5);
        bBothSides[Tube.Centre.Y > 0.0 ? 1 : 0] = true;
    }
    TestTrue(TEXT("Two fence-top rows, as many tubes as a deck row each"),
        FenceTubes > 0 && FenceTubes * DeckRows == DeckOnly.Num() * 2);
    TestTrue(TEXT("Fence-top tubes on the fence line, above the fence's top"), bOnLine);
    TestTrue(TEXT("One row each side"), bBothSides[0] && bBothSides[1]);

    // Only the fence-top rows give light (Gary: all but P02).
    Underpass.bTubeCentreRowsEmitLight = false;
    Underpass.bTubeCornerRowsEmitLight = false;
    TestTrue(TEXT("Builds with only fence-top light"), Structure->MaterializeStructure());
    const TArray<URectLightComponent*> FenceLights = TaggedTubeLights(*Structure);
    bool bFenceOnly = !FenceLights.IsEmpty();
    for (const URectLightComponent* Light : FenceLights)
    {
        bFenceOnly &= FMath::IsNearlyEqual(FMath::Abs(Light->GetComponentLocation().Y), ExpectedLineY, 0.5);
    }
    TestTrue(TEXT("Every light hangs on a fence-top tube"), bFenceOnly);
    TestTrue(TEXT("The deck tubes are still built (they glow, they light nothing)"),
        ReadEveryTube(*Structure).Num() == WithFence.Num());

    // Control: no row emitting builds no light at all.
    Underpass.bTubeFenceTopRowsEmitLight = false;
    TestTrue(TEXT("Builds with no row emitting"), Structure->MaterializeStructure());
    TestEqual(TEXT("No row emitting: no lights"), Structure->UnderpassTubeLightCount, 0);
    TestTrue(TEXT("Control: the deck rows alone had lights"), DeckLights > 0);

    // One side only, as the fence.
    Underpass.bFenceBothSides = false;
    TestTrue(TEXT("Builds with a one-sided fence"), Structure->MaterializeStructure());
    int32 PlusSide = 0;
    for (const FEverywhereTube& Tube : ReadEveryTube(*Structure))
    {
        PlusSide += Tube.Row >= DeckRows && Tube.Centre.Y > 0.0 ? 1 : 0;
    }
    TestEqual(TEXT("bFenceBothSides off: no +Y fence-top row"), PlusSide, 0);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageTubesEverywhereBlinkTest,
    "InfinityStage.Structure.TubesEverywhere.BlinkShareIsDeterministicAndSeparate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageTubesEverywhereBlinkTest::RunTest(const FString& Parameters)
{
    using T = AInfinityStageStructureActor;
    TestTrue(TEXT("Pure: lit inside the duty"), T::IsTubeBlinkOn(0.1, 0.0f, 1.0f, 1.0, 0.7));
    TestFalse(TEXT("Pure: dark after the duty"), T::IsTubeBlinkOn(0.8, 0.0f, 1.0f, 1.0, 0.7));
    TestTrue(TEXT("Pure: the phase shifts the cycle"), T::IsTubeBlinkOn(0.8, 0.5f, 1.0f, 1.0, 0.7));
    int32 StutterFlips = 0;
    bool bPrevious = T::IsTubeBlinkOn(0.92, 0.0f, 1.0f, 1.0, 0.7);
    for (double Time = 0.921; Time < 0.999; Time += 0.001)
    {
        const bool bNow = T::IsTubeBlinkOn(Time, 0.0f, 1.0f, 1.0, 0.7);
        StutterFlips += bNow != bPrevious ? 1 : 0;
        bPrevious = bNow;
    }
    TestTrue(TEXT("Pure: a stutter before it strikes again"), StutterFlips >= 4);

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 14);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmTubesEverywhere(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    TestTrue(TEXT("Builds without blinking"), Structure->MaterializeStructure());
    const TArray<FEverywhereTube> Steady = ReadEveryTube(*Structure);
    int32 Alive = 0;
    for (const FEverywhereTube& Tube : Steady)
    {
        Alive += Tube.Level > 0.0f ? 1 : 0;
    }

    Underpass.TubeBlinkFraction = 0.2;
    TestTrue(TEXT("Builds with 20% blinking"), Structure->MaterializeStructure());
    const TArray<FEverywhereTube> Blinking = ReadEveryTube(*Structure);
    FString Why;
    TestTrue(FString::Printf(TEXT("Blinking re-rolls no dead tube and moves none (%s)"), *Why),
        SameTubeIdentity(Steady, Blinking, MAX_int32, Why));
    const int32 Blinkers = Structure->UnderpassTubeBlinkers.Num();
    TestTrue(FString::Printf(TEXT("About a fifth of the %d live tubes blink (%d)"), Alive, Blinkers),
        Alive >= 40 && Blinkers >= Alive / 20 && Blinkers <= Alive * 2 / 5);
    TestNotNull(TEXT("Blinkers live in their own component"), Structure->UnderpassTubeBlinkComponent.Get());
    TestTrue(TEXT("...which is movable"), Structure->UnderpassTubeBlinkComponent
        && Structure->UnderpassTubeBlinkComponent->Mobility == EComponentMobility::Movable);
    int32 InBlinkComponent = 0;
    for (const FEverywhereTube& Tube : Blinking)
    {
        InBlinkComponent += Tube.bBlinkComponent ? 1 : 0;
    }
    TestEqual(TEXT("One blink instance per blinker"), InBlinkComponent, Blinkers);
    int32 BlinkingLights = 0;
    for (const FInfinityStageTubeBlinker& Blinker : Structure->UnderpassTubeBlinkers)
    {
        BlinkingLights += Blinker.Light ? 1 : 0;
    }
    TestTrue(TEXT("Lights on blinking hosts blink with them"), BlinkingLights > 0);

    // Deterministic: the same build twice picks the same tubes, phases and rates.
    TArray<FInfinityStageTubeBlinker> First = Structure->UnderpassTubeBlinkers;
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    bool bSame = First.Num() == Structure->UnderpassTubeBlinkers.Num();
    for (int32 Index = 0; bSame && Index < First.Num(); ++Index)
    {
        const FInfinityStageTubeBlinker& A = First[Index];
        const FInfinityStageTubeBlinker& B = Structure->UnderpassTubeBlinkers[Index];
        bSame = A.InstanceIndex == B.InstanceIndex && A.Phase == B.Phase && A.RateScale == B.RateScale;
    }
    TestTrue(TEXT("Deterministic across rebuilds"), bSame);

    // Driving: some blinker goes dark at some time; its [3] and its light follow.
    UInstancedStaticMeshComponent* BlinkComponent = Structure->UnderpassTubeBlinkComponent.Get();
    int32 Changed = 0;
    double When = 0.0;
    for (double Time = 0.0; Time < 10.0 && Changed == 0; Time += 0.05)
    {
        Changed = Structure->UpdateTubeBlinkers(Time);
        When = Time;
    }
    TestTrue(TEXT("Driving the blinkers changes some"), Changed > 0);
    bool bFollow = true;
    for (const FInfinityStageTubeBlinker& Blinker : Structure->UnderpassTubeBlinkers)
    {
        const bool bLit = T::IsTubeBlinkOn(When, Blinker.Phase, Blinker.RateScale,
            Underpass.TubeBlinkPeriodSeconds, Underpass.TubeBlinkDutyOn);
        if (BlinkComponent && Blinker.InstanceIndex != INDEX_NONE)
        {
            const float Level = BlinkComponent->PerInstanceSMCustomData[
                Blinker.InstanceIndex * BlinkComponent->NumCustomDataFloats + 3];
            bFollow &= bLit ? Level == Blinker.OnValue : Level == 0.0f;
        }
        if (Blinker.Light)
        {
            bFollow &= Blinker.Light->IsVisible() == bLit;
        }
    }
    TestTrue(TEXT("Each blinker's [3] and light match its state"), bFollow);
    TestEqual(TEXT("The same time again changes nothing"), Structure->UpdateTubeBlinkers(When), 0);
    World->DestroyWorld(false);
    return true;
}

// ---------------------------------------------------------------------------
// Fence stack (patch FS, 6 Oct; Gary: "7.5m on all passages", "Stack it"): whole
// native-height rows up to FenceHeightCm, the top row cut or rounded, doors only
// on the ground row, the fence-top tubes on the stacked top. Every non-Stack
// build is unchanged, which the first test proves against the new fields.
// ---------------------------------------------------------------------------
namespace
{
/** A stacked panel's identity: its plan centre to the cm and its row (from its bottom). */
FIntVector StackKey(const FFenceRead& Panel, const double BaseCm, const double RowCm)
{
    const FVector Centre = Panel.Box.GetCenter();
    return FIntVector(FMath::RoundToInt32(Centre.X), FMath::RoundToInt32(Centre.Y),
        FMath::RoundToInt32((Panel.Box.Min.Z - BaseCm) / RowCm));
}

TMap<FIntVector, int32> StackChoices(const TArray<FFenceRead>& Panels, const double BaseCm, const double RowCm)
{
    TMap<FIntVector, int32> Choices;
    for (const FFenceRead& Panel : Panels)
    {
        Choices.Add(StackKey(Panel, BaseCm, RowCm), Panel.Variant);
    }
    return Choices;
}

/** The fence-top tube rows' centre Z (rows numbered after the deck rows), or empty. */
TArray<double> FenceTopTubeZs(const AInfinityStageStructureActor& Structure)
{
    const int32 DeckRows = Structure.Underpass.TubeRowsCentre + (Structure.Underpass.bTubeCornerRows ? 2 : 0);
    TArray<double> Zs;
    for (const FEverywhereTube& Tube : ReadEveryTube(Structure))
    {
        if (Tube.Row >= DeckRows)
        {
            Zs.Add(Tube.Centre.Z);
        }
    }
    return Zs;
}

bool AllNear(const TArray<double>& Values, const double Want, const double Tolerance)
{
    bool bAll = !Values.IsEmpty();
    for (const double Value : Values)
    {
        bAll &= FMath::IsNearlyEqual(Value, Want, Tolerance);
    }
    return bAll;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageFenceStackDefaultsTest,
    "InfinityStage.Structure.FenceStack.DefaultsAndOtherModesBuildExactlyAsBefore",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageFenceStackDefaultsTest::RunTest(const FString& Parameters)
{
    const FInfinityStageUnderpassSettings Defaults;
    TestTrue(TEXT("Defaults: Native mode, cut top row, only D ground-row-only"),
        Defaults.FenceHeightMode == EInfinityFenceHeightMode::Native && Defaults.bFenceStackCutTopRow
        && !Defaults.FenceVariantA.bGroundRowOnly && !Defaults.FenceVariantB.bGroundRowOnly
        && !Defaults.FenceVariantC.bGroundRowOnly && Defaults.FenceVariantD.bGroundRowOnly);

    // The plan, written out for the real kit (SM_FenceBay_short_open, 302.68 cm,
    // FV3FBS-20261005-01) and for edge cases.
    using T = AInfinityStageStructureActor;
    const double KitCm = 302.676;
    const FInfinityStageFenceStackPlan Cut750 = T::PlanFenceStack(750.0, KitCm, true);
    TestTrue(FString::Printf(TEXT("750 cut: 3 rows, top row %.2f, top 750 (got %d, %.2f, %.2f)"),
            750.0 - 2.0 * KitCm, Cut750.Rows, Cut750.TopRowHeightCm, Cut750.TopCm),
        Cut750.Rows == 3 && FMath::IsNearlyEqual(Cut750.TopRowHeightCm, 750.0 - 2.0 * KitCm, 1.0e-6)
        && FMath::IsNearlyEqual(Cut750.TopCm, 750.0, 1.0e-6));
    const FInfinityStageFenceStackPlan Whole750 = T::PlanFenceStack(750.0, KitCm, false);
    TestTrue(TEXT("750 whole: 2 rows (2.48 rounds down), top 605.35, no row scaled"),
        Whole750.Rows == 2 && FMath::IsNearlyEqual(Whole750.TopCm, 2.0 * KitCm, 1.0e-6)
        && Whole750.TopRowHeightCm == Whole750.RowHeightCm);
    const FInfinityStageFenceStackPlan Sliver = T::PlanFenceStack(610.0, KitCm, true);
    TestTrue(TEXT("610 cut: a 4.6 cm rest is under a quarter row, dropped: 2 whole rows"),
        Sliver.Rows == 2 && FMath::IsNearlyEqual(Sliver.TopCm, 2.0 * KitCm, 1.0e-6));
    const FInfinityStageFenceStackPlan Low = T::PlanFenceStack(200.0, KitCm, true);
    TestTrue(TEXT("200 cut: one row cut to 200"), Low.Rows == 1 && FMath::IsNearlyEqual(Low.TopCm, 200.0, 1.0e-6));
    const FInfinityStageFenceStackPlan Exact = T::PlanFenceStack(900.0, 300.0, true);
    TestTrue(TEXT("900 / 300 cut: exactly 3 whole rows"),
        Exact.Rows == 3 && Exact.TopRowHeightCm == 300.0 && Exact.TopCm == 900.0);

    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnMaterializedPassage(*World, 6);
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    ArmTubesEverywhere(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.bTubeFenceTopRows = true;
    TestTrue(TEXT("Builds Native"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Native = SnapshotBuild(*Structure);
    const TArray<FFenceRead> NativePanels = ReadFence(*Structure);
    TestTrue(TEXT("Native: no stack rows or top recorded"),
        Structure->UnderpassFenceRowCount == 0 && Structure->UnderpassFenceStackTopCm == 0.0);

    // The new fields are read only in Stack mode: flipping them changes nothing.
    Underpass.bFenceStackCutTopRow = false;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).bGroundRowOnly = !FenceVariant(Underpass, Variant).bGroundRowOnly;
    }
    TestTrue(TEXT("Builds Native with the stack fields flipped"), Structure->MaterializeStructure());
    FString Why;
    TestTrue(FString::Printf(TEXT("Native ignores the stack fields: every component identical (%s)"), *Why),
        SameBuild(Native, SnapshotBuild(*Structure), Why));
    Underpass.bFenceStackCutTopRow = true;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).bGroundRowOnly = Variant == 3;
    }

    // A one-row stack (intended = the cube's own 100) is the Native build exactly:
    // the ground row's stream and placement are the unstacked fence's own.
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Stack;
    TestTrue(TEXT("Builds a one-row stack"), Structure->MaterializeStructure());
    TestTrue(FString::Printf(TEXT("One-row stack = Native, every component, tubes included (%s)"), *Why),
        SameBuild(Native, SnapshotBuild(*Structure), Why));
    TestTrue(TEXT("One-row stack records 1 row, top 100"),
        Structure->UnderpassFenceRowCount == 1 && FMath::IsNearlyEqual(Structure->UnderpassFenceStackTopCm, EngineShapeCm));

    // Control: a taller stack does change the build, so the comparisons can fail.
    Underpass.FenceHeightCm = 250.0;
    TestTrue(TEXT("Builds a three-row stack"), Structure->MaterializeStructure());
    TestFalse(TEXT("Control: a three-row stack differs from Native"), SameBuild(Native, SnapshotBuild(*Structure), Why));
    TestEqual(TEXT("Control: three rows of panels"), ReadFence(*Structure).Num(), NativePanels.Num() * 3);

    // And back to Native: identical to the first build.
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Native;
    Underpass.FenceHeightCm = EngineShapeCm;
    TestTrue(TEXT("Rebuilds Native"), Structure->MaterializeStructure());
    TestTrue(FString::Printf(TEXT("Native again: every component identical (%s)"), *Why),
        SameBuild(Native, SnapshotBuild(*Structure), Why));
    TestTrue(TEXT("Native again: the stack record is cleared"),
        Structure->UnderpassFenceRowCount == 0 && Structure->UnderpassFenceStackTopCm == 0.0);
    World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageFenceStackRowsTest,
    "InfinityStage.Structure.FenceStack.RowsDoorsTubesAndDeterminism",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageFenceStackRowsTest::RunTest(const FString& Parameters)
{
    // Long gaps, a column on every station: ~80 ground tiles, so every variant is drawn.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnSpacedPassage(*World, { 1000.0, 1000.0, 1000.0, 1000.0 });
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    ArmTubesEverywhere(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.ColumnEvery = 1;
    Underpass.bTubeFenceTopRows = true;
    Underpass.FenceBaseCm = 20.0;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).Weight = 0.25;
    }
    TestTrue(TEXT("Builds Native"), Structure->MaterializeStructure());
    const TArray<FFenceRead> NativePanels = ReadFence(*Structure);
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    const double StationZ = Stations.IsEmpty() ? 0.0 : Stations[0].StationWorld.GetLocation().Z;
    const double BaseCm = StationZ + Structure->Ground.FloorHeightCm + Underpass.FenceBaseCm;
    TMap<FIntVector, int32> NativeChoices = StackChoices(NativePanels, BaseCm, EngineShapeCm);

    // Stack 250 on 100 cm rows, cut: rows at 0, 100 and a 50 cm cut row at 200.
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Stack;
    Underpass.FenceHeightCm = 250.0;
    TestTrue(TEXT("Builds a 250 cm stack"), Structure->MaterializeStructure());
    const TArray<FFenceRead> Panels = ReadFence(*Structure);
    TestEqual(TEXT("Three rows: three panels per Native tile"), Panels.Num(), NativePanels.Num() * 3);
    TestTrue(TEXT("Records 3 rows, top 250"),
        Structure->UnderpassFenceRowCount == 3 && FMath::IsNearlyEqual(Structure->UnderpassFenceStackTopCm, 250.0));
    int32 PerRow[3] = { 0, 0, 0 };
    bool bRowsPlaced = !Panels.IsEmpty();
    int32 GroundDoors = 0;
    int32 UpperDoors = 0;
    for (const FFenceRead& Panel : Panels)
    {
        const int32 Row = FMath::RoundToInt32((Panel.Box.Min.Z - BaseCm) / EngineShapeCm);
        const double WantTop = Row == 2 ? 250.0 : (Row + 1) * EngineShapeCm;
        const bool bRow = Row >= 0 && Row < 3;
        bRowsPlaced &= bRow && FMath::IsNearlyEqual(Panel.Box.Min.Z, BaseCm + Row * EngineShapeCm, 0.1)
            && FMath::IsNearlyEqual(Panel.Box.Max.Z, BaseCm + WantTop, 0.1)
            && FMath::IsNearlyEqual(Panel.Data[3], static_cast<float>(WantTop - Row * EngineShapeCm), 0.01f)
            && FMath::IsNearlyEqual(Panel.Transform.GetScale3D().Z, (WantTop - Row * EngineShapeCm) / EngineShapeCm, 1.0e-4);
        PerRow[bRow ? Row : 0] += bRow ? 1 : 0;
        if (Panel.Variant == 3)
        {
            (Row == 0 ? GroundDoors : UpperDoors) += 1;
        }
    }
    TestTrue(TEXT("Rows stand at base, base + 100 and base + 200; the top row is cut to 50 (Z scale 0.5, data [3] = 50)"), bRowsPlaced);
    TestTrue(TEXT("Each row holds every tile"),
        PerRow[0] == NativePanels.Num() && PerRow[1] == NativePanels.Num() && PerRow[2] == NativePanels.Num());
    TestTrue(FString::Printf(TEXT("Fixture: some doors on the ground row (%d)"), GroundDoors), GroundDoors > 0);
    TestEqual(TEXT("Doors only on the ground row"), UpperDoors, 0);

    // The ground row keeps every Native choice: stacking re-rolls nothing below.
    const TMap<FIntVector, int32> Stacked = StackChoices(Panels, BaseCm, EngineShapeCm);
    bool bGroundKept = NativeChoices.Num() == NativePanels.Num();
    for (const TPair<FIntVector, int32>& Pair : NativeChoices)
    {
        const int32* Found = Stacked.Find(Pair.Key);
        bGroundKept &= Found && *Found == Pair.Value;
    }
    TestTrue(TEXT("The ground row's variants are the Native fence's, tile for tile"), bGroundKept);

    // Fence-top tubes ride the stacked top.
    const double Raise = Underpass.TubeFenceTopRaiseCm;
    TestTrue(TEXT("Fence-top tubes at base + 250 + raise"), AllNear(FenceTopTubeZs(*Structure), BaseCm + 250.0 + Raise, 0.5));

    // Deterministic: a rebuild is identical, component for component.
    const TArray<FBuiltLayer> First = SnapshotBuild(*Structure);
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    FString Why;
    TestTrue(FString::Printf(TEXT("A rebuild is identical (%s)"), *Why), SameBuild(First, SnapshotBuild(*Structure), Why));

    // A taller stack keeps rows 0..2's choices (each row's stream is its own).
    Underpass.FenceHeightCm = 350.0;
    TestTrue(TEXT("Builds a 350 cm stack"), Structure->MaterializeStructure());
    const TMap<FIntVector, int32> Taller = StackChoices(ReadFence(*Structure), BaseCm, EngineShapeCm);
    bool bLowerKept = Stacked.Num() == Panels.Num();
    for (const TPair<FIntVector, int32>& Pair : Stacked)
    {
        const int32* Found = Taller.Find(Pair.Key);
        bLowerKept &= Found && *Found == Pair.Value;
    }
    TestTrue(TEXT("Raising the stack keeps every lower row's variants"), bLowerKept);
    TestEqual(TEXT("350 cm: four rows"), Structure->UnderpassFenceRowCount, 4);

    // Control: a new seed re-rolls (so the comparisons above can fail).
    Underpass.FenceHeightCm = 250.0;
    Underpass.FenceSeed = 7;
    TestTrue(TEXT("Builds reseeded"), Structure->MaterializeStructure());
    TestFalse(TEXT("Control: a new seed changes the choices"),
        StackChoices(ReadFence(*Structure), BaseCm, EngineShapeCm).OrderIndependentCompareEqual(Stacked));
    Underpass.FenceSeed = 0;

    // Control: D no longer ground-only does reach the upper rows.
    Underpass.FenceVariantD.bGroundRowOnly = false;
    TestTrue(TEXT("Builds with D allowed above"), Structure->MaterializeStructure());
    int32 UpperDoorsAllowed = 0;
    for (const FFenceRead& Panel : ReadFence(*Structure))
    {
        UpperDoorsAllowed += Panel.Variant == 3 && Panel.Box.Min.Z > BaseCm + 1.0 ? 1 : 0;
    }
    TestTrue(FString::Printf(TEXT("Control: D allowed above is drawn above (%d)"), UpperDoorsAllowed), UpperDoorsAllowed > 0);
    Underpass.FenceVariantD.bGroundRowOnly = true;

    // Whole rows: 240 / 100 rounds to 2 rows, top 200, none scaled; the tubes
    // follow the built top, not FenceHeightCm.
    Underpass.FenceHeightCm = 240.0;
    Underpass.bFenceStackCutTopRow = false;
    TestTrue(TEXT("Builds whole rows"), Structure->MaterializeStructure());
    const TArray<FFenceRead> WholePanels = ReadFence(*Structure);
    bool bUnscaled = WholePanels.Num() == NativePanels.Num() * 2;
    for (const FFenceRead& Panel : WholePanels)
    {
        bUnscaled &= FMath::IsNearlyEqual(Panel.Transform.GetScale3D().Z, 1.0, 1.0e-4) && Panel.Box.Max.Z < BaseCm + 200.1;
    }
    TestTrue(TEXT("Whole 240: two unscaled rows, nothing above 200"), bUnscaled);
    TestTrue(TEXT("Whole 240: fence-top tubes at base + 200 + raise"),
        AllNear(FenceTopTubeZs(*Structure), BaseCm + 200.0 + Raise, 0.5));
    TestFalse(TEXT("Control: not at FenceHeightCm"), AllNear(FenceTopTubeZs(*Structure), BaseCm + 240.0 + Raise, 0.5));

    // With the fence off the tubes fall back to FenceHeightCm (no bay to measure).
    Underpass.bFence = false;
    TestTrue(TEXT("Builds with the fence off"), Structure->MaterializeStructure());
    TestTrue(TEXT("Fence off, Stack: fence-top tubes at base + FenceHeightCm + raise"),
        AllNear(FenceTopTubeZs(*Structure), BaseCm + 240.0 + Raise, 0.5));
    TestTrue(TEXT("Fence off: no stack record"), Structure->UnderpassFenceRowCount == 0);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());
    World->DestroyWorld(false);
    return true;
}

// ---------------------------------------------------------------------------
// Fence top row and posts (patch BW, 7 Oct; Gary: "Coil + strands", barbed wire on
// the top row only, thicker posts): a variant's TopRowMesh is drawn on the top row
// alone, with the very same variant choices; posts stand at tile joints on the top
// row. Every new field at its default builds exactly as before.
// ---------------------------------------------------------------------------
namespace
{
const TCHAR* const FenceTopRowTag = TEXT("InfinityStage.Structure.Underpass.FenceTopRow");
const TCHAR* const FencePostTag = TEXT("InfinityStage.Structure.Underpass.FencePosts");

/** Every panel of every variant layer, top-row layers included (ReadFence reads one component per tag). */
struct FTopRowPanel
{
    int32 Variant = INDEX_NONE;
    bool bTopRowLayer = false;
    const UStaticMesh* Mesh = nullptr;
    FTransform Transform;
    FBox Box = FBox(ForceInit);
};

TArray<FTopRowPanel> ReadAllPanels(const AInfinityStageStructureActor& Structure)
{
    TArray<FTopRowPanel> Panels;
    for (const UInstancedStaticMeshComponent* Component : Structure.ManagedComponents)
    {
        if (!Component)
        {
            continue;
        }
        int32 Variant = INDEX_NONE;
        for (int32 Index = 0; Index < FenceVariantTotal; ++Index)
        {
            Variant = Component->ComponentTags.Contains(FName(FenceVariantTags[Index])) ? Index : Variant;
        }
        if (Variant == INDEX_NONE)
        {
            continue;
        }
        const FBox MeshBounds = Component->GetStaticMesh()->GetBoundingBox();
        for (const FTransform& Instance : ReadInstances(*Component))
        {
            FTopRowPanel& Panel = Panels.AddDefaulted_GetRef();
            Panel.Variant = Variant;
            Panel.bTopRowLayer = Component->ComponentTags.Contains(FName(FenceTopRowTag));
            Panel.Mesh = Component->GetStaticMesh();
            Panel.Transform = Instance;
            Panel.Box = MeshBounds.TransformBy(Instance);
        }
    }
    return Panels;
}

TMap<FIntVector, int32> AllPanelChoices(const TArray<FTopRowPanel>& Panels, const double BaseCm, const double RowCm)
{
    TMap<FIntVector, int32> Choices;
    for (const FTopRowPanel& Panel : Panels)
    {
        const FVector Centre = Panel.Box.GetCenter();
        Choices.Add(FIntVector(FMath::RoundToInt32(Centre.X), FMath::RoundToInt32(Centre.Y),
            FMath::RoundToInt32((Panel.Box.Min.Z - BaseCm) / RowCm)), Panel.Variant);
    }
    return Choices;
}

/** Each post's foot (its location less the rotated offset, the offset's Z scaled with the post) and its transform. */
TArray<TPair<FVector, FTransform>> ReadPosts(const AInfinityStageStructureActor& Structure, const FVector& OffsetCm)
{
    TArray<TPair<FVector, FTransform>> Posts;
    if (const UInstancedStaticMeshComponent* Layer = FindLayer(Structure, FencePostTag))
    {
        for (const FTransform& Instance : ReadInstances(*Layer))
        {
            const FVector Scaled(OffsetCm.X, OffsetCm.Y, OffsetCm.Z * Instance.GetScale3D().Z);
            Posts.Emplace(Instance.GetLocation() - Instance.GetRotation().RotateVector(Scaled), Instance);
        }
    }
    return Posts;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FInfinityStageFenceTopRowAndPostsTest,
    "InfinityStage.Structure.FenceTopRow.WireOnTheTopRowOnlyAndPostsAtJoints",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FInfinityStageFenceTopRowAndPostsTest::RunTest(const FString& Parameters)
{
    const FInfinityStageUnderpassSettings Defaults;
    TestTrue(TEXT("Defaults: no top-row mesh on any variant, no posts, no post mesh, material or offset"),
        Defaults.FenceVariantA.TopRowMesh.IsNull() && Defaults.FenceVariantB.TopRowMesh.IsNull()
        && Defaults.FenceVariantC.TopRowMesh.IsNull() && Defaults.FenceVariantD.TopRowMesh.IsNull()
        && Defaults.FencePostJoints == EInfinityFencePostJoints::None && Defaults.FencePostMesh.IsNull()
        && Defaults.FencePostMaterial.IsNull() && Defaults.FencePostOffsetCm.IsZero());

    const TSoftObjectPtr<UStaticMesh> Cube(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));
    const TSoftObjectPtr<UStaticMesh> Cylinder(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cylinder.Cylinder")));
    const TSoftObjectPtr<UStaticMesh> Cone(FSoftObjectPath(TEXT("/Engine/BasicShapes/Cone.Cone")));
    if (!Cube.LoadSynchronous() || !Cylinder.LoadSynchronous() || !Cone.LoadSynchronous())
    {
        AddError(TEXT("Fixture: the engine cube, cylinder or cone does not load."));
        return false;
    }

    // Long gaps, a column on every station, every variant drawn; three whole 100 cm rows.
    UWorld* World = UWorld::CreateWorld(EWorldType::EditorPreview, false);
    AInfinityStagePassageActor* Passage = SpawnSpacedPassage(*World, { 1000.0, 1000.0, 1000.0, 1000.0 });
    AInfinityStageStructureActor* Structure = SpawnMachinedStructure(*World, *Passage);
    ArmFence(*Structure);
    FInfinityStageUnderpassSettings& Underpass = Structure->Underpass;
    Underpass.ColumnEvery = 1;
    Underpass.FenceBaseCm = 20.0;
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Stack;
    Underpass.FenceHeightCm = 300.0;
    Underpass.FenceVariantB.OverlayMesh = Cube;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).Weight = 0.25;
    }
    TestTrue(TEXT("Builds the plain stack"), Structure->MaterializeStructure());
    const TArray<FBuiltLayer> Plain = SnapshotBuild(*Structure);
    const TArray<FTopRowPanel> PlainPanels = ReadAllPanels(*Structure);
    TestEqual(TEXT("Plain: three rows"), Structure->UnderpassFenceRowCount, 3);
    TestTrue(TEXT("Plain: no top-row panels or posts counted"),
        Structure->UnderpassFenceTopRowPanelCount == 0 && Structure->UnderpassFencePostCount == 0);
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    Structure->GatherStations(Stations, Error);
    const double StationZ = Stations.IsEmpty() ? 0.0 : Stations[0].StationWorld.GetLocation().Z;
    const double BaseCm = StationZ + Structure->Ground.FloorHeightCm + Underpass.FenceBaseCm;
    const TMap<FIntVector, int32> PlainChoices = AllPanelChoices(PlainPanels, BaseCm, EngineShapeCm);

    // The post fields do nothing while FencePostJoints is None; a post mode with no
    // mesh does nothing either.
    Underpass.FencePostMesh = Cone;
    Underpass.FencePostOffsetCm = FVector(-5.0, -6.5, 0.0);
    TestTrue(TEXT("Builds with a post mesh and offset but no joints"), Structure->MaterializeStructure());
    FString Why;
    TestTrue(FString::Printf(TEXT("Joints None: every component identical to the plain stack (%s)"), *Why),
        SameBuild(Plain, SnapshotBuild(*Structure), Why));
    Underpass.FencePostMesh = nullptr;
    Underpass.FencePostJoints = EInfinityFencePostJoints::LineEnd;
    TestTrue(TEXT("Builds with joints but no post mesh"), Structure->MaterializeStructure());
    TestTrue(FString::Printf(TEXT("No post mesh: every component identical to the plain stack (%s)"), *Why),
        SameBuild(Plain, SnapshotBuild(*Structure), Why));
    Underpass.FencePostJoints = EInfinityFencePostJoints::None;

    // A top-row mesh on every variant: the cylinder on the top row, the cube below.
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).TopRowMesh = Cylinder;
    }
    TestTrue(TEXT("Builds with top-row meshes"), Structure->MaterializeStructure());
    const TArray<FTopRowPanel> Panels = ReadAllPanels(*Structure);
    TestEqual(TEXT("As many panels as the plain stack"), Panels.Num(), PlainPanels.Num());
    int32 TopRow = 0;
    bool bPlaced = !Panels.IsEmpty();
    for (const FTopRowPanel& Panel : Panels)
    {
        const int32 Row = FMath::RoundToInt32((Panel.Box.Min.Z - BaseCm) / EngineShapeCm);
        const bool bTop = Row == 2;
        TopRow += bTop ? 1 : 0;
        bPlaced &= bTop == Panel.bTopRowLayer && Panel.Mesh == (bTop ? Cylinder.Get() : Cube.Get())
            && FMath::IsNearlyEqual(Panel.Box.Min.Z, BaseCm + Row * EngineShapeCm, 0.1)
            && FMath::IsNearlyEqual(Panel.Box.Max.Z, BaseCm + (Row + 1) * EngineShapeCm, 0.1);
    }
    TestTrue(TEXT("The top row is the cylinder in top-row layers; rows 0 and 1 the cube; every panel in its row"), bPlaced);
    TestEqual(TEXT("One row of top-row panels"), TopRow * 3, Panels.Num());
    TestEqual(TEXT("The top-row count is reported"), Structure->UnderpassFenceTopRowPanelCount, TopRow);
    TestEqual(TEXT("Panels counted with the top row"), Structure->UnderpassFencePanelCount, Panels.Num());
    TestTrue(TEXT("Every variant's choice is the plain stack's, tile for tile and row for row"),
        AllPanelChoices(Panels, BaseCm, EngineShapeCm).OrderIndependentCompareEqual(PlainChoices));
    int32 BPanels = 0;
    for (const FTopRowPanel& Panel : Panels)
    {
        BPanels += Panel.Variant == 1 ? 1 : 0;
    }
    TestEqual(TEXT("B's overlay rides every B panel, top row included"), Structure->UnderpassFenceOverlayCount, BPanels);
    const TArray<FBuiltLayer> Topped = SnapshotBuild(*Structure);
    TestTrue(TEXT("Rebuilds"), Structure->MaterializeStructure());
    TestTrue(FString::Printf(TEXT("A rebuild is identical (%s)"), *Why), SameBuild(Topped, SnapshotBuild(*Structure), Why));
    TestFalse(TEXT("Control: the top row does change the build"), SameBuild(Plain, Topped, Why));

    // LineEnd: one post per side, at the fence line's far end in the bays' +X, on the top row.
    const FVector OffsetCm(-5.0, -6.5, 0.0);
    Underpass.FencePostMesh = Cone;
    Underpass.FencePostOffsetCm = OffsetCm;
    Underpass.FencePostJoints = EInfinityFencePostJoints::LineEnd;
    TestTrue(TEXT("Builds with line-end posts"), Structure->MaterializeStructure());
    const int32 Runs = (ColumnCentreX(*Structure).Num() - 1) * 2;
    const TArray<TPair<FVector, FTransform>> EndPosts = ReadPosts(*Structure, OffsetCm);
    TestTrue(FString::Printf(TEXT("Fixture: several runs (%d)"), Runs), Runs >= 4);
    TestEqual(TEXT("LineEnd: one post per side"), EndPosts.Num(), 2);
    TestEqual(TEXT("LineEnd: the post count is reported"), Structure->UnderpassFencePostCount, 2);
    TArray<FTopRowPanel> TopPanels = ReadAllPanels(*Structure).FilterByPredicate([](const FTopRowPanel& Panel) { return Panel.bTopRowLayer; });
    // -Y side: the bays' +X is world +X, so the line's +X end is the largest max X;
    // +Y side: their +X is world -X, so it is the smallest min X.
    double MaxMinusY = -TNumericLimits<double>::Max();
    double MinPlusY = TNumericLimits<double>::Max();
    double LineYMinus = 0.0;
    double LineYPlus = 0.0;
    for (const FTopRowPanel& Panel : TopPanels)
    {
        const FVector Centre = Panel.Box.GetCenter();
        if (Centre.Y < 0.0 && Panel.Box.Max.X > MaxMinusY)
        {
            MaxMinusY = Panel.Box.Max.X;
            LineYMinus = Centre.Y;
        }
        if (Centre.Y > 0.0 && Panel.Box.Min.X < MinPlusY)
        {
            MinPlusY = Panel.Box.Min.X;
            LineYPlus = Centre.Y;
        }
    }
    int32 MinusYEnds = 0;
    int32 PlusYEnds = 0;
    bool bEnds = EndPosts.Num() == 2;
    for (const TPair<FVector, FTransform>& Post : EndPosts)
    {
        const FVector Foot = Post.Key;
        const bool bMinusY = Foot.Y < 0.0;
        const bool bAtEnd = bMinusY
            ? FMath::IsNearlyEqual(Foot.X, MaxMinusY, 0.1) && FMath::IsNearlyEqual(Foot.Y, LineYMinus, 0.1)
            : FMath::IsNearlyEqual(Foot.X, MinPlusY, 0.1) && FMath::IsNearlyEqual(Foot.Y, LineYPlus, 0.1);
        (bMinusY ? MinusYEnds : PlusYEnds) += bAtEnd ? 1 : 0;
        bEnds &= bAtEnd && FMath::IsNearlyEqual(Foot.Z, BaseCm + 2.0 * EngineShapeCm, 0.1)
            && Post.Value.GetScale3D().Equals(FVector::OneVector, 1.0e-6)
            && FMath::IsNearlyEqual(Post.Value.GetRotation().GetAxisX().X, bMinusY ? 1.0 : -1.0, 1.0e-6);
    }
    TestTrue(TEXT("LineEnd: each foot on its side's line end, on the top row's bottom, unscaled, in the bays' frame"),
        bEnds && MinusYEnds == 1 && PlusYEnds == 1);
    TestTrue(TEXT("Posts change no panel"),
        AllPanelChoices(ReadAllPanels(*Structure), BaseCm, EngineShapeCm).OrderIndependentCompareEqual(PlainChoices));
    // Control: read without the offset, no foot lands on a joint (so the offset is applied, and bEnds can fail).
    bool bAnyRawOnJoint = false;
    for (const TPair<FVector, FTransform>& Post : ReadPosts(*Structure, FVector::ZeroVector))
    {
        for (const FTopRowPanel& Panel : TopPanels)
        {
            bAnyRawOnJoint |= FMath::IsNearlyEqual(Post.Key.Y, Panel.Box.GetCenter().Y, 0.1)
                && (FMath::IsNearlyEqual(Post.Key.X, Panel.Box.Max.X, 0.1) || FMath::IsNearlyEqual(Post.Key.X, Panel.Box.Min.X, 0.1));
        }
    }
    TestFalse(TEXT("Control: unoffset, no post foot is on a joint"), bAnyRawOnJoint);

    // Every joint: tiles + 1 per run, so exactly one more per run than the top row's tiles.
    Underpass.FencePostJoints = EInfinityFencePostJoints::Every;
    TestTrue(TEXT("Builds with posts at every joint"), Structure->MaterializeStructure());
    TestEqual(TEXT("Every: top-row tiles + one per run"), ReadPosts(*Structure, OffsetCm).Num(), TopRow + Runs);

    // A cut top row Z-scales the top-row panels and the posts together, and says so.
    Underpass.FencePostJoints = EInfinityFencePostJoints::LineEnd;
    Underpass.FenceHeightCm = 250.0;
    AddExpectedMessagePlain(TEXT("INFINITY_STAGE_STRUCTURE_FENCE_TOP_ROW_SCALED"), ELogVerbosity::Warning,
        EAutomationExpectedMessageFlags::Contains, 1);
    TestTrue(TEXT("Builds a cut 250 cm stack"), Structure->MaterializeStructure());
    bool bCut = true;
    int32 CutTop = 0;
    for (const FTopRowPanel& Panel : ReadAllPanels(*Structure))
    {
        if (Panel.bTopRowLayer)
        {
            ++CutTop;
            bCut &= FMath::IsNearlyEqual(Panel.Transform.GetScale3D().Z, 0.5, 1.0e-4)
                && FMath::IsNearlyEqual(Panel.Box.Max.Z, BaseCm + 250.0, 0.1);
        }
    }
    for (const TPair<FVector, FTransform>& Post : ReadPosts(*Structure, OffsetCm))
    {
        bCut &= FMath::IsNearlyEqual(Post.Value.GetScale3D().Z, 0.5, 1.0e-6)
            && FMath::IsNearlyEqual(Post.Key.Z, BaseCm + 2.0 * EngineShapeCm, 0.1);
    }
    TestTrue(TEXT("Cut: the top-row panels and the posts are scaled 0.5 and stand on the third row"), bCut && CutTop == TopRow);

    // Native, one row: the one row is the top row, so it is all cylinder; posts at Z scale 1 on the base.
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Native;
    Underpass.FenceHeightCm = EngineShapeCm;
    TestTrue(TEXT("Builds Native"), Structure->MaterializeStructure());
    const TArray<FTopRowPanel> NativePanels = ReadAllPanels(*Structure);
    bool bAllTop = !NativePanels.IsEmpty();
    for (const FTopRowPanel& Panel : NativePanels)
    {
        bAllTop &= Panel.bTopRowLayer && Panel.Mesh == Cylinder.Get();
    }
    TestTrue(TEXT("Native: the one row is the top row"), bAllTop);
    bool bNativePosts = Structure->UnderpassFencePostCount == 2;
    for (const TPair<FVector, FTransform>& Post : ReadPosts(*Structure, OffsetCm))
    {
        bNativePosts &= FMath::IsNearlyEqual(Post.Key.Z, BaseCm, 0.1) && FMath::IsNearlyEqual(Post.Value.GetScale3D().Z, 1.0, 1.0e-6);
    }
    TestTrue(TEXT("Native: the two line-end posts on the fence base, unscaled"), bNativePosts);

    // Everything back to default: identical to the plain stack.
    Underpass.FenceHeightMode = EInfinityFenceHeightMode::Stack;
    Underpass.FenceHeightCm = 300.0;
    Underpass.FencePostJoints = EInfinityFencePostJoints::None;
    Underpass.FencePostMesh = nullptr;
    Underpass.FencePostOffsetCm = FVector::ZeroVector;
    for (int32 Variant = 0; Variant < FenceVariantTotal; ++Variant)
    {
        FenceVariant(Underpass, Variant).TopRowMesh = nullptr;
    }
    TestTrue(TEXT("Rebuilds plain"), Structure->MaterializeStructure());
    TestTrue(FString::Printf(TEXT("Back to default: every component identical to the plain stack (%s)"), *Why),
        SameBuild(Plain, SnapshotBuild(*Structure), Why));
    TestTrue(TEXT("Back to default: no top-row panels or posts counted"),
        Structure->UnderpassFenceTopRowPanelCount == 0 && Structure->UnderpassFencePostCount == 0);
    TestTrue(TEXT("The structure is current"), Structure->IsStructureCurrent());
    World->DestroyWorld(false);
    return true;
}

#endif
