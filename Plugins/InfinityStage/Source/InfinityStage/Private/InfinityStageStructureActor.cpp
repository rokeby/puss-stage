#include "InfinityStageStructureActor.h"

#include "TimerManager.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "InfinityStageCompiler.h"
#include "InfinityStagePassageActor.h"
#include "InfinityStageShowAsset.h"
#include "Materials/MaterialInterface.h"
#include "Math/RandomStream.h"

DEFINE_LOG_CATEGORY_STATIC(LogInfinityStageStructure, Log, All);

namespace
{
const FName StructureTag(TEXT("InfinityStage.Structure"));
const FName GridironLayerTag(TEXT("InfinityStage.Structure.Gridiron"));
const FName GroundLayerTag(TEXT("InfinityStage.Structure.Ground"));
const FName UnderstageLayerTag(TEXT("InfinityStage.Structure.Understage"));
const FName ClothLayerTag(TEXT("InfinityStage.Structure.Cloth"));
const FName PortalLayerTag(TEXT("InfinityStage.Structure.Portal"));
const FName FixtureLayerTag(TEXT("InfinityStage.Structure.Fixtures"));
const FName LineLayerTag(TEXT("InfinityStage.Structure.Lines"));
const FName GrooveLayerTag(TEXT("InfinityStage.Structure.Grooves"));
const FName UnderpassColumnLayerTag(TEXT("InfinityStage.Structure.Underpass.Columns"));
const FName UnderpassPierLayerTag(TEXT("InfinityStage.Structure.Underpass.Piers"));
const FName UnderpassKneeLayerTag(TEXT("InfinityStage.Structure.Underpass.Knees"));
const FName UnderpassDeckLayerTag(TEXT("InfinityStage.Structure.Underpass.Deck"));
const FName UnderpassCatwalkLayerTag(TEXT("InfinityStage.Structure.Underpass.Catwalk"));
const FName UnderpassTubeLayerTag(TEXT("InfinityStage.Structure.Underpass.Tubes"));
const FName UnderpassTubeLightLayerTag(TEXT("InfinityStage.Structure.Underpass.TubeLights"));
/** Every fence component carries this, and its variant's own tag below. */
const FName UnderpassFenceTag(TEXT("InfinityStage.Structure.Underpass.Fence"));
const FName UnderpassFenceLayerTags[] = {
    FName(TEXT("InfinityStage.Structure.Underpass.Fence.A")),
    FName(TEXT("InfinityStage.Structure.Underpass.Fence.B")),
    FName(TEXT("InfinityStage.Structure.Underpass.Fence.C")),
    FName(TEXT("InfinityStage.Structure.Underpass.Fence.D")),
};
const FName UnderpassFenceOverlayLayerTags[] = {
    FName(TEXT("InfinityStage.Structure.Underpass.FenceOverlay.A")),
    FName(TEXT("InfinityStage.Structure.Underpass.FenceOverlay.B")),
    FName(TEXT("InfinityStage.Structure.Underpass.FenceOverlay.C")),
    FName(TEXT("InfinityStage.Structure.Underpass.FenceOverlay.D")),
};
static_assert(UE_ARRAY_COUNT(UnderpassFenceLayerTags) == FInfinityStageUnderpassSettings::FenceVariantCount, "one tag per fence variant");
static_assert(UE_ARRAY_COUNT(UnderpassFenceOverlayLayerTags) == FInfinityStageUnderpassSettings::FenceVariantCount, "one overlay tag per fence variant");

/** Per-instance custom data: variation 0..1, then length, width, depth in cm. */
constexpr int32 TimberCustomDataFloats = 4;

/** Which piece a random stream belongs to. Streams are keyed by a stable identity
 * (cue or attachment), not by index, so inserting a pair or a light re-rolls only
 * the new pieces. */
enum class ETimberPart : uint32
{
    CrossBeam = 0,
    RailNegative = 1,
    RailPositive = 2,
    Housing = 3,
    BoardLane = 4,
    Cloth = 5,
    Portal = 6,
    Groove = 7,
    UnderpassColumn = 8,
    UnderpassPier = 9,
    UnderpassKnee = 10,
    UnderpassDeck = 11,
    UnderpassCatwalk = 12,
    UnderpassTube = 13,
    UnderpassFence = 14
};

FRandomStream MakeTimberStream(const FGuid& Identity, const ETimberPart Part)
{
    return FRandomStream(static_cast<int32>(
        HashCombineFast(GetTypeHash(Identity), ::GetTypeHash(static_cast<uint32>(Part)))));
}

/** One tube row's stream within one bay, keyed by the bay's station, the row and
 * the seed. One combine per statement, so the order is fixed (memory:
 * puss-random-draw-order). */
FRandomStream MakeTubeStream(const FGuid& Station, const int32 RowKey, const int32 Seed)
{
    uint32 Hash = HashCombineFast(GetTypeHash(Station), ::GetTypeHash(static_cast<uint32>(ETimberPart::UnderpassTube)));
    Hash = HashCombineFast(Hash, ::GetTypeHash(RowKey));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Seed));
    return FRandomStream(static_cast<int32>(Hash));
}

/** One fence tile's stream, keyed by its gap's first column station, the side
 * (0 for -Y, 1 for +Y), the tile's index along the gap and the seed. One combine
 * per statement, as for the tubes. */
FRandomStream MakeFenceStream(const FGuid& Station, const int32 SideKey, const int32 TileIndex, const int32 Seed)
{
    uint32 Hash = HashCombineFast(GetTypeHash(Station), ::GetTypeHash(static_cast<uint32>(ETimberPart::UnderpassFence)));
    Hash = HashCombineFast(Hash, ::GetTypeHash(SideKey));
    Hash = HashCombineFast(Hash, ::GetTypeHash(TileIndex));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Seed));
    return FRandomStream(static_cast<int32>(Hash));
}

/** A stacked fence row's stream. Row 0 is exactly MakeFenceStream, so stacking
 * never re-rolls the ground row; each row above mixes its row index in, one
 * combine per statement. */
FRandomStream MakeFenceRowStream(const FGuid& Station, const int32 SideKey, const int32 TileIndex, const int32 Row, const int32 Seed)
{
    if (Row == 0)
    {
        return MakeFenceStream(Station, SideKey, TileIndex, Seed);
    }
    uint32 Hash = HashCombineFast(GetTypeHash(Station), ::GetTypeHash(static_cast<uint32>(ETimberPart::UnderpassFence)));
    Hash = HashCombineFast(Hash, ::GetTypeHash(SideKey));
    Hash = HashCombineFast(Hash, ::GetTypeHash(TileIndex));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Seed));
    Hash = HashCombineFast(Hash, ::GetTypeHash(Row));
    return FRandomStream(static_cast<int32>(Hash));
}

struct FFixturePlacement
{
    FGuid AttachmentGuid;
    int32 StationIndex = INDEX_NONE;
    FTransform LightWorld;
};

/**
 * Where every enabled light on the Passage's bays sits, computed from the Show
 * exactly as materialization places a station-anchored attachment: its relative
 * offset on the pair root. Reading the Show rather than the spawned light actors
 * keeps the Show the only authority.
 */
TArray<FFixturePlacement> GatherFixturePlacements(
    const UInfinityStageShowAsset& Show,
    const TArray<FInfinityStructureStation>& Stations,
    int32& OutMovingLights)
{
    OutMovingLights = 0;
    TMap<FGuid, const FInfinityShowCue*> CuesByGuid;
    for (const FInfinityShowCue& Cue : Show.Cues)
    {
        CuesByGuid.Add(Cue.CueGuid, &Cue);
    }
    TArray<FFixturePlacement> Placements;
    for (int32 StationIndex = 0; StationIndex < Stations.Num(); ++StationIndex)
    {
        const FInfinityShowCue* const* Cue = CuesByGuid.Find(Stations[StationIndex].CueGuid);
        if (!Cue || (*Cue)->Type != EInfinityCueType::WingPair)
        {
            continue;
        }
        const FTransform PairWorld = (*Cue)->WingPair.OccurrenceOffset * Stations[StationIndex].StationWorld;
        for (const FInfinityCueAttachment& Attachment : (*Cue)->WingPair.Attachments)
        {
            if (!Attachment.bEnabled || Attachment.Kind != EInfinityAttachmentKind::Light)
            {
                continue;
            }
            if (Attachment.Anchor != EInfinityAttachmentAnchor::Station)
            {
                ++OutMovingLights;
                continue;
            }
            FFixturePlacement& Placement = Placements.AddDefaulted_GetRef();
            Placement.AttachmentGuid = Attachment.AttachmentGuid;
            Placement.StationIndex = StationIndex;
            Placement.LightWorld = Attachment.RelativeTransform * PairWorld;
        }
    }
    return Placements;
}

/**
 * Fits any mesh to a timber by its bounds: scale each axis to the wanted size and
 * put the bounds centre, not the pivot, on the beam centre. A Blender timber with
 * its pivot at one end therefore drops in with no placement correction.
 */
FTransform FitMeshToTimber(
    const FBox& MeshBounds,
    const FVector& CentreWorld,
    const FQuat& Rotation,
    const FVector& SizeCm)
{
    const FVector MeshSize = MeshBounds.GetSize();
    const FVector Scale(
        MeshSize.X > UE_KINDA_SMALL_NUMBER ? SizeCm.X / MeshSize.X : 1.0,
        MeshSize.Y > UE_KINDA_SMALL_NUMBER ? SizeCm.Y / MeshSize.Y : 1.0,
        MeshSize.Z > UE_KINDA_SMALL_NUMBER ? SizeCm.Z / MeshSize.Z : 1.0);
    const FVector PivotOffset = Rotation.RotateVector(MeshBounds.GetCenter() * Scale);
    return FTransform(Rotation, CentreWorld - PivotOffset, Scale);
}

void ApplyInstances(
    UInstancedStaticMeshComponent& Component,
    const TArray<FTransform>& Transforms,
    const TArray<float>& CustomData)
{
    Component.AddInstances(Transforms, false, true, false);
    for (int32 InstanceIndex = 0; InstanceIndex < Transforms.Num(); ++InstanceIndex)
    {
        Component.SetCustomData(
            InstanceIndex,
            MakeArrayView(CustomData.GetData() + InstanceIndex * TimberCustomDataFloats, TimberCustomDataFloats),
            false);
    }
    Component.MarkRenderStateDirty();
}

uint32 HashFrame(uint32 Hash, const FTransform& Frame)
{
    // Quantized to a millimetre and a thousandth of direction, so float noise from
    // re-evaluating the same spline cannot report a false re-fit.
    const FVector Location = Frame.GetLocation();
    const FVector Forward = Frame.GetUnitAxis(EAxis::X) * 100.0;
    const FVector Up = Frame.GetUnitAxis(EAxis::Z) * 100.0;
    for (const double Value : { Location.X, Location.Y, Location.Z, Forward.X, Forward.Y, Forward.Z, Up.X, Up.Y, Up.Z })
    {
        Hash = HashCombineFast(Hash, ::GetTypeHash(FMath::RoundToInt64(Value * 10.0)));
    }
    return Hash;
}

int32 ComputeStructureSignature(
    const TArray<FInfinityStructureStation>& Stations,
    const TArray<FFixturePlacement>& Fixtures)
{
    uint32 Hash = HashCombineFast(::GetTypeHash(Stations.Num()), ::GetTypeHash(Fixtures.Num()));
    for (const FInfinityStructureStation& Station : Stations)
    {
        Hash = HashCombineFast(Hash, GetTypeHash(Station.CueGuid));
        Hash = HashFrame(Hash, Station.StationWorld);
        for (const double SideCm : { Station.NegativeSideCm, Station.PositiveSideCm })
        {
            Hash = HashCombineFast(Hash, ::GetTypeHash(FMath::RoundToInt64(SideCm * 10.0)));
        }
    }
    for (const FFixturePlacement& Fixture : Fixtures)
    {
        Hash = HashCombineFast(Hash, GetTypeHash(Fixture.AttachmentGuid));
        Hash = HashFrame(Hash, Fixture.LightWorld);
    }
    return static_cast<int32>(Hash);
}
}

AInfinityStageStructureActor::AInfinityStageStructureActor()
{
    PrimaryActorTick.bCanEverTick = false;

    // The building does not move; Static lets shadows and lighting cache it.
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SceneRoot->SetMobility(EComponentMobility::Static);
    SetRootComponent(SceneRoot);

    Tags.Add(StructureTag);
}

bool AInfinityStageStructureActor::GatherStations(
    TArray<FInfinityStructureStation>& OutStations,
    FString& OutError) const
{
    OutStations.Reset();
    if (!Passage)
    {
        OutError = TEXT("Structure has no Passage.");
        return false;
    }
    if (!Passage->ShowAsset || !Passage->Route)
    {
        OutError = FString::Printf(TEXT("Passage '%s' has no Show Asset or Route."), *Passage->GetActorNameOrLabel());
        return false;
    }
    if (!Passage->PassageGuid.IsValid())
    {
        OutError = FString::Printf(TEXT("Passage '%s' has never been materialized."), *Passage->GetActorNameOrLabel());
        return false;
    }

    const FInfinityCompileResult Compiled = FInfinityStageCompiler::Compile(*Passage->ShowAsset);
    const FInfinityCompiledPassage* CompiledPassage = Compiled.Passages.FindByPredicate(
        [this](const FInfinityCompiledPassage& Candidate) { return Candidate.PassageGuid == Passage->PassageGuid; });
    if (Compiled.HasErrors() || !CompiledPassage)
    {
        OutError = FString::Printf(TEXT("Passage '%s' does not compile."), *Passage->GetActorNameOrLabel());
        return false;
    }
    // The width comes from placed panels and the stations from the compile; if the
    // two disagree the Passage is stale and the building would fit the wrong wings.
    if (Passage->MaterializedWingPairCount != CompiledPassage->Wings.Num())
    {
        OutError = FString::Printf(
            TEXT("Passage '%s' is stale: %d pairs materialized, Show compiles %d. Materialize the Passage first."),
            *Passage->GetActorNameOrLabel(),
            Passage->MaterializedWingPairCount,
            CompiledPassage->Wings.Num());
        return false;
    }

    TMap<FGuid, TArray<FVector, TInlineAllocator<2>>> PanelLocationsByCue;
    for (const FInfinityMaterializedPanelRef& Ref : Passage->MaterializedPanels)
    {
        if (Ref.Side != EInfinityPanelSide::Top)
        {
            PanelLocationsByCue.FindOrAdd(Ref.CueGuid).Add(Ref.BaseWorldTransform.GetLocation());
        }
    }

    for (const FInfinityCompiledWing& Wing : CompiledPassage->Wings)
    {
        const TArray<FVector, TInlineAllocator<2>>* PanelLocations = PanelLocationsByCue.Find(Wing.CueGuid);
        if (!PanelLocations)
        {
            // A pair with no side meshes has no width to span; it is not a bay.
            continue;
        }
        FInfinityStructureStation& Station = OutStations.AddDefaulted_GetRef();
        Station.CueGuid = Wing.CueGuid;
        Station.DistanceCm = Wing.DistanceCm;
        Station.StationWorld = Passage->Route->GetTransformAtDistanceAlongSpline(
            Wing.DistanceCm,
            ESplineCoordinateSpace::World,
            false);
        Station.StationWorld.SetScale3D(FVector::OneVector);
        const FVector Origin = Station.StationWorld.GetLocation();
        const FVector Across = Station.StationWorld.GetUnitAxis(EAxis::Y);
        for (const FVector& PanelLocation : *PanelLocations)
        {
            const double LateralCm = FVector::DotProduct(PanelLocation - Origin, Across);
            double& SideCm = LateralCm < 0.0 ? Station.NegativeSideCm : Station.PositiveSideCm;
            SideCm = FMath::Max(SideCm, FMath::Abs(LateralCm));
        }
        Station.HalfWidthCm = FMath::Max(Station.NegativeSideCm, Station.PositiveSideCm);
    }
    OutStations.StableSort([](const FInfinityStructureStation& A, const FInfinityStructureStation& B)
    {
        return A.DistanceCm < B.DistanceCm;
    });

    if (OutStations.IsEmpty())
    {
        OutError = FString::Printf(
            TEXT("Passage '%s' has no materialized side panels to derive stations from."),
            *Passage->GetActorNameOrLabel());
        return false;
    }
    return true;
}

