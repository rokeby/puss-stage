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

## Batch 1f LID_PIVOT correction (job 63)

- **[measured]** Batch 1f imported `SK_PearlClam_Slime` and
  `A_PearlClam_SlimeOpen`, then reported the animation bone `lid` at every
  sampled frame as `[0.0, -0.479, 0.300]`. The old gate compared that result to
  `[0.0, -47.86, 30.02]` and therefore refused by exactly 100x. Evidence:
  `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.09-13.14.57.log:5403-5425`.
- **[declaration-proven]** The design pivot is Blender centimetres
  `[0.0, 47.86, 30.02]`; the build converts its bone matrices from centimetres
  to a metre-authored Blender scene, then exports with Y flipped into Unreal.
  The AnimationLibrary gate must therefore expect local animation metres
  `[0.0, -0.4786, 0.3002]`. Mesh bounds remain a separate centimetre gate.
  Evidence: `Saved/CodexConductor/ClamSlime_20261008/build_slime.py:19-23,60-85`;
  `Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py:127-135,235-257`.
- **[declaration-proven]** This pivot belongs to the generated slime skeletal
  mesh/animation, whose actor label is `S3 PearlClam Slime`. APPLY attaches that
  actor to the existing `S3 PearlClam` bottom actor identified by the
  `S3Millstone` apply record; it is not the separate `S3 PearlClam Lid` actor's
  mesh pivot. Evidence:
  `Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py:103-119,691-696,1032-1065`.
- **[inferred]** No asset rebuild is indicated: measured axes/signs and all
  sampled-frame translations match the metre expectation. After a conductor-
  owned Don't-Save restart has discarded batch 1f's seven dirty transient
  packages, repeat the normal DRY -> IMPORT -> DRY -> APPLY sequence. A changed
  sign or more than 0.05 cm equivalent pivot drift still refuses.

Proof boundary: the ordering and confirm strings are declaration-proven by
`Saved/CodexConductor/ClamSlime_20261008/slime_apply_ue.py`; run-51c measured only
the missing-import state. No rendered or PIE acceptance is claimed here.
