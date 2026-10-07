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

## 8. BENCH_PIE_APPLY / BENCH_PIE_RESTORE: the combined PIE still with marble variant C (7 Oct, offline, NOT RUN)

Gary approved one combined PIE bench of the new ground plus the s3mg marble variant C, with no level save; he does a
Don't-Save restart afterwards. The editor-world BENCH (`run_bench`) can never be in a PIE still, because PIE copies the
editor world at PIE start. Two PIE-only modes were added: `s3_shore_ground_ue.py`, section `BEGIN_BENCH_PIE` …
`END_BENCH_PIE`, wired into `s3_shore_ground_run.py`. Nothing was run in Unreal, and no MCP call was made.

**The spawn route the brief asked for does not exist [meas].** `GameplayStatics.begin_deferred_actor_spawn_from_class`
raised `AttributeError` twice in this UE 5.8 editor:
- `Saved/CodexFlatV3/swapkit/stills/before/FV3STB-20261003-02/st_pie_first_check_runtime.json` (3 Oct);
- `Saved/CodexConductor/LookBench/20261005-044136/look_bench_result.json` (5 Oct).

The header marks it `BlueprintInternalUseOnly` (`GameplayStatics.h:66-67`, and `:70-71` for `FinishSpawningActor`)
**[decl]**. That UE Python skips such functions is **[inf]**, but it matches both measured errors.
`AddComponentByClass` is `ScriptNoExport` (`Actor.h:1974`) **[decl]**.

**Consequence:** `s3mg_bench.py` `stage_apply` (`spawn_pie`, `:285-292`) will fail at the first grease-decal spawn of
variant C **[inf, from the two measured errors]**. It restores itself and logs `S3MG_FAILED`, so its `stills` stage
refuses. The marble stream has to fix this before the combined still can be taken. This stream did not edit s3mg
files.

**What the shore bench does instead: it borrows the deck's PIE copy.** This follows the `gloss4_glint_pie_spawn.py`
and `hp_test_pie_still.py` precedent. `S3 Hangar Deck` is a `StaticMeshActor`, MOVABLE, attached to `S3 Hangar Root`
(`hp_probe_walls_result.json`; DRY 181646) **[meas]**.

On its **PIE copy only**, the bench changes:
- the mesh, to `SM_S3_ShoreGround`;
- every slot, to `MI_S3_ShoreGround`;
- the relative transform, to identity, which was relative (3000, 0, 105) at scale (60, 20, 0.2) per
  `s3_pit_deck_record.json`;
- the tags: `ZZ_S3ShoreGroundBench` is added.

The v2 sand's PIE copy is hidden with `set_actor_hidden_in_game(True)` and `set_visibility(False)` per primitive
component.

The deck is therefore *replaced* rather than hidden. Its copy is the ground and rides the root at relative identity,
exactly as a spawned child would. Nothing is spawned or destroyed, and the editor world is never written.

**Apply gates.** Every refusal raises before the originals file exists, so nothing has changed. The gates are:
- PIE world present (`NO_PIE_WORLD`) and different from the editor world;
- `SM/M/MI_S3_ShoreGround` exist with the right classes;
- master PS instructions > 0 (`PENDING_COMPILE`);
- no actor already carries our tag;
- run id not used before;
- exactly one root, deck and v2 sand by label;
- deck is a `StaticMeshActor` on the root, MOVABLE, with no attached children.

**Apply steps:**
1. The originals file `S3Shore/s3_shore_pie_bench_originals_<run>.json` is written, read back and logged
   (`S3SHORE_BENCH_PIE_ORIGINALS`) **before** any change. It holds: the PIE world path and real time; the deck's mesh,
   per-slot materials, relative transform, tags, hidden and visible flags; the v2 per-component visibility; the census.
2. The changes are made, then every one is read back: mesh, MI on every slot, identity, tag, deck world location ==
   root ±0.5 cm, v2 hidden.
3. **No new dirty editor package** is allowed.

Any exception auto-restores from the file and is followed by `S3SHORE_FAILED`.

