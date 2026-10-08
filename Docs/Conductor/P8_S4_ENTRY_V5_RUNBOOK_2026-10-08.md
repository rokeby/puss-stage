# P8 S4 entry v5 - conductor runbook (8 Oct 2026)

This is an **offline-built runbook**. Nothing in it has been run in Unreal by the
P8 worktree session.

## What blocked v5

- **[measured]** The live S4 is still reveal v4, so the S4 pre-roll DRY stops on
  REVEAL_NOT_V5; the children/pigeon are static before frame 405
  (Docs/Conductor/CONDUCTOR5_LOG_2026-10-08.md:127-150).
- **[declaration-proven]** v5 samples the whole nested camera path and refuses a
  standing backcloth (Saved/CodexConductor/KlaraIngest/klara_reveal.py:2588-2615,
  :2622-2681). The existing hangar tool explicitly did not author Geometry
  Cache holds (Saved/CodexConductor/s4_hangar_hold.py:613-615).
- **[declaration-proven]** UE 5.8 exposes cache asset, offsets, rate and reverse,
  but no clamp/hold field
  (D:\Unreal Engine\UE_5.8\Engine\Plugins\Runtime\GeometryCache\Source\GeometryCacheTracks\Classes\MovieSceneGeometryCacheSection.h:20-44).
  A Geometry Cache track can create and own sections
  (...\MovieSceneGeometryCacheTrack.h:23-40). RestoreState restores prior state
  and section completion is script-settable
  (D:\Unreal Engine\UE_5.8\Engine\Source\Runtime\MovieScene\Public\MovieSceneSection.h:104-108,424-435).
- **[inferred]** The chosen design authors one direct Scene section for one
  display frame, sampling duration minus end_margin_s, with KEEP_STATE. The
  one-frame range avoids cache looping. Whether the decoded final sample remains
  visually held must be proved by the PIE probe and stills; the header does not
  prove evaluator behaviour.
- **[declaration-proven]** s4_backcloth_hold.py has independent
  DRY/APPLY/REVERT confirms, record-first backup, exact dirty census, named
  package save, and reload/read-back
  (Saved/CodexConductor/s4_backcloth_hold.py:1-20,314-461).
- **[declaration-proven]** S4 now ships as strike_lights none plus
  preroll whole_glide
  (Saved/CodexConductor/KlaraIngest/klara_reveal_s4v5_args.json:98-101).
  S4 pre-roll uses exact seconds-to-ticks section bounds and refuses motion
  coverage gaps
  (Saved/CodexConductor/KlaraIngest/klara_preroll_s4.py:180-205,477-513).
  It deliberately does **not** port S1's phase-at-cut loop alignment: S4 is
  specified to restart at the hard cut
  (Docs/Conductor/codex_briefs/p8_s4_entry_v5.md:6,14). **[inferred design]**

## Preconditions

1. **[declaration-proven]** Use PussStage MCP port 8010 and the guarded project
   Python executor (Docs/CodexUnrealMCPRunbook.md:55-56). Confirm the expected world.
2. Stop PIE/SIE, close Sequencer, and require dirty census 0 content + 0 maps.
   Never Save All. Never save /Game/L_KK_children or another Klara level.
3. Give every call a fresh run_id; only accept a marker carrying that id.
4. Do not invoke or edit klara_pendulum_s4.py or its record; the measured tick-off
   state is outside this stream.

## Ordered execution

All edits below use the matching request JSON.

1. **REVERT v4.** Use
   KlaraIngest/klara_reveal_s4v5_args.json: mode REVERT,
   confirm "REVERT KLARAREVEAL". Expect
   KLARAREVEAL_REVERT_OK|run=<id>|scene=S4.

2. **Install the cache hold before v5 DRY.**

   - s4_backcloth_hold_args.json: mode DRY, empty confirm/decider.
     Expect S4BACKCLOTH_DRY_OK|run=<id>|apply_ready=1, one section
     [fold_end, fold_end+1), zero conflicts, cache time inside [9.0, duration).
   - Then mode APPLY, confirm "APPLY S4BACKCLOTH",
     decided_by "<conductor decision>". Expect
     S4BACKCLOTH_APPLY_OK|run=<id>|...|tier=inferred_until_PIE.
   - **[measured only after the call]** Record and backup paths are printed in
     the marker. Only LS_DevScene_04 may have been saved.

