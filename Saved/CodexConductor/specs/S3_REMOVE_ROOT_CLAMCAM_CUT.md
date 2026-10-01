# Remove the retired root ClamCam1 cut section from LS_DevScene_03 (Conductor 3, 1 Oct)

Why: S3 beats run 150947 deactivated the root ClamCam1 cut [81,1501]. The handoff builder and
FindSceneCameraCut ignore IsActive (Look & camera, declaration-proven), so the rematch ends the
Entry at 81 while S3 Wide starts at 95; the coverage gate (active cuts only) refuses with gap
[81,95] (rematch STOPPED, nothing saved). Gary asked for the old clam sequences to be
disregarded. Remove ONLY that one camera-cut SECTION; keep the ClamCam1 binding and every
other track and section. The nested LS_Clams ClamCam1 cut stays deactivated, untouched.

Tool `Saved/CodexConductor/s3_remove_root_clamcam_cut.py`, dry / apply / revert modes, wrappers +
request jsons (house pattern of `Saved/CodexConductor/s3_beats_apply.py`, reuse its helpers
incl. the suffix-stripped channel_row and camera_snapshot read rules).
- Find, in `/Game/InfinityStage/Dev/Sequences/LS_DevScene_03` ROOT camera-cut track, sections
  whose camera binding resolves to the binding displayed 'ClamCam1'. Refuse unless exactly one,
  it is INACTIVE, its range is [81,1501].
- Record: its range, active flag, binding GUID, plus a fingerprint of every other cut section
  and every binding (suffix-stripped channel names).
- Backup `Backups/PreS3RemoveClamCut-YYYYMMDD-HHMM` (LS_DevScene_03.uasset).
- Apply: `cut_track.remove_section(section)`; read back: no cut section points at ClamCam1;
  every other cut and binding fingerprint unchanged; the ClamCam1 binding still exists.
  Census must be exactly content [LS_DevScene_03], maps []; save_asset that one; post census empty.
  `S3_CLAMCUT_DONE|run=..|applied|backup=..|census=..`. Dry: `S3_CLAMCUT_DRY_RUN_OK|run=..|mutated=0|plan=..`.
- Revert: re-add a camera-cut section bound to the recorded GUID with `set_range` in ONE call,
  set inactive, read back, save.
- Offline harness `test_s3_remove_root_clamcam_cut.py`: + case; − cases: two matches; active
  section; wrong range.
THIS PASS: write tool + harness, run the harness ONLY. Nothing in the editor. Commit nothing.
Crash rules: no Sequencer UI/evaluation, no SequencerTools, no get_bound_objects with open
ranges, no unreal objects in module globals, no reload, no PIE, no Save All.
