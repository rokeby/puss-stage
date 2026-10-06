#pragma once

#include "CoreMinimal.h"
#include "Engine/TimerHandle.h"
#include "GameFramework/Actor.h"
#include "InfinityStageStructureActor.generated.h"

class AInfinityStagePassageActor;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class URectLightComponent;
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
 * timber (unless PortalMesh/PortalMaterial pin its own), the floor's board mesh
 * for the forestage, the fixtures' line mesh for the lines. Off by default, so
 * existing structures are unchanged.
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

    /** The portal's own timber: posts, header, float trough and the gridiron
     * carried forward to meet it. Null builds from the gridiron's BeamMesh, as
     * the portal always did, so the gridiron can turn to underpass iron (Gary,
     * 5 Oct) while a portal pinned here stays wood. Fitted by bounds like every
     * timber, length along +X. Section sizes do not change with the mesh: the
     * carried-forward rails still take the gridiron's BeamWidthCm/BeamDepthCm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal")
    TSoftObjectPtr<UStaticMesh> PortalMesh;

    /** Null uses the gridiron's Material, as the portal always did. Independent
     * of PortalMesh: pinning only the mesh still paints it with the gridiron's
     * material. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Portal")
    TSoftObjectPtr<UMaterialInterface> PortalMaterial;
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

/** How an underpass fence panel's height is set. */
UENUM(BlueprintType)
enum class EInfinityFenceHeightMode : uint8
{
    /** The bay mesh's own height (Z scale 1): no squashed chain-link. */
    Native,
    /** Stretched to FenceHeightCm. Distorts a bay authored at another height. */
    Fit
};

