# Job 105 offline harness results

- Command: `python Saved/CodexFlatV3/p02lighting/test_p02_beam_bootstrap_offline.py`
- Result: **31 passed, 0 failed, 31 total**
- Positive controls: DRY/APPLY/REVERT argument paths, exact record selection,
  target labels/tags/material, pinned source hash, empty-target dedupe, guarded
  request/runner route, cache purge, active-PASSAGELIGHT interlock.
- Negative controls: malformed/unknown args, invalid mode, missing or wrong
  confirmations, missing APPLY plan hash, expanded ordinal/cap scope, source
  hash drift, wrong source record status/passage, missing source ordinal, and
  target label/P02ATMOS/owner-tag collisions.

This is offline planning/guard evidence only. It does not prove Unreal API
execution, package save/read-back, PASSAGELIGHT DRY success, performance, or the
rendered look.
