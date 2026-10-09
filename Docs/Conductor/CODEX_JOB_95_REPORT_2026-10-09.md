# Codex job 95 — Passage-to-Scene camera seam

Offline delivery, 9 October 2026. No Unreal or Blender process was opened.

## Verdict

- **[declaration-proven]** The existing CS v2 implementation already eases the
  route to its end and multiplies gait height/roll by an envelope that is exactly
  zero at the Passage boundary (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCameraRig.cpp:482-507`,
  `Plugins/InfinityStage/Source/InfinityStage/Private/MovieSceneInfinityPassageTrack.cpp:350-363`).
- **[declaration-proven]** It does **not** remove the bind-pose height bias during
  the walk: `StepGaitBob` applies `WalkWeight * RawLiftCm` as height, while only
  roll subtracts the running mean (`InfinityStageCameraRig.cpp:701-725`), and the
  adjacent comment explicitly says height keeps the bias (`:769-771`).
- **[measured, prior saved evidence]** The recorded P04 seam had the rig at
  `(10645.98,240000,158.74)`, roll `-2.551°`, and Entry at
  `(10668.47,240000,180)`, roll `0°`: **30.95 cm total**, comprising **22.49 cm
  forward + 21.26 cm up**, and **2.551°** rotation
  (`Saved/CodexCameraPilot/capture_crossing_pop_lit.py:22-29`).
- **[measured, prior report; not re-run here]** After CS v2, P01→S1 was reported
  as 0.36 cm forward / 0.42 cm up (0.55 cm total) and -0.004° on the last sampled
  rig frame (`Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:169-174`). This proves
  the old settle worked at that seam then; it does not prove current P03→S3.
- **[inferred]** E13 can therefore be a combination of (a) a newly stale saved
  Entry handoff, (b) the walk's visible bind-pose bias before the current
  one-second settle, and (c) Free Look being dropped at the hard cut rather than
  visibly returning before it. Offline data in this worktree do not contain
  current authoritative transforms for all six seams, so P02→S2 through P06→S6
  are deliberately **UNCLEAR**, not guessed.

## Delivered

`Saved/CodexConductor/Job95CameraSeams_20261009/camera_seam_tool.py` is one
DRY/APPLY/REVERT tool. It requires an exact census of six distinct Passage rigs
and six distinct tagged Scene Entry cameras. Each row records the evaluated
un-bobbed Passage-end transform/lens/focus, saved Entry values, deltas, and the
serialized settle duration. It normalises GUIDs with
`GuidLibrary.conv_guid_to_string`, never `str(FGuid)`.

APPLY, only after a clean DRY:

1. verifies zero dirty packages;
2. makes and SHA-256-verifies `Backups/PreJob95CameraSeam-<run>-<time>`;
3. writes a PREPARED record before mutation;
4. sets the six serialized settle durations (default **3.0 s**) and copies only
   each incoming Passage's evaluated end view to that Scene's Entry camera;
5. saves only `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
6. reads all six values back and requires zero remaining dirty packages.

REVERT takes the APPLY record, backs up the current level first, restores exact
recorded rig/camera/lens/focus values, saves only that level, and reads all six
back. The tool does not edit the Show or any sequence.

`Scripts/patches/2026-10-09_job95_bob_bias_and_free_look_settle.patch` is
**HELD, not applied, not built**. It:

- centres gait **height and roll** on the running mean, so the bind-vs-walk
  offset is not camera motion;
- changes the default crossing settle to 3 s (the live tool updates serialized
  actors);
- weights Free Look by the same Master-time settle envelope, reaching authored
  default before the Scene cut;
- adds automation controls for constant -15 cm bias, retained gait excursion,
  and full/half/zero Free Look return.

## Conductor order

1. Edit args to `DRY`, a fresh `J95-*` run, and `CONFIRM_JOB95_DRY`; execute the
   request. Archive the six-row record and inspect every delta, especially
   **P03→S3 at Master 13:43.6→13:43.8** (`LS_Choreo_Passage_3` →
   `LS_DevScene_03` / `LS_S3_HangarRise`).
2. Apply the held patch in a C++ backup/build window; build and prove its new
   UTF-16 test/log strings; run:
   `InfinityStage.ShadowCat.GaitBobMasterTimed`,
   `InfinityStage.Camera.CrossingSettle`, and
   `InfinityStage.Go1.FreeLookReturnsDuringPassageSettle`.
3. Change args to `APPLY`, fresh run/confirm, keep `settle_seconds: 3.0`; execute.
4. Run the same DRY again with a fresh id. Acceptance: census 6/6, stale 0,
   every saved base seam ≤0.5 cm / 0.05°, zero dirty packages.
5. PIE/read-only visual gate below. REVERT with the APPLY record if any gate
   fails; do not restore the backup over a live editor.

## Stills / PIE acceptance plan

For every P01→S1 … P06→S6 seam, capture the audience POV at T-3.1 s, T-1.5 s,
last Passage sample, first Scene sample, and Scene +0.2 s. Run two controls:

- default dog view (isolates rig/base transform);
- Free Look seeded to yaw +15°, pitch -8° before T-3.1 s (proves monotonic return
  to ≤0.1° by the last Passage sample, with no hard-cut reset visible).

Log Master frame, view target, POV transform, `rig_settle`, `rig_bob_cm`, and
look offset beside each still. Require boundary POV ≤1 cm / 0.1°, no last-frame
height or roll bias, no larger step than the preceding walking frame, and Gary's
visual acceptance. Transport/log success is not visual acceptance.

## Offline verification

- **[measured]** Python harness: **6/6 positive + 10/10 negative = 16/16**.
- **[measured]** all Python files compile with `py_compile`.
- **[measured]** `git apply --check` accepts the held patch against this tree.
- **[measured]** Git handoff is uncommitted: `git add` could not create
  `E:/PussStage/.git/worktrees/PussStage31/index.lock` (`Permission denied`).
  The conductor must add these three delivered paths and commit them.
- **[inferred]** Unreal API behavior and C++ compilation remain unproved until
  the conductor runs the live/build gates above.