/**
 * One kind of underpass fence panel. Panels tile each column gap: the bay mesh
 * is fitted by its bounds to its slot of the gap (local X, close to its own
 * width), keeps its own depth (local Y) and, in Native height mode, its own
 * height (local Z); local +Y faces the walkway, as on the W&T FenceBay kit, whose
 * tarp hangs on the bay's +Y side.
 *
 * The overlay is a second mesh authored in the bay mesh's own frame (the kit's
 * SM_FenceTarp_* beside SM_FenceBay_*). It is not fitted by its own bounds: it
 * takes the bay's transform exactly, so a half tarp stays half the bay's height.
 * It is built only where its bay is, in its own layer.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageFenceVariant
{
    GENERATED_BODY()

    FInfinityStageFenceVariant() = default;

    explicit FInfinityStageFenceVariant(const double InWeight, const TCHAR* InOverlayMeshPath = nullptr)
        : Weight(InWeight)
    {
        if (InOverlayMeshPath)
        {
            OverlayMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(InOverlayMeshPath));
        }
    }

    /** Null skips the variant: its share goes to the others, by their weights. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    TSoftObjectPtr<UStaticMesh> Mesh;

    /** Replaces slot 0 only (the kit's chain slot); other slots keep the mesh's
     * own, so the kit's concertina keeps its metal. Null: the mesh's own. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    TSoftObjectPtr<UMaterialInterface> Material;

    /** Relative share of the panels. 0 never builds this variant. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence", meta = (ClampMin = "0.0"))
    double Weight = 0.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    TSoftObjectPtr<UStaticMesh> OverlayMesh;

    /** Replaces the overlay's slot 0 only. Null: the overlay mesh's own. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    TSoftObjectPtr<UMaterialInterface> OverlayMaterial;
};

/**
 * The underpass: the iron rig round the wings (Gary, 5 Oct; plan
 * Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md, Phase B). Laced columns
 * on concrete piers outside the grid, knee brackets at their heads, an open-tie
 * deck over the whole Passage, and an optional catwalk rail along the deck's edges.
 *
 * Built from the gridiron's stations and nothing else, like every layer, so it
 * keeps the wings' rhythm and re-fits when the Show re-spaces them. Every piece
 * is fitted by its mesh's bounds (FitMeshToTimber): columns stretch only in
 * height, deck bays and rails only along the station gap and across the span,
 * piers and knees not at all when the sizes below match the kit's.
 *
 * Clean ends: nothing stands past the first or last station, so a Passage still
 * docks into a hangar. The column foot at an end station steps inside it, and an
 * end column carries a knee on its inward side only.
 *
 * Off by default, with no meshes: the conductor sets the kit per Passage. A part
 * with no mesh is skipped, never an error, and never moves another part.
 */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageUnderpassSettings
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass")
    bool bEnabled = false;

    /** Columns, with their piers and knees. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass")
    bool bColumns = true;

    /** Knee brackets at each column's head, along the route. Need the columns. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass")
    bool bKnees = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass")
    bool bDeck = true;

    /** A rail along each edge of the deck, standing on its top. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass")
    bool bCatwalk = false;

    /** A column pair on every Nth station, and always on the last, so the deck's
     * end is carried. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass", meta = (ClampMin = "1"))
    int32 ColumnEvery = 2;

    /** Column centre line beyond the grid's half-span (GridHalfWidthCm). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass", meta = (ClampMin = "0.0", Units = "cm"))
    double ColumnOutsetCm = 60.0;

    /** Underside of the deck above the route line: the columns' and knees' tops. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass", meta = (Units = "cm"))
    double DeckHeightCm = 2000.0;

    /** Column section: width across the route, depth along it. The kit's laced
     * column is 60 x 40. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "1.0", Units = "cm"))
    double ColumnWidthCm = 60.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "1.0", Units = "cm"))
    double ColumnDepthCm = 40.0;

    /** Pier footprint (square) and height; the column stands on the pier's top
     * whether or not a pier mesh is set. The kit's pier is 140 x 140 x 120. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "1.0", Units = "cm"))
    double PierSizeCm = 140.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "0.0", Units = "cm"))
    double PierHeightCm = 120.0;

    /** Both legs of the knee; its plate thickness is the mesh's own. Kit: 120. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "1.0", Units = "cm"))
    double KneeSizeCm = 120.0;

    /** The kit knee's vertical leg is at its local -X. If the import turned it to
     * face away from the column, set this rather than re-exporting. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes")
    bool bMirrorKnees = false;

    /** Deck bay depth. The span is the column lines plus half a column each side. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Sizes", meta = (ClampMin = "1.0", Units = "cm"))
    double DeckDepthCm = 30.0;

    /** Length along +X (height, for the column), fitted by bounds. Null skips the part. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UStaticMesh> ColumnMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UMaterialInterface> ColumnMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    bool bColumnCastShadow = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UStaticMesh> PierMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UMaterialInterface> PierMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    bool bPierCastShadow = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UStaticMesh> KneeMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UMaterialInterface> KneeMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    bool bKneeCastShadow = false;

    /** X along the bay, Y across the span (the ties), Z depth. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UStaticMesh> DeckMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UMaterialInterface> DeckMaterial;

    /** The deck is the one underpass caster: its ties band the floor and slat the shafts. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    bool bDeckCastShadow = true;

    /** X along the bay; width and height are the mesh's own. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UStaticMesh> CatwalkMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    TSoftObjectPtr<UMaterialInterface> CatwalkMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Look")
    bool bCatwalkCastShadow = false;

    /** Fluorescent tubes hung under the deck: the theatre's own tired working
     * light (Gary, 5 Oct: two rows at the centre top and one in each top corner;
     * "only occasionally in use, having a dingy office light feel"). Off, so they
     * are switched on per Passage or per stretch, never show-wide. Rows run along
     * the route between the stretch's end stations and never past them. Needs the
     * underpass on; independent of every other underpass part. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubes = false;

    /** The stretch, as station indices in route order. -1 for the last station.
     * The clean-end rule holds for the stretch: no tube passes either end station. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0"))
    int32 TubeFromStation = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "-1"))
    int32 TubeToStation = -1;

    /** Intended: /Engine/BasicShapes/Cylinder, scaled to a tube by its bounds.
     * Null builds no tube meshes; the tube positions (and any lights) still stand. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    TSoftObjectPtr<UStaticMesh> TubeMesh;

    /** The tube's length is the mesh's local Z, as on the engine Cylinder. Off for
     * a mesh authored with its length along X like the rest of the kit. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubeMeshAlongZ = true;

    /** An emissive instance, authored from Python later. Per-instance custom data:
     * [0] row (centre rows 0..N-1 across -Y to +Y, then the -Y corner, then +Y),
     * [1] tube index along the row, [2] seeded random 0..1, [3] 1 alive, 0 dead. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    TSoftObjectPtr<UMaterialInterface> TubeMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubeCastShadow = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "1.0", Units = "cm"))
    double TubeLengthCm = 150.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.5", Units = "cm"))
    double TubeDiameterCm = 5.0;

    /** The clear gap between one tube's end and the next along a row. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.0", Units = "cm"))
    double TubeGapCm = 100.0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0"))
    int32 TubeRowsCentre = 2;

    /** Centre rows are this far apart, centred on the route line. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.0", Units = "cm"))
    double TubeCentreRowSpacingCm = 120.0;

    /** A row in each top corner, on the column line. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubeCornerRows = true;

    /** Moves the corner rows inward from the column line. On the line itself a
     * corner tube passes through the knee brackets at the column stations. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (Units = "cm"))
    double TubeCornerInsetCm = 0.0;

    /** The tube's centre hangs this far below the deck's underside. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (Units = "cm"))
    double TubeDropCm = 30.0;

    /** Tubes whose custom-data random [2] is below this are dead: [3] = 0, and no light. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double TubeDeadFraction = 0.15;

    /** Mixed into every tube's random, to re-roll which tubes are dead without touching the Show. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    int32 TubeSeed = 0;

    /** Real light from the tubes, since emissive alone hardly lights the wings:
     * one rect light per TubeLightEvery tubes along a row, at the group's middle
     * tube, facing down, and none where that tube is dead. Movable, so it can be
     * dimmed, flickered and failed later. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubeLights = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "1"))
    int32 TubeLightEvery = 4;

    /** Most lights one structure builds. Above it the lights are thinned evenly:
     * TubeLightEvery is raised until they fit, and the build logs the value used. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0"))
    int32 TubeLightMax = 64;

    /** Lumens: the light's total output, so it does not change with the source
     * size (the tube length), and the unit of the looks' existing practical tubes
     * (INDUSTRIAL 2200, WASH 1500). Modest for a group of tubes: dingy, not bright. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.0"))
    float TubeLightIntensity = 1500.0f;

    /** Tired office fluorescent, not crisp daylight. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "1000.0", ClampMax = "15000.0"))
    float TubeLightTemperatureK = 4300.0f;

    /** Multiplies the temperature: a slight green cast. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    FLinearColor TubeLightColor = FLinearColor(0.92f, 1.0f, 0.88f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes", meta = (ClampMin = "0.0", Units = "cm"))
    float TubeLightAttenuationRadius = 1500.0f;

    /** Intended for the dingy hum: /Game/InfinityStage/Lighting/MI_LF_Flicker_Hum
     * (_Buzz, _Fault and _Slow also exist). Null: steady. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    TSoftObjectPtr<UMaterialInterface> TubeLightFunctionMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes")
    bool bTubeLightCastShadow = false;

    /** Tubes everywhere (Gary, 6 Oct: "add them everywhere so they can be switched
     * on or used to blink or atmosphere ... give them a low glow setting and make 20%
     * of them blink ... other than P02 only give light to the fence-top ones, not the
     * central rail ones"). Every field below defaults to the 5 Oct behaviour, so a
     * structure that sets none of them builds exactly what it built before. */

    /** With bTubeLights: whether the centre rows' tubes host lights. Off: they glow, light nothing. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere")
    bool bTubeCentreRowsEmitLight = true;

    /** With bTubeLights: whether the top-corner rows' tubes host lights. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere")
    bool bTubeCornerRowsEmitLight = true;

    /** A row along the top of each side fence: on the fence line (FenceInsetCm in from
     * the column line), its centre TubeFenceTopRaiseCm above the fence's intended top
     * (Ground.FloorHeightCm + FenceBaseCm + FenceHeightCm). Independent of bFence;
     * bFenceBothSides off builds the -Y row only. Same stretch, pitch and dead share
     * as the other rows; stream keys 1002 (-Y) and 1003 (+Y), so adding these rows
     * never re-rolls another row. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere")
    bool bTubeFenceTopRows = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere", meta = (Units = "cm"))
    double TubeFenceTopRaiseCm = 15.0;

    /** With bTubeLights: whether the fence-top rows' tubes host lights. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere")
    bool bTubeFenceTopRowsEmitLight = true;

    /** A live tube's emissive level, written to custom data [3] (M_UP_TubeEmissive
     * multiplies its emissive by [3]; dead tubes stay 0). 1 is the 5 Oct look; ~0.1-0.2
     * is a low background glow. It does not scale the rect lights (TubeLightIntensity). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere", meta = (ClampMin = "0.0", UIMax = "2.0"))
    float TubeGlowLevel = 1.0f;

    /** Share of the live, built tubes that blink in game. The pick is one draw per tube
     * from its own per-bay/row stream (key + TubeBlinkStreamKeyOffset), separate from
     * the dead/alive stream, so blinking never re-rolls which tubes are dead. Blinkers
     * are built into their own movable component; a blinker that hosts a light blinks
     * the light with it. 0 (default) builds no blinkers. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double TubeBlinkFraction = 0.0;

    /** One blink cycle (scaled per tube by 0.6-1.4 from its stream). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere", meta = (ClampMin = "0.05", Units = "s"))
    double TubeBlinkPeriodSeconds = 3.0;

    /** Share of the cycle a blinker is lit; the last 8 % of the cycle is the
     * fluorescent stutter as it strikes again. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Tubes|Everywhere", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    double TubeBlinkDutyOn = 0.7;

    static constexpr int32 TubeBlinkStreamKeyOffset = 5000;

    /** Fencing in the spaces between the columns (Gary, 5 Oct: "ground to ~3 m:
     * underpass-style fencing; the upper rig stays open and side light still gets
     * through. Mostly open chain-link, some half or torn tarp, rare door gaps").
     * Each gap between consecutive column stations, per side, is a straight chord
     * from column centre to column centre (so the fence keeps the columns' clean
     * ends), tiled with n = max(1, round(chord / native width)) panels, the native
     * width being the widest built variant's bounds X. Each panel's variant is
     * drawn on its own. Uses the column rhythm whether or not the columns
     * themselves are built. Off, and with no bay meshes: the conductor sets the
     * FenceBay kit from Python (the tarp overlays of B and C are preset). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    bool bFence = false;

    /** Native keeps each bay's own height; Fit stretches it to FenceHeightCm. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    EInfinityFenceHeightMode FenceHeightMode = EInfinityFenceHeightMode::Native;

    /** The intended height, bottom to top of the bay mesh's bounds. Fit builds it;
     * Native warns (INFINITY_STAGE_STRUCTURE_FENCE_HEIGHT_MISMATCH) for each
     * built variant whose own height is more than 10 % away from it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence", meta = (ClampMin = "1.0", Units = "cm"))
    double FenceHeightCm = 300.0;

    /** The panel's bottom above the floor (Ground.FloorHeightCm). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence", meta = (Units = "cm"))
    double FenceBaseCm = 0.0;

    /** From the column line toward the route. The default clears the 140 cm pier
     * (half 70) by 5 cm, so the panel stands just inside the iron, clear of it. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence", meta = (Units = "cm"))
    double FenceInsetCm = 75.0;

    /** Off: only the -Y side of the route (its left, looking along the stations) is fenced. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    bool bFenceBothSides = true;

    /** Intended: SM_FenceBay_open_v2 (its own MI_FenceBay_open). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    FInfinityStageFenceVariant FenceVariantA = FInfinityStageFenceVariant(0.6);

    /** Intended: SM_FenceBay_tarp_half_v2, overlay SM_FenceTarp_tarp_half_v2. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    FInfinityStageFenceVariant FenceVariantB = FInfinityStageFenceVariant(0.2,
        TEXT("/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/SM_FenceTarp_tarp_half_v2.SM_FenceTarp_tarp_half_v2"));

    /** Intended: SM_FenceBay_tarp_torn_v2, overlay SM_FenceTarp_tarp_torn_v2. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    FInfinityStageFenceVariant FenceVariantC = FInfinityStageFenceVariant(0.15,
        TEXT("/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/SM_FenceTarp_tarp_torn_v2.SM_FenceTarp_tarp_torn_v2"));

    /** Intended: SM_FenceBay_door_gap_v2 (its own MI_FenceBay_door_gap). */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    FInfinityStageFenceVariant FenceVariantD = FInfinityStageFenceVariant(0.05);

    /** Chain-link shadows are the point of the fence; panels and overlays alike. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    bool bFenceCastShadow = true;

    /** Mixed into every panel's stream, to re-roll the variants without touching the Show. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Underpass|Fence")
    int32 FenceSeed = 0;

    static constexpr int32 FenceVariantCount = 4;

    /** Variants A..D by index; any other index is D. */
    const FInfinityStageFenceVariant& GetFenceVariant(const int32 Index) const
    {
        return Index == 0 ? FenceVariantA : Index == 1 ? FenceVariantB : Index == 2 ? FenceVariantC : FenceVariantD;
    }
};

