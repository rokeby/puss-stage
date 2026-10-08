# P22: S3 shroud hessian material (weave tile + per-shroud stain overlay)

Requested by Gary, 8 Oct, via the finishing-touches session ("sure" + "actually send it to codex?"). Mode: `--worktree`, OFFLINE ONLY. Report to the finishing-touches session (Conductor 5 coordinates).

## House rules (paste into every brief)

1. **Worktrees only for code** (`--worktree`). Never write the main tree `E:\PussStage`; the conductor reviews,
   copies and commits. Never `git stash`, never `git commit -a`.
2. **No editor unless the brief grants a slot.** With `--unreal`: if PIE is running, STOP and report. Never end PIE,
   never run stop/quit/relaunch scripts, never close or restart the editor; a "PIE check" only READS the log
   (memory codex-unreal-must-not-end-pie). One editor writer at a time; the conductor hands out slots.
3. **Tool shape.** DRY → APPLY (confirm string) → REVERT. Record + `Backups/Pre<Thing>-<run>` BEFORE any change.
   Exact dirty-package census before and after; save only the named packages, never Save All. Read back, then save,
   then read back again. The success marker comes only after the asserted read-back, and carries a run id.
4. **UE 5.8 traps** (each has bitten us): never delete nodes on existing materials (editor crash); values read in the
   same call as an import or build lie, so verify in a later call; `get_marked_frames` returns a sorted copy, so
   delete by `find_marked_frame_by_label`; float channel read-back needs ~1e-4 tolerance; set_collision_enabled
   alone doesn't persist; in PIE use `unreal.load_asset`, not EditorAssetLibrary; no deferred spawn in PIE Python.
5. **Harness first.** Every tool ships with an offline harness that has negative AND positive controls, and seeded
   mutations it must catch. Report pass counts.
6. **Mark uncertainty per claim:** declaration-proven / binary-proven / measured / inferred, with `file:line`.
   Unmarked reports are rejected.
7. **Look/creative values are Gary's.** Defaults go in args; nothing look-changing is applied without his yes.
9. **Editor sky stays hidden** (Gary, standing rule): after any editor restart run
   `Saved/CodexConductor/editor_sky_toggle.py` (hide=true, transient, saves nothing). Leave the editor that way.
8. **Kill your process tree on stop** (codex.exe outlives its wrapper; memory codex-orphan-processes).

## Inputs (all on disk)
- Fuser output, unzipped: `Saved/CodexConductor/fuser_specs/hessian_stains_20261008/`
  - `hessian-stains-1-burlap-texture-close-up.jpg` (2048², WEAVE TILE: the half-offset seam test is clean [measured by eye at 1:1, finishing-touches 8 Oct]). Use this one.
  - `hessian-stains-2-…` has a visible horizontal seam: do NOT use it as the tile.
  - `hessian-stains-3…8-*.jpg` (2912×1440): six STAIN layers on plain hessian, each to be stretched ONCE across a shroud (not tiled).
  - the prompt: `Saved/CodexConductor/fuser_specs/s3_shroud_hessian_2026-10-08.txt`; the seam tests are `hessian_stains_sheet.jpg` and `weave_seam_closeup.jpg` in that folder.
- The current shroud material: the shore cast's sacks use `/Game/Metahuman/ShoreCast_20260910/Sack/Materials/MI_Sackcloth_OldGrey_Cloth_v3` (and `M_ShoreLinen`), per `Saved/CodexConductor/s3_sack_livecloth_apply_record.json`. Install / material tools: `Saved/CodexConductor/s3_sack_install.py` (+ `s3_sack_install_mat_record.json`). Read these to learn the mesh UVs, slot names and how the MI is applied. Do NOT edit them.

## Work
1. **Stain maps (offline, Python + PIL/numpy).** Each stain image has its own fine hessian weave printed under the stains. Laid over the weave tile, that would read as a double weave. For each of 3–8, produce:
   (a) `T_Shroud_Stain_0N_Tint` (sRGB): the stain's colour/darkening as a MULTIPLY map, with the base hessian removed: estimate the plain-cloth colour (e.g. a large-radius median or percentile of unstained areas), divide it out, and low-pass at about the weave period so the weave is gone but the tide-line edges stay crisp. Neutral = 1.0 → store mid-grey-normalised or plain 0–1 with documented decoding.
   (b) `T_Shroud_Stain_0N_Mask` (linear): the stain amount 0–1 (wet/greasy areas), plus a channel for soot (grey-black smears) and one for holes/darns if separable (else leave darns in the tint).
   Validate per map: weave energy at the weave frequency (FFT) is down at least 10× from the source; the tide-line edge sharpness is kept (gradient percentile); the unstained area is ≈1.0 ± 0.03. Write 4 preview composites per stain map (weave tile × stain tint), at 1:1 and full-shroud scale, plus a contact sheet.
2. **Material spec (create-only):** master `M_Shroud_Hessian` + `MI_Shroud_Hessian_0N` (one MI per stain map). BaseColor = weave tile (UV × WeaveTiling) × stain tint (UV0 × 1, + per-MI StainOffset/StainRotate params so a shroud can take a random crop). Roughness: base ~0.85, lower (~0.45) where the wet/greasy mask is set, higher in the soot. A normal map from the weave tile (generate one offline: height from luminance, document the strength) with tiling. Params for every value. Follow the project's create-only material pattern (`Saved/CodexConductor/S3Millstone/s3_props_ue.py` material_specs/BUILD_MAT; never edit nodes on existing assets).
3. **UE tool** `Saved/CodexConductor/ShroudHessian_20261008/shroud_hessian_ue.py`, NOT run: modes IMPORT_TEX (create-only, with read-back in a later call), BUILD_MAT, MAT_CHECK (later call), and APPLY / REVERT, which assign `MI_Shroud_Hessian_0N` to the shroud slot on the S3 shore cast, giving different MIs to different actors from a seeded shuffle. Record + backup first, a census, save only the named packages, read back. The live sack setup (live cloth, follower BP) must keep working: change only the material slot, and prove nothing else changes. Harness with positive and negative controls and seeded mutations.
4. **Report:** files (file:line), harness counts, the validation numbers per stain map, the preview sheet path, and every inferred item. The conductor runs the editor steps later; Gary approves the look from the previews first.

## Deliverable
Commit in your worktree; write a patch or file list for the conductor to copy into the main tree. Textures and previews go in `Saved/CodexConductor/ShroudHessian_20261008/` (in your worktree, plus a copy of the PNG outputs to that same path in the main tree is OK since `Saved/` binary outputs are not tracked; say exactly what you copied).
