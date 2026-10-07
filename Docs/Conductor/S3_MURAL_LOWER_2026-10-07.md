# S3 mural lower: 150 cm, bottom cropped by the floor (7 Oct 2026)

Gary (7 Oct, his words): "the mural image on the back wall in this scene [S3] can be lowered about 1.5m too,
cropping the lower part."

**Status: written OFFLINE. Not run in Unreal.** No MCP call, no commit. Offline harness: 14/0
(`Saved/CodexConductor/test_s3_mural_lower_offline_report.json`). A mutation control (the drop scaled
×0.9 inside the tool) made 9 of the 14 cases fail.

Tool: `Saved/CodexConductor/s3_mural_lower.py`, with `_run.py`, `_args.json` and `_request.json`.

Tiers used below: **[decl]** = declaration-proven, **[meas]** = measured, **[inf]** = inferred.

## 1. How the backdrop is placed

- **Actor, parent and mobility.** The actor is `S3 Backdrop`. It is MOVABLE and attached to `S3 Hangar Far Wall Above Exit`. **[meas]** `Saved/CodexConductor/S3Shore/s3_shore_live_reads.json` (run S3SHORE-20261007-181646).
- **Size and position.** Its root-local AABB is x 5997, y ±1000, z 115..3115. That is world z −5..2995 with the root at world (11421.97275, 160000, −120), unrotated. **[meas]** same file, `root` block.
- **Parent transform.** The parent is a Cube at world (17446.97, 160000, 1665) with scale (0.5, 21, 24.3), and it is attached to `S3 Hangar Root`. **[meas]** `s3_backwall_marble_dry.json` (run S3BWM-20261005-191401, `far_wall`).
- **Why the parent matters (the old squash).** On 3 Oct, `hangar_exit_doors.py` rescaled the parent with `_set_root_local` (`hangar_exit_doors.py:605-613`). It did not detach the child, so the plane was squashed to z 543..2973 at scale 0.81. **[meas]** `s3_backwall_marble_record.json` `before`. The cause was identified as `parent_rescale_squash` by `s3_backwall_marble.py:126-131`.
- **The restore.** The restore set the WORLD transform back and let UE recompute the relative transform. **[decl]** `s3_backwall_marble.py:449-452`. It was saved with a clean census. **[meas]** commit e2875c4, record `post_save_census`.
- **How this tool moves it.** The tool writes only `set_actor_location(world)` (`s3_mural_lower.py:528`). It never writes a scale and never touches the parent. The read-back requires:
  - relative location = ParentInverse(target), computed from the LIVE parent;
  - relative rotation and scale unchanged;
  - parent and root unmoved.

  **[decl]** `s3_mural_lower.py:298-336`.
- **Engine behaviour we rely on.** We assume UE stores a world move of an attached actor as relative = ParentInverse(world). **[inf]**: the engine `.cpp` is not on disk (memory ue58-engine-source-limits). The live read-back checks this on every run, and the harness simulates it under a rotated, non-uniformly scaled parent.

## 2. The exit-door mimic: a baked crop, not a world-position sample

- **How the mimic is made.** Its strategy is `cropped_texture_child_mi` (`hangar_exit_doors.py:182-256`, `:733-826`). It has three parts:
  - three cropped PNGs (SkinColor/Mask/Normal);
  - a child MI of `MI_S3_OpalBeach_Backdrop` with those textures;
  - a leaf mesh whose UV1 is hard-coded in backdrop metres for leaf z 0.055..4.545 m (`Tools/FlatV3/build_s3_exit_door_mesh.py:41-43`).

  The crop is computed for `BACKDROP_BOTTOM_Z_CM = -5.0` (`Tools/FlatV3/build_s3_exit_door_crop.py:27`). **[decl]**
- **So it does not follow the backdrop.** Lowering the backdrop by 150 cm leaves the leaf showing art 150 cm off: dv = −0.05 against the baked rect `[0.42525, 0.8485, 0.57475, 0.99817]`. **[decl + harness]** Our UV mapping equals `hangar_exit_doors._s3_leaf_uv_rect` before and after the move, and before the move it equals the manifest rect. Case `t_uv_matches_doors_tool`.
- **The leaf is retired.** Gary said "Close the wall" (5 Oct). `s3_close_back_door.py` (run S3DOOR-20261005-104600, record not reverted) then hid the `Exit Door Leaf` and `Exit Black` actors and added a visible `S3.BackDoorFill` patch. **[meas]** In `s3_backwall_marble_dry.json` (5 Oct 19:14), the leaf and black both read `hidden=True`.
- **What the tool does about it.** It does not re-crop. APPLY re-reads both flags live and refuses with `DOOR_MIMIC_VISIBLE_RECROP_REQUIRED` if either is visible. The post-save read-back fails with `DOOR_UNHIDDEN`. The new crop rect and a re-crop note are written to the record.
- **A guard already exists.** If anyone re-opens the door later, `hangar_exit_doors.py:224` already refuses a leaf/crop mismatch (`worst > 1e-9`). **[decl]**
- **Open question.** We do not know whether the parent MI also samples UV1 for detail; only the mesh is shown to carry UV1. This only matters if the door is re-shown. **[inf]**

