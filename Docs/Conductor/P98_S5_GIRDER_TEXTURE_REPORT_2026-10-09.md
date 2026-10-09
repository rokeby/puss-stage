# P98 — S5 girder surface texture: offline tool and run plan

## Result and boundary

- **[measured]** Gary accepts S5's brightness and fog wash; the requested change is the exposed metal structure's surface only (`Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md:24`). This job does not change fog, brightness, exposure, lights, cameras, sequences, meshes or transforms (`Saved/CodexConductor/S5GirderTexture_20261009/s5_girder_texture.py:5-18,329-334`).
- **[measured]** Deduplication found a closer reusable precedent than building another Hyper3D-like graph: `M_UP_PaintedSteel` already samples rust colour/normal and chip noise, builds grime/chips/streaks, and adds procedural rivet normal detail (`Saved/CodexConductor/underpass_materials.py:5-17,337-388`). The paper-proscenium Hyper3D pipeline establishes the same useful three-map surface vocabulary — SkinColor, SkinMask, SkinNormal (`Saved/CodexFlatV3/paperprosc/rzimport_plan_paperprosc.json:41-58`).
- **[declaration-proven]** Therefore the implementation is create-only child MIs, not a duplicate material function or an edit to the shared master. The two new assets are `MI_S5_Girder_Rig` and `MI_S5_Girder_Hangar`; all look values live in the args file and remain Gary-reviewable (`s5_girder_texture.py:35-61,74-95,223-249`). `surface_preview.svg` diagrams those defaults but is explicitly not a render (`surface_preview.svg:1-28`). **[inferred]** If later non-UP mesh families need the same layer stack and cannot inherit this master, extract its existing logic into a new `MF_GirderAging` in a separate job; doing that now would duplicate a solved graph without a live need.

## Records/manifests census

- **[measured saved record; current live state inferred]** Structure 05 recorded 277 plate-girder, 94 laced-column and 184 knee-bracket instances, all using `MI_UP_Steel_Green` before the successful v3 swap (`Saved/CodexConductor/Girders_20261007/girders_v3_originals_GV3A-20261007-024125.json:1027-1085`). The record status is APPLIED and its plan names the v3 mesh family; a live DRY must still confirm those are the currently rendered meshes (`Saved/CodexConductor/S5GirderTexture_20261009/records_census.json:3-20`).
- **[declaration-proven; current saved state inferred]** The hangar builder declares lattice actors `S5 Hangar Lattice Beam NN` and `S5 Hangar Lattice Rail N`, built as scaled engine cubes with the burnished-steel material (`Saved/CodexStructure/hangar_build.py:55-59,120-140`). No current S5 build record contains a complete actor/material census, so exact beam/rail counts, meshes and current overrides are **UNCLEAR** until DRY. The tool refuses unless both families exist and records every exact actor/component/mesh/material row (`s5_girder_texture.py:98-111,170-220`; `records_census.json:21-36`).

## Tool contract

- **[declaration-proven] DRY:** requires the correct clean editor world, finds exactly Structure 05 and exact S5 lattice labels, reads managed mesh/material/instance state, refuses occupied create-only targets, and writes a run-stamped census (`s5_girder_texture.py:151-220,319-336`).
- **[declaration-proven] APPLY:** requires `APPLY S5GIRDERTEXTURE`; writes/fsyncs originals first, copies and SHA-verifies `Backups/PreS5GirderTexture-<run>/...umap`, creates two child MIs, updates only three Structure 05 material fields plus S5 beam/rail slot 0, materializes Structure 05, saves only the two MIs and the current level, then reads everything back and requires zero dirty packages (`s5_girder_texture.py:74-95,223-316,339-373`).
- **[declaration-proven] REVERT:** requires `REVERT S5GIRDERTEXTURE`, refuses assignment drift, takes a second level backup, restores every recorded material, materializes/saves/read-backs, and retains the two created MIs rather than deleting them (`s5_girder_texture.py:376-402`).
- **[measured offline]** Harness: 22/22, including positive and negative controls for mode/confirmation, look ranges, exact actor selection, missing families, read-back tolerance, drift, and dirty scope (`test_s5_girder_texture_offline.py:15-102`; `offline_harness_report.json:1-24`). No Unreal/editor/render proof exists; offline success is not visual acceptance.

## Ordered conductor run and stills

1. Set args to DRY; execute `s5_girder_texture_request.json`. Require `S5_GIRDER_TEXTURE_DRY_OK`, inspect `inventory`, and specifically confirm v3 rig meshes, nonzero beam+rail counts, current materials, one mesh component per lattice actor, and clean census. **[inferred pending live census]**
2. Set `{"mode":"APPLY","confirm":"APPLY S5GIRDERTEXTURE"}`; execute once. Require backup + originals record, `S5_GIRDER_TEXTURE_APPLY_OK`, exact saved read-back, and `dirty_after=0+0`. **[inferred pending run]**
3. With S5's existing fog/brightness/exposure untouched, capture paired before/after stills from the same saved S5 camera/frame: (A) Gary's noted bright cloud-scene wide, (B) a crop where Structure 05 plate girders/columns/knees read, (C) a crop of the hangar lattice, (D) a grazing-angle close view showing chips/rust/grime/rivet normal. Record camera binding, sequence frame, resolution and CVars; make one labeled A/B contact sheet. **[inferred review plan]**
4. Gary judges texture scale, rust amount, paint wear and highlight strength. Tune only MI scalar/vector defaults, then REVERT followed by a fresh create-only name if a second persistent variant is needed. Do not adjust S5 light/fog to make the material pass. **[inferred creative gate]**

## Open questions

- **[UNCLEAR]** Which exact structure subset was visible in Gary's E19 frame: Structure 05, S5 hangar lattice, or both. DRY inventories both; the before still identifies the visible subset.
- **[UNCLEAR]** Scaled cube UVs may make the hangar variant's texture frequency look too coarse or too busy. The separate hangar MI isolates that correction from the v3 rig MI; only the rendered A/B decides it.
