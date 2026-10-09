# P96: P04 -> S4 total-dark hard cut

Offline-built for the conductor. Nothing here has run in Unreal. The live tool writes
only `/Game/InfinityStage/Dev/Sequences/LS_DevScene_04`; it never saves the show map,
the Show asset, `/Game/L_KK_children`, or the Klara sequence copy.

## Intended edit

1. Keep the existing S4 Entry Handoff camera from scene frame 0 through frame 405.
2. Deactivate, but do not delete, the v4 glide-camera cut.
3. At frame 405 let the existing nested `LS_Children_S4Hangar` camera cut take over.
4. Hide every live P04 materialized light for all of S4.
5. Hide every live S4-hangar light and emissive bulb/glow for all of S4.
6. Hide Klara's S4 lights/environment only before frame 405; RESTORE_STATE hands them
   back to her sequence at the cut.
7. Hide `P04 Backcloth (baked)` from frame 405 through scene end. Its existing fall
   before the cut remains untouched; the unproven Geometry Cache hold tool is not a
   dependency.

Every target is discovered live and written by path into the DRY report. Existing
exact `bHidden` coverage is deduplicated. Inert `bHiddenInGame` tracks are reported
but never trusted. Any overlapping working visibility track that is not an exact
match refuses APPLY.

## Ordered conductor run

1. End PIE/SIE, close Sequencer, and obtain an exact empty dirty census.
2. Edit `p96_args.json`:
   - `mode`: `DRY`
   - `run_id`: a fresh id such as `P96-S4-DARK-CUT-20261009-230000`
   - leave `confirm`, `dry_run`, and `decided_by` empty.
3. Send `p96_request.json`. Require
   `P96_S4_DARK_CUT_DRY_OK|run=<id>|apply_ready=1`.
4. Inspect `p96_dry_<id>.json`. The exact census is
   `plan.counts`; every actor path and existing visibility track is in
   `state.target_groups`. Require exactly one curtain and one resolved camera for
   `root_entry`, `root_exit`, and `klara_at_cut`.
5. Edit `p96_args.json`:
   - `mode`: `APPLY`
   - `run_id`: a new APPLY id
   - `dry_run`: the DRY id
   - `confirm`: `APPLY P96 S4 DARK CUT`
   - `decided_by`: Gary's E17 note and the conductor identity.
6. Send the same request. Require
   `P96_S4_DARK_CUT_APPLY_OK|run=<id>|...|saved=/Game/InfinityStage/Dev/Sequences/LS_DevScene_04|...|dirty=0`.
   The tool creates `Backups/PreP96S4DarkCut-<run>` and `p96_record.json` before
   mutation, admits exactly LS_DevScene_04 in the dirty census, target-saves it,
   and reads it back.
7. Run `SceneCutBindingsResolve`, the live scene-cut binding check, and the focused
   transition tests. Do not rebuild/save the Master unless the conductor determines
   this sequence-only edit requires it.
8. Execute `stills_plan.json`, including the uninterrupted P04 -> S4 run and the
   rehearsal jump. For Geometry Cache frames: pose, tick/decode, re-pose the same
   frame, then capture.

## Revert

With a clean editor and closed Sequencer, set:

- `mode`: `REVERT`
- `run_id`: fresh REVERT id
- `confirm`: `REVERT P96 S4 DARK CUT`

Send the request and require `P96_S4_DARK_CUT_REVERT_OK`. REVERT verifies the
applied state against the record, backs up the applied sequence, removes only the
recorded tracks/bindings, restores the two camera-section fields, target-saves
LS_DevScene_04, reads back, and archives (does not delete) the record.

## Offline verification

`python test_p96.py` -> `P96_HARNESS_OK|passed=15|total=15|positive=2|negative=9|trap=4`.