bool AInfinityStageStructureActor::IsStructureCurrent() const
{
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    if (StationCount == 0 || !GatherStations(Stations, Error))
    {
        return false;
    }
    int32 MovingLights = 0;
    return ComputeStructureSignature(
        Stations,
        GatherFixturePlacements(*Passage->ShowAsset, Stations, MovingLights)) == StationSignature;
}

void AInfinityStageStructureActor::ClearStructure()
{
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        UE_LOG(LogInfinityStageStructure, Warning, TEXT("Refusing to clear stage structure in a game world."));
        return;
    }

    Modify();

    // The array is the ownership record, but undo or reinstancing can drop a
    // reference while the component lives on. Recover those by tag, exactly as the
    // Passage does, so a rebuild never stacks a new grid on an untracked old one.
    TSet<UInstancedStaticMeshComponent*> ComponentsToDestroy;
    for (UInstancedStaticMeshComponent* Component : ManagedComponents)
    {
        if (IsValid(Component))
        {
            ComponentsToDestroy.Add(Component);
        }
    }
    const int32 ReferencedCount = ComponentsToDestroy.Num();
    // Not "OwnedComponents": that name is AActor's own member.
    TInlineComponentArray<UInstancedStaticMeshComponent*> AttachedInstanceComponents(this);
    for (UInstancedStaticMeshComponent* Component : AttachedInstanceComponents)
    {
        if (IsValid(Component) && Component->ComponentTags.Contains(StructureTag))
        {
            ComponentsToDestroy.Add(Component);
        }
    }
    if (ComponentsToDestroy.Num() > ReferencedCount)
    {
        UE_LOG(
            LogInfinityStageStructure,
            Display,
            TEXT("INFINITY_STAGE_STRUCTURE_ORPHANS_RECOVERED actor='%s' components=%d"),
            *GetActorNameOrLabel(),
            ComponentsToDestroy.Num() - ReferencedCount);
    }

    for (UInstancedStaticMeshComponent* Component : ComponentsToDestroy)
    {
        Component->Modify();
        RemoveInstanceComponent(Component);
        Component->DestroyComponent();
    }
    ManagedComponents.Reset();

    // The tube lights, recovered by tag the same way.
    TSet<URectLightComponent*> LightsToDestroy;
    for (URectLightComponent* Light : ManagedLights)
    {
        if (IsValid(Light))
        {
            LightsToDestroy.Add(Light);
        }
    }
    const int32 ReferencedLightCount = LightsToDestroy.Num();
    TInlineComponentArray<URectLightComponent*> AttachedLights(this);
    for (URectLightComponent* Light : AttachedLights)
    {
        if (IsValid(Light) && Light->ComponentTags.Contains(StructureTag))
        {
            LightsToDestroy.Add(Light);
        }
    }
    if (LightsToDestroy.Num() > ReferencedLightCount)
    {
        UE_LOG(
            LogInfinityStageStructure,
            Display,
            TEXT("INFINITY_STAGE_STRUCTURE_ORPHANS_RECOVERED actor='%s' lights=%d"),
            *GetActorNameOrLabel(),
            LightsToDestroy.Num() - ReferencedLightCount);
    }
    for (URectLightComponent* Light : LightsToDestroy)
    {
        Light->Modify();
        RemoveInstanceComponent(Light);
        Light->DestroyComponent();
    }
    ManagedLights.Reset();
    StationCount = 0;
    CrossBeamCount = 0;
    RailSegmentCount = 0;
    GridHalfWidthCm = 0.0;
    BoardCount = 0;
    SlotCount = 0;
    GroovePieceCount = 0;
    ClothCount = 0;
    PortalPieceCount = 0;
    FixtureBodyCount = 0;
    HangingLineCount = 0;
    MovingLightsWithoutHousing = 0;
    UnderpassColumnCount = 0;
    UnderpassPierCount = 0;
    UnderpassKneeCount = 0;
    UnderpassDeckCount = 0;
    UnderpassCatwalkCount = 0;
    UnderpassTubeCount = 0;
    UnderpassTubeLightCount = 0;
    UnderpassTubeLightEveryUsed = 0;
    UnderpassTubeBlinkers.Reset();
    UnderpassTubeBlinkComponent = nullptr;
    TubeBlinkLit.Reset();
    UnderpassFencePanelCount = 0;
    UnderpassFenceOverlayCount = 0;
    UnderpassFenceRowCount = 0;
    UnderpassFenceStackTopCm = 0.0;
    StationSignature = 0;
    MarkPackageDirty();
}

bool AInfinityStageStructureActor::MaterializeStructure()
{
    if (GetWorld() && GetWorld()->IsGameWorld())
    {
        UE_LOG(LogInfinityStageStructure, Error, TEXT("MaterializeStructure is editor authoring only; the structure must exist before PIE."));
        return false;
    }

    // Validate everything before clearing, so a failure leaves the last good
    // building standing rather than an empty stage.
    TArray<FInfinityStructureStation> Stations;
    FString Error;
    if (!GatherStations(Stations, Error))
    {
        UE_LOG(LogInfinityStageStructure, Error, TEXT("%s Keeping the previous structure."), *Error);
        return false;
    }
    // A mesh that will not load is an error; a material that will not load only
    // falls back to the mesh's own, since the geometry is still right.
    bool bMeshesLoaded = true;
    const auto LoadMesh = [&bMeshesLoaded](const TSoftObjectPtr<UStaticMesh>& Mesh, const TCHAR* MeshRole) -> UStaticMesh*
    {
        UStaticMesh* Loaded = Mesh.LoadSynchronous();
        if (!Loaded)
        {
            UE_LOG(LogInfinityStageStructure, Error, TEXT("%s mesh '%s' does not load. Keeping the previous structure."),
                MeshRole, *Mesh.ToSoftObjectPath().ToString());
            bMeshesLoaded = false;
        }
        return Loaded;
    };
    const auto LoadMaterial = [](const TSoftObjectPtr<UMaterialInterface>& Material, const TCHAR* MaterialRole) -> UMaterialInterface*
    {
        UMaterialInterface* Loaded = Material.LoadSynchronous();
        if (!Loaded && !Material.IsNull())
        {
            UE_LOG(LogInfinityStageStructure, Warning, TEXT("%s material '%s' does not load; using the mesh's own."),
                MaterialRole, *Material.ToSoftObjectPath().ToString());
        }
        return Loaded;
    };
    UStaticMesh* BeamMesh = Gridiron.bEnabled ? LoadMesh(Gridiron.BeamMesh, TEXT("Gridiron beam")) : nullptr;
    // The portal has its own timber when one is pinned; otherwise it is built from
    // the gridiron's, as it always was, which it needs even where a Passage has no
    // grid. Pinning lets the gridiron change (underpass iron) under a wooden portal.
    const bool bPortalOwnMesh = !Portal.PortalMesh.IsNull();
    UStaticMesh* PortalMeshLoaded = Portal.bEnabled
        ? LoadMesh(bPortalOwnMesh ? Portal.PortalMesh : Gridiron.BeamMesh,
            bPortalOwnMesh ? TEXT("Portal timber") : TEXT("Portal timber (gridiron beam)"))
        : nullptr;
    const TSoftObjectPtr<UMaterialInterface>& PortalMaterialSource =
        Portal.PortalMaterial.IsNull() ? Gridiron.Material : Portal.PortalMaterial;
    UStaticMesh* BoardMesh = Ground.bEnabled ? LoadMesh(Ground.BoardMesh, TEXT("Ground board")) : nullptr;
    UStaticMesh* UnderstageMesh = Ground.bEnabled && Ground.bUnderstage
        ? LoadMesh(Ground.UnderstageMesh, TEXT("Understage"))
        : nullptr;
    UStaticMesh* BodyMesh = Fixtures.bEnabled ? LoadMesh(Fixtures.BodyMesh, TEXT("Fixture body")) : nullptr;
    // Cloth pieces arrive from another stream on their own schedule, so a piece
    // that will not load is skipped with a warning rather than failing the build.
    TArray<UStaticMesh*> ClothPieces;
    if (Cloth.bEnabled)
    {
        for (const TSoftObjectPtr<UStaticMesh>& Piece : Cloth.Pieces)
        {
            if (UStaticMesh* Loaded = Piece.LoadSynchronous())
            {
                ClothPieces.Add(Loaded);
            }
            else
            {
                UE_LOG(LogInfinityStageStructure, Warning, TEXT("Cloth piece '%s' does not load; skipping it."),
                    *Piece.ToSoftObjectPath().ToString());
            }
        }
    }
    const bool bFixtureLines = Fixtures.bEnabled && Fixtures.bHangFromGrid && Gridiron.bEnabled;
    const bool bPortalLines = Portal.bEnabled && Portal.HangingLines > 0;
    UStaticMesh* LineMesh = bFixtureLines || bPortalLines
        ? LoadMesh(Fixtures.LineMesh, TEXT("Hanging line"))
        : nullptr;
    // The underpass is set a part at a time from Python, so a part with no mesh is
    // skipped rather than failed; a mesh that is set but will not load still fails.
    const auto LoadUnderpassMesh = [&LoadMesh](const bool bPartOn, const TSoftObjectPtr<UStaticMesh>& Mesh, const TCHAR* MeshRole) -> UStaticMesh*
    {
        return bPartOn && !Mesh.IsNull() ? LoadMesh(Mesh, MeshRole) : nullptr;
    };
    const bool bUnderpassColumns = Underpass.bEnabled && Underpass.bColumns;
    UStaticMesh* UnderpassColumnMesh = LoadUnderpassMesh(bUnderpassColumns, Underpass.ColumnMesh, TEXT("Underpass column"));
    UStaticMesh* UnderpassPierMesh = LoadUnderpassMesh(bUnderpassColumns, Underpass.PierMesh, TEXT("Underpass pier"));
    UStaticMesh* UnderpassKneeMesh = LoadUnderpassMesh(bUnderpassColumns && Underpass.bKnees, Underpass.KneeMesh, TEXT("Underpass knee"));
    UStaticMesh* UnderpassDeckMesh = LoadUnderpassMesh(Underpass.bEnabled && Underpass.bDeck, Underpass.DeckMesh, TEXT("Underpass deck"));
    UStaticMesh* UnderpassCatwalkMesh = LoadUnderpassMesh(Underpass.bEnabled && Underpass.bCatwalk, Underpass.CatwalkMesh, TEXT("Underpass catwalk"));
    UStaticMesh* UnderpassTubeMesh = LoadUnderpassMesh(Underpass.bEnabled && Underpass.bTubes, Underpass.TubeMesh, TEXT("Underpass tube"));
    // A fence variant is loaded only when it can be chosen (weight above 0); its
    // overlay only with its panel.
    TArray<UStaticMesh*> UnderpassFenceMeshes;
    TArray<UStaticMesh*> UnderpassFenceOverlayMeshes;
    for (int32 Variant = 0; Variant < FInfinityStageUnderpassSettings::FenceVariantCount; ++Variant)
    {
        const FInfinityStageFenceVariant& Kind = Underpass.GetFenceVariant(Variant);
        const bool bVariantOn = Underpass.bEnabled && Underpass.bFence && Kind.Weight > 0.0;
        UStaticMesh* Panel = LoadUnderpassMesh(bVariantOn, Kind.Mesh, TEXT("Underpass fence panel"));
        UnderpassFenceMeshes.Add(Panel);
        UnderpassFenceOverlayMeshes.Add(LoadUnderpassMesh(bVariantOn && Panel != nullptr, Kind.OverlayMesh, TEXT("Underpass fence overlay")));
    }
    // Stack mode: one plan for the fence and the fence-top tubes. The row is the
    // tallest built bay (built = loaded and a finite weight above 0, exactly the
    // fence's own rule). No built bay, or any other mode: the tubes read
    // FenceHeightCm as they always have.
    FInfinityStageFenceStackPlan FenceStack;
    double FenceTopAboveBaseCm = FMath::Max(1.0, Underpass.FenceHeightCm);
    if (Underpass.FenceHeightMode == EInfinityFenceHeightMode::Stack)
    {
        double FenceRowCm = 0.0;
        for (int32 Variant = 0; Variant < FInfinityStageUnderpassSettings::FenceVariantCount; ++Variant)
        {
            const double Weight = Underpass.GetFenceVariant(Variant).Weight;
            if (UnderpassFenceMeshes[Variant] && FMath::IsFinite(Weight) && Weight > 0.0)
            {
                FenceRowCm = FMath::Max(FenceRowCm, UnderpassFenceMeshes[Variant]->GetBoundingBox().GetSize().Z);
            }
        }
        if (FenceRowCm > UE_KINDA_SMALL_NUMBER)
        {
            FenceStack = PlanFenceStack(Underpass.FenceHeightCm, FenceRowCm, Underpass.bFenceStackCutTopRow);
            FenceTopAboveBaseCm = FenceStack.TopCm;
        }
    }
    if (!bMeshesLoaded)
    {
        return false;
    }

    ClearStructure();
    Modify();

    // Everything is placed in world space and the actor is never moved here: a
    // re-fit must not drag anything the artist attached to the building.
    StationCount = Stations.Num();
    if (BeamMesh && Gridiron.bEnabled)
    {
        UInstancedStaticMeshComponent* Component = CreateManagedComponent(
            TEXT("StructureGridiron"),
            GridironLayerTag,
            BeamMesh,
            LoadMaterial(Gridiron.Material, TEXT("Gridiron")),
            Gridiron.bCastShadow);
        BuildGridiron(Stations, *Component, BeamMesh->GetBoundingBox());
    }
    if (BoardMesh)
    {
        BuildGround(
            Stations,
            *BoardMesh,
            LoadMaterial(Ground.BoardMaterial, TEXT("Ground board")),
            UnderstageMesh,
            LoadMaterial(Ground.UnderstageMaterial, TEXT("Understage")),
            LoadMaterial(Ground.GrooveMaterial, TEXT("Groove")));
    }
    if (!ClothPieces.IsEmpty())
    {
        BuildCloth(Stations, ClothPieces, LoadMaterial(Cloth.Material, TEXT("Cloth")));
    }
    if (PortalMeshLoaded)
    {
        BuildPortal(
            Stations,
            *PortalMeshLoaded,
            LoadMaterial(PortalMaterialSource, TEXT("Portal timber")),
            BoardMesh,
            LoadMaterial(Ground.BoardMaterial, TEXT("Forestage board")),
            bPortalLines ? LineMesh : nullptr,
            LoadMaterial(Fixtures.LineMaterial, TEXT("Portal line")));
    }
    if (BodyMesh)
    {
        BuildFixtures(
            Stations,
            *BodyMesh,
            LoadMaterial(Fixtures.BodyMaterial, TEXT("Fixture body")),
            bFixtureLines ? LineMesh : nullptr,
            LoadMaterial(Fixtures.LineMaterial, TEXT("Hanging line")));
    }
    if (Underpass.bEnabled)
    {
        // A material is loaded only for a part that will be built, so a skipped
        // part never warns about its material.
        const auto UnderpassPart = [&LoadMaterial](UStaticMesh* Mesh, const TSoftObjectPtr<UMaterialInterface>& Material, const TCHAR* MaterialRole)
        {
            FInfinityUnderpassPart Part;
            Part.Mesh = Mesh;
            Part.Material = Mesh ? LoadMaterial(Material, MaterialRole) : nullptr;
            return Part;
        };
        BuildUnderpass(
            Stations,
            UnderpassPart(UnderpassColumnMesh, Underpass.ColumnMaterial, TEXT("Underpass column")),
            UnderpassPart(UnderpassPierMesh, Underpass.PierMaterial, TEXT("Underpass pier")),
            UnderpassPart(UnderpassKneeMesh, Underpass.KneeMaterial, TEXT("Underpass knee")),
            UnderpassPart(UnderpassDeckMesh, Underpass.DeckMaterial, TEXT("Underpass deck")),
            UnderpassPart(UnderpassCatwalkMesh, Underpass.CatwalkMaterial, TEXT("Underpass catwalk")));
        if (Underpass.bTubes)
        {
            BuildUnderpassTubes(
                Stations,
                UnderpassPart(UnderpassTubeMesh, Underpass.TubeMaterial, TEXT("Underpass tube")),
                Underpass.bTubeLights ? LoadMaterial(Underpass.TubeLightFunctionMaterial, TEXT("Underpass tube light function")) : nullptr,
                FenceTopAboveBaseCm);
        }
        if (Underpass.bFence)
        {
            TArray<FInfinityUnderpassPart> FencePanels;
            TArray<FInfinityUnderpassPart> FenceOverlays;
            for (int32 Variant = 0; Variant < FInfinityStageUnderpassSettings::FenceVariantCount; ++Variant)
            {
                const FInfinityStageFenceVariant& Kind = Underpass.GetFenceVariant(Variant);
                FencePanels.Add(UnderpassPart(UnderpassFenceMeshes[Variant], Kind.Material, TEXT("Underpass fence panel")));
                FenceOverlays.Add(UnderpassPart(UnderpassFenceOverlayMeshes[Variant], Kind.OverlayMaterial, TEXT("Underpass fence overlay")));
            }
            BuildUnderpassFence(Stations, FencePanels, FenceOverlays, FenceStack);
        }
    }
    int32 MovingLights = 0;
    StationSignature = ComputeStructureSignature(
        Stations,
        GatherFixturePlacements(*Passage->ShowAsset, Stations, MovingLights));
    MarkPackageDirty();

    int32 InstanceCount = 0;
    for (const UInstancedStaticMeshComponent* Component : ManagedComponents)
    {
        InstanceCount += Component ? Component->GetInstanceCount() : 0;
    }
    UE_LOG(
        LogInfinityStageStructure,
        Display,
        TEXT("INFINITY_STAGE_STRUCTURE_OK actor='%s' passage='%s' stations=%d cross_beams=%d rails=%d ")
        TEXT("boards=%d slots=%d cloths=%d portal=%d housings=%d lines=%d moving_lights_skipped=%d instances=%d half_width_cm=%.0f ")
        TEXT("underpass_columns=%d underpass_piers=%d underpass_knees=%d underpass_decks=%d underpass_catwalks=%d ")
        TEXT("underpass_tubes=%d underpass_tube_lights=%d underpass_fence_panels=%d"),
        *GetActorNameOrLabel(),
        *Passage->GetActorNameOrLabel(),
        StationCount,
        CrossBeamCount,
        RailSegmentCount,
        BoardCount,
        SlotCount,
        ClothCount,
        PortalPieceCount,
        FixtureBodyCount,
        HangingLineCount,
        MovingLightsWithoutHousing,
        InstanceCount,
        GridHalfWidthCm,
        UnderpassColumnCount,
        UnderpassPierCount,
        UnderpassKneeCount,
        UnderpassDeckCount,
        UnderpassCatwalkCount,
        UnderpassTubeCount,
        UnderpassTubeLightCount,
        UnderpassFencePanelCount);
    return true;
}

