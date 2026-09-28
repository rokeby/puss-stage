# Chaos Cloth curtain — pipeline and traps

> **26 Sep: the curtain FALLS, it does not fly** (Gary; `Docs/Conductor/BRIEF_TRANSITIONS_AND_SCALE_2026-09-26.md`).
> It is already down and lit; at the cue it drops to the floor and stays as a pile. It is the
> Kabuki *furi-otoshi*. **Chaos cannot un-pin at runtime**: the kinematic set
> (`KinematicVertices3D`) is baked when the simulation initialises, and changing MaxDistance later
> does not free those particles. So the falling asset `CA_<STEM>_Fall` pins **nothing**, and
> `BP_CurtainChaos` starts its ChaosClothComponent **suspended** (`bSuspendSimulation`,
> Sequencer-keyable), holding the hanging start pose. Un-suspending is the drop: it falls as a whole,
> the hem lands first, and it crumples up from the floor. The BP carries a hidden `FloorCatch` box (top
> at z = 0, WorldStatic, ignores Pawn/Camera/Visibility) because **the stage boards have no
> collision** (Rig & atmosphere: every structure ISM is NoCollision; the chariot slots are open).
> Unproven: whether Chaos environment collision counts a box in the cloth's *own* actor. If the
> pile drops through, FloorCatch must become a separate actor, which is a level write.
> Asymmetric release (one side first) would be pins as a stiff anim-drive spring whose stiffness
> goes to 0 at the cue. Not built.
> Scrub: tick **Simulate In Editor** (the cloth appears, hanging), then untick **Suspend
> Simulation** to drop it; `Hard Reset Simulation` and re-tick Suspend to hang it again.

Soft goods stream, 25 September 2026. The show curtain is now **Chaos Cloth simulated live
in the editor**, not a Blender bake. The bake route (`Scripts/build_curtain_cloth_bake.py`,
`DerivedAssets/CurtainCloth/CurtainCloth_Fly_V1.abc`) is kept for the one case it still wins:
a cue that needs the same silhouette every night.

**Why the route changed:** four bake cycles were rejected ("gelatinous", "waxy", "drawn-on
creases", "pretty poor"). Each was a blind guess plus a 10–15 min bake, because nobody could
touch a parameter while watching the cloth. Chaos puts the solver in the editor.

## 27 Sep: why the free fall was a "viennetta", and the guided fall

Gary rejected the first fall: "It should be a big crumpled heavy fabric sprawled on the floor, not a very
narrowly squished viennetta." Four off-stage benches (`Scripts/curtain_fall_bench.py`: transient
curtains at y >= 60000, runtime overrides through the ChaosClothAssetInteractor, one capture per few
ticks, full cleanup) found:

- **A free-released sheet cannot sprawl.** Released uniformly, a symmetric vertical sheet falls straight
  down and piles in its own footprint. Stiffer solver (8 iterations, 4 substeps), 2 cm/side
  self-collision, bending 0.3–0.5, no buckle-softening, a 4° lean, low friction and a real 2.5 m/s gust
  all still end as a strip. With the stiffer settings the pile first has volume, then **deflates** to a
  strip over ~200 ticks.
- **Guiding the heading works.** Keep the heading pinned (`CA_<STEM>`, fly mode) and carry the cloth
  component down (gravity-timed, s²) and forward over ~1.4 s, like a batten falling forward. The top edge
  folds over the body and the cloth lands crumpled and spread 2–3 m deep. **Forward distance is the dial**
  (0 m: narrow; 3 m, 6 m: progressively sprawled). Bench config: `Scripts/curtain_fall_bench_guided.json`;
  clip: `Saved/CodexSoftGoods/curtain_guided_fall_plain_vs_ragged.gif`. In the show this is a transform
  track on the cloth component; in the editor, drag the component down with Simulate In Editor on.
- **Heavy-fabric loft** (bench5, guided 4.5 m, plain): bending 0.8, no buckle-softening (BucklingRatio 0),
  3 cm/side self-collision at stiffness 1.0 turns the fine crinkle into broad heavy folds. Grip (0.9 cloth,
  0.8 floor) holds them, and damping plus 3 self-collision substeps adds crumple. A **faster drop (0.9 s)**
  billows on the way down and lands as the most crumpled, overlapping heap: the best match so far for
  "big crumpled heavy fabric sprawled". Clip: `Saved/CodexSoftGoods/curtain_guided_fall_loft.gif`.
