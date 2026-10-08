# P22b: S2 shrine hookin: bake mismatched XY camera keys, resolve CineCameraActor2, fix the camera preview
Live DRY KLARAHOOK-20261008-171230 (8 Oct, conductor) [measured], args klara_hookin_s2_args.json, tool
Saved/CodexConductor/KlaraIngest/klara_hookin.py (your P22 version, committed):
- REFUSAL: S2 REKEY_NOT_EXACT: CineCameraActor XY_KEY_TIMES_DIFFER (x 8 keys, y 8 keys at different times),
  CineCameraActor2 (x 9 keys, y 7 keys). A rotation needs X and Y at the same times.
- REFUSAL: CAMERA_PREVIEW_UNRESOLVED: CineCameraActor2 CAMERA_LOCATION_UNRESOLVED.
- Accepted: NO_FIT_ACCEPTED 378 <= 400; warnings TALLER_THAN_LATTICE, LENGTH_OFF_GRID.
- The preview klara_hookin_s2_topdown.png draws the hangar (blue) and her footprint (red) as axis-aligned boxes and
  her ONE camera far outside both (top right), pointing away. That is almost certainly wrong frame math (her camera
  should be in or near her set), OR her cameras are attached to a rig whose keys are relative.
Job (offline):
1. For any world-space binding whose X/Y key times differ: BAKE X and Y (and yaw if it's rotated) at EVERY display frame
   over the binding's keyed range by evaluating the channels (use the channel's own evaluation, not linear re-
   interpolation of keys), then rotate.
   - Report the max deviation between the original and baked curves at sub-frames (harness).
   - Keep the interpolation smooth: AUTO or LINEAR at per-frame density.
   - REVERT removes the copy as before.
2. CineCameraActor2: find out WHY its location is unresolved (attached? spawnable with a parent? keys on a child
   component?) by reading LS_NEW_SHRINE offline (bytes) + the live DRY report klara_hookin_s2_dry.json. Handle that
   case correctly, attached = do not rotate, or rotate the parent.
3. Preview: draw BOTH cameras' full paths (polyline of the keyed positions after rotation), each with a frustum at its
   first key; draw the hangar and her footprint in the SAME world frame, ROTATED (the hangar yaw 316.43). Assert in
   the harness that the camera path lies within her footprint ± 10 m, else flag PREVIEW_SUSPECT.
4. Harness -/+ controls (mismatched key times; attached camera; preview frame).
Deliver Docs/Conductor/P22B_S2_CAMERA_REKEY_2026-10-08.md.
