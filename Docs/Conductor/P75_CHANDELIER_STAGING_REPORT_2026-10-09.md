# P75 — chandelier staging offline delivery report

Date: 9 October 2026. Scope: worktree-only, offline. Unreal Editor, MCP, PIE,
Blender, builds, Show data and binary Content packages were not opened or changed.

## Delivered

- **declaration-proven:** `chandelier_staging_core.py` validates Gary-owned args,
  requires exactly 44 sockets, enforces at most four grouped lights and two shadow
  casters, orders all timing, requires silence, and gates P06 against declared
  topple/wing stations (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging_core.py:41-134,164-241`).
- **declaration-proven:** candle order is deterministic and consumes one random
  draw per socket; the projected proscenium shadow uses explicit similar-triangle
  geometry rather than a look-only guess
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging_core.py:136-157`).
- **declaration-proven:** `chandelier_staging.py` exposes DRY/APPLY/REVERT. It
  guards the production world and PIE state, requires an exact clean census,
  creates a hashed `Backups/PreP75Chandelier-<run>` plus an exclusive active
  record before mutation, checks exact dirty scope, saves only the level and two
  named sequences, reads actors/tracks back, and emits run-id success markers
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:71-129,391-532`).
- **declaration-proven:** visibility tracks bind `AActor::bHidden` as
  `("bHidden","bHidden")` and key VISIBLE booleans; bindings are looked up before
  `add_possessable`; owned tracks match by display prefix/class context rather
  than channel names; rotation lookup tolerates UE channel-name suffixes
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:278-355`).
- **declaration-proven:** the tool reuses Iron3 and P56 assets, creates no new
  asset, keys a one-pass drive-by intensity and yaw arc, reveals the 44 P56
  candles in seeded order, drives only four grouped point lights/two casters, and
  leaves P06 swing ownership with P52/P52B
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:159-276,418-503`;
  `Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging_core.py:204-233`).
- **declaration-proven:** REVERT first compares every owned actor and track to the
  applied record, then removes only P75-tagged actors/P75-prefixed tracks, saves
  narrowly, proves absence and archives rather than deletes the record
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/chandelier_staging.py:503-531`).

## Offline proof

- **measured:** the harness passed 13/13: six positive and seven negative controls.
  Positives cover the one-pass plan, hidden-shadow pair, seeded 44-candle order,
  projected size, P06 clearances and stable review hash. Negatives cover both GPU
  caps, bad hidden-shadow flags, topple overlap, 43 sockets and missing APPLY
  confirmation and a stale APPLY review hash
  (`Saved/CodexConductor/P75ChandelierStaging_20261009/test_chandelier_staging_offline.py:31-113`).
- **measured:** Python byte-compilation and `git diff --check` exited 0. The final
  line was `P75_CHANDELIER_HARNESS|PASS=13|FAIL=0|TOTAL=13|POSITIVE=6|NEGATIVE=7|OFFLINE=1|UNREAL=0|BLENDER=0`.
- **measured:** the preview renderer produced and visual inspection passed
  `p75_opening_timeline.png` (1500×640) and
  `p75_p06_0_30_timeline.png` (1500×712); both are generated from the same plan
  consumed by APPLY (`Saved/CodexConductor/P75ChandelierStaging_20261009/make_timeline_previews.py:36-117`).
- **measured (offline forecast only):** defaults yield a 331.6 × 243.2 cm peak
  shadow, candle ignition 39.40–43.06 s, P06 hang station 5700 cm, 3750 cm to the
  first topple row and 550 cm to the nearest wing station. The source snapshot
  declares the first topple station 9450 cm and chain-A creak 24.89 s
  (`Saved/CodexFlatV3/topple/topple_plan.json:269,3563`); these are not live
  read-backs.

## Acceptance boundary and open questions

- **inferred:** the Opening placement `(-400,600,900)` is a deliberate off-axis,
  high starting point, but only a live camera/frustum DRY and rendered frame can
  prove it is out of view while its shadow lands usefully on the proscenium.
- **inferred:** P06 station 5700 cm is safely before the declared topple block and
  24.89 s creak; its actual wing/camera composition, ceiling clearance and chain
  length require live route read-back and rendered acceptance.
- **UNCLEAR — asset state prohibited by brief:** the worktree lacks job 55's
  imported UE assets and delivered 24-link actor layout. Confirm the final asset
  paths, socket spelling and separately pivoted link actors in DRY. A monolithic
  chain does not satisfy P52B and must stop rather than silently claim multi-link
  swing.
- **UNCLEAR — runtime/render untested:** verify P56 activation plus visibility
  keys really reads as one-by-one ignition, hidden meshes cast hidden shadows,
  grouped-light flicker stays within GPU budget, P52B keys swing without chain
  separation, and P06 adds no audible event. No saved, runtime or visual tier has
  been reached.

## Conductor order

1. **declaration-proven:** rerun the harness and preview commands in
   `Saved/CodexConductor/P75ChandelierStaging_20261009/README.md:18-23`.
2. **declaration-proven:** follow DRY → reviewed plan hash → APPLY → P52B DRY/
   REBUILD → rendered review; exact markers and stops are in
   `Saved/CodexConductor/P75ChandelierStaging_20261009/README.md:25-49`.
3. **declaration-proven:** if rejected, use exact confirmation
   `REVERT P75 CHANDELIER`; never Save All.

## Version-control handoff

- **measured:** delivery is uncommitted on base
  `687b1c6259cd35c70e6933ee7bee6fd8d034e9b9`; this follows the P75 brief's
  instruction that the conductor commits. `.gitignore` exposes the Python and
  request files but ignores generated plans/results/PNGs and the folder README,
  so the conductor must explicitly force-add the named ignored deliverables if
  they belong in history (`.gitignore:35-49`).
