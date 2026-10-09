# P72 — Cue Book stills: tolerate live motion, skip a failing segment (Cueing stream; offline, medium effort)

Read first: `_house_rules.md`; `Tools/CueBook/unreal/cuebook_stills_driver.py` (+ its harness
`Tools/CueBook/test/test_cuebook_stills.py`); `Saved/CodexConductor/scene_stills.py` (the gates it imports: luma settle,
post-capture probe, frame restore). Dedupe: no tolerance/skip exists in either.

Measured (Conductor 5, run CBSTILLS-20261009-153346): FAILED at S3 with `post_capture_drift 39.3 vs settled 36.9`,
then `frame_not_restored;child_failed_S3`. 8 segments were captured OK before it (62 PNGs, not published). Census clean.
S3 has live cloth and fire flicker, so a strict pixel-stability gate can never settle there.

## Build (driver side; change scene_stills.py only if unavoidable, and then as a separate diff in your report)

1. **Per-segment tolerance:** args `drift_tolerance` (default as today) and `drift_tolerance_by_segment`
   (e.g. `{"S3": 4.0}`), plus `accept_motion_drift` (default true): when the post-capture probe differs from the
   settled frame but the master frame is still on target and the camera pose is unchanged (the drift is scene motion,
   not a camera move or a stale frame), accept the capture and record `motion_drift=…` in the manifest.
2. **One failing segment = report + skip:** a segment that still fails is recorded as
   `{"segment": "S3", "status": "skipped", "reason": …}` and the run continues; the run's marker becomes
   `CUEBOOK_STILLS_OK|…|skipped=S3` (or `CUEBOOK_STILLS_PARTIAL`), never a whole-run failure for one segment.
3. **Frame restore is guaranteed** on every exit path (success, skip, error): scrub back to the starting master frame
   in a finally path, and the run FAILS only if that restore fails (that's the one hard gate). The census check stays.
4. The publisher (`Tools/CueBook/publish_stills.py`) publishes the good segments of a partial run and lists the
   skipped ones; never deletes an existing still for a skipped segment.

## Harness

Extend the fake-transport harness: a segment whose probe drifts by motion only is accepted with `motion_drift`;
a segment whose camera pose changed is still rejected (negative control); a failing segment is skipped and the next
one is captured; restore runs on every path and a failed restore fails the run (negative control); the publisher
handles a partial run. Keep 24/24 existing passing. If git cannot commit (index.lock), leave the files and list them.
