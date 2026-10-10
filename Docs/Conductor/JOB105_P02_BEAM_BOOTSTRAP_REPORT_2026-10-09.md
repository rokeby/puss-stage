# Job 105 - P02 atmosphere beam bootstrap report

## Verdict

The minimal fix is four P02-owned BeamLook noise-volume actors, not a second
general atmosphere rollout and not mapping the P01 actors directly across
Passages. The existing lighting tool needs four target actor vessels and then
copies P01 state onto them field-scoped.

## Evidence and proof tiers

- **measured (saved live run, prior conductor):** the P02 lighting DRY stopped
  cleanly with `ATMOS_TARGET_BEAMS_MISSING|need=4|have=0`
  (`Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md:67,113`).
- **declaration-proven:** `atmos_plan` filters P01 beam actors to ordinals at or
  below P02's 23 target bays, sorts them, requires at least the same count of
  target beam actors, and then matches target vessels to sources
  (`Saved/CodexFlatV3/p02lighting/passage_lighting_as_source.py:487-512`).
- **declaration-proven:** the P01 atmosphere APPLY record created seven tagged
  noise actors, and the first four are B03/B07/B12/B20 with tags
  `InfinityStage.BeamLook` + `P01ATMOS`
  (`Saved/CodexConductor/Effects_20261007/p01_atmos_record.json:27816-27922,28231-28234`).
- **declaration-proven:** those noise actors were created as collision-free,
  movable StaticMeshActors, assigned the BeamLook volume material, attached to
  the Passage with KeepWorld, and read back (`Saved/CodexConductor/p03_atmos.py:1309-1338,1548-1568`).
- **inferred:** directly reusing the four P01 actors for P02 is not legitimate.
  One actor cannot be Passage-relative to both P01 and P02, and changing its
  attachment/transform would mutate P01. No record or tool was found declaring
  shared cross-Passage BeamLook ownership.
- **measured (offline repository search):** no `P02ATMOS` actor record or prior
  P02 BeamLook APPLY was found; the hits were the blocked lighting tool's args,
  code, and stopped report. Therefore there is no existing P02 structure that
  the lighting tool can safely claim or retag from saved evidence.

## Delivered guard

`Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap.py` pins the P01 record SHA-256,
selects only B03/B07/B12/B20, verifies each live P01 source retains its
record-owned tags/material, reports (but does not reject) world-transform drift
that could come from parent Passage motion, computes the current P01-relative
transform, and creates an equivalent actor
under P02 tagged `InfinityStage.BeamLook`, `P02ATMOS`, and
`P02BEAMBOOTSTRAP`. APPLY requires the DRY plan hash and exact confirmation.
It takes `Backups/PreP02BeamBootstrap-<run>` before mutation, permits only the
level package to become dirty, saves only the current level, and reads all four
actors back. REVERT drift-checks, backs up again, deletes only the triple-tagged
record-owned actors, saves only the level, and archives the record. Both APPLY
and REVERT refuse while an active `PASSAGELIGHT` record exists, enforcing the
undo order.

**UNCLEAR until the conductor runs it:** live Unreal API execution, the new
PASSAGELIGHT DRY result, saved package read-back, performance, and rendered look.
Offline harness success proves planning/guards only.

## Offline verification

- **measured (offline):** Python compilation passed for the tool, runner, and
  harness on 9 Oct 2026.
- **measured (offline):** the harness passed **31/31**, including positive and
  negative controls; see
  `Saved/CodexFlatV3/p02lighting/P02_BEAM_BOOTSTRAP_OFFLINE_HARNESS_RESULTS.md:1-14`.
- **declaration-proven:** ordered DRY/APPLY/PASSAGELIGHT-DRY and inverse undo
  instructions are in
  `Saved/CodexFlatV3/p02lighting/P02_BEAM_BOOTSTRAP_RUNBOOK.md:1-30`.

## Delivered files

- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap.py`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_run.py`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_args.json`
- `Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_request.json`
- `Saved/CodexFlatV3/p02lighting/test_p02_beam_bootstrap_offline.py`
- `Saved/CodexFlatV3/p02lighting/P02_BEAM_BOOTSTRAP_RUNBOOK.md`
- `Saved/CodexFlatV3/p02lighting/P02_BEAM_BOOTSTRAP_OFFLINE_HARNESS_RESULTS.md`