## 3. Top edge: a 35 cm band of bare wall, which needs Gary's decision

- **Heights.**
  - Roof underside is world 2880 (local 3000). **[meas]** `s3_backwall_marble_dry.json` `roof`.
  - Side-wall and far-wall tops are also 2880. **[meas]** same file.
  - The backdrop top is currently 2995, so 115 cm of it is buried in the roof slab.
- **The band.** After a 150 cm drop the top is world 2845 (local 2965). That exposes bare far wall at local 2965..3000 (35 cm), full width, under the roof. **[decl: arithmetic on meas]** harness `t_base_plan`.
- **Where the band would be seen.** The listed S3 cameras sit at local (−500, 0, 300) with rpy 0, using 28 mm and 50 mm lenses. **[meas]** `s3_shore_live_reads.json` `cameras`. With the default filmback, these see up to about local 1850, which is well below the band. **[inf]**: the filmback and camera animation were not read. Wider or tilted shots would see it.
- **Lattice.** "S3 Hangar Lattice Fly" exists **[meas]** `Saved/CodexCameraPilot/probe_lattice_glow.json`, but no saved record gives its height. DRY lists every visible `S3 *` actor in local x 5000..6050, z 2700..3300 under `overhead_near_top`. Whether the lattice hides the band is UNCLEAR until DRY runs.
- **Gate.** By default APPLY refuses with `TOP_GAP_DECISION_REQUIRED`. There are two ways forward:
  - `"top_gap_policy": "accept"` keeps the 150 cm drop and the bare band;
  - `"drop_cm": 115` keeps the top flush with the roof underside and needs no decision.

## 4. Bottom edge: cropped by the floor

- **The crop.** The lowered bottom is local −35. Local −35..115 sits under the deck top. The deck spans local x 0..6000, which covers the plane at 5997. **[meas]** `s3_shore_live_reads.json` `S3 Hangar Deck`.
- **Without the deck.** If the planned `S3 Shore Ground` replaces the deck (x 0..6012 per manifest, **[decl]** `DerivedAssets/S3Shore/SM_S3_ShoreGround_manifest.json`), it covers the plane too. The tool refuses with `BOTTOM_UNCROPPED` if no visible floor reaches the plane.
- **Flag.** The bottom 35 cm then sits below the hangar's wall base (local 0). It is invisible when landed. It may poke past the box silhouette while the hangar hinges or sinks. **[inf]** Check this in the next PIE.

## 5. Safety in the tool **[decl, s3_mural_lower.py]**

- **Landed frame.** The target is composed in the LIVE root frame. The tool refuses unless the root is LANDED (±1 cm, rot 0, scale 1).
- **Guard box.** The result must lie inside the landed local guard box x 5990..6000, y ±1001, z −60..3120.
- **Write order.** Record first (exclusive), then the `Backups/PreS3MuralLower-<run>/` umap backup, then the write.
- **Refusals.** The tool refuses on any of:
  - a dirty census at the start;
  - PIE running;
  - the wrong world;
  - ZZ_/TEMP actors present;
  - children attached to the backdrop;
  - the backdrop not at local bottom 115 (already lowered).
- **Save.** Before saving, the census must be exactly `{content: [], maps: [WORLD]}`. The level is saved with `save_map`, and the census must be clean afterwards.
- **Read-back.** The tool reads back before the save and again from a fresh index after it.
- **REVERT.** It refuses on drift since APPLY. It restores the recorded relative location exactly, then reads back the relative location, world location and AABB.
- **Markers.** S3MURAL_<MODE>_OK only after all of the above; S3MURAL_FAILED otherwise.
- **Editor-crash rules.** No UE objects at module level, and a module-cache purge in the runner.

## Run order (each step is one MCP call: `Saved/CodexConductor/s3_mural_lower_request.json` via `Saved/CodexMocap/mcp_request.py`)

1. **DRY.** The args file ships as `{"mode":"DRY"}`. Expect `S3MURAL_DRY_OK|run=…`. Read `s3_mural_lower_dry.json`: `plan.top`, `overhead_near_top`, `door_mimic.baked_matches_now == true`, and `apply`.
2. **Gary decides the top.** Either `top_gap_policy: "accept"` with 150 cm, or `drop_cm: 115`.
3. **APPLY.** Set `mode: "APPLY"`, `confirm: "APPLY S3MURAL"` and the decision. Expect `S3MURAL_APPLY_OK|run=…|level_saved=1|dirty_after=0+0`.
4. **Check the result in a PIE still:** the doorway region, the top edge, and the hangar rise silhouette.
5. **If rejected,** REVERT: `mode: "REVERT"`, `confirm: "REVERT S3MURAL"`. Expect `S3MURAL_REVERT_OK`.
