# A legible machine: grooves, wing bars, side masking, floating lamps

Proposed spec for Gary, 29 September 2026, from Rig & atmosphere. Nothing is
built yet. It follows Gary's principle: *"a semi-logical machine even if
impossible."* No visible contradiction, and no obligation to function.

## The idea that ties it together

Gary asked for grooves in the walnut and bars on the wings. The grooves are
already where the wings are. Each chariot slot the ground layer computes runs
across the stage at a wing's station (x = the station, 8 cm wide), from about
1.5 m inboard of that side's wing out to the floor edge. The wing card stands
in the same plane. So if every wing carries a **pole down into its groove**,
the floor and the wings become one visible machine. It's the Baroque
chariot-and-pole stage (Torelli): wings on poles running in slots across the
stage, readable from the camera. The machine doesn't have to work, only read.

## 1. Tram-track grooves in the walnut

- **Geometry comes free.** The ground layer already knows every slot: 96 in
  P01, 185 in P05 and 110 in P06, each with its station, side, inner edge and
  outer edge.
- **What's drawn:** per slot, a thin dark groove strip flanked by two narrow
  metal rails (tram track), laid just proud of the slab (top at +0.5, pieces
  0.2 cm above it). Nothing is cut. The slab stays whole, and the inlay reads as
  let into it.
- **Where:** a per-structure switch, on where a textured slab covers the boards
  (P01, P05, P06). P02 and P04 still show boards, where the slot is already a
  real gap.
- **Cost:** C++ (a new piece type in the ground layer, with settings for rail
  width, groove width, height and two materials), one build, then a re-fit.
  About 1,200 instances in two small instanced components, so the render cost
  is negligible.
- **Materials:** a near-black matte groove and a dull steel or brass rail. Two
  simple materials, part of the same job as the boards and bars (see 5).

## 2. Bars on the wings: a pole into the groove, and a pipe on each border

- **The authoring already exists; the motion doesn't.** The Show carries Prop
  attachments with a mesh, anchored to `LeftPanel`, `RightPanel` or
  `TopPanel`. But a Prop actor is placed ONCE, when the passage is
  materialized, from the panel's pose at that moment
  (`InfinityStagePassageActor.cpp:881`). During the show the mechanism moves the
  panel instances every frame (`EvaluateMechanismsInternal`), and nothing moves
  the props. Only Effect sources track their panel at runtime. So today a bar
  authored on a border would stay behind when the border flies. Checked in
  source; an earlier draft of this note wrongly said no C++ was needed.
- **The C++ it needs, best form:** the passage actor renders panel-anchored
  rigging (poles, pipes, lines) as instanced meshes. Each is updated in the
  same per-frame batch that already moves the panels, with instance = relative
  offset × live panel transform. That's cheap: no spawned actors, a few
  instanced components, and the transforms are computed anyway. Simpler
  alternative: re-place panel-anchored Prop actors each frame after the panel
  batch. It's less code, but it costs one spawned actor per bar, about 1,300,
  against the 40 fps ceiling.
- **Wings (Left/Right):** a pole at the card's back face on its pivot line,
  from just below the floor (standing in its groove) to a little above the
  card's top. It travels with the card.
- **Borders (Top), "overhead wings especially":** a pipe along the border's
  **bottom** edge, which is the visible edge; the top is above frame. Two lift
  lines rise from it up the border's face and on into the dark. When the border
  floats up or down, the pipe and lines move with it, so the movement has a
  visible cause. The lines are fixed-length and have no winch, which the
  principle allows.
- **Sizing:** per pair, from each card's measured bounds. Pole height follows
  the card; pipe length follows the border.
- **Cost:**
  - C++ in the passage actor (shared code; the conductor's hook is also
    there), with tests. One build.
  - Authoring as Show data (one template per anchor, sized per pair), then
    materialize.
  - Three small meshes (pole, pipe, line) with materials.

### Whose job: the structure kit, the wing card, or the Show?

**The Show's attachments, authored by Rig & atmosphere, with meshes and
materials from whoever does materials.**
- **Not the structure kit:** its pieces are static once fitted (world-space
  instances, never moved per frame), so it can't follow a flying card.
- **Not baked into the cards:** that would mean re-exporting about 260 cards
  through two pipelines (V2 and legacy). The pole also has to stand in the
  structure's groove, which a card doesn't know about.
- **The anchor system** already expresses "this belongs to that panel", and one
  template makes every wing consistent. It only needs the per-frame follow
  added in the passage actor.
- Wing materiality owns the cards and should agree to this before anything is
  authored.

## 3. Side masking: "not seeing endless space on either side"

- **Nothing exists today.** The "wall bays" were designed and never built, so
  past the wings the camera sees the dusky void.
- **Proposal: a side frame per bay**, as a new static structure layer. Posts at
  each station rise from the floor to carry the grid's rails, with a masking
  panel (black, or a timber or metal skin) between posts. It masks the void
  and makes the grid rest on something, a second legibility gain.
- **Constraint:** wing cards reach past the rails in most passages (P01 up to
  ±1094, P06 ±1078, one P02 card ±3879). So the frame must stand outboard of
  each passage's widest card, measured per passage, or it cuts cards. That's
  the "reads as broken" case.
- **Cost:** C++ (a new layer, at stations only, like the gridiron), one build,
  then a re-fit. Static instanced pieces, cheap to render. Materials: black, or
  the structure material.

## 4. Floating lamps: give them something to hang from

- **The problem:** 242 lit lamps in P01, 23 in P02, 84 in P04, 372 in P05 and
  220 in P06 sit above the 1150 grid, up to 21.7 m. Each has a housing and no
  line, because the fixture pass hangs a line only when there is grid within
  reach above.
- **Fix, per the principle:** a lamp with no grid within reach gets a line
  **up into the dark** (fixed length, e.g. to 3,000 cm) instead of none. It
  reads as hanging from something unseen.
- **Cost:** a small C++ change in `BuildFixtures`, one build, then a re-fit.

## 5. The material job (one job, four customers)

- **The customers:** the boards, the grooves and rails, the bars (pole, pipe,
  line) and the side frame all render on the engine's grey, because every kit
  mesh is an engine Cube and every material slot is empty.
- **Where materials plug in:** the structure kit has per-layer material
  settings (`Gridiron.Material`, `Ground.BoardMaterial` and so on). Prop meshes
  carry their own material.
- **One constraint:** kit pieces are Cubes scaled to size, so a material must
  tile using per-instance custom data (length, width and depth in cm are
  already passed) or world-aligned UVs, or the texture stretches.

## 6. "Top Down" (approved, shadows off): what it will and won't do

- **What they are:** lamps at grid height aimed down. They light the stage and
  the wings from above: lights living on the grid.
- **What they won't do:** light the grid itself. The beams' undersides, which
  are what Puss sees looking up, face away from them.
- **To see the grid when Puss looks up:** something must light the undersides,
  such as a few uplights at the wing tops, or the Top Down lamps' own housings
  catching light. That's a separate lighting decision.

## Suggested order

1. Grooves and poles together: one look decision. Grooves, the panel-follow
   C++ and the floating-lamp lines can share one build.
2. Border pipes.
3. Floating-lamp lines, riding the same build as the grooves.
4. Side frame.
5. Materials in parallel.
