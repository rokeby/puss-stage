# S3 shore sand: hi-res search and 2K anti-tiling fallback (7 Oct 2026)

Gary, 7 Oct: the S3 shore sand looks low-res. He asked for a hi-res search and a 2K fallback.
This work was done offline. Unreal MCP was not used, nothing was downloaded, nothing was committed, and v1 was not edited.

Tiers, per claim: **[decl]** declaration-proven (header or our own source), **[bin]** binary-proven (read from the .uasset bytes), **[meas]** measured, **[inf]** inferred, with the reason given.

## 0. Headline

**A 4K copy of the same sand scan is already in Content.** The brief said the 4K sand and mud folders were empty. That holds only for the root folder `Content/Megascans_4K/Surface/02_Soil_Sand_pjuuz0/`, which has 0 files [meas: `ls`]. The pack copy under `Content/EnvironmentPacks/Megascans_4K/` is fully populated:

| Asset (/Game/EnvironmentPacks/Megascans_4K/Surface/…) | Dimensions | Compression | .uasset |
|---|---|---|---|
| 02_Soil_Sand_pjuuz0/pjuuz_4K_Albedo | 4096×4096 | TC_Default, SRGB True | 22 MB |
| 02_Soil_Sand_pjuuz0/pjuuz_4K_Normal | 4096×4096 | TC_Normalmap, SRGB False | 41 MB |
| 02_Soil_Sand_pjuuz0/pjuuz_4K_Roughness | 4096×4096 | TC_Grayscale, SRGB False | 11 MB |
| 02_Soil_Sand_pjuuz0/pjuuz_4K_Displacement | 4096×4096 | TC_Grayscale | 2 MB |
| 12_Soil_Mud_pkbc30/pkbc3_4K_{Albedo,Normal,Roughness,Displacement} | 4096×4096 each | same pattern | 14/36/8/2 MB |

How these values were read:
- Dimensions and the SRGB flag come from the asset-registry tag strings `Dimensions` and `SRGB` inside each .uasset [bin]. The same read gives `2048x2048` for the 2K maps v1 uses, which is the control.
- `VirtualTextureStreaming=False` and `NeverStream=False` were read the same way, for both the 2K and the 4K maps [bin].
- Compression comes from the `TC_*` names in each package's name table [bin, weaker: a name in the table is not proof that it is the property's value].
- Whether these assets load cleanly in UE 5.8 is **not measured**. DRY_V2 (section 3) measures it.

The 4K maps use the same compression names as the 2K maps, so a material-instance swap should not run into a sampler-type mismatch [inf]. BUILD_MAT_V2 checks this live, per texture, before it sets anything (`s3_shore_material_v2.py:399-409`).

**Cheapest fix:** build the v2 material with its MI pointed at these 4K maps (`"mi_texture_set": "PJUUZ_4K"`). That doubles texel density, from 13.7 to 27.3 px/cm at the 1.5 m tile, and the anti-tiling removes the visible 1.5 m repeat. It needs no download.

Why the sand reads as low-res is **inferred, not measured**. Two causes are likely:
- **Repetition:** the floor is about 60 m × 20 m, which is roughly 40 × 13 repeats of a 1.5 m tile.
- **Soft close-ups:** shots like B02, the low camera, are probably soft at 13.7 px/cm.

A still of the shore floor at the B02/B09 poses, compared like-for-like (v1 2K, v2 2K, v2 PJUUZ_4K), would separate the two causes.

## 1. Disk search (Part 1a)

Search terms were folder and file names containing `*sand*`, `*beach*`, `*dune*` and `*pjuuz*`. Dimensions were read from the .uasset registry tags [bin].

