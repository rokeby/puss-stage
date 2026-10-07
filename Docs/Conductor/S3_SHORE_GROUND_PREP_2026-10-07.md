# S3 shore ground: offline prep (7 Oct 2026)

> **Read §0 first.** Gary's answers (7 Oct, evening) superseded §3's "cast island preserved / pads", §6's open
> decisions, and the §4 runner scope. §1–§2 still stand, with the live-read corrections in §0.

## 0. Update after Gary's answers and the DRY live read (S3SHORE-20261007-181646)

**Gary's decisions (relayed by Directing):**
1. Mud toward the mouth, sand toward the waves.
2. Drift caps of ~128 cm on the sides and ~105 cm at the back.
3. **Re-sculpt the cast area:** the same field as everywhere else, with no beach-v2 preservation and no pads. Objects
   are **not** moved; Gary re-arranges them himself.
4. No drifts at the wave rows. Hide the oak deck and the v2 sand rather than delete them.

**What changed [meas-here]:**
- `s3_shore_field.py` now has `PARAMS.preserve_v2_cast=False` and `use_pads=False`. The old behaviour can still be
  switched on, but only the harness's negative control does so. A new check, `CAST_STILL_V2`, fails if the cast area
  still matches v2.
- Under the old v2 footprint, the new surface now differs from v2 by a mean of 11.9 cm and a maximum of 17.4 cm. The
  fraction of points within 0.5 cm of v2 is 0.000. The new ground is **lower** there, because the v2 dome is gone.
- `PARAMS.wave_notch=True` keeps the surface exactly at floor top under all three rows across the full width. Max |h|
  under the flats = 0.000 cm.
- Drifts and the deepest dip are unchanged:

  | Drift | Max (cm) | Note |
  |---|---|---|
  | Left | 128.2 | |
  | Right | 127.5 | |
  | Back | 105.3 | 1.6 at the door |

  The deepest dip is −8.1 cm.
- Lowest vertical camera clearance is 108.6 cm (B11). This uses the 1 Oct shot poses, so it is **[decl]**.
- **Rebuilt FBX:**
  - same topology: 218,952 vertices, 217,880 quads;
  - bounds (0, −1012, 95)..(6012, 1008, 243.19);
  - sha256 `55cb8078…ec966`, recorded in the manifest.
- Previews were re-rendered, plus a new `cam_EntryHandoff`. Proxies now come from the **live** AABBs.

**Live-read corrections [meas, DRY 18:16 UTC]:**
- The root is still at its landed pose.
- The deck is MOVABLE and parented to the root.
- **All six figures have parent = None.** They are not attached to `S3 Hangar Root`, so they do not rise with the box,
  before or after this change.
- `Clam_Pedastal`: parent None, STATIC, `hidden` = **true**.
- Shore03_M59's foot is at dock z 10.45, down from 12.03. The footprint has been updated from the live reads.
- **No level CineCameraActor exists for S3 Shot B02–B12.** They are `LS_DevScene_03` spawnable templates. The level
  cameras are the Entry/Exit Handoff camera and the Sleight Hangar camera, all at local (−500, 0, 300), rpy 0 [meas].

**Seat report** (`Saved/CodexConductor/S3Shore/s3_shore_seat_report.json`) [meas-here]:
- Each object's **live** base is compared with the new surface under its **live XY AABB**. For a draped figure that
  AABB includes the drape.
- The surface is sampled every 5 cm from the mesh grid.
- Verdict, on the mean surface: **FLOATING** if base − mean > 2 cm; **BURIED** if mean − base > 2 cm; otherwise OK.
- Result: **12 FLOATING, 3 OK, 0 BURIED.**