**Restore** (`bench_run` = the apply's run):
1. If PIE is gone, or this is a new PIE session (path differs, or real time is lower than at apply), it logs `…_NOOP`.
2. Otherwise it first records a **still check**: was our state still held when the s3mg still was taken? It looks at
   mesh, MI, identity, deck on root, ground visible, v2 hidden, and records whether the root is landed.
3. It then sets every value back from the originals file and verifies each one.
4. Our tag must be gone. Other tags (e.g. `ZZ_S3MG`) are untouched.
5. A second call logs `…_NOOP|reason=already_restored`.
6. If the still check had failed, the restore still completes, then raises `RESTORED_BUT_STILL_INVALID` (FAILED): the
   picture is not evidence.

**Markers:**
- `S3SHORE_BENCH_PIE_APPLY_OK|run=`
- `S3SHORE_BENCH_PIE_RESTORE_OK|run=|bench_run=|still=STILL_STATE_HELD|root_landed=`
- `S3SHORE_BENCH_PIE_RESTORE_NOOP|run=|reason=`
- `S3SHORE_FAILED|run=|mode=|…`

The OK line is printed only after the function returned.

**Harness:** `test_s3_shore_offline.py` passes **41/41** [meas-here]: the earlier 19 plus 22 new. The new BENCH_PIE
cases run the real functions against a mock `unreal`:
- **+ apply:** the full read-back; the originals file existed before every mutation; no spawn, destroy or end-PIE; the
  `ZZ_S3MG` actor is untouched.
- **+ restore:** exact originals; only our tag is removed; it is idempotent (NOOP); PIE gone gives NOOP.
- **− refusals:** no PIE; missing assets; a stale tag; a pending compile; a wrong confirm. None of them mutates anything.
- **− injected failure:** a dirtied map mid-apply triggers an auto-restore and is FAILED.
- **− lost state before the still:** restored, then FAILED.
- **Runner:** a refusal logs `S3SHORE_FAILED` and no `_OK`; the order is OK → OK → NOOP; APPLY is still refused.
- **Save detection:**
  - a spy on every fake library saw no `save*` attribute (− control: the spy sees one);
  - a static scan of the section finds no save, PIE start/end, destroy, editor spawn or reload call (− control: a
    planted call is flagged).

`S3MarbleGrime/test_s3mg_offline.py` is still at 46/46 [meas-here].

**API names: proof per call.**

| Call | Proof |
|---|---|
| `UnrealEditorSubsystem.get_game_world / get_editor_world` | `UnrealEditorSubsystem.h:49-52` **[decl]** |
| `GameplayStatics.get_all_actors_of_class` | `GameplayStatics.h:98` **[decl]**; DRY **[run]** |
| `GameplayStatics.get_real_time_seconds` | `GameplayStatics.h:1246-1247` **[decl]** |
| `Actor.set_actor_hidden_in_game` | `Actor.h:1921-1922` **[decl]**; `beam_texture_bench.py` **[run]** |
| `hidden` (bHidden) | `Actor.h:364-365` **[decl]**; DRY **[run]** |
| `tags` | `Actor.h:1343-1344` **[decl]**, BlueprintReadWrite. Setting it on a *PIE* actor is **[inf]**. |
| `get_attach_parent_actor` | `Actor.h:3547-3548` **[decl]** |
| `get_components_by_class` | `Actor.h:3805-3807` (ScriptName) **[decl]** |
| `StaticMeshActor.static_mesh_component` | `StaticMeshActor.h:25-26` **[decl]** |
| `StaticMeshComponent.set_static_mesh` | `StaticMeshComponent.h:449-450` **[decl]**. Allowed on a registered component only when not Static (`SceneComponent.h:1363-1366`), hence the MOVABLE gate. |
| `static_mesh` property | `:132-133` **[decl]** |
| `set_material / get_material / get_num_materials` | `PrimitiveComponent.h:1599-1600 / 1565-1566 / 2325-2326` **[decl]** |
| `set_relative_transform` (out-param HitResult dropped) / `get_relative_transform` | `SceneComponent.h:459-460 / 464-465` **[decl]** |
| `set_visibility`, `is_visible` | `SceneComponent.h:916-917, 852-853` **[decl]** |
| `hidden_in_game`, `mobility` | `SceneComponent.h:225-226, 302-303` **[decl]** |
| `MaterialEditingLibrary.get_statistics` | `MaterialEditingLibrary.h:609-610` **[decl]**; `s3_sack_install.py:1885` **[run]** |
| `Transform(location=, rotation=, scale=)`, `.rotation.rotator()`, `.scale3d` | prior Saved/ scripts **[run]** |
| Actor labels readable on PIE copies | look_bench CAPTURE **[run]** |

**Inferred, not proven:**
- **[inf]** `set_static_mesh` returns False for an unchanged mesh. The code only calls it on a change and asserts the
  read-back.
- **[inf]** The new mesh has the same slot count as the cube, so the per-slot restore compares equal-length lists.
  `get_num_materials` on a mismatched override list is unverified.
- **[inf]** No Show or hangar system rewrites the deck's mesh, materials or transform, or re-shows the v2 sand, between
  apply and the still. If one does, the restore's still check reports `STILL_INVALID`.
- **[inf]** The new mesh was imported with `collision=False`, so anything in PIE that rested physically on the deck's
  cube collision would fall through. Nothing such is known in S3.
- **[inf]** Outside S3 the deck copy may be hidden by the hangar system at apply time. Apply sets it visible, and
  restore puts back the recorded value.

**Not touched:** `s3_shore_ground_args.json`. The conductor writes it per call. No new request JSON was needed:
`Saved/CodexConductor/s3_shore_ground_request.json` already runs the runner, and the args select the mode.

## 9. Dunes v2: wind-shaped, differentiated heaps; A/B/C heights; sand over the soil; millstone seat; standing stones (7 Oct evening, offline)

This folds in Gary's verdict on the §3 banks ("look pretty bad"), his follow-ups (separate heaps against the walls, sand
flowing over the soil, less regular ripples) and the conductor's two render reviews (terracing; pits on dune flanks).
**No Unreal, no MCP, no git.** Blender ran headless, one process at a time. The pre-change sources, FBX, manifest and
previews are snapshotted in `Backups/PreS3ShoreDunes-20261007-1558/`.