| # | Path | Res | Maps | Fit / note |
|---|---|---|---|---|
| D1 | `E:\PussStage\Content\EnvironmentPacks\Megascans_4K\Surface\02_Soil_Sand_pjuuz0\` | 4096² | Albedo, Normal, Roughness, Displacement | **Same scan as v1, 2× density, already in the project.** Licence is the same as the 2K copy that is already in use [inf: same pack]. |
| D2 | `E:\PussStage\Content\EnvironmentPacks\Megascans_4K\Surface\12_Soil_Mud_pkbc30\` | 4096² | A/N/R/D | The mud layer at 4K. It is included in the PJUUZ_4K set. |
| D3 | `E:\PussStage\Content\EnvironmentPacks\OceanFloor\Textures\T_SandDetail_BC` / `_N` | 4096² both | BaseColor and Normal only, no roughness | Look is **unknown**: it is an underwater pack and nobody has viewed it. A possible detail-normal source. |
| D4 | `…\OceanFloor\Textures\T_SandDunes_BC` (4096²) / `T_SandDunes_N` (2048²) | mixed | BC, N | Dune-scale macro layer. Not viewed. |
| D5 | `D:\PussStageArchive\Keep-20261003\Content\EnvironmentPacks\Brushify\Materials\Landscape\Textures\Beach\T_Beach_D` / `T_Beach_N` (and `Dunes\T_Dunes_D/_N`) | 4096² | D, N only | It was **archived out of the project on 3 Oct** (`MANIFEST-20261003.tsv`: "OK 2.681 GB Keep-20261003 Content\EnvironmentPacks\Brushify"). Bringing it back is a Content write that needs approval, and the pack is 2.7 GB. Whether roughness sits in the D alpha is UNREAD. |
| D6 | `D:\PussStageArchive\Keep-20261003\Content\EnvironmentPacks\Desert\Assets\Terrain\Dune\T_DuneMountain_0{1,2,3}_{basecolor,normal,mask}` | 4096² | BC, N, mask | Dune-mountain terrain scale, which does not fit a beach floor. Archived (2.6 GB). |
| D7 | `E:\PussStage\Content\EnvironmentPacks\Forest_Environment_Set\…\Landscape\Textures\T_ground_sand_0{1,2}_*` | 2048² | BC_H, N, MT_R_AO | No resolution gain over v1. |

These locations were searched and contained nothing usable:
- `Content/Megascans_4K` (the root copy): sand and mud folders exist but are empty.
- `Content/Megascans_2K/Surface/01_Soil_Sand_pjuuz0`: empty.
- `Content/Fab/Megascans`: holds only `3D/Roman_Marble_Plinth`.
- `C:\Users\Administrator\Documents\Megascans Library\Downloaded\UAssets\uassetsData.json`: contains `{"assets":[],"version":1}`, so the Bridge library is empty.
- `C:\Users\Administrator\Downloads`: no texture sets. The `shore_out*.jpg` files there are reference images, not textures.
- `%LOCALAPPDATA%\FabPlugins`: only `UE_5.6` and a settings file.
- `D:\PussStageSources`, `D:\PussStageTools`, `D:\Projects`, `D:\UE5 Plugins`: no sand textures.
- `Documents\Unreal Projects`, searched to depth 4: nothing.

What was **not** searched: other user profiles, `D:\SteamLibrary`, and the full contents of `D:\PussStageBackups` (those are snapshots of this same Content).

## 2. Web candidates (Part 1b). Nothing was downloaded; each file needs Gary's OK.

Ranked by fit for **fine, pale, wind-blown beach sand with little debris**.

| Rank | Asset | Licence | Res / physical size | Maps | Size (where read) | Fit |
|---|---|---|---|---|---|---|
| 1 | **Poly Haven, Sand 03**, https://polyhaven.com/a/sand_03 | **CC0** | 8192² over 2.0 × 2.0 m, about 41 px/cm | Diffuse, Normal GL/DX, Rough, Displacement, AO, ARM | 4K JPG: diffuse 14.2 MB, nor_gl 13.9 MB, rough 6.5 MB, disp 2.7 MB. 8K JPG: 55.6 / 53.9 / 21.9 / 8.5 MB | Compacted gritty grains with subtle ripples and muted brown tones. Closest to "fine beach sand", though maybe browner than pale; the MI's macro albedo can lift it. [api.polyhaven.com/info + /files, read 7 Oct] |
| 2 | **ambientCG, Ground 093 C**, https://ambientcg.com/view?id=Ground093C | **CC0** | up to 8K, physical size not stated | PBR set (zip) | 2K-JPG 18 MB, 4K-JPG 85 MB, 8K-JPG 477 MB (whole zip) | Procedural wind-eroded layered dune sand in beige, the most "wind-blown, pale" of the set. Procedural, not a scan. Released Nov 2025. Sibling variants: 093A, 093B. |
| 3 | **Fab / Quixel, "Thai Beach Sand"**, https://www.fab.com/listings/21c8230c-4a8f-46d2-a7e9-b9156fa1c078 | **Fab Standard License**. Free per the search snippet [inf: the listing page returned HTTP 403 to fetch, so the price, licence tier and file sizes are UNREAD] | 2 × 2 m scan, 4096 px/m (8K) [inf: snippet] | Basecolor, Normal, Roughness, Displacement, AO, Cavity, Gloss, Bump, Specular [inf: snippet] | UNREAD | A Megascans beach scan, and the same family as pjuuz. Related listings named in search: "Thai Rippled Beach Sand", "Thai Trampled Beach Sand". Since 2025 most Megascans are paid on Fab, and assets claimed in 2024 stay usable forever (80.lv, cgchannel). Whether Gary claimed the library in 2024 is unknown, since the Bridge library on this PC is empty. |
| 4 | **Poly Haven, Aerial Sand**, https://polyhaven.com/a/aerial_sand | **CC0** | 8192² over **15 × 15 m**, about 5.5 px/cm | same Poly Haven set | UNREAD | **A macro layer, not a close-up layer.** Its 15 m coverage could replace the procedural macro noise (MacroNoiseM about 14 m). It has tyre and foot ruts, which need to be checked. |
| 5 (wet) | **Poly Haven, Damp Beach Sand 02**, https://polyhaven.com/a/damp_beach_sand_02 | **CC0** | 8192² over 1.87 m | same Poly Haven set | UNREAD | Compacted, slightly glossy wet grit with striations. **The wet-sand option**, for the G-channel and puddle zone instead of a darkened dry sand. Published Jan 2026. |
| alt (wet/mud) | ambientCG Ground 054, https://ambientcg.com/view?id=Ground054 | CC0 | photogrammetry, about 3.5 m, up to 16K | PBR | 4K-JPG 128 MB, 8K-JPG 497 MB | Muddy beach. A candidate to replace the pkbc3 mud. |

These were rejected:
- Poly Haven `sand_02`: dark and dirty.
- `coast_sand_0x`: pebbles and debris.
- `dense_sand`, `playground_sand`, `park_sand`: trampled, with footprints.

All the Poly Haven entries come from `https://api.polyhaven.com/assets?type=textures&categories=sand`, which lists 60 assets.

