# S3 marble glisten + hand-print grime: offline prep (7 Oct 2026)

Offline only. The editor was closed, so nothing here touched Unreal, the Show, the level or Content. Look choices belong to Gary; this document gives him stills and knobs to choose from.

Tiers: **[decl]** declaration-proven (a header, shader source, record or config we can read) · **[measured]** computed or rendered offline from files on disk · **[inferred]** not verifiable offline (the reason is given).

## LIVE READS NEEDED FIRST (before any bench run)

Read-only. One MCP call per group is enough.

1. **R0 MI live values.** `MI_S3_Marble_Tiling_Daylight_R0`: parent, and every scalar (Min/Max Roughness, Brightness, Saturation, Specular, Normal Intensity, RoughnessTextureWeight, RepeatCm, Breakup*, frame params). Every texture param: is it still Marble021, i.e. variant B? The record says it is (`s3_marble_tiling_switch_record.json:5`) [decl, record only].
2. **Master sampler types.** On `M_S3_MarbleTiling`: the sampler type of each TextureObjectParameter (RoughnessTexture is expected to be LINEAR_GRAYSCALE), TangentSpaceNormal, and `material_decal_response` (expected COLOR_NORMAL_ROUGHNESS, per `s3_marble_tiling_material.py:615`). Also `T_Marble021_Roughness` compression and sRGB, so the new roughness texture is imported to match. A sampler mismatch fails compile (memory: LINEAR_GRAYSCALE).
3. **Liner actor.** `StaticMeshActor_350` ("S3 Marble Inner Wall Right"): slot count, slot-0 material, bReceivesDecals, lighting channels.
4. **The 60 in-frame print decals** (labels are listed in `geometry.json`): live decal material, sort order and DecalSize. On their v3 MIs, read OpacityGain, StainTint, NormalStrength, GlobalFlipU/V and Atlas*. Also check `M_HP_S03_Decal_v3`'s domain, blend and compile state.
5. **Renderer CVars:** `r.Substrate`, `r.DBuffer`, `r.Lumen.Reflections.*`, `r.Lumen.HardwareRayTracing`, `r.DefaultFeature.LightUnits`. Under Substrate the DBuffer path differs: the non-Substrate path in `DecalCommon.ush:108-113` is the one that shares a single opacity.
6. **S3 PPV / camera post at master frame 20756545.** Read the exposure (EV100 pinned at 3.0, per commit 307dc94), **Lumen reflection quality** and **Max Roughness To Trace** (engine default 0.4 [inferred, not checked in the 5.8 headers]). The prints proposed here sit at roughness 0.30–0.55, which straddles that cut.
7. **S3 lights live at that frame.** Read class, units, intensity, location, DiffuseScale/SpecularScale for every light that reaches the R wall, so the strips can be sized relative to them.
8. **Camera pose at frame 20756545 in PIE.** Re-confirm (14421.973, 159250, 120), yaw 75.457, pitch −5.464, FOV 37.497. Memory warns that Master timing can be stale.
9. **Line traces** from each of the three strip positions to its wall reflection point, and from the camera to that point. Is anything in the way (huddle, flats, rig, ceiling)? Is there geometry at z ≈ 384 near the L wall at y = 159060?
10. **Does a decal material write any colour with BaseColor unconnected?** Answered by the first bench still: in A, decal-only pixels should change in gloss, not in colour.

## 1. What is live today (from records and code)