3. **v5 DRY.** Restore klara_reveal_s4v5_args.json to mode DRY, empty
   confirm/decider. Expect
   KLARAREVEAL_DRY_OK|run=<id>|scene=S4|apply_ready=1. Require:

   - KLARAREVEAL_V5_BACKCLOTH includes the direct Scene hold and down coverage
     through Scene end;
   - no CAMERA_PATH_BEHIND_STANDING_BACKCLOTH;
   - zero strikes; KLARAREVEAL_V5_PREROLL says whole_glide;
   - no unmarked refusal.

4. **Preview stills before v5 APPLY.** The existing preview tool was designed
   against the applied v4 placement (klara_s4v5_preview.py:7-26). Therefore,
   after the successful v5 DRY, temporarily re-APPLY v4 with the unchanged v4
   args (klara_reveal_args.json, confirm "APPLY KLARAREVEAL"), generate
   klara_s4v5_preview_pose.json, execute its 22-call sequence, then REVERT v4
   again. Each call must emit
   S4V5PREVIEW_OK|run=<id>|phase=<jump|camera|shot|check|cleanup>.
   Gary accepts/rejects the stills. **[inferred]** This bridge is necessary
   because previewing after v4 REVERT otherwise fails its live-placement check.

5. **v5 APPLY.** klara_reveal_s4v5_args.json: mode APPLY,
   confirm "APPLY KLARAREVEAL", and a non-empty decided_by. Expect
   KLARAREVEAL_APPLY_OK|run=<id>|scene=S4. Require the printed backup/record
   and a final 0+0 census.

6. **Pre-roll DRY/APPLY.**

   - klara_preroll_s4_args.json: mode DRY. Expect
     KLARAPREROLL_DRY_OK|run=<id>|apply_ready=1; require zero
     MOTION_GAP and motion_coverage.loop_alignment =
     NOT_APPLICABLE...intentional restart.
   - Then mode APPLY, confirm "APPLY KLARAPREROLL",
     decided_by "<conductor decision>". Expect
     KLARAPREROLL_APPLY_OK|run=<id>.
   - The only named saves are LS_DevScene_04 and
     LS_Children_S4Preroll; Klara's level must never appear in the census.

7. **Tests.** Run rebuild_managed_master, then
   SavedMasterMatchesShow, SceneCutBindingsResolve singly, and the live cut
   binding check. Require each tool's normal success marker and a final 0+0
   census. **[inferred]** Test names/transport are current project precedent;
   success is not rendered acceptance.

8. **PIE proof.**

   - Set pre-roll args to mode PROBE and send its request while S4 PIE plays
     through the auto-derived windows. Expect
     KLARAPREROLL_PROBE_ARMED, then
     KLARAPREROLL_PROBE_OK|answer=MOVING. Every Child1..7 at each pre-cut
     window and Pigeon at each pre-cut window must say MOVING.
   - Use the existing hangar PIEPROBE at frames 770, 800, 1500 and the rest
     camera region; re-pose before stills. Require the backcloth
     at_last_sample=true after the fold. **[inferred until measured]**
   - Capture C-1, C, C+1 and the whole glide. Gary checks: no bind/T pose in any
     lit pre-cut frame, pigeon moving, no one-frame boundary pop, backcloth down,
     and the hard cut lands on her first shot.

## Undo

- Pre-roll first: confirm "REVERT KLARAPREROLL" ->
  KLARAPREROLL_REVERT_OK; the duplicate stays unreferenced on disk.
- Reveal second: confirm "REVERT KLARAREVEAL" ->
  KLARAREVEAL_REVERT_OK.
- Cache hold last: confirm "REVERT S4BACKCLOTH" ->
  S4BACKCLOTH_REVERT_OK.
- No tool permanently deletes the duplicate. Deleting it later requires Gary's
  explicit approval.

## Offline harness evidence

- **[measured, offline]**
  test_s4_backcloth_hold_offline.py: 5/5 passed, with positive plan/read-back
  controls and negative fold/time/conflict/confirm controls
  (Saved/CodexConductor/test_s4_backcloth_hold_offline.py:20-72).
- **[measured, offline]**
  test_klara_reveal_v5_offline.py: 44/44 passed, including 25/25 seeded mutations plus
  exact-tick, motion-gap, Scene-4 probe gate, actor-level match, and
  moving/static controls
  (Saved/CodexConductor/KlaraIngest/test_klara_reveal_v5_offline.py:397-449,905-954).
- **[measured, offline]**
  test_klara_reveal_offline.py: 75 tests ran successfully (one
  environment-dependent test skipped). Binary fixtures were read from E:\PussStage via
  PUSS_ASSET_PROJECT; that tree was not written
  (Saved/CodexConductor/KlaraIngest/test_klara_reveal_offline.py:785-790).
