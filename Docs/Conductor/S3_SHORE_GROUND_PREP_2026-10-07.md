# S3 shore ground: offline prep (7 Oct 2026)

Brief (Gary, relayed by Directing): replace the flat oak-herringbone deck in Scene 3 with a sculpted
shore-ground **mesh** (not a landscape, which was retired 30 Sep: `DECISIONS_FOR_GARY_2026-09-30.md:374-389`, `:734-750`).
Wet sand toward the wave flats, darker mud and moss behind. The whole floor covered. Drifts banking 0.5–1.5 m up the
marble walls. Dense enough to vertex-paint by hand. Attached to `S3 Hangar Root`.

**Status: offline only.** No Unreal MCP call, no editor launch, no git commit. Blender ran **headless**
(`blender.exe -b --factory-startup`). The Blender MCP addon was not connected, and Gary's open Blender session was not
touched. One observation for the conductor: `tasklist` showed an `UnrealEditor.exe` process (PID 39420, ~12 GB) while
this work ran, although the brief said the editor was closed. Nothing here touched it.

Tiers on every claim: **[decl]** = stated by a record, script or config we can read. **[bin]** = from .uasset strings.
**[meas]** = an earlier live probe read it back; this session did not re-read it, and the level has changed since.
**[meas-here]** = run in this session (offline tools, Blender). **[inf]** = inferred, with the reason given.

---

## 1. S3 interior in `S3 Hangar Root`-local cm (LANDED pose)

The footprint is in `Saved/CodexConductor/S3Shore/s3_shore_footprint.json`, with a source per field. The generator
reads only that file.

| Item | Root-local value | Tier | Source |
|---|---|---|---|
| Root landed world | (11421.97, 160000, -120), rot 0, scale 1 | [meas] 6 Oct 06:10 | `Saved/CodexFlatV3/handprints/hp_probe_walls_result.json` `root`; same in `s3_wave_reattach_record.json` `root_world` (5 Oct) |
| dock frame ↔ local | dock = local + (500, 0, −120) | [inf] arithmetic | from the dock origin in `s3_beach_v2.py:34` and the root above |
| Deck (the oak floor) | x 0..6000, y ±1000, z 95..**115** (top) | [meas] | probe `context['S3 Hangar Deck']`; material `M_Oak_Hrrngbn_01_Mat_Inst_Dup` |
| Floor top | local z **115** (world −5) | [meas] | deck world_aabb max z |
| Side marble inner faces | y = −999 / +999 (1 cm liners in front of the black walls at ±1000..1050) | [meas] | probe `S3 Marble Inner Wall Left/Right` |
| Far wall | x 6000..6050; **exit door** gap at y ±150, up to z 570 | [meas] | `S3 Hangar Far Wall Left/Right of Exit`, `Above Exit` |
| Back surface | `S3 Backdrop` plane at x 5997, y ±1000, z 115..3115 | [meas] | probe; `s3_backwall_marble_record.json` target |
| Is the back wall marble? | **UNCLEAR.** The marble liners run on the sides only. The back is `S3 Backdrop`, whose material was not read. | — | live read needed |
| Wave flats | Row1 x 3649..3735, Row2 4449..4535, Row3 5249..5332. Bases at z 115. They slide in Y (sweep 100). | [meas] + [decl] | probe decal receivers; `s3_wave_reattach_record.json`; `placement_S03.json` exclusion rule |
| Hand prints | lowest print extent **160.0 cm** above floor top (449 decals) | [decl] + [meas-here] | `DerivedAssets/FlatV3/HandPrints/placement_S03.json` `distribution.band_cm [160,400]`; computed min over all decals = 160.009 |
| Six Shore figures | local xy Shore01 (3149,−213), 02 (2699,109), 03 (2891,301), 04 (3184,262), 05 (2911,−244), 06 (3260,0); feet at h 12.3–17.0 cm above floor top | [decl] | `s3_beach_place_record.json` `figures[]` (APPLY 4 Oct, run 124209). Not re-read since. |
| Pedestal `Clam_Pedastal` | local (3000, −0.7), 61×63 cm, base at h 6.4. **Attach parent null** on 3 Oct. | [meas] 3 Oct | `s3_beach_marble_probe_response_20261003.json` |
| v2 rocks / seaweed | 8 props at local x 3200..3490 | [decl] | `s3_beach_v2.py:80-89` `PROP_SPECS` |
| v2 sand island | `sand_height()` dome centred at local (3050, 0), rx 500, ry 700 | [decl] | `s3_beach_v2.py:43-55, 168-182` |
| S3 shot cameras B02–B12 | local x 2100–3000, **110–175 cm** above floor | [decl], **stale risk** | `s3_shotlist_record.json` (1 Oct 22:57). S3 has been reworked since (Klara sequences, 7 Oct). |
| Entry/exit handoff cameras | appear only as ~2020 cm AABBs centred near local (−500, 0, 300) | [inf] | probe AABBs. **UNCLEAR → live read.** |