| Claim | Tier | Source |
|---|---|---|
| The 10 S3 liners use the per-actor MIs `MI_S3_Marble_Tiling_Daylight_{L,R}{0..4}` of the create-only master `M_S3_MarbleTiling`. The bench target, the R base liner, is `StaticMeshActor_350` with `..._R0` (ObjectRelative 1, UOffsetCm 317). | [decl] | `Saved/CodexConductor/s3_marble_tiling_record.json` (plan); commit cb9405c |
| Source B = ambientCG Marble021. The switch to B was run S3MT-20261006-131127 (Gary chose it, commit 52259b7). | [decl] | `s3_marble_tiling_switch_record.json:5` |
| Shading: `roughness = lerp(MinR, MaxR, lerp(vein, rt, RoughW))`, `colour = saturate(lerp(lum, bc, Sat) * Brightness)`, Specular is a plain param. | [decl] | `s3_marble_tiling_material.py:385,387,396,589` |
| Look params as live on 6 Oct: Brightness 1.15, Saturation 0.8, Min/Max Roughness 0.05/0.12, Specular 0.7; RoughnessTextureWeight 1 for the CC0 sets. | [decl, record "look_source": "live"] | `s3_marble_tiling_record.json:275`; `s3_marble_tiling_material.py:43-52,86` |
| **Effective clean roughness is about 0.056–0.060 everywhere.** Marble021's roughness map is 0.09–0.15 (p5–p95), and feeding it as `rt` into lerp(0.05, 0.12) uses only ~6 % of the Min..Max range. The wall reads as a uniform near-mirror with no sheen variation. | [measured] from the source JPG + record params; the live imported texture is [inferred] equal | `textures_report.json` `live_effective_roughness_p5_p50_p95` |
| **Albedo is clipped to 1.0.** Marble021 colour is ≈ 0.95 sRGB (≈ 0.89 linear); × Brightness 1.15 ≈ 1.03, then `saturate`. A white Lambertian wall has a high diffuse floor, which drowns any reflection (F0 = 0.08 × 0.7 = 0.056). | [measured] offline arithmetic; the live colour is [inferred] | `s3_marble_tiling_material.py:385,396` |
| Prints: 449 DBuffer decals (R 247, L 202), placed in band z 160–400 cm. Each uses a per-element MI of `M_HP_S03_Decal_v3`: BaseColor = atlas RGB × StainTint, Opacity = atlas alpha × OpacityGain, Roughness = atlas R, Normal = atlas normal × NormalStrength. | [decl] | `hp_place_record.json`; `placement_S03.json` stats; `hp_import_atlas.py:532-576` |
| The print roughness atlas holds **0.70–0.92** (L8 179–234), i.e. `roughness_base 0.70 + gain 0.22 × alpha`. | [measured] PNG; [decl] `Tools/FlatV3/handprints/build_handprint_atlas.py:98-99,614` | |
| **Why the prints look painted on.** One opacity drives colour, normal and roughness together (non-Substrate DBuffer: `MultiOpacity = Opacity`, `DecalCommon.ush:108-113`; applied in `DBufferDecalShared.ush:513-525`). So every print is a full-strength dark-brown albedo stamp at its alpha, with hard art edges. The roughness change is real, but the wall has nothing structured to reflect, so roughness never shows. Only the albedo stamp reads. | shader part [decl]; the visual cause is [measured] in the offline re-render (below) and otherwise [inferred] | |
| Renderer: Lumen reflections (`r.ReflectionMethod=1`), HW ray tracing on. | [decl] | `Config/DefaultEngine.ini:14,18` |
| A rect light's highlight is analytic direct specular, so it does not depend on Lumen reflection quality. Lumen quality matters only for reflecting geometry (the opposite wall, the flats). | [inferred]: engine architecture; the renderer .cpp is not in the install | |
| Lights have `DiffuseScale` and `SpecularScale` (UIMax 1) with setters. | [decl] | `LightComponent.h:90,96,357,360`; `RectLightComponent.h:33,40,46,52,81-90` |

## 2. Offline textures (`DerivedAssets/S3Marble/Grime_20261007/`)

Built by `Saved/CodexConductor/S3MarbleGrime/s3mg_build_textures.py` (seed 20261007; sha256 per file in `textures_report.json`). Pipeline from the four photos: linear grey, then exclusions (keypads, handle, tape, letter, seam), filled by normalized convolution. Then ratio to the local illumination (σ 40 px), giving `dark` (albedo) and `|1-ratio|` grease (roughness). Scratches come from a multi-scale Hessian line filter. Tileable layers are toroidal splats of feathered photo patches. All textures are power-of-two and ≤ 2048, LINEAR except the colour map.

| File | Use | Notes |
|---|---|---|
| `T_S3MG_Marble021_RoughGrime.png` 2048 L | RoughnessTexture on a NEW child or MID of R0, with **Min 0.04 / Max 0.60** | Resulting roughness p5/p50/p95/p99 = 0.054 / 0.077 / 0.139 / 0.177 [measured]. Clean areas stay glossy; scratches and wipes go to ~0.15–0.18. Seamless in U and V (wrap diff within the interior p99) [measured] |
| `T_S3MG_Marble021_NormalDX_Scratch.png` 2048 | NormalTexture | Marble021 DX normal plus scratch grooves; seamless [measured] |
| `T_S3MG_Marble021_Color_Grime_sRGB.png` 2048 | BaseColorTexture | ≤ 7 % ambient darkening |
| `T_S3MG_GreaseAtlas.png` 2048 | Grease decal mask, **same UV layout** as the 4096 print atlas | R = feathered opacity (σ ≈ 0.25 cm core + 1.1 cm bloom, photo breakup, partial-finger dropout); G = smear height; B = faint albedo weight |
| `T_S3MG_GrimeBand.png` 2048×512 | Low-wall band decal, 800 cm × 200 cm, tileable in U | Floor-kick exponential plus a hand-height (~110 cm) lobe, times photo clusters |
| `T_S3MG_SeamStrip.png` 512×2048 | Seam/corner strip, 100 × 400 cm, tileable in V | Dense at u = 0. There is no seam or corner in the main frame, so it is not used in the A/B/C stills |