Tiers: **[meas-here]** = computed or rendered in this session; **[decl]** = read from a file or code (cited);
**[inf]** = inferred, reason given.

### 9.1 What the field does now (`s3_shore_field.py`)
1. **Supply** [decl, code]:
   - A broken low bank. It exists only where an along-wall noise is high, so saddles show the bare wall base.
   - A *chain* of separate heaps along each side wall and the back wall:
     - spacing 4.8–9 m; height 30–100 %; reach 2.2–4.8 m;
     - 30 % are tongues reaching a further 2.5–4.8 m toward the centre;
     - crests stand off the wall by up to 1.4 m and are sheared along it, so crest lines are broken and offset;
     - corners are boosted.
   - One seeded Generator, one draw per statement.
2. **Wind** [decl, code `wind_transport`]: deterministic scour-and-carry, with no random numbers.
   - The wind blows toward the mouth, turned 16° toward the left wall.
   - Stoss slopes steeper than 13° are scoured. The sand is carried downwind to the first 15° lee shadow.
   - 90 steps on a 15 cm grid. After each step, an angle-of-repose talus (30.5 ± 1.5°, jittered so slip faces scallop).
3. **Fine pass (7.5 cm mesh grid)**, in order:
   1. The surface is blurred where sand is thick. This fills bed pools under heaps and removes the 15 cm facet stripes.
   2. Wind-blown **sand sheets, tongues and fans** spread downwind over the soil (`sand_sheet`).
   3. Talus at 32° pairwise, converged to 0.1 cm.
   4. **Natural ripples** (§9.1 item 4), then a short talus.
   5. The hard ceiling: wave notches flush, door corridor, camera cones.
   6. The **millstone seat**.
   7. A mass-conserving triangle relaxation. It guarantees that no triangle, on either diagonal split, exceeds 34.5°.
      On the shipped field it moved 0.0012 m³ in 9 iterations [meas-here]. The earlier corner-lowering clamp removed
      7.8 m³, and that clamp *was* the terracing.
