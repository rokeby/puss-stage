# P75 chandelier staging — conductor runbook

Offline delivery only. The worktree run did not open Unreal, MCP, PIE or Blender.
The PNGs and `p75_offline_plan.json` are forecasts from the same pure planner
used by the live tool; Gary owns every timing/look default in the args.

## Files

- `chandelier_staging_core.py`: pure validation, deterministic candle order,
  projected-shadow arithmetic, GPU guards and clearance gates.
- `chandelier_staging.py`: later-live DRY/APPLY/REVERT tool.
- `chandelier_staging_args.json`: Gary-owned staging values and asset paths.
- `chandelier_staging_run.py` + `chandelier_staging_request.json`: guarded
  project-Python MCP entry point for the conductor.
- `test_chandelier_staging_offline.py`: six positive and seven negative controls.
- `make_timeline_previews.py`: regenerates both PNGs from the live plan.

## Offline order

1. `python Saved/CodexConductor/P75ChandelierStaging_20261009/test_chandelier_staging_offline.py`
2. `python Saved/CodexConductor/P75ChandelierStaging_20261009/make_timeline_previews.py`
3. Review `p75_offline_plan.json`, both PNGs, and the asset paths/defaults in
   `chandelier_staging_args.json`.

## Later-live conductor order

1. Import/verify Iron3 and its chain from job 55. Require exactly 44 candle
   sockets (`Candle_01..44` or `SOCKET_Candle_01..44`) and the P56 child
   Blueprint. Keep PIE and Sequencer closed; require zero dirty packages.
2. Leave mode `DRY`, execute `chandelier_staging_request.json`, and require
   `P75_CHANDELIER_DRY_OK`, `mutated=0`, `dirty=0+0`. Review the placements,
   frustum/look, timing, projected size, counts, clearances and the printed plan
   hash. A live camera/frustum judgment is mandatory before APPLY; the offline
   placement is only a starting point.
3. Copy the DRY `plan` hash to `reviewed_plan_sha256`, change mode/confirm to
   `APPLY` / `APPLY P75 CHANDELIER`, then execute the same request. Require
   `P75_CHANDELIER_APPLY_OK`, `saved=3`, `readback=1`, `dirty=0+0`.
4. Point P52B at the P06 body and the delivered 24-link actor set, then run its
   DRY and REBUILD sequence. P75 does not duplicate its solver. If the imported
   chain is monolithic rather than 24 separately pivoted actors, stop: P52B's
   contract is not met and rigid P52 is only a deliberate fallback.
5. Render-review Opening and P06. Confirm the hidden chandelier is out of camera,
   the proscenium receives the predicted-scale shadow, P56 flames actually start
   as visibility keys reveal them, and P06 remains silent before chain A's creak.
6. To reverse, set mode/confirm to `REVERT` / `REVERT P75 CHANDELIER`. The tool
   validates actor/track drift, backs up all three packages again, removes only
   P75-tagged actors and P75-owned tracks, target-saves, reads back, and archives
   its active record.

## Refusal boundary

The tool refuses wrong confirms, stale APPLY hashes, missing assets/world/route,
nonzero dirty packages, more than four grouped lights, more than two shadow
casters, any socket count other than 44, overlap with declared topple/wing rows,
foreign owned-track collisions, and drift before REVERT. It never calls Save All
and does not add audio. The live API calls and rendered look remain unproved until
the conductor runs DRY/APPLY in UE 5.8.