/** One blinking underpass tube, as built: driven in game worlds by the structure's tick. */
USTRUCT(BlueprintType)
struct INFINITYSTAGE_API FInfinityStageTubeBlinker
{
    GENERATED_BODY()

    /** Instance in UnderpassTubeBlinkComponent, or -1 (no tube mesh: the light alone blinks). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Underpass|Tubes")
    int32 InstanceIndex = INDEX_NONE;

    /** Custom data [3] while lit (TubeGlowLevel at build). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Underpass|Tubes")
    float OnValue = 1.0f;

    /** 0..1 offset into the cycle. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Underpass|Tubes")
    float Phase = 0.0f;

    /** Cycle length multiplier, 0.6..1.4. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Underpass|Tubes")
    float RateScale = 1.0f;

    /** The rect light this tube hosts, if any. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Underpass|Tubes")
    TObjectPtr<URectLightComponent> Light;
};

/** One underpass part's loaded mesh and material, as MaterializeStructure hands
 * them to BuildUnderpass. Not reflected; lives only for one build. */
struct FInfinityUnderpassPart
{
    UStaticMesh* Mesh = nullptr;
    UMaterialInterface* Material = nullptr;
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

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Infinity Stage")
    FInfinityStageUnderpassSettings Underpass;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Materialization")
    TArray<TObjectPtr<UInstancedStaticMeshComponent>> ManagedComponents;