4. **Ripples** (`wind_ripples`, mode `natural`):
   - Spacing varies over the floor from 36 to 80 cm, shorter near heaps. It is integrated along the wind, so the local
     spacing is exact.
   - Crests bend around the heaps and are warped. Phase noise makes Y-junctions and terminations. Amplitude is patchy.
   - Height is capped so a ripple's lee face stays under 28°. Ripples fade on slopes of 8–16°, in wet sand and on soil.
   - Measured crest-to-trough on the 328 m² that carries ripples: p50 2.0 cm, p90 4.5 cm, p99 6.6 cm [meas-here].
   - **Gary's "6–15 cm" ripple spacing cannot exist in a 7.5 cm mesh (Nyquist limit 15 cm).** That scale belongs to the
     material normal map (the conductor briefs that separately). Heights of 5–10 cm on a 36–80 cm spacing would need lee
     faces steeper than the angle of repose [inf, geometry].
5. **Vertex colour.** The channels are unchanged: R mud, G wet, B moss, A = 1.
   - Soil shows only where the sand sheet does not cover it.
   - Crests are dry and pale (G → 0). Hollows are damp (G 0.12–0.45, below the 0.85 puddle threshold).
   - Wet near the waves; moss on soil and on dune toes.

### 9.2 Height sets [meas-here]
The hand-print stream reads `Saved/CodexConductor/S3Shore/s3_shore_height_sets.json`.

Heights are in cm above floor top, measured at the marble faces (y = ±999) and the backdrop (x = 5997). The minimum print
line is the wall maximum plus 20 cm, rounded up to the next 5 cm.

| Set | Supply | Left max | Right max | Back max | Wall max | Wall mean L/R/B | **Min print line** | Lowest camera clearance |
|---|---|---|---|---|---|---|---|---|
| A (~180) | 194 | 193.1 | 163.9 | 182.6 | 193.1 | 56/54/63 | **215** | 100.9 (B11) |
| B (~240) | 265 | 226.3 | 212.8 | 243.4 | 243.4 | 71/66/81 | **265** | 100.4 (B11) |
| C (~300) | 350 | 288.1 | 264.1 | 307.0 | 307.0 | 85/79/104 | **330** | 100.2 (B11) |

The JSON also has a per-metre wall profile (the maximum for each metre along each wall), in case the prints should follow
the dune line. The current prints start at 160 cm, so every set covers some of them
[meas-here, `current_prints_would_be_covered`].

**Recommendation: B** [inf, from the close previews and the frame geometry].
- B roughly doubles the old bank (243 cm against 128 cm), with distinct heaps and saddles.
- C reads as the most claustrophobic. But its 330 cm print line sits above the top edge of the main S3 frame at the
  right wall: with pitch −5.5° and a vertical FOV of about 21.6°, the top ray reaches about 278 cm above floor at
  1750 cm. The prints would leave the main shot.
- B's 265 cm line keeps a strip of prints in frame.
- If Gary prefers the enclosure to the prints in that shot, C is one parameter (`PARAMS["height_set"] = "C"`) and a
  rebuild.

### 9.3 Built FBX (set B) [meas-here]
- **File:** `DerivedAssets/S3Shore/SM_S3_ShoreGround.fbx`, 11,616,940 bytes, sha256 `eec3648b…809071`.
- **Mesh:** 218,952 vertices and 217,880 quads.
- **UE local bounds:** (0, −1012, 95) .. (6012, 1008, 362.35). The Y asymmetry and the mirror gate are kept.
- **Manifest:** calibration vertices as before. `_manifest.json` schema 2 adds the height set, the grid sha, the
  slope-relaxation stats and the millstone seat.
- **Field checks:** none failed.
- **Byte-identical rebuilds:** two consecutive builds wrote the same FBX sha (`SM_S3_ShoreGround_determinism_log.json`).
  This needs two things:
  - `PYTHONHASHSEED=0` plus `--python-use-system-env`. The FBX exporter derives UUIDs from Python `hash(str)`, which
    Blender randomises per process [decl, `io_scene_fbx/fbx_utils.py:823`].
  - The FBX header clock pinned (`export_fbx_bin.py:3146`).

  The build refuses to export without the hash seed.
- **Blender vs harness heights:** Blender's numpy 1.26.4 and the harness's numpy agree to within 4e-13 cm. The sha differs
  only through float noise [meas-here, `SM_S3_ShoreGround_grid_h.npy` against the harness].
- **Constraints:**
  - Wave notches: max |h| under all three flats is 0.000 cm.
  - Door gap: 2.0 cm at the back wall for |y| < 150.
  - Deepest dip: −3.6 cm.
  - Camera vertical clearance ≥ 100.4 cm (B11). This uses the 1 Oct shot poses, so it is **[decl], stale risk** as
    before.