- **WindVelocity is in m/s**, not cm/s ("a gust is above 8 m/s"). 250 means a hurricane.
- **Environment collision is gathered from the cloth's bounds, which are the reference pose.** A cloth lifted
  off the floor (even with bounds scale 2) fell straight through FloorCatch. The placed curtains land only
  because the hem touches z = 0. Unresolved.
- **The editor currently ticks at ~2.5 s idle** (background throttling plus intermittent 3 s HTTP stalls to
  generate_204), so cloth cost can't be measured until the editor runs in the foreground. The physics is
  still valid (Chaos clamps dt), just slow-motion.
- Setting a cloth component's transform through `set_editor_property` re-registers it, and its interactor
  never comes up. Use `set_relative_location/rotation(..., teleport)`.

## 28 Sep: THE PIN WAS WRONG ALL ALONG. Chaos re-sorts sim vertices

**Every guided fall before 28 Sep was from a mis-pinned curtain.** The heading selection used static-mesh
vertex indices (verified on the imported mesh), but **Chaos does not use the static mesh's vertex order
for its sim vertices**. Observed on running sims (in-situ settle tests plus an off-stage pin-order test):
Chaos orders sim vertices **column by column across the 2D pattern (low u first), bottom-to-top within
each column**. So the mesh's "top row" indices 0–146 pinned the bottom-up runs of the first two columns:
the curtain hung from its LEFT EDGE. Renumbering the source mesh (first-appearance order) changed nothing,
because Chaos re-sorts regardless. For the plain 147×67 grid the true heading is `c·67 + 66`; that holds
the whole top edge level (pin-order test, silhouettes). The indices always read back correctly on the
imported mesh, so this is invisible until a sim runs. Treat ANY index-based cloth selection or weight map
as suspect.

The sprawl, loft, breeze and gust bench findings were all measured on this mis-pinned cloth. They point
the right way but are not trustworthy numbers until re-run on a correctly pinned curtain.

Fix status: see the handover and this stream's report. The rule-derived pin (with an automated
pin-flatness check in every build) versus a position-based pin (UV mask via TextureToAttribute, or vertex
colour) is under decision. No position-based cloth selection node has been found in 5.8.

## 28 Sep: the Chaos Opening (in a duplicate sequence)

Gary: the curtain doesn't follow the camera. It stands fully in front of every wing (x ≈ 0, just
upstream of station 1) and falls UPSTAGE. `Scripts/build_opening_chaos_sequence.py` made
`/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos`, a duplicate; **the original
`LS_Opening_Curtain` is untouched** and Show cue 0 still plays it. The copy spawns:

- "Chaos Curtain" = `BP_CurtainChaosCloth` (a plain Actor with the pinned PLAIN cloth). Its actor
  transform track parks it at (0, 0, 0), yaw 90, then from frame 50 to 72 (≈0.9 s) carries it 1.8 m
  upstage and 995 cm down (s^1.5 / s² keys): the guided fall.
- "Curtain Floor" = `BP_CurtainFloorCatch` (a hidden WorldStatic box, top at z = 0, ignoring
  Pawn/Camera/Visibility/CatFloor).

Why not a subclass of `AInfinityStageCurtainRig` (the old Fire Safety rig): its constructor calls
`SetActorEnableCollision(false)` (a bare UPROPERTY Blueprint cannot flip, so a floor box inside it
is dead), it force-shows `SM_FireSafetyCurtain_01` whenever active, and the Interaction-1 automation
test counts exactly one rig. With `bSequenceOwnsCurtain` nothing outside the sequence reads
`CurtainProgress`.

The 1.8 m throw (not 4.5 m) keeps the ±888 cm pile in front of station 1's wings (x = 250, ±750).
Still open: persistence (a default spawnable pops the pile at 15 s), the camera pose and lens,
removing the x = 5400 preview (a level write), and repointing cue 0 (a Show write). All are Gary's.