**Recommended download if 4K pjuuz is not enough:** Poly Haven `sand_03` at 4K JPG. That is Diffuse, nor_gl and Rough, about 35 MB, CC0.
- **Normal format:** UE uses DirectX normals, so take `nor_dx`. The `nor_gl` map would need its green channel flipped [inf: standard convention].
- **Import:** import it into a new folder and set the MI through `mi_textures`. The v2 master does not need to change.

## 3. v2 fallback material (Part 2)

**Files.** This brief created two files:
- `E:\PussStage\Saved\CodexConductor\S3Shore\s3_shore_material_v2.py`
- `E:\PussStage\Saved\CodexConductor\S3Shore\test_s3_shore_material_v2_offline.py`

`s3_shore_ground_ue.py` and `s3_shore_field.py` were **not edited**.

**Graph.** The graph has 48 nodes and 66 edges. The data is at `s3_shore_material_v2.py:61-233` [decl]. It creates `M_S3_ShoreGround_v2` and `MI_S3_ShoreGround_v2` in `/Game/InfinityStage/Dev/Generated/S3Shore`.

**Sand at two scales:**
- **Scale A:** tiles at `SandTileM` 1.5 m.
- **Scale B:** tiles at `SandTileM2` 4.7 m. Its UVs are rotated by `SandRot2Deg` 37° and offset by (0.37, 0.61) (`CODE_TILE_ROT`, :123).
- **Blend:** a 3-octave value noise of UV metres mixes the two (`CODE_NOISE`, :131). Its period is `BlendNoiseM` 9 m and the mix sharpness is `BlendContrast` 2.
- **Normal correction:** scale B's normal is rotated back by −37° into the surface frame (`CODE_SAND_NORMAL`, :159).

**Macro variation:** a second noise field (`MacroNoiseM` 14 m) varies albedo by ±`MacroAlbedoAmp` 0.10 and roughness by ±`MacroRoughAmp` 0.08.