- **Realism** [meas-here]:

  | Metric | Value |
  |---|---|
  | Max triangle slope | 34.5° |
  | Slip faces | 138 m², p50/p95 30.4/32.1° |
  | Median slope, downwind-facing vs upwind-facing dune faces | 29.0° vs 17.2° (65 % of steep faces face downwind) |
  | Terracing residual | 2.64° rms |
  | Ripple spectral peak share | 0.18 (a single sinusoid gives 0.68) |
  | Pool dips on dunes or slopes | 0 m² |

- **Coverage** [meas-here]:
  - 91.1 % of the floor inside the walls is painted sand (R < 0.5); 8.9 % is soil.
  - In the mud zone (x < 2100), 25.3 % soil remains: patches, hollows, the wind-aligned strip and the mouth strip.

### 9.4 Millstone seat [decl input; meas-here result]
The input came from Gary via Directing.
- **Footprint:** `s3_shore_footprint.json` `millstone_seat`. Root-local (2995.03, 0.0), which is world (14417, 160000)
  minus the root. Radius 80 cm, blend 70 cm.
- **Built:** a level disc at **h 9.57 cm above floor top = root-local z 124.57**. The surface varies by only 0.027 cm
  within the radius.
- **Recorded:** in the manifest (`checks.millstone_seat`) and in the grid (`millstone_seat`).

### 9.5 Seat report on the new ground [meas-here]
`s3_shore_seat_report.json`: 5 OK, 0 FLOATING, 10 BURIED. The sand sheet now raises the cast area, so most rocks, seaweed
and figures sit below the mean surface under their AABBs. Objects were not moved; Gary arranges them.

### 9.6 Standing stones [meas-here unless noted]
Files: `standing_stones_proposal.json`, `s3_shore_standing_stones.py`.

**Rule:** pivot = the highest surface under the rotated 144 × 103 footprint, minus 135 cm. On the high side, 165 cm of the
330 cm stone is buried and 165 cm stands above the sand; the hole centre is 69 cm above the sand on that side.

The rows use the PLACE schema of `S3Millstone/s3_props_ue.py:495-530`, where `burial_cm` = median surface within 45 cm
minus the pivot.

| Stone | Root-local xy | Yaw | Lean roll/pitch | burial_cm | Pivot z | Hole z | Main camera |
|---|---|---|---|---|---|---|---|
| A | (3330, 760) | 6 | 4 / −2.5 | 119.5 | 51.4 | 255.4 | **hole in frame**, 2° off centre; hole axis 18° off the view ray |
| B | (4930, −780) | 68 | −3 / 5 | 113.3 | 75.8 | 279.8 | out of frame |
| C | (1420, 780) | −38 | 5.5 / 2 | 97.3 | 115.4 | 319.4 | out of frame |

If Gary wants only two: **A and B**.

All three clear the keep-outs:
- the millstone seat plus its blend;
- the cast objects' live AABBs plus 150 cm;
- the notches plus their blend;
- the door corridor plus 100 cm;
- the walls.

**Two blockers in the props tool [decl, code]:**
1. `plan_place` writes rotation `[0, 0, yaw]` (`s3_props_ue.py:515`). The leans are carried as `lean_roll_deg` and
   `lean_pitch_deg` but are NOT applied.
2. `GUARD_LOCAL` has a minimum z of 100 (`s3_props_ue.py:104`, checked at `:517-518`). The stone bottoms (pivot − 30)
   sit at root-local z 21, 46 and 85. That is below both the deck underside (95) and the guard. The cause: the rule
   buries 165 cm below the high side, but these dunes stand only 71–135 cm high.

   PLACE would refuse with `GUARD_LOCAL_BOX`. Either the guard is relaxed for this prop or the burial is reduced. This
   stream did not edit S3Millstone files.

### 9.7 Harness `test_s3_shore_offline.py` [meas-here]
**Checks with a negative control (the control must trip the check):**

