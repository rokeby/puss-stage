# Rig & atmosphere — brief

For the session **"Puss · Rig & atmosphere"**, from the conductor session, 2026-09-25.
Read `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` first, then this.

## What the user wants

We are inside a **Baroque stage machine**, not on a travellator past scenery.
Timber gridiron overhead, chariot grooves in the floor, hemp lines, sandbags,
walls beyond the wings, par cans hazing in the distance. Wood, rope, canvas,
paint, wear — **not** industrial steel truss. Industrial precision is a
deliberate wrongness to introduce later, never the default.

The structural rule: **the bay is the unit.** The Show compiles every wing pair
to a station along the route. Ground grooves, gridiron bays, wall panels and
practicals must all derive from **those same stations**, so the container shares
the wings' rhythm and re-fits itself if spacing changes.

And: **generate the spine, hand-place the accidents.** Your generator owns only
what it created (tag it, destroy only your own tag) and never touches
hand-placed actors. The user will drop rope, ladders, debris and sandbags by eye,
and those must survive every regeneration. That division is what stops it
looking generated.

## What you own

- New plugin files for a **`MaterializeStructure`** pass beside
  `MaterializePassage` — put it in new files so it cannot collide with another
  session's work.
- Fog and volumetrics on the level.
- Light **fixture bodies** — the lights exist but have no apparatus; give the
  attachments an optional visible mesh and hang them on the grid.

## Where it got to (this is real, verified, and saved)

**Volumetrics are tuned and persisted.** Fog density 0.022, height falloff 0.12
(was 0.34, which starved the upper corridor of medium), extinction 0.9,
scattering distribution 0.55. **136 "beam" fixtures** — the two cross spots on
every 4th bay — at volumetric scattering 9.0 with volumetric shadows on; the
other **2,382 at 0.6**. Written into the Show's light attachments so it survives
materialize, verified against the live actors, Show and level saved.

The lesson that got us there: raising scattering on *all* 2,257 fixtures made
uniform fog soup. **Discrete beams require discrete sources.** And haze is only
visible where there is light in or behind it — the far corridor reading as black
rather than deep is a missing-practicals problem, not a fog problem.

**A gridiron preview exists**: `Saved/CodexLighting/gridiron_build.py` generates
771 beams over all six Passages — one cross beam per wing station plus continuous
side rails, at 1150 cm with 220 cm overhang, 26 × 34 cm section. It derives
stations from `MaterializedPanels` (left/right base transforms, midpoint), is
regenerable by the tag `InfinityStage.Gridiron`, and is saved in the level.

**It is grey engine cubes and it is Python.** Two jobs follow: give it timber
(material and section profiles; real Baroque detail — hemp lines, sandbags,
pulleys — is Blender work you should brief Soft goods for), and **promote it to
the C++ `MaterializeStructure` pass**, because Python-created components are a
preview and may not survive save/reload cleanly.

## Your first jobs, in order

1. **Promote the gridiron to C++.** Same derivation, but owning its instances the
   way `AInfinityStagePassageActor` owns its managed ISMs (`NewObject` +
   `AddInstanceComponent` + `RegisterComponent`, `RF_Transactional`).
2. **Ground.** The floor becomes machinery: chariot grooves at the wing stations
   with the dark beneath showing, wooden boards, and — the user's idea, which is
   historically right for Baroque stages — **cloth laid over the boards, worn
   through at frays and holes** so the grooves show beneath. Per-Scene variation
   by material instance. **The cat's centre line stays clear of grooves**: Puss
   is the one thing in the music box not on rails.
3. **Landscape must go.** Passage 1 uses a `Landscape` actor (192 references in
   the umap). Landscapes are flat grids that cannot curve, and the user has
   chosen a closed-ring route with rise and fall as the target. Replace with
   mesh ground. `Docs/GroundPlaneDesign.md` specifies a naturalistic forest floor;
   its three-layer logic survives, its implementation does not. Rewrite it.
4. **Fixture bodies and wall bays.**

## What you need from other streams

- **Soft goods** owns the Blender cloth pipeline. Anything hanging, peeling or
  draped on your rig — cloth over the grid, dust sheets, rope — brief them; do
  not build it yourself.
- **Effects sources** will want haze and fire emitters on your bays. The
  `EInfinityAttachmentKind` enum lives in the shared `InfinityStageTypes.h`, so
  **that enum change goes through the conductor once**, not twice.

## Constraints

- **VSM one-pass overflow is already happening** — too many shadow-casting local
  lights per pixel, and there are ~541 shadow casters plus your 136 volumetric
  ones. It will get worse as the rig grows. Settle it early: either raise
  `r.Shadow.Virtual.OnePassProjection.MaxLightsPerPixel` or cut casters.
- Corridor half-width varies a lot: **P05 is 470 cm against P01's 970 cm**. A
  single margin will feel wrong somewhere; consider per-Passage.
- Assets should be **procedural or generated** — Blender for timber, rope and
  shapes; Meshy or purchase only for hero pieces. Do not rely on found assets.
- Builds need the editor closed and go through the conductor. Map edits and
  Show mutation take a `Backups/Pre<Thing>-YYYYMMDD-HHMM` snapshot first.
- Headless success is not rendered acceptance. The user reviews by eye.

## Relevant code

- `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp`
  — `MaterializeAttachments`, `AddPanelInstance`, managed-ISM ownership, and
  `GetAttachmentAnchorWorldTransform` (the anchor write-back path).
- `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h` —
  `FInfinityStageLightSettings`, `EInfinityAttachmentKind`, `EInfinityAttachmentAnchor`.
- `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCelestialRig.cpp`
  — owns fog colour every evaluation, so do not set inscattering on the fog actor
  and expect it to stick.
- `Saved/CodexLighting/gridiron_build.py`, `haze_beams.py`, `persist_beams_to_show.py`.