Known weaknesses [measured, by eye]: faint rectangular splat footprints in the tiling layers. The live breakup blend (a second sample rotated 37°, × 2.37) should hide the 150 cm repeat [inferred]. The photo scale assumes a ~90 cm door leaf [inferred].

## 3. Geometry: main camera, wall, mirror light (`geometry.json`, `s3mg_geometry.py`)

- The main S3 camera is still 0 of `PSTILLS-S3-20261007-173228-floathold` (the 144232-held still 0 has the identical pose): loc (14421.973, 159250, 120), yaw 75.457, pitch −5.464, hFOV 37.497 [decl, manifest]. It looks at the **R wall** (y = 160999) about 17.5–21.8 m away, and the frame covers wall x 14281–15588, z from the floor up to ~290 cm [measured, computed].
- Model check: the predicted floor/wall junction row is 387.5 px; the still shows ~390 [measured]. The re-rendered decal layout lands on the still's prints, and the baseline re-render differs from the still by mean |Δ| 0.037 sRGB on wall pixels [measured].
- 60 R-wall print decals fall in the frame (±50 px) [measured].
- **Mirror light (variant C).** The camera is mirrored through the wall plane, and rays from the mirror image through wall points continue to a light plane 60 cm off the L liner (y = 159060), behind the camera. Three **RectLight strips, 300 × 120 cm, facing +Y (yaw 90)**, sit at (14697.6 / 15494.0 / 16290.3, 159060, 383.8). They reflect at wall x 14553 / 14930 / 15308, z 245 (the print band in frame), as 142 × 57 cm highlights. Incidence is 14.5°, wall→light magnification 2.109, and all three project outside the frame [measured, computed]. Whether the paths are clear is [inferred] until live read 9.
- **Strip intensity is a sweep, not a number** [inferred]. Aiming the highlight at ~18× the wall's diffuse luminance gives ~4000 cd per strip, assuming EV100 3 and UE's 1/(1.2·2^EV) exposure. That much spill would roughly double the wall's diffuse level (3 strips at ~19 m), hence **DiffuseScale 0.10** in C: a deliberately non-physical, specular-dominant light, which is Gary's call. C_phys (1500 cd, DiffuseScale 1) is the honest comparison.

## 4. Previews (`preview_{baseline,A,B,C}.png`, `sheet_ABC.png`; `s3mg_preview.py`)

This is a fake-spec sketch, not a renderer of record. Non-wall pixels are the live still. The wall is re-shaded as diffuse plus a Schlick specular of the room, plus (C only) the strips blurred by GGX-like width (σ_wall = 1839·r² cm). Exposure is per-channel calibrated so the baseline re-render matches the still's clean wall [measured].

- **baseline**: reproduces today's look; the prints read as dark stamps. Decal-pixel roughness is 0.63 against 0.058 clean [measured]. This is the "painted on" problem.
- **A** (new marble tile, grease decals carrying roughness+normal only, the v3 colour at OpacityGain 0.22): the prints become faint grey ghosts. **Without something to reflect, the roughness work is nearly invisible** [measured in the sketch]. This supports Gary's "not much to reflect" reading [inferred for the real render].
- **B** (A + low-wall grime band): a soft grime gradient from the floor and at hand height. The wall's clean mean roughness rises from 0.084 to 0.103 [measured].
- **C** (A + mirror strips): three glossy highlights sit across the print band, and inside them the prints show as dull grease marks breaking the reflection, which is the reference photos' effect. Wall p99 luma goes from 0.557 to 0.729 [measured]. **The strips read as three rectangular windows.** Whether that is wanted, or one long soft strip is better, is a look question for Gary.

## 5. Bench script (DRAFT, NOT RUN): `Saved/CodexConductor/S3MarbleGrime/s3mg_bench.py`

Stages, one MCP call each:

