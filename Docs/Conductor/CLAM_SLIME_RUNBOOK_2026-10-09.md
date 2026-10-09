# ClamSlime import and apply runbook

This is the missing prerequisite for post-bake queue item 14b. The run-51c DRY result
`apply_ready=0|imported=0|record=0|actor=0|binding=0` means **IMPORT has not run**;
the absent actor, binding, and apply record are expected until import succeeds.

1. Start from the correct PussStage editor, no PIE/SIE, Sequencer closed, and an exact empty dirty-package census.
2. Run `DRY` with `slime_apply_args.json`. Require `CLAMSLIME_DRY_OK`, `sources=OK`, `lid=OK`, `plan=OK`, and `next=IMPORT`.
3. Change the args to `{"mode":"IMPORT","confirm":"IMPORT CLAMSLIME","run":"<fresh-run-id>"}` and run `slime_apply_ue.py` once. Require `CLAMSLIME_IMPORT_OK`; this create-only step imports the skeletal mesh and animation, creates the materials/MIs, writes `slime_import_record.json`, saves only the created asset packages, and refuses if any target already exists.
4. Restore `DRY` with a fresh run id. Require `apply_ready=1|imported=1|next=APPLY`, plus an empty dirty-package census.
5. Change the args to `{"mode":"APPLY","confirm":"APPLY CLAMSLIME","run":"<fresh-run-id>"}`. Require `CLAMSLIME_APPLY_OK`, then read back the one actor, its attachment, the one resolving sequence binding, animation/visibility sections, saved map and scene, and zero dirty packages.
6. If APPLY has to be undone, use `{"mode":"REVERT","confirm":"REVERT CLAMSLIME","run":"<fresh-run-id>"}`. REVERT removes only the recorded actor and binding; imported assets remain.

Do not synthesize the actor, binding, or apply record to bypass IMPORT. `NOT_IMPORTED`,
`TARGETS_EXIST`, source/curve mismatch, or a non-empty census is a stop condition.

Proof boundary: the ordering and confirm strings are declaration-proven by
`Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py`; run-51c measured only
the missing-import state. No rendered or PIE acceptance is claimed here.
