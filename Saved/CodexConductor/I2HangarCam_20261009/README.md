# P27 — I2 hangar hold camera

This bundle is offline-authored and has not been run in Unreal. It creates one
free world `CineCameraActor`, then changes only the I2 camera-cut binding IDs for
the hangar side `[0,1250)`. It never edits or removes the old hangar-camera
binding or its tracks.

## Evidence boundary

- **declaration-proven** — the requested save scope is exactly
  `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` plus
  `/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips`; see
  `Docs/Conductor/codex_briefs/p27_i2_hangar_hold_camera.md:20-29`.
- **measured (upstream, not re-measured here)** — Conductor 5's 9 Oct evidence
  reports the I2 display/tick rates, `[0,2226)` playback, the live cut at frame
  1250, the bad attached-camera PIE pose, and the successful 18:02 free-camera
  framing; see the brief at lines 16-17 and its named Saved/Captures evidence.
- **inferred** — using an unattached camera should remove the inherited
  sunk/tipped hangar-root transform. Only the requested post-APPLY PIE stills can
  prove the rendered result.
- **measured (offline)** — `test_i2_hangar_cam.py` currently passes 19/19 fake-
  Unreal controls; `harness_result.json` is the machine-readable result.

`preview_plan.png` and `preview_frame.png` are analytical cards generated from
the args, not scene renders. Gary's already-sent `GOBOREVIEW-20261008-180257`
stills remain the creative reference.

## Files

- `i2_hangar_cam.py` — DRY/APPLY/REVERT implementation.
- `i2_hangar_cam_run.py` + `i2_hangar_cam_request.json` — project-Python route.
- `i2_hangar_cam_args.json` — every pose/lens/focus choice.
- `test_i2_hangar_cam.py` — fake-Unreal positive, negative, and seeded-mutation harness.
- `make_previews.py` — regenerates the two PNG framing cards from the args.

## Slot run order

1. With PIE stopped, Sequencer closed, the vertical-slice world current, and the
   editor package census empty, inspect `i2_hangar_cam_args.json`. Regenerate the
   analytical cards offline with `python make_previews.py` if Gary changes a
   framing value.
2. Set a unique `run_id`, keep `mode: "DRY"` and
   `confirm: "DRY I2HANGARCAM"`, then send `i2_hangar_cam_request.json` through
   the guarded `ExecuteProjectPythonFile` route. Require
   `I2_HANGAR_CAM_DRY_OK`, `live_cut=1250`, `apply_ready=1`, a clean census, and
   inspect the DRY JSON. Gary's 18:02 rendered stills have already been sent.
3. Without any intervening I2/gobo/order edit, change only the mode, confirm and
   run id to `APPLY`, `APPLY I2HANGARCAM`, and a fresh id. Run the same request.
   Require `I2_HANGAR_CAM_APPLY_OK`; it reports the backup, record, exact two
   saves, read-back HFOV, cut count, and `unattached=1`.
4. Run these focused editor tests singly and require each to pass:
   `InfinityStage.Editor.SavedMasterMatchesShow`, then
   `InfinityStage.Editor.SceneCutBindingsResolve`.
5. Start the conductor-owned PIE still slot. For `scene_stills` use passage
   `"I2"` and fractions below (I2 is 2226/25 = 89.04 s); they correspond to
   2.7, 4.5, 6.2, 8.0, 10.7 and 50.4 seconds:

   ```json
   {"passage":"I2","fractions":[0.03032345,0.05053908,0.06963163,0.08984726,0.12017071,0.56603774],"label":"hangar-hold"}
   ```

6. Gary judges those six rendered stills. Do not promote the change from saved
   read-back to visual acceptance without that review.

## Revert

With a clean editor and no intervening change, set a fresh id plus
`mode: "REVERT"` and `confirm: "REVERT I2HANGARCAM"`, then send the same
request. REVERT first verifies the state and DRY guard hashes, makes
`Backups/PreI2HangarCamRevert-<run>`, restores the original cut binding IDs,
removes only a binding it created, destroys only the tagged actor, saves only
the two named packages, and requires exact read-back. If the gobo/order state
changed, it stops with `GUARD_CHANGED_SINCE_DRY`; coordinate the change rather
than overwriting it.
