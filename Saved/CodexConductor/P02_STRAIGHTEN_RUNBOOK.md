# P02 straighten: supervised runbook (written 7 Oct, offline; nothing below has run)

Gary, 7 Oct: "P02 is still extremely slow walking speed and not straightened". Anchor **DOCK** (Gary 5 Oct): the
camera END view stays on the S2 hangar dock and P02's mouth moves about 97 m and turns -66.5 deg
(`p02_straighten_dry_P02STR-20261006-014311.json` start_delta.DOCK, measured).

Do all of it in **one supervised editor session**, in this order. Every step goes through the guarded MCP route
(`Saved/CodexMocap/mcp_request.py` with the step's `*_request.json`). Edit the step's args file before you send it.

**Rules for every step**
- A step has passed only when its OK marker is in the Unreal log with this run's `run=` id. Parse for the marker
  itself; do not use `tail -1` (memory: log markers need run ids).
- `*_FAILED`, `*_STOPPED`, a Python exception, or a missing OK marker means **stop**. Do not start the next step.
- If the failure text says `NOTHING SAVED; Don't-Save restart`, or anything was written before the failure: close the
  editor with **Don't Save**, restart it, reopen the level and confirm the census is 0+0. Never use Save All, never
  reload the open level, and never open or scrub the Master in Sequencer (doing that dirties the map).
- Leave PIE as it is. A tool must never end PIE or quit the editor.
- If the session has to be undone, revert in LIFO order (see the end of this file).

## 0. Snapshot
- Take a full snapshot to `D:\PussStageBackups`.
- Also copy these files to `Backups/PreP02StraightenSession-<YYYYMMDD-HHMM>/`:
  - `L_InfinityStage_V1VerticalSlice.umap`
  - `DA_InfinityStage_V1Show.uasset`
  - `LS_InfinityStage_V1Master.uasset`
  - `LS_Interaction_01_WashingTheBoy.uasset`
  - the Scene 1 and Scene 2 sequence `.uasset` files
- Before you start: no PIE, census 0+0, no `ZZ_` actors, Sequencer closed.

## 1. Follow-ons CAPTURE (read-only; must run before the straighten)
- Args: `p02_straighten_followons_args.json` with `"mode": "CAPTURE"`.
- Request: `p02_straighten_followons_request.json`.
- Marker: `P02_FOLLOWONS_CAPTURE_OK|run=..|actors=7|keys=485,2|unclassified=0|foreign=0|path=..`.
- The run writes `p02_straighten_followons_capture.json`. This file is the only copy of the old curve's frames, so
  keep it.
- If `unclassified` or `foreign` is above 0: stop and classify those actors in `POLICY`. Do not add an ack.

## 2. Follow-ons DRY, predicted
- Args: `"mode": "DRY"`. The route is still curved, so the DRY uses `predicted_route_start`.
- Marker: `P02_FOLLOWONS_DRY_OK|route=PREDICTED|..`.
- At this point `refusals_if_apply` should list only `STRAIGHTEN_NOT_SAVED` and `ROUTE_NOT_STRAIGHT`.

## 3. p02_straighten DRY
- Args `p02_straighten_args.json`:
  `{"mode":"DRY","anchor":"DOCK","floor_step":false,"floor_material":"KEEP"}`.
- **The file currently in the folder says floor_step true / WALNUT. Change it.** floor_step is flawed: Ground off
  also blanks Structure Fixtures and Gridiron (measured 6 Oct on P03), and P02's floor was already done by
  `P02FLOOR-20261006-160506`.
- Marker: `P02_STRAIGHTEN_DRY_OK`.
- In `P02_STRAIGHTEN_DRY_REFUSALS_IF_APPLY`, DOCK should show only `FOLLOWONS_NOT_ACKED|MATCH_HANDOFFS,ROUTE_ACTORS`.
- `mouth_actors` should be the same 7 labels as in step 1.

## 4. p02_straighten APPLY
- Args:
  `{"mode":"APPLY","confirm":"APPLY P02STRAIGHT","anchor":"DOCK","floor_step":false,"floor_material":"KEEP","followons_ack":["MATCH_HANDOFFS","ROUTE_ACTORS"]}`.
- Marker: `P02_STRAIGHTEN_APPLY_OK|run=..|anchor=DOCK|..|followons=MATCH_HANDOFFS,ROUTE_ACTORS`.
- Also check `END_VIEW_MEASURED` vs_dock: it must be within 25 cm and 0.5 deg.
- This step saves the level with the route actors stranded. Steps 5-7 must follow in the same session.

## 5. Follow-ons DRY, live
- Args: `"mode": "DRY"`.
- Marker: `P02_FOLLOWONS_DRY_OK|route=LIVE|..|refusals_if_apply=0|walk_vs_cam={xy_cm<1,..}`.
- Review the per-actor `ACTOR` rows against the offline prediction:

  | Actor | Expected |
  |---|---|
  | I1 sleight camera, stalls camera, mouth lantern | each moves about 110-115 m, yaw -66.4 deg |
  | Car light | moves about 16.7 m, yaw -33.1 deg |
  | Pit liner | stays |
  | Handoff cameras | stay |

## 6. Follow-ons APPLY
- Args: `{"mode":"APPLY","confirm":"APPLY P02FOLLOW"}`.
- Marker: `P02_FOLLOWONS_APPLY_OK|run=..|actors=4|seq_items=3|seq_saved=1|level_saved=1|readback=1|dirty_after=0+0`.
- It saves only the level and `LS_Interaction_01_WashingTheBoy`.
- Record: `p02_straighten_followons_record.json`.

## 7. MATCH_HANDOFFS
- No existing tool calls `MatchNamedSceneHandoffs(show,[S1,S2],2)` in a single call (grep of `Saved/`: every caller
  passes one Scene and a count of 1). Run the two single-Scene tools one after the other:
  1. `Saved/CodexCameraPilot/match_scene1_handoff.py` (`match_scene1_request.json`). Marker: `PUSS_MATCH_P1_S1_DONE`.
  2. `Saved/CodexCameraPilot/match_scene2_handoff.py` (`match_scene2_request.json`). Marker: `PUSS_MATCH_P2_S2_DONE`.
- Each one also logs `INFINITY_SCENE_HANDOFF_MATCHED|..|ok=1|stale_before=..|stale_after=0`. The call returns true
  only when the matched Scene ends not stale (`InfinityStageCameraPilotLibrary.cpp:595-624`), so matching a Scene that
  was not stale is a valid re-take.
- Each tool backs up the level and its Scene sequence to `Backups/PreMatchP*S*-<ts>`. Neither has a revert script:
  the revert is to restore those files with the editor closed.

## 8. Rebuild the Master
- Tool: `Saved/CodexSoftGoods/rebuild_master.py` (`rebuild_master_request.json`).
- Marker: `PUSS_SOFTGOODS_MASTER_REBUILT`. It saves only the Master (and the Show if the rebuild dirtied it).

## 9. Tests (one at a time)
- `run_saved_master_test.py`, then `run_scene_cut_test.py`.
- Each one logs `CONDUCTOR_AUTOMATION_QUEUED|run=..`. Read that test's own result line after the queue marker for
  that run (memory: the swapkit stage is fake).
- Pass requires `InfinityStage.Editor.SavedMasterMatchesShow` and `InfinityStage.Editor.SceneCutBindingsResolve` to
  both be Success.

## 10. Stills
- Start PIE with `conductor_pie_begin.py`.
- Run `passage_stills_run.py` with `{"passage":"P02"}`. Marker: `PASSAGE_STILLS_OK`.
- Also look at the I1 frames around the sleight and the walk-in end. Gary judges these.

## 11. passage_retime_to_music for P02 (song + short tail; Gary 5 Oct)
- Args `passage_retime_to_music_args.json`: `"passages":["2"]`, `tail_s` 2.0, song 45.51424 s.
  - DRY: `PASSAGE_RETIME_DRY_OK`. Copy `expected_for_apply_args` into `per_passage.2.expected`.
  - APPLY: `PASSAGE_RETIME_APPLY_OK`.
- The prerequisite check accepts `p02_straighten_record.json` with status "saved"
  (`passage_retime_to_music.py:650`).
- The tool refuses `TIME_KEYED_CHANNEL` / `RELATIVE_PIN` inside P02. If that happens, stop and report.
- **Then the I1 walk-in needs a re-plan (inferred; Gary / Look & camera to decide).**
  - The walk-in's end speed was planned at 66.3 cm/s, which is P02's current slow start (`curtain_sleight_record_I1.json`
    plan.walk.report.v_end_cm_s).
  - After the retime, P02 starts at about 250 cm/s (roughly 11858 cm in about 47.5 s, inferred), so the speed jumps
    at the I1 to P02 cut-in.
  - There is no walk-only re-key tool. The re-plan is `curtain_sleight` FIXUP_PILE_REVERT, then REVERT, then APPLY for
    I1 (main_revert_gate order). That run must be its own supervised step, after checking its live gates.

## 12. P02 rig pattern
- Use `p02_rig_pattern_run.py` (`p02_rig_pattern_request.json`).
  - DRY: `P02RIGPATTERN_DRY_OK`. Copy the rows into `expected_targets` and `ack_records` verbatim.
  - APPLY with `"confirm":"APPLY P02RIGPATTERN"`: `P02RIGPATTERN_APPLY_OK`.
- Then repeat step 9 (both tests) and step 10 (stills).

## Undo (LIFO)
Each step's REVERT checks that the live state equals what that step's APPLY left. Revert in this order:
1. Rig pattern REVERT (`REVERT P02RIGPATTERN`).
2. Retime REVERT (`PASSAGE_RETIME_REVERT_OK`).
3. Restore the `PreMatchP*S*` backups for steps 7-8 with the editor closed, then rerun `rebuild_master.py`.
4. **Follow-ons REVERT** (`"confirm":"REVERT P02FOLLOW"`): `P02_FOLLOWONS_REVERT_OK`.
5. p02_straighten REVERT (`"confirm":"REVERT P02STRAIGHT"`): `P02_STRAIGHTEN_REVERT_OK`.
6. `rebuild_master.py` again.
7. Tests.

The follow-ons REVERT must run **before** the straighten REVERT.
