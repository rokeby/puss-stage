# Codex job 109 — S3 figure diagnosis v2 (offline delivery)

## Outcome and proof boundary

- **declaration-proven:** `Saved/CodexConductor/s3_visual_diag_20261009.py` is now schema `s3_visual_diag/2`. It reads component visibility and render flags, all assigned shroud/T-shirt/shorts material chains, effective MI parameters, base-material flags, texture metadata, UV evidence, and foot bones (`Saved/CodexConductor/s3_visual_diag_20261009.py:167,304-424,536-573,646-686`).
- **declaration-proven:** it evaluates `/Game/Scenes/LS_Clams` at frames 300 and 2400 through a transient `LevelSequencePlayer` with restore-state, without opening editor Sequencer (`Saved/CodexConductor/s3_visual_diag_20261009.py:810-843`). It stops the player, destroys its transient actor, and requires dirty-package, actor, and figure-state censuses to be identical (`Saved/CodexConductor/s3_visual_diag_20261009.py:1200-1204`).
- **measured (offline):** Python compilation passed and the harness passed **4/4 positive + 5/5 negative = 9/9**. Positive controls include indexed Ground-B-style ray hit/miss checks; negative controls reject a save call and omissions of visibility, frame 2400, socket/bone discovery, and shading-model coverage (`Saved/CodexConductor/test_s3_visual_diag_v2_offline.py:75-108`).
- **UNCLEAR:** no Unreal call was made in this job. Therefore the identities of the no-visible-shroud and translucent figures, the material values, binding coverage, and foot depths are not yet measured. The existing `S3_VISUAL_DIAG_20261009.json` remains the live-run-1 v1 artifact until the conductor runs v2.

## What the live read must prove

- **declaration-proven:** for every shroud, T-shirt, and shorts assignment, `assigned_materials[]` records the base master plus `Material.blend_mode`, `shading_model`, `two_sided`, `opacity_mask_clip_value`, all effective texture/scalar/vector parameters, and child overrides (`Saved/CodexConductor/s3_visual_diag_20261009.py:304-424`).
- **declaration-proven:** every relevant cloth/outfit component records `visible`, `is_visible()`, `hidden_in_game`, `render_in_main_pass`, owner-hidden, and effective main-pass visibility at both requested frames (`Saved/CodexConductor/s3_visual_diag_20261009.py:167-220,846-878`).
- **declaration-proven:** foot discovery no longer depends only on `get_num_bones()`: it also inventories `get_all_socket_names()`, probes explicit MetaHuman/mannequin names, validates each with `get_bone_index()`, and records failure detail. Each valid world-Z sample is ray-tested downward against Ground B LOD0 triangles (`Saved/CodexConductor/s3_visual_diag_20261009.py:646-750`). Empty actor-frame samples make the run STOP after the JSON has captured why (`Saved/CodexConductor/s3_visual_diag_20261009.py:1179-1207`).

## Black / shiny / untextured hessian: exact reads

- **inferred diagnostic candidate:** overly glossy/dark response — read resolved Roughness/Specular-like MI scalars and the master shading model.
- **inferred diagnostic candidate:** missing/wrong UV channel — read mesh UV-channel count and each `MaterialExpressionTextureCoordinate.coordinate_index`.
- **inferred diagnostic candidate:** weave scaled out — read texture-coordinate `u_tiling`/`v_tiling` plus Tiling/Tile/UV/Scale/Weave scalars.
- **inferred diagnostic candidate:** wrong texture interpretation — read `Texture2D.compression_settings`, `srgb`, and `flip_green_channel`.
- **inferred diagnostic candidate:** transparency/culling mismatch — read `blend_mode`, `two_sided`, `opacity_mask_clip_value`, and opacity/alpha/mask parameters. These candidates and their JSON paths are emitted by the tool (`Saved/CodexConductor/s3_visual_diag_20261009.py:1021-1066`).

## Conductor run order

1. **declaration-proven:** with PussStage's correct editor world open, no PIE/SIE, run `Saved/CodexConductor/s3_visual_diag_v2_request.json` through the guarded project-Python MCP route.
2. **measured acceptance required:** require `S3_VISUAL_DIAG_V2_SUCCESS`, `foot_samples>0`, an explicit direct-binding count, and all three census flags equal 1; any unresolved direct binding remains marked UNCLEAR in the JSON (`Saved/CodexConductor/s3_visual_diag_20261009.py:1206-1212`).
3. **measured acceptance required:** read back `Saved/CodexConductor/S3_VISUAL_DIAG_20261009.json`; do not infer visual acceptance from transport success.