void AInfinityStageStructureActor::MaterializeStructureInEditor()
{
    if (!MaterializeStructure())
    {
        UE_LOG(
            LogInfinityStageStructure,
            Error,
            TEXT("Infinity Stage Materialize Structure editor action failed for '%s'; the previous structure was retained."),
            *GetActorNameOrLabel());
    }
}

UInstancedStaticMeshComponent* AInfinityStageStructureActor::CreateManagedComponent(
    const FName BaseName,
    const FName LayerTag,
    UStaticMesh* Mesh,
    UMaterialInterface* Material,
    const bool bCastShadow)
{
    const FName ComponentName = MakeUniqueObjectName(this, UInstancedStaticMeshComponent::StaticClass(), BaseName);
    UInstancedStaticMeshComponent* Component =
        NewObject<UInstancedStaticMeshComponent>(this, ComponentName, RF_Transactional);
    Component->CreationMethod = EComponentCreationMethod::Instance;
    Component->ComponentTags.Add(StructureTag);
    Component->ComponentTags.Add(LayerTag);
    Component->SetupAttachment(SceneRoot);
    Component->SetMobility(EComponentMobility::Static);
    Component->SetStaticMesh(Mesh);
    if (Material)
    {
        for (int32 MaterialIndex = 0; MaterialIndex < FMath::Max(1, Mesh->GetStaticMaterials().Num()); ++MaterialIndex)
        {
            Component->SetMaterial(MaterialIndex, Material);
        }
    }
    Component->SetCastShadow(bCastShadow);
    Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Component->SetCanEverAffectNavigation(false);
    Component->SetNumCustomDataFloats(TimberCustomDataFloats);
    AddInstanceComponent(Component);
    Component->RegisterComponent();
    ManagedComponents.Add(Component);
    return Component;
}

FInfinityStageFenceStackPlan AInfinityStageStructureActor::PlanFenceStack(
    const double IntendedCm, const double RowCm, const bool bCutTopRow)
{
    FInfinityStageFenceStackPlan Plan;
    const double Row = FMath::Max(1.0, FMath::IsFinite(RowCm) ? RowCm : 1.0);
    const double Intended = FMath::Max(1.0, FMath::IsFinite(IntendedCm) ? IntendedCm : 1.0);
    Plan.RowHeightCm = Row;
    Plan.TopRowHeightCm = Row;
    if (!bCutTopRow)
    {
        Plan.Rows = FMath::Max(1, FMath::RoundToInt32(Intended / Row));
    }
    else
    {
        const int32 Whole = FMath::FloorToInt32(Intended / Row);
        const double Rest = Intended - Row * Whole;
        if (Whole == 0)
        {
            // Lower than one row: one row, cut to the height.
            Plan.Rows = 1;
            Plan.TopRowHeightCm = Intended;
        }
        else if (Rest >= Row * FInfinityStageUnderpassSettings::FenceStackMinCutFraction)
        {
            Plan.Rows = Whole + 1;
            Plan.TopRowHeightCm = Rest;
        }
        else
        {
            Plan.Rows = Whole;
        }
    }
    Plan.TopCm = Row * (Plan.Rows - 1) + Plan.TopRowHeightCm;
    return Plan;
}

void AInfinityStageStructureActor::BuildUnderpassFence(
    const TArray<FInfinityStructureStation>& Stations,
    const TArray<FInfinityUnderpassPart>& Panels,
    const TArray<FInfinityUnderpassPart>& Overlays,
    const FInfinityStageFenceStackPlan& StackPlan)
{
    constexpr int32 VariantCount = FInfinityStageUnderpassSettings::FenceVariantCount;
    if (Stations.Num() < 2 || Panels.Num() != VariantCount || Overlays.Num() != VariantCount)
    {
        return;
    }

    // The weights. Every variant with a weight is in the first draw, built or not,
    // so nulling one variant's mesh re-rolls only the panels that drew it; the
    // second draw re-deals those among the built variants by their weights.
    double Weights[VariantCount];
    double AllWeight = 0.0;
    double BuiltWeight = 0.0;
    FBox Bounds[VariantCount];
    // The tile width: the widest built bay. The FenceBay kit's bays are all one size.
    double TileWidthCm = 0.0;
    for (int32 Variant = 0; Variant < VariantCount; ++Variant)
    {
        const double Weight = Underpass.GetFenceVariant(Variant).Weight;
        Weights[Variant] = FMath::IsFinite(Weight) ? FMath::Max(0.0, Weight) : 0.0;
        AllWeight += Weights[Variant];
        const bool bBuilt = Panels[Variant].Mesh && Weights[Variant] > 0.0;
        BuiltWeight += bBuilt ? Weights[Variant] : 0.0;
        Bounds[Variant] = Panels[Variant].Mesh ? Panels[Variant].Mesh->GetBoundingBox() : FBox(ForceInit);
        if (bBuilt)
        {
            TileWidthCm = FMath::Max(TileWidthCm, Bounds[Variant].GetSize().X);
        }
    }
    if (BuiltWeight <= 0.0 || TileWidthCm <= UE_KINDA_SMALL_NUMBER)
    {
        return;
    }
    // Stack rows above the ground row draw from the same weights with every
    // ground-row-only variant (the door gap) at 0.
    double UpperWeights[VariantCount];
    double UpperAllWeight = 0.0;
    double UpperBuiltWeight = 0.0;
    for (int32 Variant = 0; Variant < VariantCount; ++Variant)
    {
        UpperWeights[Variant] = Underpass.GetFenceVariant(Variant).bGroundRowOnly ? 0.0 : Weights[Variant];
        UpperAllWeight += UpperWeights[Variant];
        UpperBuiltWeight += Panels[Variant].Mesh && UpperWeights[Variant] > 0.0 ? UpperWeights[Variant] : 0.0;
    }
    const auto PickFrom = [&Panels](const double* InWeights, const double InAllWeight, const double InBuiltWeight,
                                    const float Roll, const bool bBuiltOnly) -> int32
    {
        double Remaining = static_cast<double>(Roll) * (bBuiltOnly ? InBuiltWeight : InAllWeight);
        int32 LastEligible = INDEX_NONE;
        for (int32 Variant = 0; Variant < VariantCount; ++Variant)
        {
            if (InWeights[Variant] <= 0.0 || (bBuiltOnly && !Panels[Variant].Mesh))
            {
                continue;
            }
            LastEligible = Variant;
            if (Remaining < InWeights[Variant])
            {
                return Variant;
            }
            Remaining -= InWeights[Variant];
        }
        return LastEligible;
    };
    const auto Pick = [&PickFrom, &Weights, &UpperWeights, AllWeight, BuiltWeight, UpperAllWeight, UpperBuiltWeight](
                          const float Roll, const bool bBuiltOnly, const bool bUpperRow) -> int32
    {
        return bUpperRow
            ? PickFrom(UpperWeights, UpperAllWeight, UpperBuiltWeight, Roll, bBuiltOnly)
            : PickFrom(Weights, AllWeight, BuiltWeight, Roll, bBuiltOnly);
    };

    // Stack: rows of the plan's height, the last perhaps cut. Any other mode is
    // one row, built exactly as before the stack existed.
    const bool bStack = Underpass.FenceHeightMode == EInfinityFenceHeightMode::Stack && StackPlan.RowHeightCm > UE_KINDA_SMALL_NUMBER;
    const int32 Rows = bStack ? FMath::Max(1, StackPlan.Rows) : 1;
    if (bStack)
    {
        UnderpassFenceRowCount = Rows;
        UnderpassFenceStackTopCm = StackPlan.TopCm;
        UE_LOG(LogInfinityStageStructure, Display,
            TEXT("INFINITY_STAGE_STRUCTURE_FENCE_STACK actor='%s' rows=%d row_cm=%.2f top_row_cm=%.2f top_cm=%.2f intended_cm=%.1f cut_top_row=%d"),
            *GetActorNameOrLabel(), Rows, StackPlan.RowHeightCm, StackPlan.TopRowHeightCm, StackPlan.TopCm,
            Underpass.FenceHeightCm, Underpass.bFenceStackCutTopRow ? 1 : 0);
        if (Rows > 1 && UpperBuiltWeight <= 0.0)
        {
            UE_LOG(LogInfinityStageStructure, Warning,
                TEXT("INFINITY_STAGE_STRUCTURE_FENCE_STACK_NO_UPPER_VARIANT actor='%s' (every built variant is ground-row-only: the rows above it stay empty)"),
                *GetActorNameOrLabel());
        }
    }

    // Native height keeps each bay as authored; say so where that is not the
    // height the fence was meant to be (W&T's 3 m bays will match).
    const bool bNativeHeight = Underpass.FenceHeightMode == EInfinityFenceHeightMode::Native;
    const double IntendedHeightCm = FMath::Max(1.0, Underpass.FenceHeightCm);
    for (int32 Variant = 0; bNativeHeight && Variant < VariantCount; ++Variant)
    {
        const double OwnHeightCm = Bounds[Variant].GetSize().Z;
        if (Panels[Variant].Mesh && Weights[Variant] > 0.0 && FMath::Abs(OwnHeightCm - IntendedHeightCm) > IntendedHeightCm * 0.1)
        {
            UE_LOG(LogInfinityStageStructure, Warning,
                TEXT("INFINITY_STAGE_STRUCTURE_FENCE_HEIGHT_MISMATCH actor='%s' variant=%c mesh='%s' native_cm=%.1f intended_cm=%.1f (Native height mode builds the mesh's own)"),
                *GetActorNameOrLabel(), TCHAR('A' + Variant), *Panels[Variant].Mesh->GetPathName(), OwnHeightCm, IntendedHeightCm);
        }
    }

    // The column rhythm and feet exactly as BuildUnderpass stands them: every Nth
    // station and the last, an end foot stepped inside its end station. The fence
    // tests check that the tiles end on the built column centres, so a drift fails.
    const double ColumnLineCm = GetFloorHalfSpanCm(Stations) + FMath::Max(0.0, Underpass.ColumnOutsetCm);
    const double EndInsetCm = FMath::Max(FMath::Max(1.0, Underpass.PierSizeCm), FMath::Max(1.0, Underpass.ColumnDepthCm)) * 0.5;
    const double LineCm = ColumnLineCm - Underpass.FenceInsetCm;
    const double BaseCm = Ground.FloorHeightCm + Underpass.FenceBaseCm;
    const int32 Every = FMath::Max(1, Underpass.ColumnEvery);
    const int32 Last = Stations.Num() - 1;
    TArray<int32> ColumnStations;
    for (int32 Index = 0; Index <= Last; ++Index)
    {
        if (Index % Every == 0 || Index == Last)
        {
            ColumnStations.Add(Index);
        }
    }
    const auto FootOnLine = [&Stations, Last, EndInsetCm, LineCm, BaseCm](const int32 Index, const double Side)
    {
        const FTransform& World = Stations[Index].StationWorld;
        const double InsetCm = Index == 0 ? EndInsetCm : (Index == Last ? -EndInsetCm : 0.0);
        return World.GetLocation() + World.GetUnitAxis(EAxis::X) * InsetCm
            + World.GetUnitAxis(EAxis::Y) * (Side * LineCm) + World.GetUnitAxis(EAxis::Z) * BaseCm;
    };

    struct FVariantInstances
    {
        TArray<FTransform> Transforms;
        TArray<float> Data;
    };
    FVariantInstances Built[VariantCount];

    for (int32 Gap = 0; Gap + 1 < ColumnStations.Num(); ++Gap)
    {
        const int32 From = ColumnStations[Gap];
        const int32 To = ColumnStations[Gap + 1];
        const FVector BayUp = (Stations[From].StationWorld.GetUnitAxis(EAxis::Z)
            + Stations[To].StationWorld.GetUnitAxis(EAxis::Z)).GetSafeNormal();
        for (const double Side : { -1.0, 1.0 })
        {
            if (Side > 0.0 && !Underpass.bFenceBothSides)
            {
                continue;
            }
            const FVector Start = FootOnLine(From, Side);
            const FVector End = FootOnLine(To, Side);
            const double ChordCm = FVector::Distance(Start, End);
            if (ChordCm < 1.0)
            {
                continue;
            }
            // Tiles along the chord, each its slot's length: X scale close to 1.
            const int32 Tiles = FMath::Max(1, FMath::RoundToInt32(ChordCm / TileWidthCm));
            const double SlotCm = ChordCm / Tiles;
            const FVector Along = (End - Start) / ChordCm;
            // Local X along the chord, Z up, so +Y faces the route on either side:
            // the -Y side runs with the stations, the +Y side against them.
            const FQuat Rotation = FRotationMatrix::MakeFromXZ(Side < 0.0 ? Along : -Along, BayUp).ToQuat();
            for (int32 Tile = 0; Tile < Tiles; ++Tile)
            {
                for (int32 Row = 0; Row < Rows; ++Row)
                {
                    // Three draws, each its own statement and always made, so no
                    // choice depends on another tile or row, or on which variants
                    // are built. Row 0's stream is the unstacked fence's own.
                    FRandomStream Stream = MakeFenceRowStream(Stations[From].CueGuid, Side < 0.0 ? 0 : 1, Tile, Row, Underpass.FenceSeed);
                    const float Roll = Stream.FRand();
                    const float Redeal = Stream.FRand();
                    const float Tone = Stream.FRand();
                    const bool bUpperRow = Row > 0;
                    int32 Variant = Pick(Roll, false, bUpperRow);
                    if (Variant == INDEX_NONE || !Panels[Variant].Mesh)
                    {
                        Variant = Pick(Redeal, true, bUpperRow);
                    }
                    if (Variant == INDEX_NONE)
                    {
                        continue;
                    }
                    const double DepthCm = FMath::Max(1.0, Bounds[Variant].GetSize().Y);
                    double HeightCm = bNativeHeight ? FMath::Max(1.0, Bounds[Variant].GetSize().Z) : IntendedHeightCm;
                    double BottomCm = 0.0;
                    if (bStack)
                    {
                        HeightCm = Row == Rows - 1 ? StackPlan.TopRowHeightCm : StackPlan.RowHeightCm;
                        BottomCm = StackPlan.RowHeightCm * Row;
                    }
                    const FVector SizeCm(SlotCm, DepthCm, HeightCm);
                    const FVector Centre = Start + Along * (SlotCm * (Tile + 0.5)) + BayUp * (BottomCm + HeightCm * 0.5);
                    Built[Variant].Transforms.Add(FitMeshToTimber(Bounds[Variant], Centre, Rotation, SizeCm));
                    Built[Variant].Data.Append({ Tone, static_cast<float>(SlotCm), static_cast<float>(DepthCm), static_cast<float>(HeightCm) });
                }
            }
        }
    }

    // One layer per variant, and its overlay's on the very same transforms. The
    // variant's material goes on slot 0 alone: the kit's concertina (slot 1)
    // keeps its own metal.
    const auto Emit = [this](const FVariantInstances& Instances, const TCHAR* BaseName, const FName LayerTag,
                             const FInfinityUnderpassPart& Part)
    {
        UInstancedStaticMeshComponent* Component =
            CreateManagedComponent(FName(BaseName), LayerTag, Part.Mesh, nullptr, Underpass.bFenceCastShadow);
        Component->ComponentTags.Add(UnderpassFenceTag);
        if (Part.Material)
        {
            Component->SetMaterial(0, Part.Material);
        }
        ApplyInstances(*Component, Instances.Transforms, Instances.Data);
    };
    const TCHAR* const PanelNames[] = {
        TEXT("StructureUnderpassFenceA"), TEXT("StructureUnderpassFenceB"),
        TEXT("StructureUnderpassFenceC"), TEXT("StructureUnderpassFenceD") };
    const TCHAR* const OverlayNames[] = {
        TEXT("StructureUnderpassFenceOverlayA"), TEXT("StructureUnderpassFenceOverlayB"),
        TEXT("StructureUnderpassFenceOverlayC"), TEXT("StructureUnderpassFenceOverlayD") };
    for (int32 Variant = 0; Variant < VariantCount; ++Variant)
    {
        if (Built[Variant].Transforms.IsEmpty())
        {
            continue;
        }
        Emit(Built[Variant], PanelNames[Variant], UnderpassFenceLayerTags[Variant], Panels[Variant]);
        UnderpassFencePanelCount += Built[Variant].Transforms.Num();
        if (Overlays[Variant].Mesh)
        {
            Emit(Built[Variant], OverlayNames[Variant], UnderpassFenceOverlayLayerTags[Variant], Overlays[Variant]);
            UnderpassFenceOverlayCount += Built[Variant].Transforms.Num();
        }
    }
}

