# P96: P04 -> S4 total-dark hard cut

Offline-built for the conductor. Nothing here has run in Unreal. The live tool writes
only `/Game/InfinityStage/Dev/Sequences/LS_DevScene_04`; it never saves the show map,
the Show asset, `/Game/L_KK_children`, or the Klara sequence copy.

## Intended edit

1. Keep the existing S4 Entry Handoff camera from scene frame 0 through frame 405.
2. Deactivate, but do not delete, the v4 glide-camera cut.
3. At frame 405 let the existing nested `LS_Children_S4Hangar` camera cut take over.
4. Hide every live P04 materialized light for all of S4. The census walks all
   attachment descendants, not only direct children of the Passage actor.
5. Hide P04 bulb/practical/glimmer body meshes and other emissive descendants from
   frame 0 through the cut frame (the half-open range is `[0,406)`). It also audits
   S4 Arrival's pre-scene light drives. Hiding the body actor suppresses both its
   emissive mesh and any transient bulb-owned point-light component.
6. Hide every live S4-hangar light and emissive bulb/glow for all of S4.
7. Hide Klara's S4 lights/environment only before frame 405; RESTORE_STATE hands them
   back to her sequence at the cut.
8. Hide `P04 Backcloth (baked)` from frame 405 through scene end. Its existing fall
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
   - for a fresh edit, `mode`: `APPLY`
   - when `p96_record.json` already records the saved Job 96 cut, `mode`: `RESUME`
   - `run_id`: a new APPLY id
   - `dry_run`: the DRY id
   - `confirm`: `APPLY P96 S4 DARK CUT` or `RESUME P96 S4 DARK CUT`
   - `decided_by`: Gary's E17 note and the conductor identity.
6. Send the same request. Require `P96_S4_DARK_CUT_APPLY_OK` for a fresh edit or
   `P96_S4_DARK_CUT_RESUME_OK` for the saved Job 96 extension. RESUME verifies the
   original applied record/camera/tracks, adds only newly discovered darkness tracks,
   and reports `camera_repeated=0`.
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

`python test_p96.py` -> `P96_HARNESS_OK|passed=18|total=18|positive=3|negative=10|trap=5`.
# P04-tail Master darkness bridge (Job 140)

`p96_master_tail.py` is the narrow DRY/APPLY/REVERT companion for the pre-S4
acceptance gap. It reads the original P96 record and refuses unless that record
contains exactly the reviewed 67 `hangar_lights_and_emissives` targets. It adds
Master-owned `bHidden` sections only over the last two rounded-up Master frames
of P04 through the first S4 frame, plus one owned linear black fade at the cut.
It saves only `LS_InfinityStage_V1Master`; the existing S4-local P96 sections
remain authoritative after the one-frame bridge releases.