Two checks agreed [meas-here]: `s3_beach_v2.sand_height()` at each recorded figure xy gives exactly the record's
`surface_z_cm`. For example, Shore01 = 9.576 in both.

## 2. Material research

**`MTL_MWL_GeneralVertex_MASTER`** (strings only):
- **[bin]** It blends two texture layers (`MW_TextureBaseColor`/`2`, `MW_TextureNormal`/`2`, `MW_TextureMask`/`2`)
  through `MaterialExpressionVertexColor`. The channel is chosen by a **static component-mask parameter**,
  `MW_VertexMaskChannel` (`MaterialExpressionStaticComponentMaskParameter`, `MF_MW_RGBASplit`).
  - **UNCLEAR:** which channel is the default. The default is stored as binary bools, not strings. An MI can set it
    explicitly anyway.
- **[bin]** A third "top layer" (`MW_TextureTopBaseColor/Mask/Normal`, `MW_TopLayerIsMoss`, `MF_MW_TopLayer`) and
  moss (`MF_MW_Moss`: `PixelNormalWS`, `MW_UseMossMask`, `MW_InvertMossMask`) are driven by the **normal and a mask**.
  - **[inf]** These look slope/up-facing driven rather than vertex driven.
- **[bin]** Wetness is `MF_MW_Wetness` with `MW_WetnessLineWorldPosition`, `MW_WetnessLineContrast` and
  `MW_WetnessLineVariationSize`. The master also references `MF_MW_WorldZPositionMask` and the strings `WorldZPositionRAW`
  and `OceanLine`.
  - **[inf, strong]** The wet line is a **world-Z height line**, not vertex colour. That suits a static shore, not a box
    that rises through Z, and it cannot wet the dips.
- **[bin]** There is **no puddle parameter.** `MF_MW_Puddle` exists in `Func/` but the master does not reference it.
- **[bin]** The layers expect MW-packed `_msk` textures. The pack has Dirt, Moss, Forest, Rock and Stones, but **no
  sand**.
- **[bin]** Only `Trees/MTL_MWL_TreeBark` instances this master.

**Textures on disk [meas-here, `ls`]:**
- `Content/Megascans_4K/Surface/02_Soil_Sand_pjuuz0` and `12_Soil_Mud_pkbc30` are **empty folders**.
- The 2K sets are complete: `EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0` and `09_Soil_Mud_pkbc30`, each
  with Albedo, Normal, Roughness and Displacement. Their MIs are children of `Megascans_2K/Master_Materials/Standard_MasterMaterial` [bin].
- The sand MI was re-saved on 4 Oct by beach v2 (`s3_beach_place_record.json` `finished_by`).

**Proposal: a small new master, `M_S3_ShoreGround` + `MI_S3_ShoreGround`**
(spec in `S3Shore/s3_shore_ground_ue.py` `graph_spec()`):
- Vertex **R = mud** (Megascans sand to Megascans mud, with a contrast control so hand-painted edges stay crisp).
- Vertex **G = wetness**: darkens albedo and lowers roughness. Above `PuddleFromG` it flattens the normal, giving a
  standing-water look.
- Vertex **B = moss**, using the MW `TEX_MWL_GroundMoss_col/nrm`.
- Vertex **A** is reserved.
- UV0 is in metres, so tiling rides with the box. Nanite on; vertex colour works with Nanite.

The alternative is an MI of the MW master. It would need the sand textures packed into the MW `_msk` layout, and its
wetness would follow world Z rather than paint. It is not recommended.

## 3. The mesh (first pass)

Everything regenerates from `s3_shore_footprint.json` and `PARAMS` in `s3_shore_field.py`.

`"C:/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python Saved/CodexConductor/S3Shore/s3_shore_blender_build.py`
(about 10 s with previews).

**Shape [meas-here: build output + manifest]:**
- A 7.5 cm grid over local x 0..6012 and y −1012..+1008, plus a skirt down to z 95 on all four edges.
- 218,952 vertices and 217,880 quads (about 436k triangles). The FBX is 12.3 MB.
- Local bounds: (0, −1012, 95) .. (6012, 1008, 243.2).
- The asymmetric Y extent is deliberate, so the import bounds expose a Y mirror. The edges sit inside the
  side walls and the far wall.
- The actor attaches at **relative identity**: the mesh is authored in root-local space.

**Design:**
- **Mud plateau** toward the mouth: about 5 cm higher, with lumps, nine moss hummocks and five shallow pools (6–11 cm).
- **Sand** from x ≈ 2900. **Wet flats with ripples** (1.2 cm, 42 cm wavelength) from x ≈ 3300.
- **Runnels** between the wave rows.
- **Drifts:**
  - Side drifts go up to 140 cm (smaller in the mud zone). They are exponential banks, scalloped by noise, and taper
    to nothing at the mouth.
  - Back drifts go up to 130 cm, with a door gap at |y| < 180 that is full height by |y| = 380.