1. `plan` (already run offline, which wrote `s3mg_bench_plan.json`).
2. `assets` (editor): imports the 6 textures and builds the create-only decal master `/Game/ZZ_Bench/S3MarbleGrime/M_ZZ_S3MG_GreaseDecal`. Its outputs are Opacity, Roughness and Normal only, **no BaseColor**; blend is set before domain. Nothing is saved, no node is deleted, and no existing asset is edited. GC runs after.
3. `verify_assets`: a log gate on "Failed to compile" since the run's START marker, plus a PS instruction count.
4. `apply <A|B|C|C_phys|base_C>` (PIE only). **It writes `s3mg_bench_originals.json` and logs the path before any change.** Then it changes PIE copies only:
   - a MID on liner R0 with the new textures and Min/Max;
   - MIDs on the 60 in-frame print decals with OpacityGain 0.22;
   - one ZZ_ grease decal per print, with the atlas rect copied from its MI;
   - B: a ZZ_ band decal;
   - C: the 3 ZZ_ RectLights, using UFUNCTION setters with units set to CANDELAS and read back.

   Every change is asserted by read-back. On any exception it restores in the same call.
5. `stills`: the existing `scene_stills_run.py` with `{"passage":"S3","fractions":[0.3],"label":"s3mg_<variant>"}`.
6. `restore` (PIE): resets the materials from the file, destroys the ZZ_S3MG-tagged PIE actors and verifies them against the file.
7. `census` (editor world unchanged).

**Deviation, flagged:** the spawned PIE actors live across calls (apply → stills → restore). The mitigations are that they exist only in PIE, are tagged, are non-transient and so findable by GameplayStatics, include no SceneCapture, and die at PIE end. API names marked [inferred] in the file (`KismetMaterialLibrary.create_dynamic_material_instance`, `k2_get_*_parameter_value`, label lookup on PIE copies) need checking against the 5.8 Python stubs before the run.

**Approval:** the run needs PIE (the conductor starts it; the bench must never end PIE). It creates unsaved ZZ_Bench assets, and those need a Don't-Save, or must be re-created by APPLY.

## 6. Later APPLY outline (after Gary picks)

1. Take a `Backups/PreS3MarbleGrime-YYYYMMDD-HHMM` snapshot.
2. Import the chosen textures to `/Game/InfinityStage/Dev/Materials/S3Marble/Grime/` in batches with GC, and save only those.
3. Create **new** per-actor MIs `MI_S3_Marble_Tiling_Grime_{L,R}{0..4}` as children of the existing `..._Daylight_*`, so the frame params are inherited. Set the 3 textures and Min/Max; leave the existing MIs untouched.
4. Build and save a new `M_HP_S03_Grease` master, the same graph as the bench.
5. Put the decal changes on new assets only, not new per-element MIs (the 213-MI OOM). Options:
   - (a) a second grease decal per print with one MI per element, batched at ≤ 20 per call (as `hp_mi_v3_batch`);
   - (b) better: a v4 print master whose colour opacity and roughness opacity are separate params. One decal still shares a single opacity, so (b) needs either colour = marble mean × (1 − darken) at full opacity [inferred approximation, valid only because Marble021 is near-white] or the two-decal split.
6. Swap the liner materials and the decal materials in the level, with read-back.
7. Lights: a Show-authored S3 cue for the strips. Lighting cues belong to the Show (puss-two-authorities), so authoring them needs Gary's look approval and the lighting stream.
8. Run SavedMasterMatchesShow; save only the affected assets and the level, then read back and check the log marker.

## Files

- `Saved/CodexConductor/S3MarbleGrime/`: `s3mg_geometry.py`, `s3mg_build_textures.py`, `s3mg_preview.py`, `s3mg_bench.py` (draft), `s3mg_bench_plan.json`
- `DerivedAssets/S3Marble/Grime_20261007/`: 6 textures, `masks/`, `geometry.json`, `textures_report.json`, `preview_*.png`, `sheet_ABC.png`, `preview_report.json`

## 7. Bench v2 for Gary's pick C (written 7 Oct, evening; offline, NOT RUN)

Gary picked **C**: grease, scratches and faint grime, plus three 3 × 1.2 m mirror-angle window strips at DiffuseScale 0.1. It is a PIE bench with no save, followed by a Don't-Save restart. Files are in `Saved/CodexConductor/S3MarbleGrime/`:

