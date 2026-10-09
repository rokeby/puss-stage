# P34 — I2 sleight: a camera MOVE-IN instead of the hard cut (Codex, offline)

Read `_house_rules.md` first; every rule applies (worktree, offline only, DRY/APPLY/REVERT, harness with -/+ controls,
proof tiers, Gary's values in args with previews, <700-word final message).

## What Gary asked (9 Oct, after his I2 recording)
"the cut at 0.50.4 should be a camera move-in instead, to look more natural" — the sleight cut in
`/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips` at I2 frame **1250** (25 fps display; 50.0 s).

## The sleight (what must stay hidden)
Two identical curtain set-ups in two places; the cut swaps the audience from one to the other:
- **Hangar side** [0,1250): free camera "I2 Hangar Hold Camera" (P27; binding `55C3CAC6436730E6463F3A8220611E72`,
  level actor tagged `I2HangarHoldCamera`) at (13393, 78777, 510) cm, yaw -43.57, pitch 0, HFOV 50, focus 2441 cm,
  looking at the hangar drape (GeometryCache spawnable "Sleight Hangar Drape", hung centre (15161.66, 77094.5, ~510),
  yaw -43.57). **No transform track yet.**
- **Mouth side** [1250,2226): "I2 Sleight Mouth Camera" (binding `E6CF63464549232FD6CEA88D81178F0D`), transform track
  "CurtainSleight (Conductor)" keyed constant (-2167.135, 160000, 444.866) over [0,2226], plus CameraComponent child
  binding `A4162B8C4B7F601B6D73BF97DB42FD91` with CurrentFocalLength / ManualFocusDistance (1378.8) float tracks.
  Mouth drape "Transition Drape (baked)" hung centre ~(-1, 160000, 520), facing -X (camera yaw 0).
- Both drapes carry the same animated boy gobo (two spots, MPC "ShadowGobo Frame (Conductor)" root track) — the spot
  sits ~2860 cm behind/above each drape on its axis, so the shadow is mirrored identically [measured: probe
  I2PROBE-222723 + I2ORDER record]. Do NOT touch spots, their light_function_material, or the MPC track.
Evidence: `Saved/CodexConductor/I2HangarCam_20261009/i2_hangar_cam_record.json`,
`Saved/CodexConductor/I2Order_20261008/i2_order_record.json` (snapshot_after), `.../i2_drape_probe_I2PROBE-222723.json`.

## Design to build (defaults in args; Gary judges previews)
A cloth-on-cloth match cut hidden inside a push-in:
1. Hangar camera: hold until `move_start` (default 1150), then ease (cubic in-out) straight along its view axis toward
   the drape until `close_distance_cm` (default 600) from the drape plane at frame 1249/1250. Add a transform track
   to the EXISTING binding 55C3CAC6 (look it up; never add_possessable a bound actor — rule 9).
2. Cut stays at 1250 (do not move the cut section boundary).
3. Mouth camera at 1250 starts at the MATCHED pose: same distance from its drape plane, same height relative to the
   drape centre, same HFOV and focus as the hangar camera's last frame, so the two frames are interchangeable; then
   `mouth_after`: "EASE_OUT" (default: cubic ease back to its current hold pose over `ease_out_s`, default 6 s) or
   "HOLD_CLOSE". Rewrite only the mouth transform/lens/focus keys from 1250 onward; keys before 1250 unchanged.
4. Focus tracks follow the distance (manual focus = distance to drape plane). Focal length: compute from HFOV 50 and the
   camera's sensor (read it in DRY); assert both sides equal at the cut.
5. Guard: the drape bounds must fill the frame at close distance (no pelmet/frame/floor edge in view): compute it
   offline from the drape extents in the records and refuse args that would show an edge.
Previews (offline, analytical): a plan-view diagram of both camera paths + per-frame frame-coverage cards at
1150/1200/1249/1250/1300/1400 for both sides.

## Tool contract
`Saved/CodexConductor/I2SleightMoveIn_20261009/i2_sleight_move_in.py` + args/request/runner, DRY/APPLY/REVERT
(confirm "<MODE> I2MOVEIN"), record + Backups/PreI2MoveIn-<run> (sequence .uasset only), census exactly
{LS_Interaction_02_Turnips}, save that one package, read back every key (float32 tolerance), marker
`I2_MOVE_IN_<MODE>_OK|run=..`. Guards: refuse if the cut is not at 1250, if binding GUIDs differ, if the mouth
transform keys differ from the recorded constant, or if anything else in I2 changed since DRY (hash the snapshot).
Harness: fake-Unreal with negative controls (moved cut, rebound camera, edge-in-frame args, PIE running, dirty census,
existing hangar transform track) and a positive APPLY->REVERT round trip.
