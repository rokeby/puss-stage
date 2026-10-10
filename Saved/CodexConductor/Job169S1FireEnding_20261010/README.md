# Job 169 — S1 camera pan to a small corner-wing fire

Offline-authored only. Nothing in this bundle has run in Unreal. It supersedes
Job 168's animal scale fade: **the animals are not bound or changed at all**.
Their existing Klara-authored hide/exit remains underneath the camera move.

Only `/Game/InfinityStage/Dev/Sequences/LS_DevScene_01` is save-eligible in
Stage A. Klara's copied sequence and `L_Animals` are hash-guarded; no level is
ever saved.

## Reviewed timing (S1 local, 25 fps)

- frame 3559: wrapper camera takes over from Klara's exact source frame 3666;
- `[3559,3634]`: three-second eased pan to `SM_R__Wing_2_Animals5`;
- frame 3570: small `NS_Stylish_Fire_1` and warm point light spawn;
- `[3570,3590]`: fire scale and light intensity ramp up;
- `[3634,3900)`: hold on the corner-wing fire;
- `[3800,3838]`: Job 29 rig lights fade out;
- frame 3899: last valid S1 frame; 3900 is the exclusive end.

The fire and its warm point light remain through frame 3899. They are the last
light after the hangar rig fades; both despawn and are hidden at the S1 boundary.

## Camera precedence

Nested camera cuts outrank root cuts. Stage A therefore splits only the
wrapper's Klara shot section at 3559. The tail continues Klara's animation with
hierarchical bias `-1000`; the wrapper-owned spawnable camera's root cut then
wins through the end. Klara's sequence is neither edited nor saved. DRY refuses
unless 3559 maps exactly to her integral frame 3666, so the first camera key can
copy her transform and lens without interpolation ambiguity.

## Ordered DRY / APPLY

For every call, edit `job169_args.json` with the named `stage`, matching `mode`,
and `confirm: "<MODE> JOB169"`; then send `job169_request.json` through guarded
project Python. Use one run id for a reviewed DRY/APPLY pair.

1. `CAMERA_FIRE` DRY. Inspect chosen wing bounds, exact source-camera sample,
   analytical 30–50% framing, negative tail bias, and zero dirty packages.
2. `CAMERA_FIRE` APPLY. Require `JOB169_S1_FIRE_ENDING_APPLY_OK` and
   `klara_saved=0|levels_saved=0`.
3. `LIGHTS_OUT` DRY/APPLY. Require `[3800,3838]`.
4. `SHRINK` DRY. Review its exhaustive at/past-3900 inventory, then APPLY.
5. `VALIDATE` DRY. Require `JOB169_VALIDATE_OK`, Show/Master equality, camera
   coverage `[3559,3900]`, two continuous Klara wrapper sections, three owned
   spawnables, bHidden-bound visibility, the three hangar holds ending at 3900,
   unchanged Klara hashes, and zero dirty packages.

Also run `InfinityStage.Editor.SavedMasterMatchesShow` and the sequence binding
resolver. A spawnable camera is intended to resolve in the show level, but that
still requires the live resolver and PIE proof.

## REVERT (strict reverse order)

1. `SHRINK` REVERT.
2. `LIGHTS_OUT` REVERT.
3. `CAMERA_FIRE` REVERT.

Each mutating stage writes a transaction and `Backups/Pre...` copy before its
first mutation. Never Save All. A refusal after an in-memory mutation means a
Don't-Save restart followed by record inspection.

## PIE stills plan (later)

- 3550: Klara's camera immediately before takeover;
- 3600: pan under way, fire beginning, animals disappearing off-camera;
- 3650: pan settled, corner wing/fire composition;
- 3700: held fire composition;
- 3800: first lights-out frame, fire still legible;
- 3899: last valid S1 frame, fire as the last light; separately verify next-cue
  camera ownership at the exclusive frame-3900 boundary.
