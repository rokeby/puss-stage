# Q3 P02 industrial / P06 Wing 044 UV / scaffold handoff

Scope: offline investigation and dormant tools only. No Blender, Unreal, MCP, PIE, or render was run, per the brief (`E:/PussStage/Docs/Conductor/codex_briefs/w_q3_p02ind_p06uv_scaffold.md:1-5`).

## A. P02 industrial retexture

- **Binary-proven:** all six requested mesh packages resolve `Front` to `MI_Billboard_Front`, `Flap` to `MI_Billboard_Flap`, and both `Timber` and `Edge` to `M_Wing_CanvasEdge_Master` v1. Their package import records point to the six FBXs under `DerivedAssets/FlatV3/Overnight/P02Industrial` (`Saved/CodexConductor/Q3_P02IND_P06UV_Scaffold_20261009/p02_uasset_string_audit.json:7-23`, repeated for the other five packages at `:27-123`).
- **Binary-proven + measured:** both billboard MIs reference `T_BB_Colour/Mask/Normal`; their package strings point to the placeholder PNGs, whose IHDR dimensions are 64×64 (`p02_uasset_string_audit.json:127-213`). Therefore the earlier 640×900 values are review-cell dimensions, not the live texture sources. The audit itself already called the industrial pixel density non-meaningful and current mips/winding UNCLEAR (`E:/PussStage/Saved/CodexFlatV3/p02p03_audit/AUDIT.md:19,35,41-74`).
- **Measured:** suitable on-disk CC0 sources are POT: `IndustrialPaintedSteel/FlakingPaint` 2K, `IndustrialZinc/WeatheredGalvanised` 2K, and `IndustrialTarp/GrimyPlastisolCanvas` 4K (`E:/PussStage/DerivedAssets/TextureLibrary/library.json:680-748,759-827,984-1057`). `source_plan()` re-opens every selected JPG and rejects non-square, non-POT, or sub-2K input (`Saved/CodexConductor/Q3_P02IND_P06UV_Scaffold_20261009/p02_industrial_retexture.py:54-65`).
- **Measured:** the pure-FBX winding probe found at least one non-outward/mixed Edge section in every requested mesh/LOD family (`Saved/CodexConductor/Q3_P02IND_P06UV_Scaffold_20261009/p02_edge_winding_FenceTarp_L.json:4-26`; equivalent five reports beside it). Therefore Edge v3 is held and the tool leaves Edge unchanged, emitting `REBUILD_OUTWARD_EDGE_WALLS_BEFORE_EDGE_V3` (`q3_defaults.py:35-42`; `p02_industrial_retexture.py:112-118,157-164`).
- **Declaration-proven scaffold:** `p02_industrial_retexture.py` provides confirmed DRY/APPLY/REVERT, create-only texture import, FromTextureGroup mips, POT source gates, dedicated per-profile MIs, exact dirty scope, pre-change mesh backups, named saves/readback, and non-destructive REVERT retaining created assets (`p02_industrial_retexture.py:102-181`).
- **UNCLEAR / blocker:** `/Game/Scenes/Wings/PaintedSurface/Industrial/M_Wing_IndustrialTiling_Master` is an explicit prerequisite and was not found in the binary audit. Conductor must author it with `BaseColorTexture`, `NormalTexture`, `RoughnessTexture`, `AOTexture`, `TileSizeCmU/V`, sampling UV1 metres. DRY intentionally refuses until it exists (`q3_defaults.py:20-31`; `p02_industrial_retexture.py:109-115`).

## B. P06 Wing 044 burn UV