- `s3mg_bench.py`: the stages.
- `s3mg_run.py`: the runner. It purges the module cache, puts the run id on every marker, and logs `S3MG_FAILED` on any refusal or exception. `_OK` is logged only after the stage returns.
- `s3mg_run_<stage>.py`: one wrapper per stage, with a matching `s3mg_<stage>_request.json`.
- `s3mg_args.json`: holds the run id and variant. The runner refuses the placeholder run id.
- `test_s3mg_offline.py`: 46/46 PASS [measured]. It covers:
  - the landed→current rigid mapping, with a negative control on the mock;
  - Gary's C parameters;
  - the assets idempotency classes (REUSED / CREATED / PARTIAL / MISMATCH / in-PIE refusal);
  - runner control flow and the request/wrapper wiring;
  - that the bench contains no save, end-PIE, node-delete, level-load, `EditorLevelLibrary`, `get_sequence_player` or `k2_` names.

What changed from the draft:

- **API names fixed.** The draft's `k2_get_scalar_parameter_value` / `k2_get_texture_parameter_value` are wrong in Python; the UFUNCTIONs carry `ScriptName="GetScalarParameterValue"` / `"GetTextureParameterValue"` (`MaterialInstanceDynamic.h:56-57,84-85`) [decl]. The draft's `EditorLevelLibrary` spawn targeted the editor world; the bench now uses `GameplayStatics.begin_deferred_actor_spawn_from_class` / `finish_spawning_actor` on the PIE world (`GameplayStatics.h:67,71`).
- **Pose-independent placement.** The stills scrub into S3 after apply, so PIE may start with the hangar in another pose. Each grease decal is attached to its own print decal with SNAP_TO_TARGET (identity). Lights are mapped LANDED → current through the S3 Hangar Root (landed = (11421.97275, 160000, -120), rotation 0, measured live by the shore stream in `S3Shore/s3_shore_live_reads.json`) and attached KEEP_WORLD to it. The band is mapped through a print-decal anchor (HP_S03 R 0150) and attached to that decal's wall. The anchors' world poses are read live, scale-free.
- **Restore checks before restoring.** If the root is landed, each light and the band must be within 2 cm of the plan. The liner and decal MIDs must still be in place, i.e. not swapped back by a Show compile or a scrub. Otherwise the stage logs `RESTORED_BUT_STILL_INVALID` → `S3MG_FAILED`, even though the restore itself completed.
- **Time** uses the shared `scene_stills.py`, which drives the Show Root transport (`InfinityStageShowRoot.transport.scrub_to_master_frame`, `scene_stills.py:618,654`). It takes **one still per fresh PIE** at S3 fraction 0.3 (master frame 20756545, the floathold pose). Its end-of-run scrub back from inside S3 will be refused (UNSAFE_EXTERNAL_CLOCK). That refusal is recorded in its manifest but does not fail the run (`scene_stills.py:514-522`) [decl].

### API verification

No generated stub exists: `Intermediate/PythonStub` is absent, and no large `unreal*.py` was found under the project or `D:/Unreal Engine/UE_5.8` (searched 7 Oct). Each name is checked against the 5.8 headers and/or prior use in Saved/ scripts outside this folder.