| Check | Negative control |
|---|---|
| Drift over the proposed print line | the print line lowered |
| Door gap open | door corridor closed |
| Wave bases flush | notch off |
| Slopes within repose | relaxation off, 40° talus |
| Ripples present | ripples removed |
| Ripples not too regular | the regular single-sinusoid field of 17:04 |
| No terracing | the 17:04 pipeline |
| No pits on dunes | the 17:04 pools and punched hollows |
| Lee/windward asymmetry | no wind transport |
| Seat level | seat not built |
| Grid determinism (two field builds byte-identical) | a seed change moves the grid hash |
| Last two Blender FBX identical | a tampered hash is caught |

**Consistency checks:**
- the height-set JSON agrees with the field;
- Blender heights equal the harness heights;
- the standing-stone proposal is built on this field.

Result: **56/56 PASS** [meas-here, `test_s3_shore_offline_report.json`]. The 41 earlier BENCH_PIE, runner and seat cases are unchanged.

### 9.8 Previews [meas-here, EEVEE Next]
Cycles is not offered under `--factory-startup` here, so the previews use EEVEE Next.

Preview-only settings:
- Proxies cast no shadows. The 12 m walls would otherwise put a low sun in total shadow.
- The cast and rock boxes are hidden in the close stills.
- The sun rakes at 14° across each frame.
- The red line is the current print line (160 cm); the blue line is the set's proposed line.

Files, all under `DerivedAssets/S3Shore/previews/`:
- **A/B/C close comparison:** `sets/{A,B,C}_{wall_main_B04,corner_back_right,wall_left_close}.png`. `wall_main_B04` is the
  main S3 camera pose from the brief.
- **Recommended set B, with the millstone seat and the three stones:**
  - close: `wall_main_B04.png`, `corner_back_right.png`, `wall_left_close.png`;
  - overviews: `overview_from_mouth.png`, `overview_high_three_quarter.png`;
  - other views: `back_wall_drifts_door.png`, `mud_front_low.png`, `cam_B02.png`, `cam_B09.png`, `cam_EntryHandoff.png`;
  - vertex colour: `plan_vertex_colour_RGB.png`.

### 9.9 Commands
| Step | Command |
|---|---|
| Field + sets JSON | `python Saved/CodexConductor/S3Shore/s3_shore_field.py --sets` |
| Close A/B/C stills | `blender -b --factory-startup --python .../s3_shore_blender_build.py -- --sets A,B,C` |
| Export (byte-identical) | `PYTHONHASHSEED=0 blender -b --factory-startup --python-use-system-env --python .../s3_shore_blender_build.py -- --no-render` |
| Overview stills + stones | `blender -b --factory-startup --python .../s3_shore_blender_build.py -- --overview` |
| Stones proposal | `python Saved/CodexConductor/S3Shore/s3_shore_standing_stones.py` |
| Harness | `python .../test_s3_shore_offline.py` |

**Open [inf]:**
- The editor import and bench of this FBX have not been run.
- The UE look (Megascans sand, Nanite at this relief) is unverified.
- Ripple crests that run at an angle to the 7.5 cm grid alias visibly in the close stills. The material's normal map
  may need to carry the fine scale.


## 10. Set B into the level: IMPORT `mesh_name`, APPLY / REVERT (7 Oct evening, offline, NOT RUN)

Gary wants the set-B dune ground in the level now. The set-B FBX is
`DerivedAssets/S3Shore/SM_S3_ShoreGround.fbx` (sha `eec3648b…`, height_set B, bounds
min [0, −1012, 95], max [6012, 1008, 362.35]). The tier is **measured**: the manifest was read here.

This is offline code only. No MCP, no Unreal, no commit.

### 10.1 What changed
- **IMPORT** takes `"mesh_name"`.
  - The default `SM_S3_ShoreGround` is unchanged, so the v1 asset, the v1 import record and BENCH/BENCH_PIE all
    behave as before.
  - `SM_S3_ShoreGround_B` imports the same FBX into a **new** asset. It is create-only: `MESH_EXISTS` if the asset is
    there, and nothing is ever reimported in place.
  - The gates are the same as for v1: census clean, FBX hash, Nanite, VC REPLACE, 1 LOD, bounds == manifest ±0.5
    (the Y asymmetry −1012/+1008 is the mirror gate), stray-folder diff, only this package dirty, save, clean after.
  - The record goes to `s3_shore_ground_record.json.import-SM_S3_ShoreGround_B`, and the import refuses if that file
    exists. Names must start `SM_S3_ShoreGround` and use only `[A-Za-z0-9_]`.