**Detail normal:** the sand normal is sampled again at `DetailTileM` 0.35 m with strength `DetailNormalStrength` 0.4, combined by whiteout blend.

**Swappable textures:** every texture is a parameter, using v1's names: SandAlbedo, SandNormalT, SandRoughT, MudAlbedo, MudNormalT, MudRoughT, MossAlbedo.
- **Shared names:** several sample nodes share one parameter name, for example three SandNormalT nodes. UE treating same-named nodes as one parameter is **[inf]**. BUILD asserts that the master's texture-parameter list holds each name exactly once (:509) and reads every MI texture back (:513-519).
- **Override sets:** MI overrides come from `mi_texture_set` (`2K` or `PJUUZ_4K`, :79) and/or `mi_textures`. Each one is gated on its sampler type matching the default's (:407).

**Vertex colour:** v1's logic (R mud, G wet and puddle, B moss) is **character-identical** to v1. `CODE_TILE`, `CODE_MUDW`, `CODE_BASE`, `CODE_ROUGH` and `CODE_NORMAL` at :104-117 are equal to `s3_shore_ground_ue.py:104-117`. The harness proves this by parsing v1 with ast [meas]. v1's 11 scalar defaults are kept unchanged [meas].

**Build gates**, in order:
1. Census is clean.
2. Graph-spec has no problems.
3. Neither v2 name exists (`EXISTS|`).
4. Neither name equals a v1 name.
5. Each v1 `.uasset` is sha256-hashed on disk.
6. Textures load; override samplers match.
7. Master is created, nodes are made, custom code and inputs are read back, links are made, and recompile has no errors.
8. The Nanite usage flag reads back.
9. The expression count equals the nodes made.
10. The MI is created, parent is set, texture parameters are listed and each is read back, and scalar defaults are read back.
11. Census equals exactly {master, MI}.
12. The folder diff equals exactly {master, MI}.
13. Both are saved, and the post-save census is clean.
14. The v1 hashes are unchanged (`V1_CHANGED`).
15. `collect_garbage`, the record file is written, and only then is `S3SHOREMAT2_OK|run=…` logged. Any refusal logs `S3SHOREMAT2_FAILED|run=|mode=|reason` instead.

The file has **no delete, destroy, reload or rename call**; the harness checks this with an AST scan and a control.

**Unverified in UE [inf]:**
- HLSL compile: covered by the RECOMPILE gate and a log check about 20 s later, because compile is async (memory).
- Whether `get_texture_parameter_names` returns shared names once.
- Whether `blueprint_get_size_x` reads non-zero; this is reported only, never gated.

**Declarations checked against the UE 5.8 headers [decl]:**
- `MaterialEditingLibrary.h:141` GetMaterialExpressions
- `:426` / `:430` Get/SetMaterialInstanceTextureParameterValue
- `:510` GetTextureParameterNames (out-param)
- `Texture2D.h:361` Blueprint_GetSizeX
- `MaterialExpression.h:195` Desc

The rest of the API calls copy v1's BUILD_MAT, which ran and saved on 7 Oct [meas: `s3_shore_ground_record.json.build_mat`, run S3SHORE-20261007-193358-MAT].

**Harness:** run `python Saved/CodexConductor/S3Shore/test_s3_shore_material_v2_offline.py`. The result is **ALL_PASS, 7 checks** [meas, 7 Oct]. Every check that has controls also had each control fail as expected.

| Check | What the controls broke (each must FAIL) |
|---|---|
| graph_wiring | dropped detail-normal edge; pin fed twice; custom pin unused in code; cycle; texture UVs unfed |
| v1_vertex_colour_logic_verbatim | v1 CODE_BASE changed; v1 scalar default changed |
| v1_untouched_static | delete call injected into the source; v2 master renamed to the v1 name |
| mock_build_success_saves_only_v2 | positive only: the fake `unreal` saw exactly {M_v2, MI_v2} created and saved, and PJUUZ_4K reached the MI |
| mock_build_refusals | v2 master exists; v2 MI exists; dirty editor; name pointed at v1; override sampler mismatch; unknown override parameter; setter claims success but stores nothing; v1 file changes during the run; compile error. Each refuses with the expected reason, and the pre-create refusals create nothing |
| b_scale_normal_back_rotated | evaluates the **real** HLSL strings (`CODE_TILE_ROT`, the first lines of `CODE_SAND_NORMAL`): a surface direction survives the UV rotation and the back-rotation. Control: rotation sign flipped |
| anti_tiling_blend_coverage | a Python **mirror** of `CODE_NOISE` [inf ≡ HLSL]. Over the 60 × 20 m floor, scale B dominates on 25 % of samples and scale A on 10 %; the blend weight differs at +1.5 m on 80 %. Controls: noise period 1000 m; BlendContrast 0 |