URectLightComponent* AInfinityStageStructureActor::CreateManagedLight(const FName BaseName, const FName LayerTag)
{
    // Owned exactly as CreateManagedComponent owns an instance layer: transactional,
    // an instance component of this actor, tagged, attached to the root and saved
    // with the level. Movable, unlike the iron: a tube is dimmed, flickered and
    // failed at run time, and nothing here is baked. A movable child under the
    // static root is allowed; only the reverse is not.
    const FName ComponentName = MakeUniqueObjectName(this, URectLightComponent::StaticClass(), BaseName);
    URectLightComponent* Light = NewObject<URectLightComponent>(this, ComponentName, RF_Transactional);
    Light->CreationMethod = EComponentCreationMethod::Instance;
    Light->ComponentTags.Add(StructureTag);
    Light->ComponentTags.Add(LayerTag);
    Light->SetupAttachment(SceneRoot);
    Light->SetMobility(EComponentMobility::Movable);
    AddInstanceComponent(Light);
    Light->RegisterComponent();
    ManagedLights.Add(Light);
    return Light;
}

void AInfinityStageStructureActor::BuildGridiron(
    const TArray<FInfinityStructureStation>& Stations,
    UInstancedStaticMeshComponent& Component,
    const FBox& MeshBounds)
{
    double WidestPanelCm = 0.0;
    for (const FInfinityStructureStation& Station : Stations)
    {
        WidestPanelCm = FMath::Max(WidestPanelCm, Station.HalfWidthCm);
    }
    // One width for the whole Passage: a gridiron is a rigid building, and rails
    // that followed each pair's width would wander.
    const double HalfSpanCm = WidestPanelCm + Gridiron.OverhangCm;
    GridHalfWidthCm = HalfSpanCm;

    const double Variation = FMath::Clamp(Gridiron.SectionVariation, 0.0, 0.5);
    const double MaxTwist = FMath::Clamp(Gridiron.TwistDegrees, 0.0, 10.0);
    TArray<FTransform> Transforms;
    TArray<float> CustomData;
    const auto AddTimber = [&](
        const FVector& CentreWorld,
        const FVector& Along,
        const FVector& Up,
        const double LengthCm,
        FRandomStream Stream)
    {
        // Always draw the same four numbers in the same order, so changing one
        // wear setting never reshuffles the others.
        const double WidthJitter = Stream.FRandRange(-1.0, 1.0);
        const double DepthJitter = Stream.FRandRange(-1.0, 1.0);
        const double TwistJitter = Stream.FRandRange(-1.0, 1.0);
        const float Tone = Stream.FRand();
        const FVector SizeCm(
            LengthCm,
            Gridiron.BeamWidthCm * (1.0 + WidthJitter * Variation),
            Gridiron.BeamDepthCm * (1.0 + DepthJitter * Variation));
        const FQuat Rotation = FRotationMatrix::MakeFromXZ(Along, Up).ToQuat()
            * FQuat(FVector::ForwardVector, FMath::DegreesToRadians(TwistJitter * MaxTwist));
        Transforms.Add(FitMeshToTimber(MeshBounds, CentreWorld, Rotation, SizeCm));
        CustomData.Append({ Tone, static_cast<float>(SizeCm.X), static_cast<float>(SizeCm.Y), static_cast<float>(SizeCm.Z) });
    };

    const int32 Every = FMath::Max(1, Gridiron.CrossBeamEvery);
    // Rails sit on top of the crosses: rail centre one nominal depth higher.
    const double RailLiftCm = Gridiron.HeightCm + Gridiron.BeamDepthCm;
    for (int32 Index = 0; Index < Stations.Num(); ++Index)
    {
        const FInfinityStructureStation& Station = Stations[Index];
        const FVector Origin = Station.StationWorld.GetLocation();
        const FVector Across = Station.StationWorld.GetUnitAxis(EAxis::Y);
        const FVector Up = Station.StationWorld.GetUnitAxis(EAxis::Z);
        if (Index % Every == 0)
        {
            AddTimber(
                Origin + Up * Gridiron.HeightCm,
                Across,
                Up,
                HalfSpanCm * 2.0,
                MakeTimberStream(Station.CueGuid, ETimberPart::CrossBeam));
            ++CrossBeamCount;
        }
        if (Index + 1 >= Stations.Num())
        {
            continue;
        }
        const FInfinityStructureStation& Next = Stations[Index + 1];
        const FVector NextOrigin = Next.StationWorld.GetLocation();
        const FVector NextAcross = Next.StationWorld.GetUnitAxis(EAxis::Y);
        const FVector NextUp = Next.StationWorld.GetUnitAxis(EAxis::Z);
        const FVector RailUp = (Up + NextUp).GetSafeNormal();
        for (const double Side : { -1.0, 1.0 })
        {
            const FVector Start = Origin + Across * (Side * HalfSpanCm) + Up * RailLiftCm;
            const FVector End = NextOrigin + NextAcross * (Side * HalfSpanCm) + NextUp * RailLiftCm;
            const double LengthCm = FVector::Distance(Start, End);
            if (LengthCm < 1.0)
            {
                continue;
            }
            AddTimber(
                (Start + End) * 0.5,
                (End - Start) / LengthCm,
                RailUp,
                LengthCm,
                MakeTimberStream(Station.CueGuid, Side < 0.0 ? ETimberPart::RailNegative : ETimberPart::RailPositive));
            ++RailSegmentCount;
        }
    }

    ApplyInstances(Component, Transforms, CustomData);
}

void AInfinityStageStructureActor::BuildGround(
    const TArray<FInfinityStructureStation>& Stations,
    UStaticMesh& BoardMesh,
    UMaterialInterface* BoardMaterial,
    UStaticMesh* UnderstageMesh,
    UMaterialInterface* UnderstageMaterial,
    UMaterialInterface* GrooveMaterial)
{
    const USplineComponent& Route = *Passage->Route;
    const double RouteLengthCm = Route.GetSplineLength();
    const double StartCm = FMath::Clamp(Stations[0].DistanceCm - Ground.ApronCm, 0.0, RouteLengthCm);
    const double EndCm = FMath::Clamp(Stations.Last().DistanceCm + Ground.ApronCm, 0.0, RouteLengthCm);
    if (EndCm - StartCm < 1.0)
    {
        return;
    }

    const double HalfSpanCm = GetFloorHalfSpanCm(Stations);

    const double BoardWidthCm = FMath::Max(4.0, Ground.BoardWidthCm);
    const double GapCm = FMath::Max(0.0, Ground.BoardGapCm);
    const double ThicknessCm = FMath::Max(0.5, Ground.BoardThicknessCm);
    const double MinLengthCm = FMath::Max(20.0, FMath::Min(Ground.MinBoardLengthCm, Ground.MaxBoardLengthCm));
    const double MaxLengthCm = FMath::Max(MinLengthCm, Ground.MaxBoardLengthCm);
    const double HalfSlotCm = FMath::Max(1.0, Ground.SlotWidthCm) * 0.5;
    const double LanePitchCm = BoardWidthCm + GapCm;
    const int32 LaneCount = FMath::Max(1, FMath::FloorToInt32((HalfSpanCm * 2.0 + GapCm) / LanePitchCm));
    const double FirstLaneCm = -(LaneCount * LanePitchCm - GapCm) * 0.5 + BoardWidthCm * 0.5;

    // Where each station's slots begin, measured out from the route line, per
    // side: each side's slots start under that side's own wing, so an
    // asymmetric pair (P01: -750 / +500) still stands over its slots. A side
    // with no wing gets no slot, and no slot ever comes nearer the route line
    // than the cat's clearance, whatever the wings do.
    TArray<double> SlotInnerNegativeCm;
    TArray<double> SlotInnerPositiveCm;
    const auto SlotInner = [this, HalfSpanCm](const double WingCm)
    {
        const double InnerCm = FMath::Max(WingCm - Ground.SlotInboardCm, Ground.CatClearanceCm);
        return Ground.bCutChariotSlots && WingCm > 0.0 && InnerCm < HalfSpanCm
            ? InnerCm
            : TNumericLimits<double>::Max();
    };
    for (const FInfinityStructureStation& Station : Stations)
    {
        SlotInnerNegativeCm.Add(SlotInner(Station.NegativeSideCm));
        SlotInnerPositiveCm.Add(SlotInner(Station.PositiveSideCm));
        SlotCount += (SlotInnerNegativeCm.Last() < HalfSpanCm ? 1 : 0) + (SlotInnerPositiveCm.Last() < HalfSpanCm ? 1 : 0);
    }

    const FBox BoardBounds = BoardMesh.GetBoundingBox();
    TArray<FTransform> Boards;
    TArray<float> BoardData;
    const auto AddBoard = [&](const double LaneCm, const double FromCm, const double ToCm, FRandomStream& Stream)
    {
        const double LengthCm = ToCm - FromCm;
        if (LengthCm < 1.0)
        {
            return;
        }
        // Each board is a chord of the route, so a curving route still gets
        // straight timber rather than bent planks.
        const FTransform Frame = Route.GetTransformAtDistanceAlongSpline(
            (FromCm + ToCm) * 0.5, ESplineCoordinateSpace::World, false);
        const FVector CentreWorld = Frame.GetLocation()
            + Frame.GetUnitAxis(EAxis::Y) * LaneCm
            + Frame.GetUnitAxis(EAxis::Z) * (Ground.FloorHeightCm - ThicknessCm * 0.5);
        Boards.Add(FitMeshToTimber(BoardBounds, CentreWorld, Frame.GetRotation(), FVector(LengthCm, BoardWidthCm, ThicknessCm)));
        BoardData.Append({ Stream.FRand(), static_cast<float>(LengthCm), static_cast<float>(BoardWidthCm), static_cast<float>(ThicknessCm) });
    };

    for (int32 Lane = 0; Lane < LaneCount; ++Lane)
    {
        const double LaneCm = FirstLaneCm + Lane * LanePitchCm;
        const double LaneOuterCm = FMath::Abs(LaneCm) + BoardWidthCm * 0.5;
        const TArray<double>& SideSlotInnerCm = LaneCm < 0.0 ? SlotInnerNegativeCm : SlotInnerPositiveCm;
        // Stations are in route order, so the cuts this lane crosses are too.
        TArray<double> CutsCm;
        for (int32 Index = 0; Index < Stations.Num(); ++Index)
        {
            if (LaneOuterCm > SideSlotInnerCm[Index])
            {
                CutsCm.Add(Stations[Index].DistanceCm);
            }
        }
        FRandomStream Stream(static_cast<int32>(HashCombineFast(
            HashCombineFast(GetTypeHash(Passage->PassageGuid), ::GetTypeHash(static_cast<uint32>(ETimberPart::BoardLane))),
            ::GetTypeHash(Lane))));
        // Each lane starts part-way through a board, so joints stagger across the floor.
        // Two statements, never one product: C++ leaves the order of a product's operands
        // unspecified, and the 29 Sep rebuild flipped it here, re-rolling the joints of
        // every saved floor. Length first is the order the saved floors were laid in
        // (pinned by InfinityStage.Structure.SavedFloorsSurviveARebuild).
        const double FirstLengthCm = Stream.FRandRange(MinLengthCm, MaxLengthCm);
        double NextLengthCm = FirstLengthCm * Stream.FRandRange(0.2, 1.0);
        double FromCm = StartCm;
        int32 CutIndex = 0;
        while (FromCm < EndCm - 1.0)
        {
            while (CutIndex < CutsCm.Num() && CutsCm[CutIndex] + HalfSlotCm <= FromCm)
            {
                ++CutIndex;
            }
            double ToCm = FMath::Min(FromCm + NextLengthCm, EndCm);
            double NextFromCm = ToCm + GapCm;
            if (CutIndex < CutsCm.Num() && CutsCm[CutIndex] - HalfSlotCm < ToCm)
            {
                // The board stops at the slot's edge and the next begins beyond it.
                ToCm = CutsCm[CutIndex] - HalfSlotCm;
                NextFromCm = CutsCm[CutIndex] + HalfSlotCm;
                ++CutIndex;
            }
            AddBoard(LaneCm, FromCm, ToCm, Stream);
            FromCm = NextFromCm;
            NextLengthCm = Stream.FRandRange(MinLengthCm, MaxLengthCm);
        }
    }

    // Boards cast shadows: without them every lamp would light the understage
    // straight through the floor, and the slots would stop reading as dark cuts.
    UInstancedStaticMeshComponent* BoardComponent = CreateManagedComponent(
        TEXT("StructureGround"), GroundLayerTag, &BoardMesh, BoardMaterial, true);
    ApplyInstances(*BoardComponent, Boards, BoardData);
    BoardCount = Boards.Num();

    // Steel grooves: each slot's gap lined with a channel, two walls on the faces
    // where the boards stop and a bottom plate, running across the stage from the
    // first cut lane's inner edge to the floor's edge. Local X is the run.
    if (Ground.bSteelGrooves && SlotCount > 0)
    {
        const double PlateCm = FMath::Clamp(Ground.GroovePlateCm, 0.1, FMath::Min(HalfSlotCm, ThicknessCm * 0.5));
        const double FloorOuterCm = (LaneCount * LanePitchCm - GapCm) * 0.5;
        TArray<FTransform> Plates;
        TArray<float> PlateData;
        for (int32 Index = 0; Index < Stations.Num(); ++Index)
        {
            const FTransform Frame = Route.GetTransformAtDistanceAlongSpline(
                Stations[Index].DistanceCm, ESplineCoordinateSpace::World, false);
            const FVector Forward = Frame.GetUnitAxis(EAxis::X);
            const FVector Across = Frame.GetUnitAxis(EAxis::Y);
            const FVector Up = Frame.GetUnitAxis(EAxis::Z);
            FRandomStream Stream = MakeTimberStream(Stations[Index].CueGuid, ETimberPart::Groove);
            for (const double Side : { -1.0, 1.0 })
            {
                const double InnerCm = (Side < 0.0 ? SlotInnerNegativeCm : SlotInnerPositiveCm)[Index];
                if (InnerCm >= HalfSpanCm)
                {
                    continue;
                }
                // The first lane this slot cuts, counted from the route line out.
                double RunFromCm = FloorOuterCm;
                for (int32 Lane = 0; Lane < LaneCount; ++Lane)
                {
                    const double LaneCm = FMath::Abs(FirstLaneCm + Lane * LanePitchCm);
                    if (LaneCm + BoardWidthCm * 0.5 > InnerCm)
                    {
                        RunFromCm = FMath::Min(RunFromCm, LaneCm - BoardWidthCm * 0.5);
                    }
                }
                const double RunCm = FloorOuterCm - RunFromCm;
                if (RunCm < 1.0)
                {
                    continue;
                }
                const FVector RunCentre = Frame.GetLocation() + Across * (Side * (RunFromCm + FloorOuterCm) * 0.5)
                    + Up * Ground.FloorHeightCm;
                const float Variation = Stream.FRand();
                const auto Plate = [&](const FVector& Centre, const FQuat& PlateRotation, const FVector& SizeCm)
                {
                    Plates.Add(FitMeshToTimber(BoardMesh.GetBoundingBox(), Centre, PlateRotation, SizeCm));
                    PlateData.Append({ Variation, static_cast<float>(SizeCm.X), static_cast<float>(SizeCm.Y), static_cast<float>(SizeCm.Z) });
                };
                // The bottom sits on whatever is below (the floor slab at -5 where
                // there is one), its top a plate's thickness above the boards' underside.
                Plate(RunCentre + Up * (-ThicknessCm + PlateCm * 0.5),
                    FRotationMatrix::MakeFromXY(Across, Forward).ToQuat(),
                    FVector(RunCm, HalfSlotCm * 2.0, PlateCm));
                for (const double Face : { -1.0, 1.0 })
                {
                    Plate(RunCentre + Forward * (Face * (HalfSlotCm - PlateCm * 0.5)) + Up * (-(ThicknessCm - PlateCm) * 0.5),
                        FRotationMatrix::MakeFromXY(Across, Up).ToQuat(),
                        FVector(RunCm, ThicknessCm - PlateCm, PlateCm));
                }
            }
        }
        if (!Plates.IsEmpty())
        {
            // Like housings: thin pieces cast no shadow.
            UInstancedStaticMeshComponent* GrooveComponent = CreateManagedComponent(
                TEXT("StructureGrooves"), GrooveLayerTag, &BoardMesh, GrooveMaterial, false);
            ApplyInstances(*GrooveComponent, Plates, PlateData);
            GroovePieceCount = Plates.Num();
        }
    }

    if (!UnderstageMesh)
    {
        return;
    }
    // A floor far below, in route-following slabs, seen only through slots and gaps.
    constexpr double SlabLengthCm = 1000.0;
    constexpr double SlabThicknessCm = 10.0;
    const FBox UnderstageBounds = UnderstageMesh->GetBoundingBox();
    TArray<FTransform> Slabs;
    TArray<float> SlabData;
    for (double FromCm = StartCm; FromCm < EndCm - 1.0; FromCm += SlabLengthCm)
    {
        const double ToCm = FMath::Min(FromCm + SlabLengthCm, EndCm);
        const FTransform Frame = Route.GetTransformAtDistanceAlongSpline(
            (FromCm + ToCm) * 0.5, ESplineCoordinateSpace::World, false);
        const FVector CentreWorld = Frame.GetLocation() + Frame.GetUnitAxis(EAxis::Z)
            * (Ground.FloorHeightCm - ThicknessCm - Ground.UnderstageDepthCm - SlabThicknessCm * 0.5);
        const FVector SizeCm(ToCm - FromCm, HalfSpanCm * 2.0, SlabThicknessCm);
        Slabs.Add(FitMeshToTimber(UnderstageBounds, CentreWorld, Frame.GetRotation(), SizeCm));
        SlabData.Append({ 0.5f, static_cast<float>(SizeCm.X), static_cast<float>(SizeCm.Y), static_cast<float>(SizeCm.Z) });
    }
    UInstancedStaticMeshComponent* UnderstageComponent = CreateManagedComponent(
        TEXT("StructureUnderstage"), UnderstageLayerTag, UnderstageMesh, UnderstageMaterial, false);
    ApplyInstances(*UnderstageComponent, Slabs, SlabData);
}