| Name(s) used | Evidence | Tier |
|---|---|---|
| `DecalComponent.create_dynamic_material_instance()`, `set_decal_material`, `get_decal_material`, `set_sort_order`; props `decal_size`, `sort_order` | `DecalComponent.h:39,82,109,117,121,125` | decl |
| `ADecalActor.Decal` via `get_editor_property("decal")` (private, BlueprintReadOnly) | `DecalActor.h:29-30`; prior use 3× | decl + prior use |
| `PrimitiveComponent.create_dynamic_material_instance(i, src)` | `PrimitiveComponent.h:1629` | decl |
| MID `get_scalar_parameter_value` / `get_texture_parameter_value` (ScriptName), `set_scalar_parameter_value`, `set_texture_parameter_value` | `MaterialInstanceDynamic.h:56-57,84-85` | decl |
| `KismetMaterialLibrary.create_dynamic_material_instance(world, parent)` | `KismetMaterialLibrary.h:46` | decl |
| `GameplayStatics.begin_deferred_actor_spawn_from_class`, `finish_spawning_actor`, `get_all_actors_of_class` | `GameplayStatics.h:67,71,98` | decl |
| `RectLight` prop `rect_light_component` | `RectLight.h:15-16` | decl |
| `set_source_width/height`, `set_barn_door_angle/length` | `RectLightComponent.h:80-90` (UFUNCTIONs) | decl |
| `set_intensity`, `set_specular_scale`, `set_diffuse_scale` | `LightComponent.h:286,357,360` | decl |
| `set_attenuation_radius`, `set_intensity_units` | `LocalLightComponent.h:53,57` | decl |
| `set_cast_shadows` | `LightComponentBase.h:146` | decl |
| `UnrealEditorSubsystem.get_editor_world` / `get_game_world` | `UnrealEditorSubsystem.h:49,52` | decl |
| `MathLibrary.make_rot_from_xz`, `transform_location/direction`, `inverse_transform_location/direction` | `KismetMathLibrary.h:2276,3970,3977,3991,3998`; prior use | decl + prior use |
| `Texture2D.blueprint_get_size_x/y` | `Texture2D.h:361`; prior use 21× | decl + prior use |
| `get_statistics(m).get_editor_property("num_pixel_shader_instructions")` | `MaterialEditingLibrary.h:31,610`; prior use | decl + prior use |
| `get_scalar_parameter_names` / `get_texture_parameter_names` (out-param → returned list) | `MaterialEditingLibrary.h:502,510`; prior use 27× | decl + prior use |
| `AttachmentRule.SNAP_TO_TARGET` / `KEEP_WORLD`, `attach_to_actor`, `get_attach_parent_actor` | `EngineTypes.h:71`; `curtain_sleight.py:1843`, `scene_exit_block.py:741` | decl + prior use |
| AssetImportTask fields, `import_asset_tasks`, texture `srgb` / `compression_settings` / `flip_green_channel` | `s3_marble_tiling_material.py:746-758` (ran 6 Oct) | prior use |
| `get_actor_label()` on PIE copies | `Saved/CodexFlatV3/handprints/hp_test_pie_still.py:145` (PIE) | prior use; that labels survive PIE duplication is [inferred] from that run |