    /** The tube lights this actor generated, owned and cleared like ManagedComponents. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Materialization")
    TArray<TObjectPtr<URectLightComponent>> ManagedLights;

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

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassColumnCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassPierCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassKneeCount = 0;

    /** One per bay, between each station and the next. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassDeckCount = 0;

    /** Two per bay when the catwalk is on. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassCatwalkCount = 0;

    /** Tube meshes built, dead ones included (they are dark, not missing). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassTubeCount = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassTubeLightCount = 0;

    /** The TubeLightEvery the lights were built with: above the setting when the cap thinned them. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassTubeLightEveryUsed = 0;

    /** Blinking tubes (TubeBlinkFraction), driven by Tick in game worlds only. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization", AdvancedDisplay)
    TArray<FInfinityStageTubeBlinker> UnderpassTubeBlinkers;

    /** The movable component the blinkers' tube meshes live in (null without blinkers). */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization", AdvancedDisplay)
    TObjectPtr<UInstancedStaticMeshComponent> UnderpassTubeBlinkComponent;

    /** Pure: whether a blinker is lit at TimeSeconds. */
    static bool IsTubeBlinkOn(double TimeSeconds, float Phase, float RateScale, double PeriodSeconds, double DutyOn);

    /** Applies the blink state at TimeSeconds (the blink timer's work; public for tests). Returns how many blinkers changed. */
    int32 UpdateTubeBlinkers(double TimeSeconds);