- **Measured saved-state:** the later RZSW record supersedes the relayout snapshot: Wing 044 L is now `SM_FlatV3_P06_rf_26_concrete_panel_wood_L_t5p` (`E:/PussStage/Saved/CodexFlatV3/rzswap/rzswap_originals_P06_RZSW-20261007-114344.json:1668-1697`), matching the current P06 FX guard (`Saved/CodexConductor/P06FX_20261008/p06_fx_defaults.py:33-34`).
- **Measured:** pure binary-FBX UV0 read shows LOD0 `Front` (material 0) and `Flap` (1) planar in Y/Z with maximum residuals 3.05e-8 to 3.32e-8. `Timber` (2) is deliberately tiled/non-planar at 3.807/8.502; `Edge` (3) is planar. LOD1 Front/Edge remain planar while Timber is non-planar (`Saved/CodexConductor/Q3_P02IND_P06UV_Scaffold_20261009/p06_wing044_uv_audit.json:5-203,209-353`).
- **Measured cause:** the rejected probe iterates *every* vertex instance without material-section filtering, then demands one global Y→U/Z→V fit (`Saved/CodexConductor/P06FX_20261008/p06_wingburn_mi.py:105-119`). Its large residual is caused by pooling the tiled Timber section, not by Front/Flap.
- **Recommended (inferred, no mesh change):** add `UseBurnLocalPlanar` to both allowed billboard masters, and feed only the burn-distance branch from `TransformPosition(AbsoluteWorldPosition, World→Local)`. For this mesh, initialize the child MI with `BurnU = LocalYcm * -0.002920604825 + 0.0209960942` and `BurnV = LocalZcm * 0.000985839843 + 0.00708007855`; expose the two scales and offsets as scalar parameters. Front and Flap fits agree, so one parameter set covers both. Keep SkinColor/normal sampling on existing UV0. Also change the DRY probe to measure only requested Front/Flap polygon groups. This is more LOD-stable than rebuilding.
- **Alternative (inferred):** after an approved bake, rebuild UV1 as planar metres (`U=Y/100`, `V=Z/100`) for Front/Flap only, retaining box-mapped Timber/Edge as required by Flat V3 (`Docs/FlatV3Spec_2026-09-30.md:160-165`). Do not rebuild merely to clear the current false-negative.

## C. P06 real scaffold

- **Measured source inventory:** the blend is 3 bays × 4 lifts, 8.4×1.5×10 m, 9,752 triangles, nine procedural/no-image materials, procedural alpha net, and 12 point lights that do not import (`E:/PussStage/DerivedAssets/FlatV3/Review_2026-10-07/p06_plan/README.md:54-70`). The recommended 2-bay width is 5.6 m because 8.4 m exceeds the 6.5 m slot (`README.md:69`).
- **Measured replacement rows:** the guarded plan targets Wing 033 L/R, Wing 045 R, and OLD 23 R—the four remaining SteelScaffold sides (`E:/PussStage/Saved/CodexFlatV3/p06relayout/relayout_plan_offline.json:180-202,600-621,833-858`). The installer refuses any cue GUID or current-mesh drift (`q3_defaults.py:64-70`; `p06_scaffold_install.py:72-83`).
- **Declaration-proven scaffold:** `scaffold_bake.py` provides headless create-only 2K BaseColor/Normal/Roughness/NetOpacity baking; `scaffold_export.py` produces 2/3-bay UE-frame FBXs with four canonical slots and LOD1; `p06_scaffold_install.py` imports create-only, defaults to 2-bay, blocks 3-bay without explicit oversize approval, preserves panel transforms/facing, backs up Show+level, materializes only P06, performs named saves/readback, and REVERT retains imported assets. Source point lights are excluded; Rig owns later real-light attachments (`scaffold_bake.py:1-87`; `scaffold_export.py:1-119`; `p06_scaffold_install.py:86-174`).
- **UNCLEAR / blockers:** Blender scripts were not run; baked maps, FBXs, and four scaffold MIs do not yet exist. Source-object filtering, atlas UV uniqueness, LOD grouping, 1.5 m route overlap, net shimmer, material appearance, and rendered acceptance all require the ordered DRY/visual gates below. The preview is a diagram, not a render (`Docs/Conductor/Q3_P02IND_P06UV_Scaffold_20261009/scaffold_plan_preview.svg:1-22`).

## Ordered conductor run

1. Author the missing industrial master; run `p02_industrial_run.py` DRY, review, then set `APPLY P02IND`. Do not enable Edge v3 until outward walls are rebuilt.
2. Conductor changes the burn material graph and section-scoped probe above; rerun `p06_wingburn_mi.py` DRY before APPLY.
3. Run `scaffold_bake.py` DRY then APPLY headless; visually approve four PNGs.
4. Run `scaffold_export.py` DRY then APPLY headless; validate FBX slots, LODs, frame, bounds.
5. Create the four configured scaffold MIs from approved maps; run `p06_scaffold_run.py` DRY, inspect overlap/placement sheet, then APPLY.

## Verification

- **Measured:** offline harness: 23 tests, 0 failures, 0 errors; positive and negative controls cover POT sources, uasset bindings/64 px placeholders, UV sections, mixed winding, confirmations, drift, oversize, offline imports, and deletion prohibition (`Saved/CodexConductor/Q3_P02IND_P06UV_Scaffold_20261009/test_q3_offline.py:1-70`; `offline_harness_report.json:1-7`).
- **UNCLEAR:** no saved Unreal readback, runtime component state, Blender bake/export, or rendered result exists because those applications were expressly prohibited.
