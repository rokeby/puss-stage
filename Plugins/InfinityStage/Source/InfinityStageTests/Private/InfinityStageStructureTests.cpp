#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "InfinityStageStructureActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
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

#endif