Still [inferred] until the run: that a decal material with BaseColor unconnected writes no DBuffer colour; that scrubs and Show compiles leave PIE MIDs alone (the restore pose check catches it if they don't); that `set_sort_order` on a PIE decal is harmless.

### Coexistence with the shore-ground bench

- **Separate by construction:**
  - tag `ZZ_S3MG` and label prefix `ZZ_S3MG_` (shore uses `RigAtmos.S3ShoreGround` / `ZZ_S3ShoreGroundBench`);
  - own originals, applied and restored files, keyed by run id;
  - restore destroys only `ZZ_S3MG`-tagged actors and resets only the materials in our originals file;
  - no census-equality gate in apply or restore (census is reported only), so shore dirtiness can't false-fail us;
  - we never touch S3 Hangar Deck or Beach V2 Sand.
- **BLOCKER for one shared still [decl, read]:** shore `run_bench` (`s3_shore_ground_ue.py:307-348`) spawns into the EDITOR world (`get_editor_world`, EditorActorSubsystem, `transient=True`) and destroys it in `finally` in the same call. Its stills are a TODO (`:338`). A PIE world is a copy of the editor world taken when PIE starts, so that spawn can never appear in a PIE still. To share our still, the shore stream needs a PIE-world apply/restore split like ours, run between our apply and stills. That is their file, so I have not changed it.

### Exact call sequence (one MCP call per line; wait for the marker before the next)

0. Offline: set `s3mg_args.json` to `{"run": "S3MG-<UTC stamp>", "variant": "C"}`. Run `python Saved/CodexConductor/S3MarbleGrime/test_s3mg_offline.py` and expect 46/46.
1. Editor up, NO PIE: send `s3mg_assets_request.json` → `S3MG_ASSETS_OK|run=..|mode=CREATED|unsaved=1`.
2. About 30 s later: `s3mg_verify_assets_request.json` → `S3MG_VERIFY_ASSETS_OK|run=..|ps=N`. If the reason is `PENDING_COMPILE`, wait and resend.
3. The conductor starts a FRESH PIE (the transport must be outside S3; the bench never starts or ends PIE).
4. `s3mg_apply_request.json` → `S3MG_BENCH_ORIGINALS|run=..|path=..`, then `S3MG_APPLY_OK|run=..|variant=C|spawned=63|mids=61`.
5. (Optional) the shore stream's PIE-world apply, once it exists.
6. `s3mg_stills_request.json` → `S3MG_STILLS_OK|run=..|armed..`, then the async `PASSAGE_STILLS_OK|run=PSTILLS-S3-..-s3mg_..`. The still is `00_f300.png` in that dir. `PASSAGE_STILLS_FAILED` means no valid still.
7. `s3mg_restore_request.json` (while PIE is still in S3) → `S3MG_RESTORE_OK|run=..|destroyed=63|pose=POSE_OK`. `S3MG_FAILED ... RESTORED_BUT_STILL_INVALID` means the restore happened but the still must be discarded.
8. (Optional) the shore stream's restore.
9. The conductor ends PIE. Then send `s3mg_census_request.json` → `S3MG_CENSUS_OK|run=..|editor_clean_of_bench|dirty=..`. The dirty content will list the unsaved `/Game/ZZ_Bench/S3MarbleGrime` assets, which is expected.
10. For another still (C_phys, C_band, a different intensity): set a new run id and variant, then repeat steps 3-9. Steps 1-2 are REUSED within the same editor session.
11. Gary: Don't-Save restart, which discards the ZZ_Bench assets.

## 8. Bench v3: editor-world POOL (supersedes the spawn route and the call sequence of section 7)

**Why** [measured by the conductor]: UE 5.8 Python has no way to spawn an actor into a running PIE world.
- `GameplayStatics.begin_deferred_actor_spawn_from_class` and `finish_spawning_actor` raised AttributeError in this editor twice: `Saved/CodexFlatV3/swapkit/stills/before/FV3STB-20261003-02/st_pie_first_check_runtime.json` and `Saved/CodexConductor/LookBench/20261005-044136/look_bench_result.json`.
- `GameplayStatics.h:66-67,70-71` marks both BlueprintInternalUseOnly [decl].
- `look_bench.py:5-10` reached the same conclusion and built a pool.

v3 follows that pattern. A new `prespawn` stage runs in the EDITOR world before PIE, using `EditorActorSubsystem.spawn_actor_from_class` (`EditorActorSubsystem.h:227-228`). It spawns a hidden pool of 64 actors, all labelled `ZZ_S3MG_*` and tagged `ZZ_S3MG`:
- 3 RectLights (`ZZ_S3MG_Strip_0..2`): 300×120 cm, 0 cd, attached KEEP_WORLD to S3 Hangar Root at the plan's LANDED positions;
- 60 grease decals (`ZZ_S3MG_Grease_<print>`): SNAP_TO_TARGET onto their print decal, with the grease master as their material;
- 1 band decal (`ZZ_S3MG_Band`): attached to the anchor print's wall, shown only by the `*_band` variants.

PIE copies the pool. In PIE, `apply` only makes MIDs, swaps materials, shows actors and sets intensities on the PIE copies. It first checks that every copy exists, is still hidden, and sits within 2 cm of the plan for the current hangar pose. `restore` hides the copies again and restores the liner and print materials; it never spawns or destroys anything in PIE. After PIE ends, a new `unspawn` stage destroys the editor-world pool by reference. It refuses to delete any ZZ_S3MG actor that is not in the prespawn record, and it never saves. The map stays dirty, so a Don't-Save restart follows; saves would refuse on ZZ_ actors anyway (memory puss-benches-are-level-activity).

Gates added in v3:
- `prespawn` refuses while PIE runs.
- It refuses if the MAP is already dirty, because the Don't-Save restart would throw away someone else's level work.
- It refuses if any dirty content is not our ZZ_Bench assets, if a ZZ_S3MG actor already exists, if the run was already prespawned, or if the editor root is not LANDED (±1 cm, rotation 0).
- It writes the pool labels to `s3mg_prespawn_<run>.json` BEFORE the first spawn. On any failure it destroys that call's spawns by reference.
- Each fresh PIE in a run gets its own `"pie": N` in `s3mg_args.json`. Its files are `s3mg_{originals,applied,restored}_<run>-p<N>.json`.

API additions [decl]:
- `EditorActorSubsystem.spawn_actor_from_class` / `destroy_actor` (`EditorActorSubsystem.h:227-236`);
- `Actor.set_actor_hidden_in_game` (`Actor.h:1921-1922`) and `set_actor_enable_collision` (`:1925-1926`);
- `SceneComponent.is_visible` (`SceneComponent.h:852-853`). It is used instead of `AActor::IsHidden`, which is not a UFUNCTION (`Actor.h:4523`).
- `set_actor_label(label, False)` and `set_visibility(False, True)`: as used in `look_bench.py:1337-1363`.

Harness `test_s3mg_offline.py`: **67/67 PASS** [measured]. New since v2:
- an AST scan of the bench CODE: none of `begin_deferred_actor_spawn_from_class`, `finish_spawning_actor`, `k2_get_*`, `EditorLevelLibrary`, save, end-PIE, node-delete or level-load names appear;
  - **+ control:** a doctored copy containing a `begin_deferred_*` call is detected;
  - **− control:** the docstring's mention alone is not counted.
- a scan of the PIE region (apply, stills, restore): no `spawn_actor_from_class`, `destroy_actor`, `EditorActorSubsystem`, `set_actor_label`, `attach_to_actor`;
  - **+ control:** a doctored spawn in that region is detected.
- `spawn_actor_from_class` appears only in `stage_prespawn`;
- the pool is 64 unique `ZZ_S3MG_` labels;
- `prespawn` refusals are mocked: in PIE, dirty map, foreign dirty content, existing pool;
  - **+ control:** a clean editor passes the census gates and stops at the assets gate;
- request files and wrappers exist for all 8 stages.

Coexistence with the shore bench:
- The shore PIE bench now BORROWS the PIE deck copy and spawns nothing: tag `ZZ_S3ShoreGroundBench`; `BEGIN_BENCH_PIE` section at `s3_shore_ground_ue.py:720-1021`, with `run_bench_pie_apply` at :856 and `run_bench_pie_restore` at :953. Its editor-world `run_bench` is at :586-704 (the citation was corrected in our docstring). The section-7 BLOCKER no longer applies.
- Tags never collide (exact-match, `ZZ_S3MG` vs `ZZ_S3ShoreGroundBench`).
- Its PIE apply has no clean-census gate, so our prespawn dirt does not block it [decl, read :856-930]. Our prespawn, however, needs a CLEAN map, so it must run before anything else dirties the level.

### Updated interleaved call sequence (one MCP call per line; wait for the marker)

0. Offline: set `s3mg_args.json` to `{"run":"S3MG-<UTC>","variant":"C","pie":1}`. Run `test_s3mg_offline.py` and expect 67/67.
1. Editor, no PIE, CLEAN map: `s3mg_assets_request.json` → `S3MG_ASSETS_OK|run=..|mode=CREATED|unsaved=1`.
2. About 30 s later: `s3mg_verify_assets_request.json` → `S3MG_VERIFY_ASSETS_OK|run=..|ps=N`. If the reason is `PENDING_COMPILE`, resend.
3. `s3mg_prespawn_request.json` → `S3MG_PRESPAWN_RECORD|..|n=64`, then `S3MG_PRESPAWN_OK|run=..|pool=64|hidden|map_dirty_expected|NEEDS_DONT_SAVE_RESTART`.
4. (Shore) any editor-side shore prep that needs no clean map.
5. The conductor starts a FRESH PIE (transport outside S3).
6. `s3mg_apply_request.json` → `S3MG_BENCH_ORIGINALS|..|pie=<run>-p1`, then `S3MG_APPLY_OK|run=..|pie=..-p1|variant=C|shown=63|mids=61|max_pose_err_cm=..`.
7. (Shore) its PIE apply (`run_bench_pie_apply`) → its own OK marker.
8. `s3mg_stills_request.json` → `S3MG_STILLS_OK|..|armed`, then async `PASSAGE_STILLS_OK|run=PSTILLS-S3-..-s3mg_..-p1`. This is ONE still with both benches applied.
9. `s3mg_restore_request.json` (PIE still in S3) → `S3MG_RESTORE_OK|run=..|pie=..-p1|hidden=64|pose=POSE_OK`. `RESTORED_BUT_STILL_INVALID` means discard the still.
10. (Shore) its PIE restore (`run_bench_pie_restore`).
11. For another still: the conductor ends PIE, sets `"pie": 2` (and the variant if needed), then repeat steps 5-10. The pool persists in the editor world.
12. The conductor ends PIE. Then `s3mg_unspawn_request.json` → `S3MG_UNSPAWN_OK|run=..|destroyed=64|not_saved|NEEDS_DONT_SAVE_RESTART`.
13. `s3mg_census_request.json` → `S3MG_CENSUS_OK|run=..|editor_clean_of_bench|dirty=..` (the map is dirty, as expected).
14. Gary: Don't-Save restart, which discards the map dirt and the unsaved ZZ_Bench assets.

Any `S3MG_FAILED|run=..|stage=..|reason=..` stops the sequence. If it fails at prespawn, the stage has already destroyed that call's spawns; check `s3mg_prespawn_<run>.json`.