double AInfinityStageStructureActor::GetFloorHalfSpanCm(const TArray<FInfinityStructureStation>& Stations) const
{
    // The floor meets the building's walls: the grid's span when there is one.
    if (GridHalfWidthCm > 0.0)
    {
        return GridHalfWidthCm;
    }
    double WidestPanelCm = 0.0;
    for (const FInfinityStructureStation& Station : Stations)
    {
        WidestPanelCm = FMath::Max(WidestPanelCm, Station.HalfWidthCm);
    }
    return WidestPanelCm + Gridiron.OverhangCm;
}

void AInfinityStageStructureActor::BuildPortal(
    const TArray<FInfinityStructureStation>& Stations,
    UStaticMesh& TimberMesh,
    UMaterialInterface* TimberMaterial,
    UStaticMesh* BoardMesh,
    UMaterialInterface* BoardMaterial,
    UStaticMesh* LineMesh,
    UMaterialInterface* LineMaterial)
{
    const USplineComponent& Route = *Passage->Route;
    const double RouteLengthCm = Route.GetSplineLength();
    // The portal may stand before the route begins (P01's route starts at its
    // curtain line), so its frame is the route's nearest frame carried along its
    // own forward axis rather than a spline sample clamped to the start.
    const double PortalCm = Stations[0].DistanceCm + Portal.OffsetFromFirstStationCm;
    const double SampleCm = FMath::Clamp(PortalCm, 0.0, RouteLengthCm);
    const FTransform Frame = Route.GetTransformAtDistanceAlongSpline(SampleCm, ESplineCoordinateSpace::World, false);
    const FVector Forward = Frame.GetUnitAxis(EAxis::X);
    const FVector Across = Frame.GetUnitAxis(EAxis::Y);
    const FVector Up = Frame.GetUnitAxis(EAxis::Z);
    const FVector RoutePoint = Frame.GetLocation() + Forward * (PortalCm - SampleCm);
    const auto AtRoute = [&](const double DistanceCm) { return RoutePoint + Forward * (DistanceCm - PortalCm); };
    const FVector FloorPoint = RoutePoint + Up * Ground.FloorHeightCm;

    const FQuat Vertical = FRotationMatrix::MakeFromXY(Up, Across).ToQuat();
    const FQuat Crosswise = FRotationMatrix::MakeFromXZ(Across, Up).ToQuat();
    const FQuat Lengthwise = FRotationMatrix::MakeFromXZ(Forward, Up).ToQuat();
    const double HalfOpeningCm = FMath::Max(50.0, Portal.OpeningHalfWidthCm);
    const double PostCm = FMath::Max(5.0, Portal.PostWidthCm);
    const double HeaderCm = FMath::Max(5.0, Portal.HeaderDepthCm);
    const double OpeningCm = FMath::Max(100.0, Portal.OpeningHeightCm);

    FRandomStream Stream = MakeTimberStream(Passage->PassageGuid, ETimberPart::Portal);
    const auto Piece = [&Stream](TArray<FTransform>& Transforms, TArray<float>& Data, const FBox& Bounds,
                                 const FVector& CentreWorld, const FQuat& Rotation, const FVector& SizeCm)
    {
        Transforms.Add(FitMeshToTimber(Bounds, CentreWorld, Rotation, SizeCm));
        Data.Append({ Stream.FRand(), static_cast<float>(SizeCm.X), static_cast<float>(SizeCm.Y), static_cast<float>(SizeCm.Z) });
    };

    // The frame: two posts and a header, the proscenium around the curtain.
    const FBox TimberBounds = TimberMesh.GetBoundingBox();
    TArray<FTransform> Timbers;
    TArray<float> TimberData;
    const double PostHeightCm = OpeningCm + HeaderCm;
    for (const double Side : { -1.0, 1.0 })
    {
        Piece(Timbers, TimberData, TimberBounds,
            FloorPoint + Across * (Side * (HalfOpeningCm + PostCm * 0.5)) + Up * (PostHeightCm * 0.5),
            Vertical, FVector(PostHeightCm, PostCm, PostCm));
    }
    Piece(Timbers, TimberData, TimberBounds, FloorPoint + Up * (OpeningCm + HeaderCm * 0.5),
        Crosswise, FVector((HalfOpeningCm + PostCm) * 2.0, PostCm, HeaderCm));

    // The forestage covers only floor the ground layer does not, so boards never
    // double up. P01's ground starts at the route start, which is its portal line.
    const double GroundStartCm = Ground.bEnabled
        ? FMath::Clamp(Stations[0].DistanceCm - Ground.ApronCm, 0.0, RouteLengthCm)
        : PortalCm;
    const double ForestageStartCm = PortalCm - FMath::Max(0.0, Portal.ForestageDepthCm);
    const double ForestageEndCm = FMath::Min(PortalCm, GroundStartCm);
    // The stage front is boarded from the ground's kit, so it needs the ground.
    const bool bStageFront = Portal.bStageFront && BoardMesh && Ground.bEnabled;
    const double MouthHalfCm = FMath::Max(HalfOpeningCm, Portal.MouthHalfWidthCm);
    const double BoardWidthCm = FMath::Max(4.0, Ground.BoardWidthCm);
    const double BoardGapCm = FMath::Max(0.0, Ground.BoardGapCm);
    const double BoardThicknessCm = FMath::Max(0.5, Ground.BoardThicknessCm);
    const double BoardPitchCm = BoardWidthCm + BoardGapCm;
    const FBox BoardBounds = BoardMesh ? BoardMesh->GetBoundingBox() : FBox(ForceInit);
    // Lanes that fill [FromCm, ToCm] edge to edge, all one width, so a stage-front
    // edge lands exactly where the spec (and the curtain bake's colliders) put it.
    const auto EvenLanes = [BoardGapCm, BoardPitchCm](const double FromCm, const double ToCm, TArray<double>& OutCentres)
    {
        const int32 Count = FMath::Max(1, FMath::RoundToInt32((ToCm - FromCm + BoardGapCm) / BoardPitchCm));
        const double LaneWidthCm = FMath::Max(1.0, (ToCm - FromCm - (Count - 1) * BoardGapCm) / Count);
        for (int32 Lane = 0; Lane < Count; ++Lane)
        {
            OutCentres.Add(FromCm + Lane * (LaneWidthCm + BoardGapCm) + LaneWidthCm * 0.5);
        }
        return LaneWidthCm;
    };
    TArray<FTransform> Boards;
    TArray<float> BoardData;
    if (BoardMesh && ForestageEndCm - ForestageStartCm > 1.0)
    {
        const FVector Middle = AtRoute((ForestageStartCm + ForestageEndCm) * 0.5)
            + Up * (Ground.FloorHeightCm - BoardThicknessCm * 0.5);
        if (bStageFront)
        {
            // As wide as the mouth, to take the curtain's spill.
            TArray<double> LaneCentres;
            const double LaneWidthCm = EvenLanes(-MouthHalfCm, MouthHalfCm, LaneCentres);
            for (const double LaneCm : LaneCentres)
            {
                Piece(Boards, BoardData, BoardBounds, Middle + Across * LaneCm, Lengthwise,
                    FVector(ForestageEndCm - ForestageStartCm, LaneWidthCm, BoardThicknessCm));
            }
        }
        else
        {
            const int32 Lanes = FMath::Max(1, FMath::FloorToInt32((HalfOpeningCm * 2.0 + BoardGapCm) / BoardPitchCm));
            const double FirstLaneCm = -(Lanes * BoardPitchCm - BoardGapCm) * 0.5 + BoardWidthCm * 0.5;
            for (int32 Lane = 0; Lane < Lanes; ++Lane)
            {
                Piece(Boards, BoardData, BoardBounds, Middle + Across * (FirstLaneCm + Lane * BoardPitchCm), Lengthwise,
                    FVector(ForestageEndCm - ForestageStartCm, BoardWidthCm, BoardThicknessCm));
            }
        }
    }
    // The float trough at the lip, sitting on the boards.
    if (Portal.bFloatTrough && Portal.ForestageDepthCm > 1.0)
    {
        const double TroughDepthCm = FMath::Max(1.0, Portal.TroughDepthCm);
        const double TroughHeightCm = FMath::Max(1.0, Portal.TroughHeightCm);
        Piece(Timbers, TimberData, TimberBounds,
            AtRoute(ForestageStartCm + TroughDepthCm * 0.5) + Up * (Ground.FloorHeightCm + TroughHeightCm * 0.5),
            Crosswise, FVector(HalfOpeningCm * 2.0, TroughDepthCm, TroughHeightCm));
    }
    // The stage front (FInfinityStagePortalSettings::bStageFront): every stage edge
    // the curtain can reach gets a boarded face down to a house floor that wraps
    // the mouth on the front and both sides. Positions are along the route from
    // the portal line (negative toward the audience), across it, and up from the
    // stage floor, all square to the portal.
    TArray<FTransform> FrontBoards;
    TArray<float> FrontData;
    if (bStageFront)
    {
        const double ThickCm = BoardThicknessCm;
        const double LipCm = ForestageStartCm - PortalCm;
        const double MouthStartCm = ForestageEndCm - PortalCm;
        const double MouthEndCm = Stations[0].DistanceCm - PortalCm;
        const double SideEndCm = MouthEndCm + FMath::Max(0.0, Portal.SideRunUpstageCm);
        const double HouseCm = FMath::Max(10.0, Portal.HouseFloorDepthCm);
        const double HouseHalfCm = FMath::Max(MouthHalfCm + ThickCm, Portal.HouseFloorHalfWidthCm);
        const double MinLengthCm = FMath::Max(20.0, FMath::Min(Ground.MinBoardLengthCm, Ground.MaxBoardLengthCm));
        const double MaxLengthCm = FMath::Max(MinLengthCm, Ground.MaxBoardLengthCm);
        // The passage floor's actual outer edge, from its lanes as BuildGround lays them.
        const int32 GroundLanes = FMath::Max(1, FMath::FloorToInt32((GetFloorHalfSpanCm(Stations) * 2.0 + BoardGapCm) / BoardPitchCm));
        const double GroundOuterCm = (GroundLanes * BoardPitchCm - BoardGapCm) * 0.5;
        const auto At = [&](const double AlongCm, const double AcrossCm, const double UpCm)
        {
            return FloorPoint + Forward * AlongCm + Across * AcrossCm + Up * UpCm;
        };
        // Boards along LengthAxis, in even lanes across WidthAxis, filling the
        // rectangle [L0, L1] x [W0, W1] on the plane through PlaneOrigin, with
        // staggered joints as on the passage floor.
        const auto LayBoards = [&](const FVector& PlaneOrigin, const FVector& LengthAxis, const FVector& WidthAxis,
                                   const double L0, const double L1, const double W0, const double W1)
        {
            if (L1 - L0 < 1.0 || W1 - W0 < 1.0)
            {
                return;
            }
            const FQuat BoardRotation = FRotationMatrix::MakeFromXY(LengthAxis, WidthAxis).ToQuat();
            TArray<double> LaneCentres;
            const double LaneWidthCm = EvenLanes(W0, W1, LaneCentres);
            for (const double LaneCm : LaneCentres)
            {
                // Fraction first, then length: the order the saved stage fronts were laid
                // in. The compiler chose the opposite order here to BuildGround's, from
                // the same expression, which is why neither is left to it (see BuildGround).
                const double FirstFraction = Stream.FRandRange(0.2, 1.0);
                double NextLengthCm = Stream.FRandRange(MinLengthCm, MaxLengthCm) * FirstFraction;
                double FromCm = L0;
                while (FromCm < L1 - 0.5)
                {
                    double ToCm = FMath::Min(FromCm + NextLengthCm, L1);
                    if (L1 - ToCm < MinLengthCm * 0.25)
                    {
                        ToCm = L1;    // no sliver at the end of a run
                    }
                    Piece(FrontBoards, FrontData, BoardBounds,
                        PlaneOrigin + LengthAxis * ((FromCm + ToCm) * 0.5) + WidthAxis * LaneCm,
                        BoardRotation, FVector(ToCm - FromCm, LaneWidthCm, ThickCm));
                    FromCm = ToCm + BoardGapCm;
                    NextLengthCm = Stream.FRandRange(MinLengthCm, MaxLengthCm);
                }
            }
        };
        // The mouth: stage-level floor either side of the passage floor, out to the
        // mouth's width, from the forestage to the first station; and across the
        // middle too, where the passage floor starts only after the portal line.
        const double GroundStartAlongCm = GroundStartCm - PortalCm;
        if (GroundStartAlongCm > MouthStartCm + 1.0)
        {
            LayBoards(At(0.0, 0.0, -ThickCm * 0.5), Forward, Across,
                MouthStartCm + BoardGapCm, FMath::Min(GroundStartAlongCm - BoardGapCm, MouthEndCm),
                -GroundOuterCm, GroundOuterCm);
        }
        if (MouthHalfCm > GroundOuterCm + BoardGapCm)
        {
            LayBoards(At(0.0, 0.0, -ThickCm * 0.5), Forward, Across,
                MouthStartCm + BoardGapCm, MouthEndCm, GroundOuterCm + BoardGapCm, MouthHalfCm);
            LayBoards(At(0.0, 0.0, -ThickCm * 0.5), Forward, Across,
                MouthStartCm + BoardGapCm, MouthEndCm, -MouthHalfCm, -GroundOuterCm - BoardGapCm);
        }
        // The fascia at the lip, coursed horizontally down to the house floor, and
        // wide enough to close the corners with the side returns.
        LayBoards(At(LipCm - ThickCm * 0.5, 0.0, 0.0), Across, Up,
            -MouthHalfCm - ThickCm, MouthHalfCm + ThickCm, -HouseCm, 0.0);
        for (const double Side : { -1.0, 1.0 })
        {
            // The mouth's sides, from the lip to the first station.
            LayBoards(At(0.0, Side * (MouthHalfCm + ThickCm * 0.5), 0.0), Forward, Up,
                LipCm, MouthEndCm, -HouseCm, 0.0);
            // Where the mouth steps back to the passage floor's width.
            if (MouthHalfCm > GroundOuterCm)
            {
                LayBoards(At(MouthEndCm + ThickCm * 0.5, 0.0, 0.0), Across, Up,
                    Side > 0.0 ? GroundOuterCm : -MouthHalfCm - ThickCm,
                    Side > 0.0 ? MouthHalfCm + ThickCm : -GroundOuterCm, -HouseCm, 0.0);
            }
            // Along the passage floor's sides, past the first station.
            LayBoards(At(0.0, Side * (GroundOuterCm + ThickCm * 0.5), 0.0), Forward, Up,
                MouthEndCm + ThickCm, SideEndCm, -HouseCm, 0.0);
        }
        // The house floor: in front of the lip, then beside the mouth and beside the
        // passage floor on both sides.
        const FVector HouseOrigin = At(0.0, 0.0, -HouseCm - ThickCm * 0.5);
        LayBoards(HouseOrigin, Forward, Across,
            LipCm - FMath::Max(0.0, Portal.HouseFloorDownstageCm), LipCm - ThickCm, -HouseHalfCm, HouseHalfCm);
        LayBoards(HouseOrigin, Forward, Across, LipCm - ThickCm, MouthEndCm + ThickCm, MouthHalfCm + ThickCm, HouseHalfCm);
        LayBoards(HouseOrigin, Forward, Across, LipCm - ThickCm, MouthEndCm + ThickCm, -HouseHalfCm, -MouthHalfCm - ThickCm);
        LayBoards(HouseOrigin, Forward, Across, MouthEndCm + ThickCm, SideEndCm, GroundOuterCm + ThickCm, HouseHalfCm);
        LayBoards(HouseOrigin, Forward, Across, MouthEndCm + ThickCm, SideEndCm, -HouseHalfCm, -GroundOuterCm - ThickCm);
        // A timber nosing along the lip, proud of the fascia.
        if (Portal.NosingDepthCm > 0.5 && Portal.NosingHeightCm > 0.5)
        {
            Piece(Timbers, TimberData, TimberBounds,
                At(LipCm - ThickCm - Portal.NosingDepthCm * 0.5, 0.0, -Portal.NosingHeightCm * 0.5),
                Crosswise, FVector((MouthHalfCm + ThickCm) * 2.0, Portal.NosingDepthCm, Portal.NosingHeightCm));
        }
    }
    // The gridiron carried forward to meet the portal: a cross beam over it and
    // rails back to the first station, so the tunnel recedes above the curtain.
    // They are portal pieces, so they take the portal's timber (TimberMesh), but
    // keep the gridiron's section and height whichever mesh that is.
    const double GridTopCm = Gridiron.HeightCm + Gridiron.BeamDepthCm * 1.5;
    if (Portal.bExtendGridiron && Gridiron.bEnabled && GridHalfWidthCm > 0.0)
    {
        Piece(Timbers, TimberData, TimberBounds, RoutePoint + Up * Gridiron.HeightCm,
            Crosswise, FVector(GridHalfWidthCm * 2.0, Gridiron.BeamWidthCm, Gridiron.BeamDepthCm));
        const FInfinityStructureStation& First = Stations[0];
        const FVector FirstOrigin = First.StationWorld.GetLocation();
        const FVector FirstAcross = First.StationWorld.GetUnitAxis(EAxis::Y);
        const FVector FirstUp = First.StationWorld.GetUnitAxis(EAxis::Z);
        const double RailLiftCm = Gridiron.HeightCm + Gridiron.BeamDepthCm;
        for (const double Side : { -1.0, 1.0 })
        {
            const FVector Start = RoutePoint + Across * (Side * GridHalfWidthCm) + Up * RailLiftCm;
            const FVector End = FirstOrigin + FirstAcross * (Side * GridHalfWidthCm) + FirstUp * RailLiftCm;
            const double LengthCm = FVector::Distance(Start, End);
            if (LengthCm >= 1.0)
            {
                Piece(Timbers, TimberData, TimberBounds, (Start + End) * 0.5,
                    FRotationMatrix::MakeFromXZ((End - Start) / LengthCm, Up).ToQuat(),
                    FVector(LengthCm, Gridiron.BeamWidthCm, Gridiron.BeamDepthCm));
            }
        }
    }
    // Hemp lines from the header up into the dark, spread across the opening.
    TArray<FTransform> Lines;
    TArray<float> LineData;
    if (LineMesh && Portal.HangingLines > 0)
    {
        const double FromCm = OpeningCm + HeaderCm;
        const double ToCm = Gridiron.bEnabled ? GridTopCm : FromCm + 600.0;
        const double ThicknessCm = FMath::Max(0.5, Fixtures.LineThicknessCm);
        const FBox LineBounds = LineMesh->GetBoundingBox();
        for (int32 Index = 0; Index < Portal.HangingLines && ToCm - FromCm > 1.0; ++Index)
        {
            const double LateralCm = -HalfOpeningCm + (Index + 0.5) * (HalfOpeningCm * 2.0 / Portal.HangingLines);
            Piece(Lines, LineData, LineBounds,
                RoutePoint + Across * LateralCm + Up * ((FromCm + ToCm) * 0.5),
                Vertical, FVector(ToCm - FromCm, ThicknessCm, ThicknessCm));
        }
    }

    UInstancedStaticMeshComponent* TimberComponent = CreateManagedComponent(
        TEXT("StructurePortal"), PortalLayerTag, &TimberMesh, TimberMaterial, true);
    ApplyInstances(*TimberComponent, Timbers, TimberData);
    PortalPieceCount = Timbers.Num();
    if (!Boards.IsEmpty())
    {
        UInstancedStaticMeshComponent* BoardComponent = CreateManagedComponent(
            TEXT("StructureForestage"), PortalLayerTag, BoardMesh, BoardMaterial, true);
        ApplyInstances(*BoardComponent, Boards, BoardData);
        PortalPieceCount += Boards.Num();
    }
    if (!FrontBoards.IsEmpty())
    {
        UInstancedStaticMeshComponent* FrontComponent = CreateManagedComponent(
            TEXT("StructureStageFront"), PortalLayerTag, BoardMesh, BoardMaterial, true);
        ApplyInstances(*FrontComponent, FrontBoards, FrontData);
        PortalPieceCount += FrontBoards.Num();
    }
    if (!Lines.IsEmpty())
    {
        UInstancedStaticMeshComponent* LineComponent = CreateManagedComponent(
            TEXT("StructurePortalLines"), PortalLayerTag, LineMesh, LineMaterial, false);
        ApplyInstances(*LineComponent, Lines, LineData);
        PortalPieceCount += Lines.Num();
    }
}