    /** Fence panels built, every variant together: the tiles, not the gaps. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassFencePanelCount = 0;

    /** Overlays (tarps) built on those panels. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Materialization")
    int32 UnderpassFenceOverlayCount = 0;

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

protected:
    virtual void BeginPlay() override;

private:
    /** Last applied lit state per blinker (transient; sized on first update). */
    TArray<uint8> TubeBlinkLit;

    /** A looping 30 Hz world timer, set only in a game world with blinkers. A timer
     * rather than an actor tick, so saved instances' tick flags never matter. */
    FTimerHandle TubeBlinkTimer;
    void OnTubeBlinkTimer();

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

    /** A part whose Mesh is null is skipped; no part's placement depends on another's mesh. */
    void BuildUnderpass(
        const TArray<FInfinityStructureStation>& Stations,
        const FInfinityUnderpassPart& Column,
        const FInfinityUnderpassPart& Pier,
        const FInfinityUnderpassPart& Knee,
        const FInfinityUnderpassPart& Deck,
        const FInfinityUnderpassPart& Catwalk);

    /** Tube rows and their lights. A null Tube.Mesh builds the lights alone. */
    void BuildUnderpassTubes(
        const TArray<FInfinityStructureStation>& Stations,
        const FInfinityUnderpassPart& Tube,
        UMaterialInterface* LightFunction);

    /** Fence panels, one entry per variant A..D in each array. A null panel mesh
     * skips its variant; a null overlay mesh builds the panel alone. */
    void BuildUnderpassFence(
        const TArray<FInfinityStructureStation>& Stations,
        const TArray<FInfinityUnderpassPart>& Panels,
        const TArray<FInfinityUnderpassPart>& Overlays);

    URectLightComponent* CreateManagedLight(FName BaseName, FName LayerTag);
};