- **APPLY** (`confirm "APPLY S3SHORE"`) lives in the `BEGIN_APPLY` section of `s3_shore_ground_ue.py`. It follows the
  run-proven pattern of `S3Millstone/s3_props_ue.py` `run_apply` / `_revert_record`.
  1. **Gates:** no PIE; editor world == the vertical slice; census clean; no `s3_shore_ground_record.json`; no
     "S3 Shore Ground" label or `RigAtmos.S3ShoreGround` tag. The mesh and MI must load through `unreal.load_asset`.
     There must be exactly one root, one deck and one v2 sand.
  2. **Reads:** the deck's and the v2 sand's bindings in `LS_S3_HangarRise` and `LS_DevScene_03`. A binding counts
     if `locate_bound_objects` resolves it, or if its display name equals the label or object name. The track
     classes and visibility sections go into the record and the OK marker (`reveal_report`).
  3. **Record first** (exclusive create), then the backup `Backups/PreS3ShoreGround-<run>/`: the umap,
     `LS_S3_HangarRise.uasset` and the record, all sha-checked.
  4. **Spawn** a StaticMeshActor "S3 Shore Ground" with these settings:
     - mesh = `mesh_name`;
     - slot 0 = `mi` (default `MI_S3_ShoreGround_v2`);
     - MOVABLE, NO_COLLISION, tag `RigAtmos.S3ShoreGround`, the deck's outliner folder;
     - attached KEEP_RELATIVE to "S3 Hangar Root", relative transform set to identity.
  5. **Reveal**, `reveal: "mirror_deck"` (the default):
     - **The deck has one RISE binding with one visibility section:** the section is copied to the new actor
       (`add_possessable` + `MovieSceneVisibilityTrack`, as the millstone did). The actor is hidden in game, and
       `LS_S3_HangarRise` joins the save set. The marker then says `float_hold_reapply_needed=True`: the S3 float
       hold (`s4_hangar_hold.py` FLOAT, `s3_hangar_float_hold_record.json`) must be re-applied to include the new
       binding. That is reported, not done.
     - **No visibility track anywhere:** no reveal. The ground rides the root exactly as the deck does.
     - **Refused:** a deck visibility track in `LS_DevScene_03`, several bindings or sections, or a sequence that
       could not be read. `reveal: "none"` overrides this.
  6. **Hide** the deck and the v2 sand. The actor is set hidden in game, and every primitive component gets
     visibility off and hidden in game, after `modify()`. Each flag is read back against the exact originals in the
     record. Because this is done at component level, an actor-level rise visibility track cannot re-show them. This
     is the precedent of the `Clam_Pedastal` hide.
  7. **Narrow save.** The census must be exactly `{content: [] or [RISE], maps: [WORLD]}`, with no ZZ_ actors. Then
     `save_map`, plus `save_asset(RISE)` only if a reveal was copied, and the census must be clean afterwards.
  8. **Read back** with fresh lookups after the save:
     - the parent is the root, the relative transform is identity ±0.01, and mesh, MI0, tag, mobility, collision
       and the hidden flag are as set;
     - the deck and v2 flags equal the record's `after`, and the reveal binding resolves and its keys match;
     - the landed-box guard: the actor's root-local AABB is inside `LANDED_LOCAL_BOX` ±2 cm.
     Only then is `S3SHORE_APPLY_OK|run=…` logged.
  9. **Failure** at any step after the record is written: an in-memory auto-undo runs (reveal removed, actor
     destroyed by reference, flags restored), and the record is renamed to `.failed-<run>`. **The map may still be
     dirty: Don't-Save restart.**
- **REVERT** (`confirm "REVERT S3SHORE"`):
  1. Gates: census clean, record saved.
  2. `_verify_applied`. Any drift since APPLY refuses before anything is mutated.
  3. Backup `-REVERT`.
  4. Remove our binding (only after proving it resolves to our actor), destroy the actor, and restore the deck and
     v2 flags exactly.
  5. Narrow save, then read back: the actor is gone and the flags equal the record's `before`.
  6. The record is renamed to `.reverted-<run>`. The assets stay.
- **VERIFY** is still refused by the runner.