**Breeze** (bench6): under 1 m/s, a breeze makes no measurable difference to the hanging 0.8 kg/m²
velvet. Mean frame-to-frame change: still 1.50, 0.3 m/s 1.48, 0.6 m/s 1.47, 0.6 m/s with drag 0.15
1.17. Not baked. Options: none, a 1–2 m/s gust timed at release, or a lighter-feeling fabric.

**Air at the release** (28 Sep, Gary's choice): the plain pinned asset carries a constant 1.5 m/s
wind UPSTAGE, in the cloth's COMPONENT space (upstage = local −Y for a yaw-90 curtain), drag 0.08
(`AIR_BY_STEM` in `build_curtain_chaos_asset.py`). Benched (bench8): inert while hanging (motion
1.41 vs 1.46 still), and it adds a subtle upstage billow once the cloth falls, so it is functionally
"air at the release" with no timing machinery. A scene Wind Directional Source (strength 1, speed 5)
did NOT measurably reach the cloth, so a Sequencer-keyed wind actor cannot deliver a gust. A literally
timed gust would need a small C++ component (a keyable float feeding the interactor's WindVelocity).
Not built.

## Read this first: the rest-shape trap

**Chaos takes the cloth's rest shape from the 3D mesh by default.** Two settings:

| Node | Setting | Default | Must be |
| --- | --- | --- | --- |
| `SimulationStretchConfig` | `bStretchUse3dRestLengths` | `True` | **`False`**: rest lengths from the flat 2D pattern (UV0 × UVScale) |
| `SimulationBendingConfig` | `RestAngleType` | `Use3DRestAngles` | **`FlatnessRatio`**, `FlatnessRatio` = 1: flat at rest |

The mesh's 3D positions are the pleated *start pose*. With the defaults, those pleats become
the rest state and the solver holds them forever. That is the "creases drawn on in repeated
patterns" defect Gary rejected twice in the Blender route, in a different engine. **Shape the
start pose; let the solver make every crease.** The same rule applies to the pattern cutter:
raggedness is boundary topology made from non-repeating noise. Sine sums repeated about 11× across
the 35 m pattern and were thrown out.

## Files

| What | Where |
| --- | --- |
| Pattern cutter (Blender 4.4, headless) | `Scripts/build_curtain_chaos_pattern.py` → `DerivedAssets/CurtainCloth/Chaos/SM_<STEM>.fbx` + `<STEM>.json` + `<STEM>_pattern.png` |
| Weave maps | `Scripts/build_curtain_weave_maps.py` → `DerivedAssets/CurtainCloth/Chaos/Textures/` |
| Unreal build (textures, velvet material, mesh, Dataflow, cloth asset) | `Scripts/build_curtain_chaos_asset.py` |
| Place a scrubbable instance in the level (**needs the conductor's level slot**) | `Scripts/place_curtain_chaos_preview.py` |
| Unreal content | `/Game/Scenes/Curtain/Chaos/` |

`<STEM>` is `CurtainChaos_Ragged_Q15` (15 cm quads, ~15k vertices: interactive) or
`CurtainChaos_Ragged_Q09` (9 cm, ~41k: the bake resolution, for once the values are settled).

Unreal scripts run through the guarded MCP route: copy into `Saved/CodexSoftGoods/`, then
`python Saved/CodexMocap/mcp_request.py tools/call --params-file <request>.json`
(`ExecuteProjectPythonFile`, relativeSavedPath `CodexSoftGoods/<script>.py`). Each script
checks it is in the expected world, refuses to start if any package is dirty, saves only what
it made, and ends on an explicit `PUSS_SOFTGOODS_*_SUCCESS` marker.

## Rebuild

```bash
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python Scripts/build_curtain_chaos_pattern.py
python Scripts/build_curtain_weave_maps.py
```

Then run `build_curtain_chaos_asset.py` in the editor. It re-imports the mesh and textures,
rebuilds the material in place, and deletes and recreates `DF_`/`CA_` (they are derived data).
Pattern knobs are environment variables: `CURTAIN_QUADS_PER_BOLT` (9 → 15 cm, 15 → 9 cm),
`CURTAIN_SEED`, `CURTAIN_FULLNESS`, `CURTAIN_RAGGED=0`. For the Unreal side, set `CURTAIN_STEM`.

## Pattern

- Flat pattern **fullness 2.0**: 35.5 m of fabric for a 17.77 m track, 10 m drop. UV0 is that
  pattern normalised 0–1. Chaos `StaticMeshImport` uses UVChannel 0 with UVScale =
  (pattern width, drop) in cm, so the 2D rest lengths are the real fabric's.
- Start pose: the fabric gathered onto the track in pleats. The gather is by arc length, so it
  starts unstretched, and pleat depth varies per pleat, never per vertex.
- Columns are sized so a **seam** falls on a grid line every **1.37 m** of flat fabric (one bolt).
  The material draws the seams from UV0.
- Rags: an aperiodic torn hem, 3–5 tongues torn well up, frayed sides, 4–7 tears ripped up from
  the hem (split edges, opened 4 mm so they cannot re-weld) and 5–8 holes. Cut edges are
  relaxed off the grid. Anything not connected to the heading is removed.
- **Heading** = the top row, tied to the batten. Its vertex indices go into the sidecar JSON;
  the build checks after import that every one of them is on the top edge.

## Physics: what carried over from the bakes

Relationships, not numbers. Blender's per-vertex mass and stiffness units do not translate.

| Relationship | Chaos |
| --- | --- |
| Will not stretch | `Stretch` PBD, stiffness 1.0, **area constraint off** (it resists compression → plate); tethers stiffness 1, scale 1 |
| Folds for free (Blender tension 200 / compression 3) | `Bending` PBD stiffness 0.05, **buckling stiffness 0.005** after buckling ratio 0.5 |
| Heavy, not jelly | Density **0.8 kg/m²** (heavy velour, about 25 oz/yd²). The Blender "7 kg/m²" was a solver artefact, not a fabric weight |
| No flutter | Damping 0.05, drag/lift 0.03 |
| Folds keep their structure | Self-collision on, friction 0.8 |
| Heading on the batten | `Selection` "Heading" (SimVertices3D indices) → `MaxDistance.InKinematic`; MaxDistance 10000 cm for everything else |

Tune in the graph (`DF_CurtainChaos_Ragged_Q15`) with the cloth running. Numbers that settle
go back into `PHYSICS` in `build_curtain_chaos_asset.py` so a rebuild keeps them.

## Velvet

`M_CurtainVelvet` / `MI_CurtainVelvet_DeepRed`: **Cloth** shading model, two-sided, with sheen
from Fuzz Color. The base is darkened face-on and lifts toward grazing (Fresnel), which is the
nap turning away, the cue that reads as weight under raking beams. Flat deep-red base
(Gary, 25 Sep), weave from `FireSafetyCurtain_01_WeaveDetail_v1` at 12 cm tiles and ~20%,
seams darkened along a 2.4 cm line. **Nothing is painted into the colour**: TextileV5 is a picture of a
whole curtain with crumples painted in and must not be used on simulated cloth.

## Engine traps (UE 5.8), each hit once

1. **MaxDistance defaults to 0 when no weight map is painted**, which freezes the whole cloth.
   Set Low/High high and pin with `InKinematic` instead.
2. **`DataflowBlueprintLibrary.EvaluateDataflow` returns False for cloth assets even on
   success.** Epic's `DF_StaticMeshClothTemplate` and `DF_EmptyClothAssetTemplate` return False
   too. Don't gate on it. The evidence of a build is `LogSkeletalMesh: Built Skeletal Mesh
   CA_…` plus the cloth asset's material slots, which the evaluation fills.
3. **`MaterialEditingLibrary.DeleteAllMaterialExpressions` deletes only about half per call**
   (15 → 7 → 3). Loop until `GetNumMaterialExpressions` is 0, or orphans pile up on every rebuild.
4. **The Cloth model's "Cloth" input (CustomData0) is not reachable from Python.** Go through
   `MakeMaterialAttributes`: its `ClearCoat` pin *is* CustomData0.
5. **Saving a cloth asset sets the Clothing usage flag** and re-dirties the material instance
   unless the base material already has `used_with_clothing`.
6. **Dataflow authoring is fully scriptable**: `DataflowEditorBlueprintLibrary.add_dataflow_node`
   / `set_dataflow_node_property` (ImportText strings, e.g. `(bIsAnimatable=True,Low=1,High=1)`)
   / `connect_dataflow_nodes` (pins `Collection`; terminal input `CollectionLods[0]`). Node type
   names are the struct names, e.g. `FChaosClothAssetStaticMeshImportNode_v2`. The cloth asset
   links to its graph through `dataflow_instance.dataflow_asset` / `dataflow_terminal`, a
   deprecated-warning property path that still works.
8. **A configured game trace channel is named by its display name in Python.** `ECC_GameTraceChannel1`
   = "CatFloor" is `unreal.CollisionChannel.ECC_CAT_FLOOR`; there is no `ECC_GAME_TRACE_CHANNEL1`.
   Also, `set_collision_response_to_all_channels(BLOCK)` writes all 32 slots, including channels
   not yet defined, and an explicit per-component response beats the channel's default. So FloorCatch
   ignores CatFloor explicitly (the cat must not stand on the cloth's hidden safety net).
9. **`suspend_simulation` is a bool PROPERTY in Python**: it shadows the SuspendSimulation function, so
   calling it raises "'bool' object is not callable". Set it with `set_editor_property`.
   `resume_simulation()` is a real method.
10. **To put a curtain back to rest, switch Simulate In Editor off FIRST, then suspend.** The other order
    undoes the suspend and leaves the curtain live-simulating in the editor (hit twice on 27 Sep, once by
    the conductor and once by this stream; both caught on read-back). `simulate_in_editor` refuses
    `set_editor_property` on templates: use `set_simulate_in_editor()`.
7. `ChaosClothComponent.bSimulateInEditor` is transient and per instance ("Simulate In Editor" in
   Details): switching it on never dirties the level. `bEnableSimulation` and `bSuspendSimulation`
   are Sequencer-keyable.

## State and proof (25 Sep)

- Built: the CA/DF/mesh/material/textures under `/Game/Scenes/Curtain/Chaos`. **Tier: saved
  read-back.** 7/7 assets load, the cloth is linked to its graph and carries the velvet MI, 0 dirty
  (`Saved/CodexSoftGoods/verify_chaos_curtain.json`).
- Placed (26 Sep, 01:57, approved by Gary): `BP_CurtainChaos` and one instance, "CurtainChaos
  Preview", in `L_InfinityStage_V1VerticalSlice` at (5400, 0, 0), yaw 90 (P01's world, currently
  dark: judge the velvet after Rig's back-thrown lamps). Simulate In Editor is off; switching it
  on is Gary's call. Read-back: one actor, the right asset, dirty 0/0. Backup
  `Backups/PreCurtainChaosPreview-20260926-0156`. This save also absorbed the conductor's
  capture-tool map flag (`absorbed_capture_map_flag`). The conductor's HOLD reached this stream
  only after the save.
- The actor's bounds extend about 128 cm deeper and lower than the geometry. Probably cloth bounds
  padding; not confirmed.
- **Disproven (28 Sep):** Chaos does NOT keep the static-mesh vertex order; see "THE PIN WAS WRONG ALL ALONG".
- **Not yet seen:** any rendered frame. The look, the weight and the frame rate are unverified.
- Not started: the sequencer swap (conductor's call), velvet/sack/hanging-cloth variants,
  peeling wing-edge strips, dust sheets.
- **Festoon retired** (26 Sep, 20:01, Gary's go): the "CurtainCloth Preview" actor at x = 4400 and
  `GC_CurtainCloth_Festoon_V1` are gone. Before deleting, the asset registry, a byte search of all 30
  LevelSequences and the in-memory bindings all confirmed the level was the only referencer.
  Backup `Backups/PreFestoonRemoval-20260926-2001` (the .umap + the cache, hash-verified). The fly
  bake `.abc` on disk stays as a record.
- **Plain variant**: `CA_CurtainChaos_Plain_Q15_Fall` (fullness 1.25, no rags) and
  `BP_CurtainChaos_Plain_Q15`, unplaced, for Gary to compare with the ragged one. This is the one that
  matches "heavy, thick… nothing too fancy, a core fabric rather than drapery".