| Object | Kind | Base z | Surface min / max / mean | Gap vs mean (cm) | Verdict |
|---|---|---|---|---|---|
| Shore01_M56 Clam | figure | 129.58 | 114.53 / 117.22 / 115.83 | +13.75 | **FLOATING** |
| Shore02_F52 Clam | figure | 128.49 | 116.85 / 120.20 / 118.61 | +9.88 | **FLOATING** |
| Shore03_M59 Clam | figure | 130.45 | 115.37 / 119.38 / 117.75 | +12.71 | **FLOATING** |
| Shore04_F55 Clam | figure | 127.34 | 114.54 / 117.00 / 115.55 | +11.79 | **FLOATING** |
| Shore05_M53 Clam | figure | 128.74 | 114.96 / 119.09 / 117.46 | +11.28 | **FLOATING** |
| Shore06_F25 Clam | figure | 128.70 | 114.92 / 117.39 / 116.28 | +12.42 | **FLOATING** |
| Clam_Pedastal | pedestal | 121.38 | 115.75 / 117.07 / 116.42 | +4.96 | **FLOATING** |
| S3 Beach V2 Rock 01 | rock | 121.14 | 115.24 / 117.35 / 116.31 | +4.83 | **FLOATING** |
| S3 Beach V2 Rock 02 | rock | 115.17 | 114.14 / 115.42 / 114.82 | +0.35 | **OK** |
| S3 Beach V2 Rock 03 | rock | 119.14 | 115.39 / 116.80 / 116.09 | +3.06 | **FLOATING** |
| S3 Beach V2 Rock 04 | rock | 123.80 | 114.10 / 115.32 / 114.69 | +9.10 | **FLOATING** |
| S3 Beach V2 Rock 05 | rock | 115.65 | 114.37 / 115.65 / 115.13 | +0.52 | **OK** |
| S3 Beach V2 Seaweed 01 | seaweed | 116.90 | 115.62 / 117.12 / 116.42 | +0.48 | **OK** |
| S3 Beach V2 Seaweed 02 | seaweed | 126.22 | 114.32 / 115.65 / 114.98 | +11.24 | **FLOATING** |
| S3 Beach V2 Seaweed 03 | seaweed | 121.24 | 114.78 / 116.05 / 115.48 | +5.75 | **FLOATING** |

All z values are root-local cm; floor top is 115.
- **[inf]** The figures float by about 10–14 cm because they stood on the v2 dome, which the re-sculpt removes.
- **[inf]** The pedestal float of 5 cm uses its AABB minimum. Its actual base contact shape was not read.
- Rocks were embedded in the v2 sand by design, so their "OK" or "FLOATING" verdicts mean they now sit on top of the
  surface, or above it, rather than in it.

**Harness:** `test_s3_shore_offline.py` passes **19/19** [meas-here].
- **New + control:** v2 cast preservation is absent from the shipped field.
- **New − control:** switching preservation back on **is** detected.
- **Seat-report controls:** a synthetic floating object is flagged FLOATING; a synthetic buried one is flagged BURIED;
  a synthetic seated one is OK.
- The seat report matches the live run: 15 objects, Shore03 foot at 130.454.
- The wave-notch negative control was **re-based** onto `wave_notch=False`. The old control had only failed because
  of the v2 island.
- **Material graph:** the spec has no problems, and removing an edge is detected.
- **Runner:**
  - confirm strings must equal `"<MODE> S3SHORE"`;
  - APPLY and REVERT are refused;
  - there is no save call in the BENCH path.

**Editor side (still not run):**
- `s3_shore_ground_ue.py` now implements:
  - **IMPORT**, gated on: LOD count, Nanite, bounds/mirror, `has_vertex_colors`, no strays, exact census;
  - **BUILD_MAT**, create-only: master graph from `graph_spec()` (Custom nodes, as in the sack material), MI read-back,
    exact-census save, then GC;
  - **BENCH**: originals written to a file first; a transient spawn; deck and v2 sand hidden through `set_visibility`;
    slate-tick stills of B02, B04, B09 and the Entry Handoff from the `LS_DevScene_03` templates (the pattern of
    `s3_beach_marble_stills.py`, which ran on 3 Oct); restore on finish or failure; no save;
  - **BENCH_RESTORE** for out-of-band recovery.
- `s3_shore_ground_run.py` dispatches DRY, IMPORT, BUILD_MAT, BENCH and BENCH_RESTORE, each with its confirm string.
  APPLY, REVERT and VERIFY are refused.
- Two deviations to note:
  - The BENCH actor lives across slate ticks inside one run, rather than "same call". It is held by reference, and
    BENCH_RESTORE is the backstop.
  - Moss uses albedo only. The MW `_nrm` may be RG-packed, since the pack ships `MF_MW_RG2Nrm` [bin+inf].