void AInfinityStageStructureActor::BuildCloth(
    const TArray<FInfinityStructureStation>& Stations,
    const TArray<UStaticMesh*>& Pieces,
    UMaterialInterface* Material)
{
    const USplineComponent& Route = *Passage->Route;
    const double RouteLengthCm = Route.GetSplineLength();
    const double FloorWidthCm = GetFloorHalfSpanCm(Stations) * 2.0;
    const double MinWidth = FMath::Max(0.1, FMath::Min(Cloth.WidthFraction.X, Cloth.WidthFraction.Y));
    const double MaxWidth = FMath::Max(MinWidth, FMath::Max(Cloth.WidthFraction.X, Cloth.WidthFraction.Y));
    const double MaxOffsetCm = FMath::Max(0.0, Cloth.MaxOffsetCm);
    const double MaxYaw = FMath::Clamp(Cloth.MaxYawDegrees, 0.0, 45.0);

    TArray<TArray<FTransform>> TransformsByPiece;
    TArray<TArray<float>> DataByPiece;
    TransformsByPiece.SetNum(Pieces.Num());
    DataByPiece.SetNum(Pieces.Num());
    // One chance per bay, between each station and the next.
    for (int32 Bay = 0; Bay + 1 < Stations.Num(); ++Bay)
    {
        FRandomStream Stream = MakeTimberStream(Stations[Bay].CueGuid, ETimberPart::Cloth);
        // Draw every number up front, so coverage never reshuffles the pieces.
        const bool bCovered = Stream.FRand() < Cloth.Coverage;
        const int32 PieceIndex = Stream.RandRange(0, Pieces.Num() - 1);
        const double AlongCm = Stream.FRandRange(-MaxOffsetCm, MaxOffsetCm) * 0.5;
        const double AcrossCm = Stream.FRandRange(-MaxOffsetCm, MaxOffsetCm);
        const double LengthScale = Stream.FRandRange(0.85, 1.2);
        const double WidthScale = Stream.FRandRange(MinWidth, MaxWidth);
        const double FlipDegrees = Stream.FRand() < 0.5 ? 180.0 : 0.0;     // two statements: see BuildGround
        const double YawDegrees = FlipDegrees + Stream.FRandRange(-MaxYaw, MaxYaw);
        const float Tone = Stream.FRand();
        if (!bCovered)
        {
            continue;
        }

        UStaticMesh* Piece = Pieces[PieceIndex];
        const double FromCm = Stations[Bay].DistanceCm;
        const double ToCm = Stations[Bay + 1].DistanceCm;
        const FTransform Frame = Route.GetTransformAtDistanceAlongSpline(
            FMath::Clamp((FromCm + ToCm) * 0.5 + AlongCm, 0.0, RouteLengthCm), ESplineCoordinateSpace::World, false);
        const FVector MeshSize = Piece->GetBoundingBox().GetSize();
        const double LengthCm = (ToCm - FromCm) * LengthScale;
        const double WidthCm = FloorWidthCm * WidthScale;
        // Placed by pivot at floor height and never scaled vertically: the cloth
        // keeps its simulated rumple and the clearance built in above the boards.
        const FVector Scale(
            MeshSize.X > UE_KINDA_SMALL_NUMBER ? LengthCm / MeshSize.X : 1.0,
            MeshSize.Y > UE_KINDA_SMALL_NUMBER ? WidthCm / MeshSize.Y : 1.0,
            1.0);
        const FQuat Rotation = Frame.GetRotation() * FQuat(FVector::UpVector, FMath::DegreesToRadians(YawDegrees));
        const FVector Location = Frame.GetLocation()
            + Frame.GetUnitAxis(EAxis::Y) * AcrossCm
            + Frame.GetUnitAxis(EAxis::Z) * Ground.FloorHeightCm;
        TransformsByPiece[PieceIndex].Add(FTransform(Rotation, Location, Scale));
        DataByPiece[PieceIndex].Append({ Tone, static_cast<float>(LengthCm), static_cast<float>(WidthCm), static_cast<float>(MeshSize.Z) });
    }

    for (int32 PieceIndex = 0; PieceIndex < Pieces.Num(); ++PieceIndex)
    {
        if (TransformsByPiece[PieceIndex].IsEmpty())
        {
            continue;
        }
        UInstancedStaticMeshComponent* Component = CreateManagedComponent(
            TEXT("StructureCloth"), ClothLayerTag, Pieces[PieceIndex], Material, Cloth.bCastShadow);
        ApplyInstances(*Component, TransformsByPiece[PieceIndex], DataByPiece[PieceIndex]);
        ClothCount += TransformsByPiece[PieceIndex].Num();
    }
}

void AInfinityStageStructureActor::BuildFixtures(
    const TArray<FInfinityStructureStation>& Stations,
    UStaticMesh& BodyMesh,
    UMaterialInterface* BodyMaterial,
    UStaticMesh* LineMesh,
    UMaterialInterface* LineMaterial)
{
    const TArray<FFixturePlacement> Placements =
        GatherFixturePlacements(*Passage->ShowAsset, Stations, MovingLightsWithoutHousing);
    if (Placements.IsEmpty())
    {
        return;
    }

    const FBox BodyBounds = BodyMesh.GetBoundingBox();
    const FVector BodySize = Fixtures.BodySizeCm.ComponentMax(FVector(1.0));
    const double LineThickness = FMath::Max(0.5, Fixtures.LineThicknessCm);
    TArray<FTransform> Bodies;
    TArray<float> BodyData;
    TArray<FTransform> Lines;
    TArray<float> LineData;
    for (const FFixturePlacement& Placement : Placements)
    {
        const FInfinityStructureStation& Station = Stations[Placement.StationIndex];
        const FVector Throw = Placement.LightWorld.GetUnitAxis(EAxis::X);
        const FVector Across = Station.StationWorld.GetUnitAxis(EAxis::Y);
        // Lamps hang plumb whatever the route does; only a lamp thrown straight up
        // or down needs a second reference to stay upright.
        const FQuat Rotation = FMath::Abs(Throw.Z) > 0.98
            ? FRotationMatrix::MakeFromXY(Throw, Across).ToQuat()
            : FRotationMatrix::MakeFromXZ(Throw, FVector::UpVector).ToQuat();
        // The source is the housing's open front, so the housing sits behind it.
        const FVector BodyCentre = Placement.LightWorld.GetLocation() - Throw * (BodySize.X * 0.5);
        Bodies.Add(FitMeshToTimber(BodyBounds, BodyCentre, Rotation, BodySize));
        FRandomStream Stream = MakeTimberStream(Placement.AttachmentGuid, ETimberPart::Housing);
        BodyData.Append({ Stream.FRand(), static_cast<float>(BodySize.X), static_cast<float>(BodySize.Y), static_cast<float>(BodySize.Z) });

        if (!LineMesh || GridHalfWidthCm <= 0.0)
        {
            continue;
        }
        // A line only where there is grid overhead: inside the building's span and
        // within reach below it. Lamps beyond the span wait for the wall bays.
        const FVector Origin = Station.StationWorld.GetLocation();
        const FVector StationUp = Station.StationWorld.GetUnitAxis(EAxis::Z);
        const double Lateral = FMath::Abs(FVector::DotProduct(BodyCentre - Origin, Across));
        const double GridTopZ = (Origin + StationUp * (Gridiron.HeightCm + Gridiron.BeamDepthCm * 1.5)).Z;
        const double HousingTopZ = BodyCentre.Z + BodySize.Z * 0.5;
        const double Drop = GridTopZ - HousingTopZ;
        if (Lateral > GridHalfWidthCm || Drop < 1.0 || Drop > Fixtures.MaxDropCm)
        {
            continue;
        }
        Lines.Add(FitMeshToTimber(
            LineMesh->GetBoundingBox(),
            FVector(BodyCentre.X, BodyCentre.Y, HousingTopZ + Drop * 0.5),
            FRotationMatrix::MakeFromXY(FVector::UpVector, Across).ToQuat(),
            FVector(Drop, LineThickness, LineThickness)));
        LineData.Append({ Stream.FRand(), static_cast<float>(Drop), static_cast<float>(LineThickness), static_cast<float>(LineThickness) });
    }

    // Housings and lines cast no shadow. Each source sits on its housing's face,
    // where a caster invites self-shadow acne, and the rig already spends the VSM
    // budget on the lamps themselves.
    UInstancedStaticMeshComponent* BodyComponent = CreateManagedComponent(
        TEXT("StructureFixtures"), FixtureLayerTag, &BodyMesh, BodyMaterial, false);
    ApplyInstances(*BodyComponent, Bodies, BodyData);
    FixtureBodyCount = Bodies.Num();
    if (!Lines.IsEmpty())
    {
        UInstancedStaticMeshComponent* LineComponent = CreateManagedComponent(
            TEXT("StructureLines"), LineLayerTag, LineMesh, LineMaterial, false);
        ApplyInstances(*LineComponent, Lines, LineData);
        HangingLineCount = Lines.Num();
    }
}