### 10.2 Evidence tiers
- **declaration-proven:**
  - `SetCollisionEnabled` / `GetCollisionEnabled`: PrimitiveComponent.h:2025-2026, 2618-2619.
  - `SetHiddenInGame`: SceneComponent.h:932-933.
  - `GetFolderPath` / `SetFolderPath`: Actor.h:2757-2758, 2782-2783.
- **run-proven elsewhere** (7 Oct, `s3_props_ue.py` millstone APPLY, commit 15255da): spawn, KEEP_RELATIVE attach,
  `_set_flags` hide, the RISE visibility-track copy, `save_map` + `save_asset`, `locate_bound_objects`, and the
  GUID binding remove.
- **measured here** (mock unreal): harness, see 10.4.
- **inferred / UNCLEAR:**
  - **Is the deck revealed by a rise visibility track? UNCLEAR.** The offline files hold only the *pedestal's*
    RISE binding (`S3Millstone/s3_props_dry_S3PROPS-20261007-173420.json`, guid 2425E62E…, keys 0:false / 139:true).
    No offline file lists the deck's or the v2 sand's bindings in either sequence. The searches were
    `probe_s3_clam_rock.json`, the s3_props DRY/apply records and `s3_shore_live_reads.json`. The deck's last read
    state was hidden_ed false, hidden_game false, parent the root (`probe_s3_clam_rock.json`). That fits a box part
    with no reveal, but it is not proof. APPLY reads the bindings and decides, and its marker reports the result.
  - **Is the new ground visible during the hangar rise?** It is attached to the root at identity, so it moves with
    the box as the deck does. Its visibility mirrors the deck's: always visible if the deck has no track, or the
    copied reveal if it has one. Inferred from the attachment; not yet measured in PIE.
  - Whether `set_collision_enabled` dirties anything beyond the map: the census-exact save gate catches this. It is
    not measured.

### 10.3 Run order (Gary waiting)
1. `{"mode":"IMPORT","confirm":"IMPORT S3SHORE","run":"S3SHORE-<ts>-IMPB","mesh_name":"SM_S3_ShoreGround_B"}`.
   Expect `S3SHORE_IMPORT_OK`, with bounds max z ≈ 362.35.
2. `{"mode":"APPLY","confirm":"APPLY S3SHORE","run":"S3SHORE-<ts>-APPLY","mesh_name":"SM_S3_ShoreGround_B"}`.
   - `mi` defaults to MI_S3_ShoreGround_v2.
   - Read `reveal_report` and `float_hold_reapply_needed` from the marker.
3. Tests: `InfinityStage.Editor.SavedMasterMatchesShow` and `InfinityStage.Editor.SceneCutBindingsResolve`, queued
   after a run-id marker.
4. If `float_hold_reapply_needed=True`, re-apply the S3 float hold (conductor's call).

To undo: `{"mode":"REVERT","confirm":"REVERT S3SHORE","run":"S3SHORE-<ts>-REV"}`.

### 10.4 Harness
`test_s3_shore_offline.py` gains 23 APPLY cases, using a new editor-world mock in which every mutation dirties the
map and is logged with record-file existence. The cases cover:
- \+ APPLY: placement, flags, one map-only save, record before every mutation.
- \+ REVERT exact, including a non-default `Skirt.hidden_in_game`.
- − refusals: dirty census (APPLY and REVERT), existing record, missing _B, deck reveal only in DevScene_03, PIE,
  revert drift.
- − a foreign package dirtied mid-apply: DIRTY_SCOPE, auto-undo, `.failed` record.
- \+ deck reveal mirrored, RISE saved, float hold flagged; REVERT removes only our binding.
- mesh_name: default unchanged, B, bad names refused.
- − IMPORT `_B` exists / dirty census, refused before any import task.
- Runner: wrong confirm; APPLY_OK → REVERT_OK → VERIFY refused.
- A static scan of the APPLY section for `EditorAssetLibrary.load_asset`, reload, Save-All, reimport and
  GetBoundObjects, with a − control.

Two existing runner checks were updated on purpose: APPLY and REVERT are now enabled, and VERIFY is still refused.
Result: see the end of this section.

Result (7 Oct evening, measured here): `S3SHORE_OFFLINE 79/79` (56 previous + 23 new), exit 0.