**UE 5.8 API names used, and what they were checked against.** No `unreal.py` stub exists: `Intermediate/PythonStub`
is absent and none was found under `D:\Unreal Engine\UE_5.8`. Names were checked against the headers (**[decl]**) or
against earlier project runs (**[run]**).

| Name | Proof |
|---|---|
| `mesh_pipeline.build_nanite / import_static_meshes / import_skeletal_meshes / collision` | [decl] `Plugins/Interchange/Runtime/Source/Pipelines/Public/InterchangeGenericMeshPipeline.h:134/73/204/101` |
| `common_meshes_properties.import_lods / recompute_normals / vertex_color_import_option` | [decl] `InterchangeGenericAssetsPipelineSharedSettings.h:95/127/111`. The default is already `IVCIO_Replace`, so it is only read back (the Python enum spelling is [inf]). |
| `material_pipeline.import_materials`, `texture_pipeline.import_textures`, `asset_name`, `import_offset_*`, `InterchangePipelineStackOverride.add_pipeline` | [run] `s3_beach_v2.py:666-699` (4 Oct); [decl] `InterchangeGenericMaterialPipeline.h:85`, `InterchangeGenericTexturePipeline.h:32` |
| `StaticMesh.get_num_lods`, `get_bounding_box`, `nanite_settings.enabled`, `static_materials` | [decl] `Engine/Classes/Engine/StaticMesh.h:2176-2177, 2203-2204, 746, 1096`; `EngineTypes.h:3285` |
| `StaticMeshEditorSubsystem.has_vertex_colors` | [decl] `Editor/StaticMeshEditor/Public/StaticMeshEditorSubsystem.h:468-470` |
| Reading vertex-colour **values** | **Not exposed.** `StaticMeshDescription.h:77-78` has only the C++ accessor, so the calibration bytes stay UNREAD. |
| `EditorActorSubsystem.spawn_actor_from_class(..., transient)` | [decl] `EditorActorSubsystem.h:227-228` |
| `SceneComponent.set_visibility / set_mobility / set_relative_transform`, `Actor.attach_to_actor / destroy_actor`, `PrimitiveComponent.set_material`, `StaticMeshComponent.set_static_mesh` | [decl] `SceneComponent.h:916, 1295, 459`; `Actor.h:2041, 1933`; `PrimitiveComponent.h:1599`; `StaticMeshComponent.h:449` |
| `Material.used_with_nanite` | [decl] `Engine/Public/Materials/Material.h:863` |
| `MaterialExpressionVertexColor` | [decl] class exists (`MaterialExpressionVertexColor.h:12`). The name of its **output pin "" = RGB is [inf]**, because the .cpp is not in the install; `recompile_material` errors would expose a wrong name. |
| `MaterialEditingLibrary.create_material_expression / connect_material_expressions / connect_material_property / recompile_material / get_material_expression_input_names / set_material_instance_parent / update_material_instance / get_material_instance_scalar_parameter_value`, `MaterialExpressionCustom` + `CustomInput` + `CMOT_FLOAT1/2/3`, `MaterialExpressionTextureCoordinate`, `TextureSampleParameter2D` pins `UVs/RGB/R` | [run] `s3_sack_install.py` BUILD_MAT (6 Oct, saved); [decl] `MaterialEditingLibrary.h:232, 325, 408`; `MaterialExpressionCustom.h:19` |
| `LevelSequence.get_spawnables`, `binding.get_object_template`, `EditorLevelLibrary.get/set_level_viewport_camera_info`, `register_slate_post_tick_callback`, `HighResShot` | [run] `s3_beach_marble_stills.py` (3 Oct). `EditorLevelLibrary` is the deprecated wrapper; `UnrealEditorSubsystem.h:32` is the successor. |
| `GameplayStatics.get_all_actors_of_class`, `get_actor_bounds`, `get_attach_parent_actor`, `get_cine_camera_component` | [run] DRY S3SHORE-20261007-181646 |
| Post-destroy listing: whether `get_all_actors_of_class` still returns a just-destroyed actor | [inf] UNVERIFIED. If it does, `_restore_from_originals` could false-fail `BENCH_ACTOR_SURVIVED`. |

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
