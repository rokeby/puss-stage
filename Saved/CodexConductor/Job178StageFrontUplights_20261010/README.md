# Job 178A - 3D stage-front uplights

Offline-authored only. Nothing here has run in Unreal.

The tool finds exactly the eight actors created by
`StageFront3D_20261010` using both label and `PussStage.StageFront3D*` tags.
It reads the six live `P87 Stage Front Uplight *` Show attachments and requires
their complete style to agree with the Job 87 record before planning one new
uplight per 3D piece. The Show remains authority: APPLY mints eight Light
attachments beside P87's source rows, materializes Passage 01, and saves only
the Show and production level.

Run order:

1. `python Saved/CodexConductor/Job178StageFrontUplights_20261010/test_job178_stagefront_uplights_offline.py`
2. Keep `DRY` / `DRY JOB178A STAGE FRONT UPLIGHTS`; run the request through the
   guarded project-Python route. Require eight `JOB178A_PAIR` rows and
   `JOB178A_STAGE_FRONT_UPLIGHTS_DRY_OK` with `mutated=0|dirty=0+0`.
3. Review every piece -> light mapping. Set `APPLY` and the exact confirm
   `APPLY JOB178A STAGE FRONT UPLIGHTS`.
4. Require `JOB178A_STAGE_FRONT_UPLIGHTS_APPLY_OK`, backup path, readback 8 and
   `dirty=0+0`. Capture the opening wide still; automation is not visual proof.
5. Reversal: `REVERT` / `REVERT JOB178A STAGE FRONT UPLIGHTS`; require the
   matching revert marker and zero owned GUID survivors.

APPLY writes `Backups/PreJob178AStageFrontUplights-<run>` and an exclusive
`job178a_ACTIVE.json` before mutation. REVERT makes a second backup and archives
the active record. Never Save All.
