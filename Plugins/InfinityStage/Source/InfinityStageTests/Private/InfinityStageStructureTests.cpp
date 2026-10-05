#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageStructureActor.h"
#include "Components/InstancedStaticMeshComponent.h"
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
    TArray<FInfinityCueAttachment>& Attachments = Passage->ShowAsset->Cues[0].WingPair.Attachments;
    Attachments.Append({ Hung, Outside, Off, Riding });

    TestTrue(TEXT("Structure with lights materializes"), Structure->MaterializeStructure());
    TestEqual(TEXT("A housing for each enabled station light"), Structure->FixtureBodyCount, 2);
    TestEqual(TEXT("A line only where the grid is overhead"), Structure->HangingLineCount, 1);
    TestEqual(TEXT("A panel-riding light is reported, not housed"), Structure->MovingLightsWithoutHousing, 1);
    TestEqual(TEXT("Gridiron, housings and lines are separate layers"), Structure->ManagedComponents.Num(), 3);

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
    Attachments[0].RelativeTransform.AddToTranslation(FVector(0.0, 0.0, -50.0));
    TestFalse(TEXT("Moving a light in the Show leaves its housing stale"), Structure->IsStructureCurrent());

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

#endif