void AInfinityStageStructureActor::BuildUnderpass(
    const TArray<FInfinityStructureStation>& Stations,
    const FInfinityUnderpassPart& Column,
    const FInfinityUnderpassPart& Pier,
    const FInfinityUnderpassPart& Knee,
    const FInfinityUnderpassPart& Deck,
    const FInfinityUnderpassPart& Catwalk)
{
    // One station is no bay: nothing to span, and no way to keep both ends clean.
    if (Stations.Num() < 2)
    {
        return;
    }
    // Every size comes from the settings, never from another part's mesh, so a
    // part left without a mesh moves nothing else.
    const double ColumnLineCm = GetFloorHalfSpanCm(Stations) + FMath::Max(0.0, Underpass.ColumnOutsetCm);
    const double ColumnWidthCm = FMath::Max(1.0, Underpass.ColumnWidthCm);
    const double ColumnDepthCm = FMath::Max(1.0, Underpass.ColumnDepthCm);
    const double PierSizeCm = FMath::Max(1.0, Underpass.PierSizeCm);
    const double PierHeightCm = FMath::Max(0.0, Underpass.PierHeightCm);
    const double KneeSizeCm = FMath::Max(1.0, Underpass.KneeSizeCm);
    const double DeckDepthCm = FMath::Max(1.0, Underpass.DeckDepthCm);
    const double DeckUndersideCm = Underpass.DeckHeightCm;
    const double ColumnBaseCm = Ground.FloorHeightCm + PierHeightCm;
    const double ColumnHeightCm = DeckUndersideCm - ColumnBaseCm;
    const double DeckHalfSpanCm = ColumnLineCm + ColumnWidthCm * 0.5;
    // At an end station the whole foot (pier and column, kept concentric) steps
    // inside it, so the pier's outer face is flush with the Passage's end.
    const double EndInsetCm = FMath::Max(PierSizeCm, ColumnDepthCm) * 0.5;
    const int32 Every = FMath::Max(1, Underpass.ColumnEvery);
    const int32 Last = Stations.Num() - 1;

    struct FPartInstances
    {
        TArray<FTransform> Transforms;
        TArray<float> Data;
    };
    FPartInstances Columns;
    FPartInstances Piers;
    FPartInstances Knees;
    FPartInstances Decks;
    FPartInstances Rails;
    const auto AddPiece = [](FPartInstances& Into, const FBox& Bounds, const FVector& CentreWorld,
                             const FQuat& Rotation, const FVector& SizeCm, const float Tone)
    {
        Into.Transforms.Add(FitMeshToTimber(Bounds, CentreWorld, Rotation, SizeCm));
        Into.Data.Append({ Tone, static_cast<float>(SizeCm.X), static_cast<float>(SizeCm.Y), static_cast<float>(SizeCm.Z) });
    };
    const FBox ColumnBounds = Column.Mesh ? Column.Mesh->GetBoundingBox() : FBox(ForceInit);
    const FBox PierBounds = Pier.Mesh ? Pier.Mesh->GetBoundingBox() : FBox(ForceInit);
    const FBox KneeBounds = Knee.Mesh ? Knee.Mesh->GetBoundingBox() : FBox(ForceInit);
    const FBox DeckBounds = Deck.Mesh ? Deck.Mesh->GetBoundingBox() : FBox(ForceInit);
    const FBox CatwalkBounds = Catwalk.Mesh ? Catwalk.Mesh->GetBoundingBox() : FBox(ForceInit);

    // Columns, piers and knees. Each part has its own stream per station, and every
    // draw is its own statement made whether or not the part is built, so a part
    // switched on or off never re-rolls another (memory: puss-random-draw-order).
    const bool bBuildColumns = Underpass.bColumns && ColumnHeightCm >= 1.0;
    const bool bBuildKnees = bBuildColumns && Underpass.bKnees && ColumnHeightCm >= KneeSizeCm;
    for (int32 Index = 0; bBuildColumns && Index <= Last; ++Index)
    {
        if (Index % Every != 0 && Index != Last)
        {
            continue;
        }
        const FInfinityStructureStation& Station = Stations[Index];
        const FVector Forward = Station.StationWorld.GetUnitAxis(EAxis::X);
        const FVector Across = Station.StationWorld.GetUnitAxis(EAxis::Y);
        const FVector Up = Station.StationWorld.GetUnitAxis(EAxis::Z);
        const double InsetCm = Index == 0 ? EndInsetCm : (Index == Last ? -EndInsetCm : 0.0);
        const FVector Foot = Station.StationWorld.GetLocation() + Forward * InsetCm;
        // The column's length is local X (up); width across, depth along the route.
        const FQuat Upright = FRotationMatrix::MakeFromXY(Up, Across).ToQuat();
        const FQuat Square = FRotationMatrix::MakeFromXZ(Forward, Up).ToQuat();
        FRandomStream ColumnStream = MakeTimberStream(Station.CueGuid, ETimberPart::UnderpassColumn);
        FRandomStream PierStream = MakeTimberStream(Station.CueGuid, ETimberPart::UnderpassPier);
        FRandomStream KneeStream = MakeTimberStream(Station.CueGuid, ETimberPart::UnderpassKnee);
        for (const double Side : { -1.0, 1.0 })
        {
            const FVector Line = Foot + Across * (Side * ColumnLineCm);
            const float PierTone = PierStream.FRand();
            const float ColumnTone = ColumnStream.FRand();
            if (Pier.Mesh && PierHeightCm >= 1.0)
            {
                AddPiece(Piers, PierBounds, Line + Up * (Ground.FloorHeightCm + PierHeightCm * 0.5), Square,
                    FVector(PierSizeCm, PierSizeCm, PierHeightCm), PierTone);
            }
            if (Column.Mesh)
            {
                AddPiece(Columns, ColumnBounds, Line + Up * (ColumnBaseCm + ColumnHeightCm * 0.5), Upright,
                    FVector(ColumnHeightCm, ColumnWidthCm, ColumnDepthCm), ColumnTone);
            }
            if (!bBuildKnees)
            {
                continue;
            }
            // A knee each way along the route, its top under the deck and its
            // vertical leg on the column's face. An end column keeps only its
            // inward knee, so nothing reaches past the Passage's end.
            for (const double Direction : { -1.0, 1.0 })
            {
                const float KneeTone = KneeStream.FRand();
                const bool bOutward = (Index == 0 && Direction < 0.0) || (Index == Last && Direction > 0.0);
                if (!Knee.Mesh || bOutward)
                {
                    continue;
                }
                const FVector KneeX = Forward * (Underpass.bMirrorKnees ? -Direction : Direction);
                const FVector KneeCentre = Line + Forward * (Direction * (ColumnDepthCm + KneeSizeCm) * 0.5)
                    + Up * (DeckUndersideCm - KneeSizeCm * 0.5);
                AddPiece(Knees, KneeBounds, KneeCentre, FRotationMatrix::MakeFromXZ(KneeX, Up).ToQuat(),
                    FVector(KneeSizeCm, FMath::Max(1.0, KneeBounds.GetSize().Y), KneeSizeCm), KneeTone);
            }
        }
    }

    // The deck and its catwalk rails, one bay per station gap: each bay runs from
    // its station to the next and no further, so the last station ends the deck.
    const FVector CatwalkSize = CatwalkBounds.IsValid ? CatwalkBounds.GetSize().ComponentMax(FVector(1.0)) : FVector(1.0);
    for (int32 Index = 0; Index < Last; ++Index)
    {
        const FInfinityStructureStation& Station = Stations[Index];
        const FInfinityStructureStation& Next = Stations[Index + 1];
        const FVector Up = Station.StationWorld.GetUnitAxis(EAxis::Z);
        const FVector NextUp = Next.StationWorld.GetUnitAxis(EAxis::Z);
        const FVector Start = Station.StationWorld.GetLocation() + Up * DeckUndersideCm;
        const FVector End = Next.StationWorld.GetLocation() + NextUp * DeckUndersideCm;
        const double LengthCm = FVector::Distance(Start, End);
        if (LengthCm < 1.0)
        {
            continue;
        }
        const FVector BayUp = (Up + NextUp).GetSafeNormal();
        const FQuat BayRotation = FRotationMatrix::MakeFromXZ((End - Start) / LengthCm, BayUp).ToQuat();
        const FVector BayAcross = BayRotation.GetAxisY();
        const FVector Middle = (Start + End) * 0.5;
        FRandomStream DeckStream = MakeTimberStream(Station.CueGuid, ETimberPart::UnderpassDeck);
        const float DeckTone = DeckStream.FRand();
        if (Deck.Mesh && Underpass.bDeck)
        {
            AddPiece(Decks, DeckBounds, Middle + BayUp * (DeckDepthCm * 0.5), BayRotation,
                FVector(LengthCm, DeckHalfSpanCm * 2.0, DeckDepthCm), DeckTone);
        }
        if (!Catwalk.Mesh || !Underpass.bCatwalk)
        {
            continue;
        }
        FRandomStream RailStream = MakeTimberStream(Station.CueGuid, ETimberPart::UnderpassCatwalk);
        for (const double Side : { -1.0, 1.0 })
        {
            const float RailTone = RailStream.FRand();
            AddPiece(Rails, CatwalkBounds,
                Middle + BayAcross * (Side * (DeckHalfSpanCm - CatwalkSize.Y * 0.5)) + BayUp * (DeckDepthCm + CatwalkSize.Z * 0.5),
                BayRotation, FVector(LengthCm, CatwalkSize.Y, CatwalkSize.Z), RailTone);
        }
    }

    // One component per part, and none for a part with nothing to show.
    const auto Emit = [this](const FPartInstances& Built, const TCHAR* BaseName, const FName LayerTag,
                             const FInfinityUnderpassPart& Part, const bool bCastShadow, int32& OutCount)
    {
        if (Built.Transforms.IsEmpty())
        {
            return;
        }
        UInstancedStaticMeshComponent* Component =
            CreateManagedComponent(FName(BaseName), LayerTag, Part.Mesh, Part.Material, bCastShadow);
        ApplyInstances(*Component, Built.Transforms, Built.Data);
        OutCount = Built.Transforms.Num();
    };
    Emit(Piers, TEXT("StructureUnderpassPiers"), UnderpassPierLayerTag, Pier, Underpass.bPierCastShadow, UnderpassPierCount);
    Emit(Columns, TEXT("StructureUnderpassColumns"), UnderpassColumnLayerTag, Column, Underpass.bColumnCastShadow, UnderpassColumnCount);
    Emit(Knees, TEXT("StructureUnderpassKnees"), UnderpassKneeLayerTag, Knee, Underpass.bKneeCastShadow, UnderpassKneeCount);
    Emit(Decks, TEXT("StructureUnderpassDeck"), UnderpassDeckLayerTag, Deck, Underpass.bDeckCastShadow, UnderpassDeckCount);
    Emit(Rails, TEXT("StructureUnderpassCatwalk"), UnderpassCatwalkLayerTag, Catwalk, Underpass.bCatwalkCastShadow, UnderpassCatwalkCount);
}

bool AInfinityStageStructureActor::IsTubeBlinkOn(
    const double TimeSeconds,
    const float Phase,
    const float RateScale,
    const double PeriodSeconds,
    const double DutyOn)
{
    const double Period = FMath::Max(0.05, PeriodSeconds) * FMath::Max(0.1, static_cast<double>(RateScale));
    const double Position = FMath::Frac(TimeSeconds / Period + static_cast<double>(Phase));
    if (Position < FMath::Clamp(DutyOn, 0.0, 1.0))
    {
        return true;
    }
    // The strike: a fast stutter over the last 8 % of the cycle before it is lit again.
    if (Position >= 0.92)
    {
        return (FMath::FloorToInt32(Position * 160.0) % 2) == 0;
    }
    return false;
}

int32 AInfinityStageStructureActor::UpdateTubeBlinkers(const double TimeSeconds)
{
    if (TubeBlinkLit.Num() != UnderpassTubeBlinkers.Num())
    {
        // Everything is built lit: start from that.
        TubeBlinkLit.Init(1, UnderpassTubeBlinkers.Num());
    }
    UInstancedStaticMeshComponent* Component = UnderpassTubeBlinkComponent.Get();
    int32 Changed = 0;
    for (int32 Index = 0; Index < UnderpassTubeBlinkers.Num(); ++Index)
    {
        const FInfinityStageTubeBlinker& Blinker = UnderpassTubeBlinkers[Index];
        const bool bLit = IsTubeBlinkOn(TimeSeconds, Blinker.Phase, Blinker.RateScale,
            Underpass.TubeBlinkPeriodSeconds, Underpass.TubeBlinkDutyOn);
        if ((TubeBlinkLit[Index] != 0) == bLit)
        {
            continue;
        }
        TubeBlinkLit[Index] = bLit ? 1 : 0;
        ++Changed;
        if (Component && Blinker.InstanceIndex != INDEX_NONE)
        {
            Component->SetCustomDataValue(Blinker.InstanceIndex, 3, bLit ? Blinker.OnValue : 0.0f, false);
        }
        if (URectLightComponent* Light = Blinker.Light.Get())
        {
            Light->SetVisibility(bLit);
        }
    }
    if (Changed > 0 && Component)
    {
        Component->MarkRenderStateDirty();
    }
    return Changed;
}

void AInfinityStageStructureActor::BeginPlay()
{
    Super::BeginPlay();
    // Only a game world with blinkers pays anything; the editor never runs it, so
    // blinking never touches the level at edit time.
    UWorld* World = GetWorld();
    if (World && World->IsGameWorld() && !UnderpassTubeBlinkers.IsEmpty())
    {
        World->GetTimerManager().SetTimer(
            TubeBlinkTimer, this, &AInfinityStageStructureActor::OnTubeBlinkTimer, 1.0f / 30.0f, true);
    }
}

void AInfinityStageStructureActor::OnTubeBlinkTimer()
{
    if (const UWorld* World = GetWorld())
    {
        UpdateTubeBlinkers(World->GetTimeSeconds());
    }
}

