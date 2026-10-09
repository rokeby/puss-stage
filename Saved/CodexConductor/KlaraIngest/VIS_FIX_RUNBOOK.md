# P26 visibility rollout runbook

This runbook was written offline. It has not been run in Unreal.

- **declaration-proven:** `vis_fix.py` selects only visibility tracks whose
  property is `bHiddenInGame`; existing `bHidden` and `None` properties are not
  targets (`vis_fix.py:120`).
- **declaration-proven:** APPLY records and backs up the named sequence before
  its first UObject mutation, permits exactly that content package to become
  dirty, saves only that sequence, and reads it back (`vis_fix.py:288`).
- **declaration-proven:** REVERT refuses drift and restores the recorded property,
  path, defaults and keys rather than blindly inverting again (`vis_fix.py:328`).
- **inferred:** every repaired actor should be visible outside its fixed section.
  That is why the shipped PIE args say `outside_hidden: false`; change it only
  with scene-specific evidence.

Run scenes in this order: **S1, S4, S6, S3**. Finish all steps for one scene
before starting the next.

1. Confirm the editor has zero dirty content packages and zero dirty maps, PIE is
   stopped, and Sequencer is closed.
2. Copy `vis_fix_args_S<n>.json` to `vis_fix_args.json`. Replace `run` with a
   unique run id. Leave `mode`/`confirm` as `DRY` / `DRY VISFIX`.
3. Execute `KlaraIngest/vis_fix.py` through the guarded project-Python route.
   Require one `VISFIX_DRY_TRACK` line per proposed track and the terminal
   `VISFIX_DRY_OK` marker. Review binding, GUID, track index, and every range in
   `vis_fix_dry_S<n>.json`.
4. In `vis_fix_args.json`, change only `mode` to `APPLY` and `confirm` to
   `APPLY VISFIX`; use a new run id. Execute the same script. Require
   `VISFIX_APPLY_OK`, one named package saved, zero maps saved, zero dirty
   packages, `vis_fix_record_S<n>.json`, and
   `Backups/PreVisFix-S<n>-<run>/LS_DevScene_0<n>.uasset`.
5. Start the conductor's own PIE. Copy `vis_fix_pie_args_S<n>.json` to
   `vis_fix_pie_probe_args.json`, replace `run`, and execute
   `KlaraIngest/vis_fix_pie_probe.py`. It never starts or stops PIE. Require every
   `VISFIX_PIE_ROW` to pass and the terminal `VISFIX_PIE_OK`; retain the emitted
   `vis_fix_pie_S<n>_<run>.json`.
6. Stop PIE normally before moving to the next scene. Re-check the exact dirty
   package census.

To revert one scene: stop PIE, close Sequencer, copy that scene's args template
to `vis_fix_args.json`, set `mode` / `confirm` to `REVERT` / `REVERT VISFIX`, use
a new run id, execute `vis_fix.py`, and require `VISFIX_REVERT_OK`. REVERT takes a
fresh `Backups/PreVisFixRevert-S<n>-<run>` backup and archives the APPLY record.

**Open verification boundary:** until the conductor performs steps 2-5, saved
read-back and PIE visibility remain unmeasured. Transport success alone is not
acceptance.
