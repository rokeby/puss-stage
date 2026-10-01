# S3 beats in the Scene 3 sequence (Conductor 3, 1 Oct)

**Gary (his session, 1 Oct):** set up Scene 3's sequence with his 12 beats
(`Docs/Scene3BeatSheet_2026-10-01.md`); the old clam cameras go (LS_Clams was an animation
test; its animation STAYS, its cameras start from scratch); static cameras come later;
placeholder timings approved, ~260 s total.

**Structure (Look & camera, tagged in their reply, 1 Oct):** markers on the ROOT of
`LS_DevScene_03`; every camera a ROOT cut; no nested beat sequence. The transport reads the
marker label `InfinityStage.HiddenChangeover` — NEVER use it. `FindSceneCameraCut` reads root
cuts only and ignores IsActive (declaration-proven), and nested cuts outrank root (measured).

## Order (each step: DRY RUN, read it, then APPLY; stop at the first refusal)

### Step A — lengthen Scene 3 to 260.000 s (6240 display frames at 24 fps)
Tool: `Saved/CodexSoftGoods/extend_scene_playback.py`, procedure in `Docs/ChaosClothCurtain.md`
§"Lengthening Scenes" (lines 36–59): mode file with Scene 3's exact cue label (read it from
the Show), dry run, check `next_segment.match_would_refuse=false`, `key_gate=[]`, `delta_s`;
apply; `segment_errors=[]`; `run_master_match_test.py`; census. If `key_gate` refuses, STOP and
report (Look & camera: it predates patch K and may refuse needlessly — that is MY call, not yours).

### Step B — new tool `Saved/CodexConductor/s3_beats_apply.py` (dry / apply / revert)
On `LS_DevScene_03` (root) and `/Game/Scenes/LS_Clams`, after Step A:
1. **S3 Wide**: a SPAWNABLE CineCameraActor named `S3 Wide` in LS_DevScene_03, its transform
   and lens COPIED from the Entry Handoff camera's spawnable template after the match (not
   typed numbers). Root camera-cut section for it over `[95, end − exit_hold)` where
   exit_hold is the Exit Handoff's designed hold (read it from the current Exit cut; expect
   24 display frames). Use `set_range` in ONE call, never set_start/set_end separately.
2. **Retire root ClamCam1**: deactivate its cut section (`set_is_active(False)`). Do NOT delete
   anything. Its end must be ≤ S3 Wide's end (the builder treats the latest-ending cut as the
   last interior shot); if not, STOP.
3. **Retire nested ClamCam1**: in LS_Clams, deactivate its camera-cut section. Leave every
   skeletal-animation track and the ClamCam2 binding untouched.
4. **Markers** on LS_DevScene_03 root (display frames at 24 fps; scene time 0 = frame 0):
   | frame | label |
   |---|---|
   | 0 | S3 B01 Arrive - strike |
   | 360 | S3 B02 Figures sway - wide to figures |
   | 960 | S3 B03 Clam on pedestal (shut) |
   | 1440 | S3 B04 Agitation builds - waves |
   | 2880 | S3 B05 Clam opens slowly |
   | 3000 | S3 B06 Close-up of opening |
   | 3480 | S3 B07 Pearl glows - song of forgetting |
   | 4200 | S3 B08 Figures calm |
   | 4680 | S3 B09 Calm swaying (animation start) |
   | 5040 | S3 B10 Defocus - Puss's thoughts |
   | 5520 | S3 B11 Pearl rises to camera |
   | 5880 | S3 B12 Float out - to curtain |
   Refuse if any existing marker already carries an `S3 B` label (idempotence: report, don't duplicate).
5. Read back everything; census must be exactly {LS_DevScene_03, LS_Clams} content, no maps;
   save those two assets only (`save_asset`). Backup both .uasset files first
   (`Backups/PreS3Beats-YYYYMMDD-HHMM`), record file with before state (section ranges and
   active flags, marker list) so revert can restore it exactly.
   Markers: `S3_BEATS_DRY_RUN_OK|run=..|mutated=0|plan=..`, `S3_BEATS_DONE|run=..|applied|backup=..|census=..`.
6. Offline harness `test_s3_beats_plan.py`: + case; − cases: a HiddenChangeover label; an
   existing `S3 B` marker; retired ClamCam1 ending after S3 Wide; split set_start/set_end.

### Step C — `rematch_only` with the same extend tool (re-copies the Exit from S3 Wide).
Then `run_master_match_test.py` (SavedMasterMatchesShow) and the census.

### Step D — the binding gate: run the automation test `InfinityStage.Editor.SceneCutBindingsResolve`
by its EXACT name (never a broader filter; NEVER `PussStage`). Read the result in the log.

## THIS PASS: Step A DRY RUN only, plus write Step B's tool + harness and run the harness.
Do not apply anything. Do not commit. Final message: the Step A dry-run report fields above,
the harness result, each tagged measured/inferred.

## Crash and dirt rules (each has crashed or dirtied this editor)
- NEVER open Sequencer or the Master; never scrub, play or evaluate (it dirties the map).
- No `SequencerTools`; no `get_bound_objects`/`locate_bound_objects` with open ranges.
- No `unreal` objects in module globals; never reload a level/package; no PIE; never Save All.
- If PIE is running: STOP.
