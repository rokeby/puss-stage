# Job 106 — P02 Top facing-only tool

## Verdict

- **declaration-proven:** the tool is hard-scoped to P02 and exactly 23 Top panels; DRY refuses any Top that is not `AUTO_BY_ROLE`, has image flip enabled, lacks the approved local yaw 180, or does not have the opposite route-facing sign from both L/R controls (`p02_top_facing_core.py:12-22,90-121`).
- **measured (pre-existing live record, checked offline here):** `rzswap_dry_P02_RZSW-20261009-194606.json` contains 23 P02 rows; the harness parsed every row and found 23/23 L and R with `front_s < back_s`, 23/23 Top with `front_s > back_s`, no Top image flip, and all Top policies `AUTO_BY_ROLE` (`test_p02_top_facing_offline.py:178-184`).
- **declaration-proven:** APPLY's sole panel property setter is `facing_policy = ROTATE180_AROUND_UP`; it does not set image flip, local transform, mesh, materials, or UV data (`p02_top_facing.py:76-99`). Whole-Show export-text controls reject any change outside those 23 Top FacingPolicy fields (`p02_top_facing_core.py:160-178`).
- **declaration-proven:** APPLY and REVERT require a clean starting census, take verified Show+level backups, materialize only P02, permit only Show+level dirtiness, save only those named packages, read back all 23 facing signs after materialization and again after save, and emit run-id success markers (`p02_top_facing.py:42-53,150-249,252-320`).
- **measured (offline):** the harness passes **35/35** controls, including stale-state, image-flip, non-target/other-passage, facing-sign, dirty-package, rollback, and record-retirement failures (`test_p02_top_facing_offline_report.json`).
- **inferred:** the Unreal API path and physical result are not live-proven by this job because the brief forbids Unreal. The conductor must run DRY, APPLY, and REVERT in the editor and retain their JSON records and log markers.

## Ordered conductor run

1. Re-run the offline harness: `python Saved/CodexFlatV3/p02_top_facing/test_p02_top_facing_offline.py`.
2. Keep `p02_top_facing_args.json` in its shipped DRY state and submit `p02_top_facing_request.json` through the guarded loopback project-Python route. Require `P02_TOP_FACING_DRY_OK`, `tops=23`, and a clean editor census.
3. Read `p02_top_facing_dry_LATEST.json`. Confirm every target reports `before_sign: 1`, `L/R: -1`, `expected_after_sign: -1`, `flip_image_horizontally: false`, and the intended local transform.
4. Change args to APPLY using the exact `next_confirm` printed by DRY (format: `APPLY P02 TOP FACING #<hash8>`), add `"dry_record": "p02_top_facing_dry_<run>.json"`, and set `"decided_by": "Gary approved E9 2026-10-09"`.
5. Submit the same request. Require `P02_TOP_FACING_APPLY_OK`, the APPLY JSON record, clean census, named Show+level saves, and `23/23_front_lt_back` after materialization and post-save read-back.
6. Inspect/film separately for visual acceptance. Read-back is not rendered proof.
7. Change args to REVERT using `REVERT P02 TOP FACING <apply-run-id>`, then submit the request. Require `P02_TOP_FACING_REVERT_OK`, clean census, and `23/23_front_gt_back`. REVERT renames the active/original records instead of permanently deleting them.

No Unreal or Blender process was opened by Job 106.
