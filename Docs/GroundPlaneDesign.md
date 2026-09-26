# Infinity Stage ground design

Rewritten 26 September 2026 by Rig & atmosphere for the container world
(`Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md`). The earlier version
specified a naturalistic forest floor. The direction has changed: we are inside a
Baroque stage machine, so the floor is machinery. The earlier three-layer logic
survives; its implementation does not.

## Creative direction

The floor is the stage of the machine: timber boards, chariot slots cut across
them where the wings run, darkness beneath, and cloth laid over the boards and
worn through at frays and holes so the boards and slots show beneath. Gary's
idea, and historically right: Baroque stages covered their boards with painted
ground cloths.

It is still the closest scenery to the camera, so it must still carry evidence
of use — worn cloth, repaired boards, dropped rope, sandbags — and still let the
wings lead.

**Puss is the one thing in the machine not on rails.** No slot, groove or track
ever crosses the cat's centre line. This is enforced by construction, not by
convention (below).

## Core decision

The floor is a layer of the **structure pass**, `AInfinityStageStructureActor`
(one per Passage, `Plugins/InfinityStage/Source/InfinityStage/…/InfinityStageStructureActor.*`),
beside the gridiron and the lamp housings. Like every structure layer it derives
from the Passage's compiled wing stations, so the floor re-fits when the wings are
re-spaced, and it owns only components tagged `InfinityStage.Structure`, so
anything placed by hand survives every regeneration.

Generate the spine, hand-place the accidents: the pass lays boards, slots and
cloth with deterministic variation; sandbags, rope, ladders and debris are
dropped by eye and never touched by it.

Disconnected worlds still change behind a Scene cut, not by blending floors.

## The three layers

### 1. Walkable substrate — the boards

Plank boards in lanes along the route, tops at the route line (`FloorHeightCm`,
default 0), 24 cm wide with 0.8 cm joints and 5 cm thick. Lengths are drawn per
lane from 240–480 cm, and each lane starts part-way through a board, so joints
stagger instead of forming a grid. Boards run along the direction of travel, so
perspective reinforces the passage. They are chords of the route, so a curving or
rising route gets straight timber, not bent planks.

The floor spans the building: the gridiron's half-span (widest panel plus
overhang) either side of the route line.

Boards currently have **no collision**: nothing on the stage is physics-driven
(the cat follows the GO1 telemetry path). Add simple collision only if a walker
ever needs it; never collide the visible detail.

### 2. Hero surface — slots and understage

A **chariot slot** (8 cm) is cut across the boards at every wing station, on both
sides, running from `SlotInboardCm` (150 cm) inside the wing's line out to the
building's wall, so a wing travelling inward still stands over its slot. No slot
comes nearer the route line than `CatClearanceCm` (120 cm): **the cat's line is
clear by construction**, whatever the wings do.

A dark **understage** slab lies 2.5 m below the boards, seen only through slots
and joints, so a slot reads as a cut into depth rather than a painted line. The
boards cast shadows precisely so that lamps cannot light the understage through
the floor.

### 3. Dressing and history — cloth and accidents

**Ground cloths** from Soft goods (`/Game/Scenes/Curtain/FloorCloth/SM_FloorCloth_A–D`,
sources in `DerivedAssets/FloorCloth/`): four settled cloth-sim pieces, pivot at
centre, 0.3–3.3 cm above the boards, two with torn ends, masked material with
three wear patterns. The pass lays at most one per bay (coverage 0.7 by default),
with 180° flips, ±4° yaw and small offsets, fitted to the bay by bounds and never
scaled vertically, so the simulated rumple survives. The cat's line may be
covered: cloth is not rails.

**Accidents** are placed by hand and are never regenerated.

## Material vocabulary

Every structure instance carries four custom-data floats: `[0]` variation 0..1,
`[1]` length, `[2]` width, `[3]` depth in cm. Materials use `[1]`/`[2]` to tile
grain or weave at true scale however the piece is fitted, and `[0]` for tone
(and, for cloth, the wear pattern). Per-Passage variation is by material instance
on each structure actor (`BoardMaterial`, `UnderstageMaterial`, `Cloth.Material`).

Still worth keeping from the earlier design: vary colour, normal and roughness
together, never colour alone; worn centres and protected edges; dark, shallow
joints; restrained repairs rather than uniform newness.

## State, 26 September 2026

| Passage | Ground | Why |
| --- | --- | --- |
| P01, P02, P04, P05, P06 | on | corridor floor was empty |
| P03 | off | the "Passage 3 - Wet Ground" Landscape sits at about +10 cm and would bury the boards |

- **Built and verified:** the ground layer compiled into `UnrealEditor-InfinityStage.dll`;
  `InfinityStage.Structure.GroundSlotsKeepTheCatLineClear` and
  `ClothLiesOverTheBoards` pass; swapped into the level (26,090 boards, 480 slots),
  saved and read back after a reload from disk, zero dirty.
- **Not yet seen in a frame.** P01 is the test: its "ForestedLandscape" lies
  at y 54,800–67,400, not under the corridor, which is why P01 looked down into a
  void. Nobody has accepted the floor by eye.
- **Boards are engine cubes** with no material yet. A timber board mesh (Blender)
  and a board material are the next look work.
- **Cloth is off** until Soft goods' pieces are imported into `/Game`.
- **The two Landscapes** (P01's misplaced ForestedLandscape, P03's Wet Ground)
  still exist. Removing P03's lets its ground go on; P01's is not in the way.

## Non-goals

- No forest floor, soil or moss: the register is timber, rope and canvas.
- No generated clutter on the cat's line.
- No runtime regeneration: the floor is materialized in the editor and saved.
- No blending between disconnected worlds; change them behind a Scene cut.