- **Cast island:** inside the beach-v2 footprint the surface **reproduces `sand_height()` exactly**. Every
  object seated by beach v2 therefore stays seated with no re-seat:
  - Figure and pedestal pads are flat at their seated height.
  - Rock and seaweed pads follow v2, so their embed fractions are unchanged.
- **Wave notches:** the surface is exactly at floor top under all three rows, across the full width, because the flats slide.

**Checks (`s3_shore_field.checks`, run at build time; build refuses on any failure) [meas-here]:**
- **Pads:** max deviation 0.10 cm, on Shore01, whose blend overlaps Rock 03.
- **Pedestal:** embedded 8.6 cm, the same as it is in v2 sand today.
- **Wave bases:** max |h| under the flats = 0.000 cm.
- **Walls:**

  | Wall | Max (cm) | Mean (cm) |
  |---|---|---|
  | Left | 128.2 | 71.5 |
  | Right | 127.5 | 71.8 |
  | Back | 105.3 | — |

  The back is 1.6 cm at the door. Every maximum is below the 160 cm print line minus a 10 cm margin. Drifts never
  reach the prints, but they can reach the lower part of the decal band region.
- **Cameras:** minimum vertical clearance 98.6 cm (B11). The minimum 3D distance within 150 cm is 97.4 cm.
  - The old 150 cm 3D prop rule from `s3_beach_plan.json` is **not** applied to the ground. A camera at 110 cm over
    the floor cannot clear 150 cm to any floor. The v2 tool answered this by cutting holes in the sand under the low
    cameras (`s3_beach_v2.py:185-212`). **[inf]** the new floor has no holes.
- **Deepest dip:** −8.1 cm, above the deck underside at −20.

**Harness:** `S3Shore/test_s3_shore_offline.py` passes **10/10** [meas-here].
- The shipped parameters pass.
- Five negative controls each fail as intended: drift over prints, door blocked, wave base buried, pad removed,
  camera low.
- The manifest checks pass: Y asymmetry, footprint hash, FBX hash, no build failures.

**FBX round trip [meas-here]:**
- Re-imported into a fresh Blender: same vertex and face counts, colour layer `Col`, UV layers `UVMap` (metres) and
  `UVNorm` (0..1), one slot `MI_S3_ShoreGround`.
- 99% of faces point up. Blender-space Y comes back as −10.08..+10.12 m, which is the expected mirror of UE.
- The FBX hash changes on every build (the FBX carries a timestamp). The manifest records the hash of the current file.

**Vertex colour, first pass:**
- R = mud: front zone, not on drift tops, not on the cast island.
- G = wet: wave zone, pools, runnels, notches; dry on drift tops.
- B = moss: mud zone patches, hummocks and wall bases.
- A = 1.
- Exported LINEAR. **UNCLEAR:** whether Interchange sRGB-encodes the bytes. The four hidden skirt-corner vertices carry
  calibration colours (0.5, 0.25, 0.75, 1) and others. The IMPORT gate reads them.

**Previews** (EEVEE, preview-only grain and proxies, **not** the UE look) are in `DerivedAssets/S3Shore/previews/`:
- `overview_high_three_quarter`
- `overview_from_mouth`
- `mud_front_low` (moss, mud and a pool)
- `back_wall_drifts_door` (back drifts and the door gap)
- `drift_left_wall`
- `cam_B02`, `cam_B04`, `cam_B09` (S3 shot poses from the 1 Oct record; the filmback of 23.76 mm is assumed [inf])
- `plan_vertex_colour_RGB` (top-down; left wall at the image top, mouth at the left)

## 4. Editor plan (DRY → IMPORT → BUILD_MAT → BENCH → APPLY → VERIFY)

Draft in `S3Shore/s3_shore_ground_ue.py` (**not run**). DRY, IMPORT and BENCH are written. APPLY, REVERT and VERIFY
are specified in the file footer and are left unwritten until the DRY numbers exist.

1. **DRY** (read-only) writes `s3_shore_live_reads.json`. `footprint_from_live_reads()` then updates the footprint
   offline, logging every change. Re-run the build and the harness after that.
2. **IMPORT:**
   - One asset, `/Game/InfinityStage/Dev/Generated/S3Shore/SM_S3_ShoreGround`, through an Interchange override:
     no materials or textures, Nanite on, vertex colours REPLACE, no LODs, no LodGroup.
   - Gates: 1 LOD, Nanite enabled, bounds equal to the manifest within 0.5 cm (mirror gate), a folder diff showing no
     strays, the census equal to the mesh package only, then save and check the census is empty.
   - Memory constraints: `ue58-fbx-import-traps` (set and read back every option); `ue58-bulk-import-oom-crash` (one
     asset per call).