void AInfinityStageStructureActor::BuildUnderpassTubes(
    const TArray<FInfinityStructureStation>& Stations,
    const FInfinityUnderpassPart& Tube,
    UMaterialInterface* LightFunction,
    const double FenceTopAboveBaseCm)
{
    // The stretch. Fewer than two stations in it is no run: nothing is built.
    const int32 Last = Stations.Num() - 1;
    const int32 From = FMath::Clamp(Underpass.TubeFromStation, 0, FMath::Max(0, Last));
    const int32 To = Underpass.TubeToStation < 0 ? Last : FMath::Min(Underpass.TubeToStation, Last);
    if (Last < 1 || To <= From)
    {
        return;
    }

    const double LengthCm = FMath::Max(1.0, Underpass.TubeLengthCm);
    const double DiameterCm = FMath::Max(0.5, Underpass.TubeDiameterCm);
    const double GapCm = FMath::Max(0.0, Underpass.TubeGapCm);
    const double PitchCm = LengthCm + GapCm;
    const double DeadFraction = FMath::Clamp(Underpass.TubeDeadFraction, 0.0, 1.0);
    const double ColumnLineCm = GetFloorHalfSpanCm(Stations) + FMath::Max(0.0, Underpass.ColumnOutsetCm);

    // The rows across the route. Centre rows are numbered -Y to +Y, the corners
    // after them; each row's stream key is fixed by its role, so switching the
    // corners off never re-rolls a centre row.
    struct FTubeRow
    {
        int32 Index;
        int32 StreamKey;
        double LateralCm;
        /** Up from the bay's deck line (negative hangs below it). */
        double VerticalCm;
        bool bEmitLight;
    };
    TArray<FTubeRow> Rows;
    const int32 CentreRows = FMath::Max(0, Underpass.TubeRowsCentre);
    const double RowSpacingCm = FMath::Max(0.0, Underpass.TubeCentreRowSpacingCm);
    const double DeckRowVerticalCm = -Underpass.TubeDropCm;
    for (int32 Row = 0; Row < CentreRows; ++Row)
    {
        Rows.Add({ Row, Row, (Row - (CentreRows - 1) * 0.5) * RowSpacingCm, DeckRowVerticalCm,
            Underpass.bTubeCentreRowsEmitLight });
    }
    int32 NextRowIndex = CentreRows;
    if (Underpass.bTubeCornerRows)
    {
        const double CornerCm = ColumnLineCm - Underpass.TubeCornerInsetCm;
        Rows.Add({ NextRowIndex++, 1000, -CornerCm, DeckRowVerticalCm, Underpass.bTubeCornerRowsEmitLight });
        Rows.Add({ NextRowIndex++, 1001, CornerCm, DeckRowVerticalCm, Underpass.bTubeCornerRowsEmitLight });
    }
    if (Underpass.bTubeFenceTopRows)
    {
        // On the fence line, above the fence's intended top, measured from the
        // station like the fence; the bays below run at deck height, so offset back.
        const double FenceLineCm = ColumnLineCm - Underpass.FenceInsetCm;
        const double FenceTopCm = Ground.FloorHeightCm + Underpass.FenceBaseCm
            + FenceTopAboveBaseCm + Underpass.TubeFenceTopRaiseCm;
        const double FenceVerticalCm = FenceTopCm - Underpass.DeckHeightCm;
        Rows.Add({ NextRowIndex++, 1002, -FenceLineCm, FenceVerticalCm, Underpass.bTubeFenceTopRowsEmitLight });
        if (Underpass.bFenceBothSides)
        {
            Rows.Add({ NextRowIndex++, 1003, FenceLineCm, FenceVerticalCm, Underpass.bTubeFenceTopRowsEmitLight });
        }
    }
    const float GlowLevel = FMath::Clamp(Underpass.TubeGlowLevel, 0.0f, 8.0f);
    const double BlinkFraction = FMath::Clamp(Underpass.TubeBlinkFraction, 0.0, 1.0);

    // The run under the deck's underside: the same straight bays the deck is
    // built from, station to station, so every tube hangs under a deck bay.
    struct FTubeBay
    {
        FVector Start;
        FVector Along;
        FVector Across;
        FVector Up;
        double StartCm;
        int32 Station;
    };
    TArray<FTubeBay> Bays;
    double RunCm = 0.0;
    for (int32 Index = From; Index < To; ++Index)
    {
        const FInfinityStructureStation& Station = Stations[Index];
        const FInfinityStructureStation& Next = Stations[Index + 1];
        const FVector Up = Station.StationWorld.GetUnitAxis(EAxis::Z);
        const FVector NextUp = Next.StationWorld.GetUnitAxis(EAxis::Z);
        const FVector Start = Station.StationWorld.GetLocation() + Up * Underpass.DeckHeightCm;
        const FVector End = Next.StationWorld.GetLocation() + NextUp * Underpass.DeckHeightCm;
        const double BayCm = FVector::Distance(Start, End);
        if (BayCm < 1.0)
        {
            continue;
        }
        const FQuat BayRotation = FRotationMatrix::MakeFromXZ((End - Start) / BayCm, (Up + NextUp).GetSafeNormal()).ToQuat();
        Bays.Add({ Start, BayRotation.GetAxisX(), BayRotation.GetAxisY(), BayRotation.GetAxisZ(), RunCm, Index });
        RunCm += BayCm;
    }

    // Tubes per row: as many as fit with a gap between each, the spare length
    // split between the two ends.
    const int32 PerRow = Bays.IsEmpty() || RunCm < LengthCm
        ? 0
        : FMath::FloorToInt32((RunCm + GapCm) / PitchCm + 1.0e-9);
    const double MarginCm = (RunCm - (PerRow * LengthCm + FMath::Max(0, PerRow - 1) * GapCm)) * 0.5;

    // Clean ends, checked rather than assumed: on a curved route an outer row's
    // tube can lean past an end station's plane. Such a tube is not built.
    const FVector FirstPoint = Stations[From].StationWorld.GetLocation();
    const FVector FirstForward = Stations[From].StationWorld.GetUnitAxis(EAxis::X);
    const FVector LastPoint = Stations[To].StationWorld.GetLocation();
    const FVector LastForward = Stations[To].StationWorld.GetUnitAxis(EAxis::X);

    struct FTubeSpot
    {
        FVector Centre = FVector::ZeroVector;
        FVector Along = FVector::XAxisVector;
        FVector Up = FVector::ZAxisVector;
        bool bAlive = false;
        bool bBuilt = false;
        int32 BlinkerIndex = INDEX_NONE;
    };
    TArray<TArray<FTubeSpot>> Spots;
    TArray<FTransform> Transforms;
    TArray<float> Data;
    TArray<FTransform> BlinkTransforms;
    TArray<float> BlinkData;
    const FBox TubeBounds = Tube.Mesh ? Tube.Mesh->GetBoundingBox() : FBox(ForceInit);
    int32 Trimmed = 0;
    for (const FTubeRow& Row : Rows)
    {
        TArray<FTubeSpot>& RowSpots = Spots.AddDefaulted_GetRef();
        int32 BayIndex = 0;
        int32 StreamBay = INDEX_NONE;
        FRandomStream Stream;
        FRandomStream BlinkStream;
        for (int32 TubeIndex = 0; TubeIndex < PerRow; ++TubeIndex)
        {
            const double AlongCm = MarginCm + LengthCm * 0.5 + TubeIndex * PitchCm;
            while (BayIndex + 1 < Bays.Num() && AlongCm >= Bays[BayIndex + 1].StartCm)
            {
                ++BayIndex;
            }
            const FTubeBay& Bay = Bays[BayIndex];
            if (StreamBay != BayIndex)
            {
                Stream = MakeTubeStream(Stations[Bay.Station].CueGuid, Row.StreamKey, Underpass.TubeSeed);
                BlinkStream = MakeTubeStream(Stations[Bay.Station].CueGuid,
                    Row.StreamKey + FInfinityStageUnderpassSettings::TubeBlinkStreamKeyOffset, Underpass.TubeSeed);
                StreamBay = BayIndex;
            }
            // One draw per tube, made whether or not the tube is built.
            const float Random = Stream.FRand();
            // The blink stream is separate and drawn in fixed statements (never two
            // draws in one expression: memory puss-random-draw-order).
            const float BlinkPick = BlinkStream.FRand();
            const float BlinkPhase = BlinkStream.FRand();
            const float BlinkRate = BlinkStream.FRand();
            FTubeSpot& Spot = RowSpots.AddDefaulted_GetRef();
            Spot.Centre = Bay.Start + Bay.Along * (AlongCm - Bay.StartCm) + Bay.Across * Row.LateralCm + Bay.Up * Row.VerticalCm;
            Spot.Along = Bay.Along;
            Spot.Up = Bay.Up;
            Spot.bAlive = Random >= DeadFraction;
            const FVector HalfLength = Bay.Along * (LengthCm * 0.5);
            Spot.bBuilt = FVector::DotProduct(Spot.Centre - HalfLength - FirstPoint, FirstForward) >= -0.1
                && FVector::DotProduct(Spot.Centre + HalfLength - LastPoint, LastForward) <= 0.1;
            if (!Spot.bBuilt)
            {
                ++Trimmed;
                continue;
            }
            const bool bBlinker = Spot.bAlive && BlinkFraction > 0.0 && BlinkPick < BlinkFraction;
            if (bBlinker)
            {
                FInfinityStageTubeBlinker& Blinker = UnderpassTubeBlinkers.AddDefaulted_GetRef();
                Blinker.InstanceIndex = Tube.Mesh ? BlinkTransforms.Num() : INDEX_NONE;
                Blinker.OnValue = GlowLevel;
                Blinker.Phase = BlinkPhase;
                Blinker.RateScale = 0.6f + 0.8f * BlinkRate;
                Spot.BlinkerIndex = UnderpassTubeBlinkers.Num() - 1;
            }
            if (!Tube.Mesh)
            {
                continue;
            }
            const FQuat Rotation = Underpass.bTubeMeshAlongZ
                ? FRotationMatrix::MakeFromZX(Bay.Along, Bay.Up).ToQuat()
                : FRotationMatrix::MakeFromXZ(Bay.Along, Bay.Up).ToQuat();
            const FVector SizeCm = Underpass.bTubeMeshAlongZ
                ? FVector(DiameterCm, DiameterCm, LengthCm)
                : FVector(LengthCm, DiameterCm, DiameterCm);
            // [3] is the emissive multiplier: the glow level alive (1 = the 5 Oct look), 0 dead.
            TArray<FTransform>& OutTransforms = bBlinker ? BlinkTransforms : Transforms;
            TArray<float>& OutData = bBlinker ? BlinkData : Data;
            OutTransforms.Add(FitMeshToTimber(TubeBounds, Spot.Centre, Rotation, SizeCm));
            OutData.Append({
                static_cast<float>(Row.Index),
                static_cast<float>(TubeIndex),
                Random,
                Spot.bAlive ? GlowLevel : 0.0f });
        }
    }
    if (Trimmed > 0)
    {
        UE_LOG(LogInfinityStageStructure, Display,
            TEXT("INFINITY_STAGE_STRUCTURE_TUBES_TRIMMED actor='%s' tubes=%d (past an end station on the curve)"),
            *GetActorNameOrLabel(), Trimmed);
    }
    if (!Transforms.IsEmpty())
    {
        UInstancedStaticMeshComponent* Component = CreateManagedComponent(
            TEXT("StructureUnderpassTubes"), UnderpassTubeLayerTag, Tube.Mesh, Tube.Material, Underpass.bTubeCastShadow);
        ApplyInstances(*Component, Transforms, Data);
        UnderpassTubeCount = Transforms.Num();
    }
    if (!BlinkTransforms.IsEmpty())
    {
        // Blinkers change custom data at runtime: their own movable component, so
        // the steady tubes stay a static, cached component.
        UInstancedStaticMeshComponent* Component = CreateManagedComponent(
            TEXT("StructureUnderpassTubesBlink"), UnderpassTubeLayerTag, Tube.Mesh, Tube.Material, Underpass.bTubeCastShadow);
        Component->SetMobility(EComponentMobility::Movable);
        ApplyInstances(*Component, BlinkTransforms, BlinkData);
        UnderpassTubeBlinkComponent = Component;
        UnderpassTubeCount += BlinkTransforms.Num();
    }
    if (!UnderpassTubeBlinkers.IsEmpty())
    {
        UE_LOG(LogInfinityStageStructure, Display,
            TEXT("INFINITY_STAGE_STRUCTURE_TUBE_BLINKERS actor='%s' blinkers=%d fraction=%.2f glow=%.2f"),
            *GetActorNameOrLabel(), UnderpassTubeBlinkers.Num(), BlinkFraction, GlowLevel);
    }

    if (!Underpass.bTubeLights || PerRow == 0)
    {
        return;
    }
    // One light per group of Every tubes along a row, on the group's middle tube,
    // and none where that tube is dead or trimmed, nor in a row that emits no light.
    const auto LitHosts = [&Spots, &Rows, PerRow](const int32 Every)
    {
        TArray<const FTubeSpot*> Hosts;
        for (int32 RowIndex = 0; RowIndex < Spots.Num(); ++RowIndex)
        {
            const TArray<FTubeSpot>& RowSpots = Spots[RowIndex];
            if (!Rows[RowIndex].bEmitLight)
            {
                continue;
            }
            for (int32 GroupStart = 0; GroupStart < PerRow; GroupStart += Every)
            {
                const int32 GroupSize = FMath::Min(Every, PerRow - GroupStart);
                const FTubeSpot& Host = RowSpots[GroupStart + (GroupSize - 1) / 2];
                if (Host.bBuilt && Host.bAlive)
                {
                    Hosts.Add(&Host);
                }
            }
        }
        return Hosts;
    };
    // Over the cap, thin evenly rather than refuse: the iron is right and a light
    // count is no reason to keep the last build. Every is raised until the lights
    // fit, so they stay evenly spaced along every row; the value used is logged.
    const int32 Cap = FMath::Max(0, Underpass.TubeLightMax);
    const int32 Asked = FMath::Max(1, Underpass.TubeLightEvery);
    int32 Every = Asked;
    TArray<const FTubeSpot*> Hosts = LitHosts(Every);
    while (Hosts.Num() > Cap && Every < PerRow)
    {
        ++Every;
        Hosts = LitHosts(Every);
    }
    if (Hosts.Num() > Cap)
    {
        UE_LOG(LogInfinityStageStructure, Warning,
            TEXT("INFINITY_STAGE_STRUCTURE_TUBE_LIGHTS_REFUSED actor='%s' lights=%d cap=%d: one light per row is over the cap; no tube lights built."),
            *GetActorNameOrLabel(), Hosts.Num(), Cap);
        return;
    }
    if (Every != Asked)
    {
        UE_LOG(LogInfinityStageStructure, Display,
            TEXT("INFINITY_STAGE_STRUCTURE_TUBE_LIGHTS_THINNED actor='%s' every=%d asked=%d lights=%d cap=%d"),
            *GetActorNameOrLabel(), Every, Asked, Hosts.Num(), Cap);
    }
    for (const FTubeSpot* Host : Hosts)
    {
        URectLightComponent* Light = CreateManagedLight(TEXT("StructureUnderpassTubeLight"), UnderpassTubeLightLayerTag);
        // A rect light emits along its +X: down, with its width along the tube.
        Light->SetWorldLocationAndRotation(
            Host->Centre - Host->Up * (DiameterCm * 0.5),
            FRotationMatrix::MakeFromXY(-Host->Up, Host->Along).ToQuat());
        Light->SetSourceWidth(static_cast<float>(LengthCm));
        Light->SetSourceHeight(static_cast<float>(DiameterCm));
        Light->SetIntensityUnits(ELightUnits::Lumens);
        Light->SetIntensity(FMath::Max(0.0f, Underpass.TubeLightIntensity));
        Light->SetLightColor(Underpass.TubeLightColor);
        Light->SetUseTemperature(true);
        Light->SetTemperature(FMath::Clamp(Underpass.TubeLightTemperatureK, 1000.0f, 15000.0f));
        Light->SetAttenuationRadius(FMath::Max(0.0f, Underpass.TubeLightAttenuationRadius));
        Light->SetCastShadows(Underpass.bTubeLightCastShadow);
        Light->SetLightFunctionMaterial(LightFunction);
        if (UnderpassTubeBlinkers.IsValidIndex(Host->BlinkerIndex))
        {
            UnderpassTubeBlinkers[Host->BlinkerIndex].Light = Light;
        }
    }
    UnderpassTubeLightCount = Hosts.Num();
    UnderpassTubeLightEveryUsed = Hosts.IsEmpty() ? 0 : Every;
}