The mock checks prove the script's logic against a fake. They are not proof of UE behaviour.

## 4. What the conductor runs (v2 is reversible and create-only, so the conductor can approve it; the look is Gary's)

1. **Back up.** Copy `Content/InfinityStage/Dev/Generated/S3Shore/` to `Backups/PreS3ShoreMatV2-YYYYMMDD-HHMM/`. This follows the AGENTS rule before Show or Content writes.
2. **Dry run.** Write `Saved/CodexConductor/S3Shore/s3_shore_material_v2_args.json`:
   `{"mode":"DRY_V2","run":"S3SHOREMAT2-<ts>-DRY","mi_texture_set":"PJUUZ_4K"}`.
   Run it with `ExecuteProjectPythonFile` on `Saved/CodexConductor/S3Shore/s3_shore_material_v2.py`, through `Saved/CodexMocap/mcp_request.py`.
   - **Proceed only if:**
     - the log shows `S3SHOREMAT2_OK|run=S3SHOREMAT2-<ts>-DRY|mode=DRY_V2`;
     - `exists` shows v2 false;
     - `graph_problems=0`;
     - the census is clean.
   - **Also read** `s3_shore_material_v2_dry.json`: the PJUUZ_4K sizes should be 4096 and the samplers should match. This is the first live proof that the 4K assets load.
3. **Build.** Change the args to `{"mode":"BUILD_MAT_V2","confirm":"BUILD_MAT_V2 S3SHOREMAT2","run":"S3SHOREMAT2-<ts>","mi_texture_set":"PJUUZ_4K"}`. Use `"2K"` instead for the pure fallback.
   - **Check:** after `S3SHOREMAT2_OK|run=S3SHOREMAT2-<ts>|mode=BUILD_MAT_V2`, wait about 20 s and grep `Saved/Logs/PussStage.log` for `Failed to compile` and `M_S3_ShoreGround_v2`.
   - **On failure:** `S3SHOREMAT2_FAILED` leaves unsaved packages. Restart with Don't-Save. Never delete.
4. **Look at it.** Nothing applies v2 yet. The v1 BENCH and BENCH_PIE in `s3_shore_ground_ue.py`, owned by the other agent, hard-code `MI_S3_ShoreGround`. Two ways to view v2:
   - the owner adds an `mi` argument to the bench;
   - Gary sets the material on the bench or ground actor by hand.

   Then compare B02 and B09 stills of v1 2K against v2 PJUUZ_4K. The look values (tiles, 37°, noise periods, amplitudes) are first-pass and Gary's to tune in the MI.
5. **If 4K still reads soft,** ask Gary for a per-file OK to download Poly Haven `sand_03` at 4K: Diffuse, nor_dx and Rough JPG, about 35 MB, CC0. Then import it with a new create-only script and add it through `mi_textures`.

Sources: [Poly Haven sand_03](https://polyhaven.com/a/sand_03), [Poly Haven aerial_sand](https://polyhaven.com/a/aerial_sand), [Poly Haven damp_beach_sand_02](https://polyhaven.com/a/damp_beach_sand_02), [Poly Haven API](https://api.polyhaven.com/assets?type=textures&categories=sand), [ambientCG Ground093C](https://ambientcg.com/view?id=Ground093C), [ambientCG Ground054](https://ambientcg.com/view?id=Ground054), [Fab Thai Beach Sand](https://www.fab.com/listings/21c8230c-4a8f-46d2-a7e9-b9156fa1c078), [80.lv: Megascans no longer free after 2024](https://80.lv/articles/megascans-no-longer-free-after-2024/), [CG Channel on Megascans free until end-2024](https://www.cgchannel.com/2024/10/epic-games-has-made-megascans-free-to-all-but-only-until-the-end-of-2024/).
