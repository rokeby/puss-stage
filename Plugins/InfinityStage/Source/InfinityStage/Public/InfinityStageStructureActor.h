#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "InfinityStageStructureActor.generated.h"

class AInfinityStagePassageActor;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class USceneComponent;
class UStaticMesh;

/**
 * One bay of the stage machine: a compiled wing station, read back through the
 * Passage's route and its materialized panels.
 *
 * Everything the structure pass builds derives from these, never from its own
 * spacing, so the building shares the wings' rhythm and re-fits when the Show
 * re-spaces them.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStructureStation
{
    GENERATED_BODY()

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure")
    FGuid CueGuid;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure", meta = (Units = "cm"))
    double DistanceCm = 0.0;

    /** Route frame at the station: X along the route, Y across it, Z up. The
     * location lies on the route line, not between the panels, so a single
     * nudged pair cannot put a kink in the building. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure")
    FTransform StationWorld = FTransform::Identity;

    /** Farthest materialized panel from the route line, measured across it. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure", meta = (Units = "cm"))
    double HalfWidthCm = 0.0;

    /** Farthest panel on each side of the route line, as positive distances (-Y
     * and +Y of the station frame). Corridors are often asymmetric (P01's wings
     * stand at -750 and +500), and each side's slots must start under that
     * side's own wing. Zero means the side has no panel. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure", meta = (Units = "cm"))
    double NegativeSideCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Structure", meta = (Units = "cm"))
    double PositiveSideCm = 0.0;
};

/**
 * Timber gridiron over a Passage: a cross beam at every wing station and a
 * continuous rail along each side, resting on the crosses.
 *
 * Every timber is its own instance with deterministic per-instance variation, so
 * regeneration reproduces the same grid rather than reshuffling it. Per-instance
 * custom data carries [variation 0..1, length, width, depth in cm] so a material
 * can run grain along each beam at true scale however it is stretched.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageGridironSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron")
    bool bEnabled = true;

    /** Cross-beam centre above the route line. Clears the 10 m wings. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron", meta = (Units = "cm"))
    double HeightCm = 1150.0;

    /** How far the grid reaches past the widest panel on each side. Per Passage,
     * because corridors differ by a factor of two (P05 470 cm, P01 970 cm). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron", meta = (ClampMin = "0.0", Units = "cm"))
    double OverhangCm = 220.0;

    /** Timber section: width is horizontal across the beam, depth vertical. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron", meta = (ClampMin = "1.0", Units = "cm"))
    double BeamWidthCm = 26.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron", meta = (ClampMin = "1.0", Units = "cm"))
    double BeamDepthCm = 34.0;

    /** A cross beam on every Nth station. Rails always run the full length. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron", meta = (ClampMin = "1"))
    int32 CrossBeamEvery = 1;

    /** Hand-hewn timbers are not identical: each section varies by up to this
     * fraction either way. Zero gives machined stock. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron|Wear", meta = (ClampMin = "0.0", ClampMax = "0.5"))
    double SectionVariation = 0.06;

    /** Largest roll of any timber about its own length, in degrees. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron|Wear", meta = (ClampMin = "0.0", ClampMax = "10.0", Units = "deg"))
    double TwistDegrees = 0.6;

    /** Any mesh works: it is fitted to each beam by its bounds, length along +X.
     * The engine cube stands in until a Blender timber replaces it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron|Look")
    TSoftObjectPtr<UStaticMesh> BeamMesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron|Look")
    TSoftObjectPtr<UMaterialInterface> Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gridiron|Look")
    bool bCastShadow = true;
};

/**
 * The stage floor as machinery: boards laid along the route, chariot slots cut
 * across them at every wing station, and a dark understage beneath, so each slot
 * reads as a cut into depth rather than a painted line.
 *
 * Slots run only from the wing zone outward, never across the middle. The cat's
 * centre line is kept clear by construction: Puss is the one thing in the machine
 * that is not on rails.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageGroundSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground")
    bool bEnabled = true;

    /** Top of the boards relative to the route line. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground", meta = (Units = "cm"))
    double FloorHeightCm = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Boards", meta = (ClampMin = "4.0", Units = "cm"))
    double BoardWidthCm = 24.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Boards", meta = (ClampMin = "0.0", Units = "cm"))
    double BoardGapCm = 0.8;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Boards", meta = (ClampMin = "0.5", Units = "cm"))
    double BoardThicknessCm = 5.0;

    /** Plank lengths are drawn from this range per lane, so joints stagger rather
     * than lining up into a grid. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Boards", meta = (ClampMin = "20.0", Units = "cm"))
    double MinBoardLengthCm = 240.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Boards", meta = (ClampMin = "20.0", Units = "cm"))
    double MaxBoardLengthCm = 480.0;

    /** How far the floor runs before the first station and past the last. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground", meta = (ClampMin = "0.0", Units = "cm"))
    double ApronCm = 400.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots")
    bool bCutChariotSlots = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots", meta = (ClampMin = "1.0", Units = "cm"))
    double SlotWidthCm = 8.0;

    /** Slots begin this far inside the wing's line, so a wing travelling inward
     * still stands over its slot. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots", meta = (ClampMin = "0.0", Units = "cm"))
    double SlotInboardCm = 150.0;

    /** No slot comes nearer the route line than this. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots", meta = (ClampMin = "0.0", Units = "cm"))
    double CatClearanceCm = 120.0;

    /** Line each chariot slot with a steel channel (Gary, 29 Sep: "walnut planks,
     * procedural steel for the grooves"): a plate on each face of the gap and one
     * across its bottom, so the slot reads as a tram-track groove let into the
     * planked floor. Engine Cubes like the boards, local X along the slot's run
     * across the stage, with the kit's custom data [variation, length, width,
     * thickness]. They take Ground.GrooveMaterial. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots")
    bool bSteelGrooves = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Slots", meta = (ClampMin = "0.1", Units = "cm"))
    double GroovePlateCm = 0.5;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Understage")
    bool bUnderstage = true;

    /** Depth of the dark beneath the boards, seen only through slots and gaps. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Understage", meta = (ClampMin = "10.0", Units = "cm"))
    double UnderstageDepthCm = 250.0;

    /** Fitted by bounds, length along +X like the timbers. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Look")
    TSoftObjectPtr<UStaticMesh> BoardMesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Look")
    TSoftObjectPtr<UMaterialInterface> BoardMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Look")
    TSoftObjectPtr<UStaticMesh> UnderstageMesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Look")
    TSoftObjectPtr<UMaterialInterface> UnderstageMaterial;

    /** The slot grooves' steel (bSteelGrooves). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground|Look")
    TSoftObjectPtr<UMaterialInterface> GrooveMaterial;
};

/**
 * Ground cloths laid over the boards, worn through at frays and holes so boards
 * and slots show beneath. Pieces come from Soft goods; this layer only places
 * them, one per bay at most, with deterministic variation.
 *
 * Placed by pivot at floor height and never scaled vertically, so the cloth
 * keeps its simulated rumple and the clearance its author built in above the
 * boards. Custom data [1] and [2] carry the true length and width so the weave
 * tiles at real size however the piece is fitted.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageClothSettings
{
    GENERATED_BODY()

    /** Off until the Soft goods pieces exist in the project. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth")
    bool bEnabled = false;

    /** Pivot at centre, length along +X. Pieces that do not load are skipped. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth")
    TArray<TSoftObjectPtr<UStaticMesh>> Pieces = {
        TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Scenes/Curtain/FloorCloth/SM_FloorCloth_A.SM_FloorCloth_A"))),
        TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Scenes/Curtain/FloorCloth/SM_FloorCloth_B.SM_FloorCloth_B"))),
        TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Scenes/Curtain/FloorCloth/SM_FloorCloth_C.SM_FloorCloth_C"))),
        TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Scenes/Curtain/FloorCloth/SM_FloorCloth_D.SM_FloorCloth_D")))
    };

    /** Optional override; empty uses each piece's own material. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth")
    TSoftObjectPtr<UMaterialInterface> Material;

    /** Fraction of bays that get a cloth; the rest show bare boards. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float Coverage = 0.7f;

    /** Largest nudge along and across the route, so pieces never sit on a grid. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth", meta = (ClampMin = "0.0", Units = "cm"))
    double MaxOffsetCm = 60.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth", meta = (ClampMin = "0.0", ClampMax = "45.0", Units = "deg"))
    double MaxYawDegrees = 4.0;

    /** Piece width as a fraction of the floor, drawn from this range per bay. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth", meta = (ClampMin = "0.1", ClampMax = "1.5"))
    FVector2D WidthFraction = FVector2D(0.55, 0.9);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cloth")
    bool bCastShadow = true;
};

/**
 * The portal: a timber proscenium where a Passage begins, with the house curtain
 * hanging in it. Two posts, a header, the gridiron carried forward to meet it,
 * a short forestage with a float trough at its lip, and hemp lines dropping to
 * the header out of the dark. It is the first image of the show (Gary, 28 Sep:
 * "the full curtain filling the frame with a little sense of the surrounding
 * structure") and the same object a hangar mouth will need.
 *
 * Built only from the machine's constant modules: the gridiron's beam mesh for
 * timber, the floor's board mesh for the forestage, the fixtures' line mesh for
 * the lines. Off by default, so existing structures are unchanged.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStagePortalSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal")
    bool bEnabled = false;

    /** Where the portal stands along the route, from the first station. Negative
     * is in front of it: -250 puts P01's portal at the route start, just ahead of
     * its first wing pair. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (Units = "cm"))
    double OffsetFromFirstStationCm = -250.0;

    /** Half the clear opening, route line to the inside of a post. 950 frames the
     * 17.77 m curtain with a little room. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "50.0", Units = "cm"))
    double OpeningHalfWidthCm = 950.0;

    /** Underside of the header above the floor: above the 10 m curtain's batten. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "100.0", Units = "cm"))
    double OpeningHeightCm = 1050.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "5.0", Units = "cm"))
    double PostWidthCm = 40.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "5.0", Units = "cm"))
    double HeaderDepthCm = 45.0;

    /** Boards carried forward of the portal line, so the curtain stands on a stage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "0.0", Units = "cm"))
    double ForestageDepthCm = 150.0;

    /** A long low timber box at the forestage lip, for the floats. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal")
    bool bFloatTrough = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "1.0", Units = "cm"))
    double TroughHeightCm = 25.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "1.0", Units = "cm"))
    double TroughDepthCm = 35.0;

    /** Carry the gridiron's rails forward from the first station to the portal,
     * with a cross beam over it: the tunnel, implied above the curtain. The rails
     * are |OffsetFromFirstStationCm| long (2.5 m at a passage mouth). Turn this
     * off for a portal placed far from its passage's first station (a hangar
     * mouth in a Scene), or the rails bridge the whole distance. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal")
    bool bExtendGridiron = true;

    /** Hemp lines from the header up into the dark, spread across the opening. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal", meta = (ClampMin = "0", ClampMax = "32"))
    int32 HangingLines = 5;

    /** A raised stage round the portal's mouth (Gary, 28 Sep, option A): the
     * forestage and the mouth widened to MouthHalfWidthCm, a boarded fascia from
     * the lip down to a house floor, and returns wherever a stage edge meets the
     * house. A curtain that overspills any edge then drapes over it onto
     * something instead of lying on air. Built square to the portal, for a
     * straight approach. Needs the ground layer's boards. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front")
    bool bStageFront = true;

    /** The house floor, this far below the stage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "10.0", Units = "cm"))
    double HouseFloorDepthCm = 120.0;

    /** The stage-level floor's half-width from the lip to the first station:
     * wider than the passage's own floor, to take the curtain's spill. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "50.0", Units = "cm"))
    double MouthHalfWidthCm = 1300.0;

    /** How far the house floor runs toward the audience from the lip: past the
     * camera, so no view runs off its far edge. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "0.0", Units = "cm"))
    double HouseFloorDownstageCm = 2450.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "0.0", Units = "cm"))
    double HouseFloorHalfWidthCm = 2000.0;

    /** Past the first station, the house floor and the returns along the
     * passage floor's sides run this far upstage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "0.0", Units = "cm"))
    double SideRunUpstageCm = 750.0;

    /** A timber nosing along the lip, proud of the fascia, top flush with the
     * stage. Off (depth 0) until a curtain bake includes it: the cloth drapes
     * over the lip there, and a rail the bake never saw would cut through it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "0.0", Units = "cm"))
    double NosingHeightCm = 12.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal|Stage Front", meta = (ClampMin = "0.0", Units = "cm"))
    double NosingDepthCm = 0.0;
};

/**
 * Lamp housings for the Show's lights, so the rig reads as apparatus rather than
 * light from nowhere. A housing sits behind every enabled station-anchored light
 * attachment, and a hemp line runs from it up through the grid when the lamp
 * hangs under the building.
 *
 * Placement is read from the Show's attachment offsets, the same authority the
 * lights materialize from, so moving a light in the level and re-fitting the
 * structure carries its housing with it. Lights anchored to moving panels get no
 * housing: a static housing would part company with its lamp.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageFixtureSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures")
    bool bEnabled = true;

    /** Housing size: X runs back from the source along the throw, then width and
     * height. A box lantern suits the Baroque register better than a modern can. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures", meta = (Units = "cm"))
    FVector BodySizeCm = FVector(45.0, 32.0, 32.0);

    /** Fitted by bounds like the timbers, throw along +X. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Look")
    TSoftObjectPtr<UStaticMesh> BodyMesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Look")
    TSoftObjectPtr<UMaterialInterface> BodyMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Hanging")
    bool bHangFromGrid = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Hanging", meta = (ClampMin = "0.5", Units = "cm"))
    double LineThicknessCm = 3.0;

    /** Lamps farther below the grid than this stand on their own (booms, ground
     * rows) and get no line. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Hanging", meta = (ClampMin = "0.0", Units = "cm"))
    double MaxDropCm = 900.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Look")
    TSoftObjectPtr<UStaticMesh> LineMesh = TSoftObjectPtr<UStaticMesh>(
        FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube")));

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fixtures|Look")
    TSoftObjectPtr<UMaterialInterface> LineMaterial;
};

/**
 * The stage machine around one Passage — the structure pass beside
 * MaterializePassage.
 *
 * Generate the spine, hand-place the accidents: this actor owns only the
 * components it created (tagged InfinityStage.Structure) and never touches any
 * other actor, so rope, ladders and sandbags dropped by hand survive every
 * regeneration. It is a separate actor rather than part of the Passage so that
 * wings and building can be rebuilt independently.
 */