3. **BUILD_MAT:** create-only master + MI in a separate call, with GC between calls. The textures already exist; nothing
   is imported.
4. **BENCH** (no save path):
   - Originals go to `s3_shore_bench_originals_<run>.json` and the path is logged **before** anything changes.
   - Spawn the transient `ZZ_S3ShoreGroundBench` attached to the root at identity. Hide the deck and the v2 sand with
     `set_visibility`.
   - S3 shot stills: wire in the `s3_beach_marble_stills.py` capture.
   - In `finally`: destroy by reference, restore, verify against the file.
   - It records whether these calls dirty the map (**[inf] unknown**). If they do, restart the editor with
     "Don't Save" before APPLY.
5. **APPLY:**
   - Backup `Backups/PreS3ShoreGround-<run>` (umap, sha-checked) plus the D: snapshot.
   - Spawn `S3 Shore Ground` (tag `RigAtmos.S3ShoreGround`) attached KEEP_RELATIVE at identity, with mobility matched
     to the deck's measured value.
   - Hide the deck and the v2 sand (`modify()`, visible False, hidden_in_game True). Collision is left alone.
   - Save census-exact: the map plus the three new assets.
   - Read back from the saved state:
     - parent and relative identity;
     - world AABB inside the landed box, composed with the **live** root (memory `puss-level-saved-landed-frame-trap`);
     - the success marker only after every assert.
6. **VERIFY:** run `SavedMasterMatchesShow` and `SceneCutBindingsResolve` after a run-id queue marker. Take PIE stills
   from the S3 entry, B02 and B04 cameras. Confirm the box rise carries the ground: scrub through the Hangar Fold and
   the S3 hangar hold/float hold, which exists since 7 Oct.
7. **REVERT:** destroy the actor by its recorded path and restore the deck and v2 flags. The assets stay.

## 5. Live reads needed before IMPORT/APPLY (all in DRY)

1. Root landed transform: is it still (11421.97, 160000, −120)?
2. Deck mobility and collision profile, and whether anything uses deck collision.
3. Current transforms of the six figures, the pedestal, the v2 rocks and seaweed, plus their **attach parents**.
   - The pedestal was unattached on 3 Oct. If the cast is not on the root, it does not rise with the box, before or
     after this change.
4. The v2 sand floor actor: is it still present and visible?
5. **Every current S3 camera:**
   - level shot cameras;
   - Sequencer shot templates in `LS_DevScene_03` and Klara's sub-sequences, read through the root-component relative
     transform (memory `ue58-fbx-import-traps`);
   - the S1→S3 entry/exit handoff cameras, poses and heights.
6. The `S3 Backdrop` material: is the back wall "marble" in Gary's sense?
7. The door: is the exit door open during S3? The gap is kept either way.
8. Interchange property names for Nanite and vertex colours on `InterchangeGenericAssetsPipeline` (marked UNVERIFIED in
   `_pipeline()`), and the vertex-instance-colour getter on `StaticMeshDescription`.

## 6. Decisions for Gary (look) / conductor (scope)

- **Reading of "behind":** I placed mud and moss toward the **mouth** (away from the waves), not behind the waves. One
  parameter flips this (`mud_to_sand_x`).
- **Drift height:** the maximum is 128 cm against his 50–150 range, because the hand prints start at 160 cm. Going
  higher means `drift_cap_cm` above 150, and the drift would cover prints.
- **Wave rows:** the drifts are **notched** to floor level at each wave row, because the flats slide. The alternative
  is to let drifts bury the flat ends.
- **Deck:** hide it (reversible), rather than delete it.
- **Cast island:** keep beach v2 exactly (no re-seat) or re-sculpt it. Re-sculpting means re-seating the figures and
  rocks, which is a separate write.
- **Material:** a new small master (recommended) or the MW master (see §2).

## 7. Files (all new)

- `Saved/CodexConductor/S3Shore/s3_shore_footprint.json`: inputs, with a source and tier per field
- `Saved/CodexConductor/S3Shore/s3_shore_field.py`: height and vertex-colour field, plus checks (numpy; offline)
- `Saved/CodexConductor/S3Shore/s3_shore_blender_build.py`: headless build, FBX export, previews, manifest
- `Saved/CodexConductor/S3Shore/test_s3_shore_offline.py` (+ `_report.json`): harness, 10/10
- `Saved/CodexConductor/S3Shore/s3_shore_ground_ue.py`: editor-side draft (NOT RUN)
- `DerivedAssets/S3Shore/SM_S3_ShoreGround.fbx`, `.blend`, `_manifest.json`, `previews/*.png`
