# Chaos Cloth curtain — pipeline and traps

Soft goods stream, 25 September 2026. The show curtain is now **Chaos Cloth simulated live
in the editor**, not a Blender bake. The bake route (`Scripts/build_curtain_cloth_bake.py`,
`DerivedAssets/CurtainCloth/CurtainCloth_Fly_V1.abc`) is kept for the one case it still wins:
a cue that needs the same silhouette every night.

**Why the route changed:** four bake cycles were rejected ("gelatinous", "waxy", "drawn-on
creases", "pretty poor"). Each was a blind guess plus a 10–15 min bake, because nobody could
touch a parameter while watching the cloth. Chaos puts the solver in the editor.

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
7. `ChaosClothComponent.bSimulateInEditor` is transient and per instance ("Simulate In Editor" in
   Details): switching it on never dirties the level. `bEnableSimulation` and `bSuspendSimulation`
   are Sequencer-keyable.

## State and proof (25 Sep)

- Built: the CA/DF/mesh/material/textures under `/Game/Scenes/Curtain/Chaos`. **Tier: saved
  read-back.** 7/7 assets load, the cloth is linked to its graph and carries the velvet MI, 0 dirty
  (`Saved/CodexSoftGoods/verify_chaos_curtain.json`).
- **Not yet proven:** that Chaos keeps the static-mesh vertex order, i.e. that the heading pin
  lands on the top row. The import order *is* proven. Only a running sim proves the pin.
- **Not yet seen:** any rendered frame. The look, the weight and the frame rate are unverified.
- Not started: the sequencer swap (conductor's call), velvet/sack/hanging-cloth variants,
  peeling wing-edge strips, dust sheets.
- The festoon Geometry Cache and its preview actor stay as they are.