UCLASS(BlueprintType)
class INFINITYSTAGE_API AInfinityStageStructureActor : public AActor
{
    GENERATED_BODY()

public:
    AInfinityStageStructureActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Infinity Stage")
    TObjectPtr<USceneComponent> SceneRoot;

    /** The Passage whose stations this structure follows. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    TObjectPtr<AInfinityStagePassageActor> Passage;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStageGridironSettings Gridiron;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStageGroundSettings Ground;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStageClothSettings Cloth;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStagePortalSettings Portal;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStageFixtureSettings Fixtures;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Materialization")
    TArray<TObjectPtr<UInstancedStaticMeshComponent>> ManagedComponents;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 StationCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 CrossBeamCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 RailSegmentCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization", meta = (Units = "cm"))
    double GridHalfWidthCm = 0.0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 BoardCount = 0;

    /** One per wing side per station where a slot is cut. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 SlotCount = 0;

    /** Steel plates lining the slots: three per slot (two walls and a bottom). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 GroovePieceCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 ClothCount = 0;

    /** Timbers, forestage boards and lines that make up the portal. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 PortalPieceCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 FixtureBodyCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 HangingLineCount = 0;

    /** Enabled lights left without a housing because they ride a moving panel. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 MovingLightsWithoutHousing = 0;

    /** Fingerprint of the stations and light placements the build was fitted to. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization", AdvancedDisplay)
    int32 StationSignature = 0;

    /** Rebuilds everything this actor owns from the Passage's current stations.
     * Validates first: on any failure the previous build is left standing. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool MaterializeStructure();

    /** Details-panel button; Unreal buttons need a void, parameterless function. */
    UFUNCTION(CallInEditor, Category = "Infinity Stage", meta = (DisplayName = "Materialize Structure"))
    void MaterializeStructureInEditor();

