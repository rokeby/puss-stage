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