    /** Removes only the components this actor generated. */
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Infinity Stage")
    void ClearStructure();

    /** The stations every structure layer derives from, in route order. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool GatherStations(TArray<FInfinityStructureStation>& OutStations, FString& OutError) const;

    /** False once the wings have been re-spaced or re-routed, or a light moved,
     * since this structure was built — it needs a re-fit. */
    UFUNCTION(BlueprintCallable, Category = "Infinity Stage")
    bool IsStructureCurrent() const;

private:
    UInstancedStaticMeshComponent* CreateManagedComponent(
        FName BaseName,
        FName LayerTag,
        UStaticMesh* Mesh,
        UMaterialInterface* Material,
        bool bCastShadow);

    void BuildGridiron(
        const TArray<FInfinityStructureStation>& Stations,
        UInstancedStaticMeshComponent& Component,
        const FBox& MeshBounds);

    void BuildGround(
        const TArray<FInfinityStructureStation>& Stations,
        UStaticMesh& BoardMesh,
        UMaterialInterface* BoardMaterial,
        UStaticMesh* UnderstageMesh,
        UMaterialInterface* UnderstageMaterial,
        UMaterialInterface* GrooveMaterial);

    void BuildPortal(
        const TArray<FInfinityStructureStation>& Stations,
        UStaticMesh& TimberMesh,
        UMaterialInterface* TimberMaterial,
        UStaticMesh* BoardMesh,
        UMaterialInterface* BoardMaterial,
        UStaticMesh* LineMesh,
        UMaterialInterface* LineMaterial);

    void BuildCloth(
        const TArray<FInfinityStructureStation>& Stations,
        const TArray<UStaticMesh*>& Pieces,
        UMaterialInterface* Material);

    /** Half the floor's width: the grid's span when built, else widest panel plus overhang. */
    double GetFloorHalfSpanCm(const TArray<FInfinityStructureStation>& Stations) const;

    void BuildFixtures(
        const TArray<FInfinityStructureStation>& Stations,
        UStaticMesh& BodyMesh,
        UMaterialInterface* BodyMaterial,
        UStaticMesh* LineMesh,
        UMaterialInterface* LineMaterial);
};
