# P52 - cue-kick sway and motion-driven pendulum report

Date: 9 October 2026. Scope: offline only. Unreal, PIE, MCP, Blender and builds
were not opened or run.

## Delivered

- **declaration-proven:** `Scripts/patches/2026-10-09_sway_kick.patch` adds
  `KickCueIds`, `KickAmplitudeDegrees` and `KickDecaySeconds` to cord sway; cue
  IDs resolve to compiled Passage cue times and raw seconds are refused
  (`Scripts/patches/2026-10-09_sway_kick.patch:52-80,128-144`).
- **declaration-proven:** the held patch returns through the established idle
  calculation when no kick is present, and includes an exact equality automation
  assertion for the no-kick compatibility contract
  (`Scripts/patches/2026-10-09_sway_kick.patch:29-34,186-192`).
- **declaration-proven:** `pendulum_core.py` implements deterministic fixed-step,
  small-angle damped motion from support acceleration, with joint pitch/yaw
  error-bounded decimation and numerical drift comparison
  (`Saved/CodexConductor/P52PendulumSwing_20261009/pendulum_core.py:104-177,195-201`).
- **declaration-proven:** `pendulum_swing.py` exposes DRY/APPLY/REVERT/REBUILD/CHECK,
  fingerprints the absolute Master speed channel, samples the project's camera
  evaluator (route plus camera score), writes one named owned transform track,
  refuses drift, backs up before mutation, and narrowly saves only Master/level
  (`Saved/CodexConductor/P52PendulumSwing_20261009/pendulum_swing.py:24-28,179-222,286-346,358-425`).
- **declaration-proven:** target lookup checks existing bindings before
  `add_possessable`; an existing binding is never renamed, and any non-owned
  transform track causes refusal
  (`Saved/CodexConductor/P52PendulumSwing_20261009/pendulum_swing.py:251-304`).
- **declaration-proven:** `README.md`, args, runner and guarded MCP request give
  the conductor the ordered later-live procedure
  (`Saved/CodexConductor/P52PendulumSwing_20261009/README.md:9-36`).

## Offline proof

- **measured:** `git apply --check Scripts/patches/2026-10-09_sway_kick.patch`
  exited 0 against HEAD `89c3268`. The patch is held; it was not applied for
  delivery and was not compiled.
- **measured:** Python byte-compilation exited 0 for the core, editor tool,
  runner and harness.
- **measured:** the offline harness passed 10/10. Positive controls prove
  constant speed gives idle only, braking gives forward swing then decay, a
  changed speed input rebuild differs and equals a fresh simulation, decimation
  stays inside its error bound, and fingerprints are order-stable
  (`Saved/CodexConductor/P52PendulumSwing_20261009/test_pendulum_offline.py:50-87`).
- **measured:** negative controls prove hand-edited owned keys fail the drift
  comparison, non-zero kick without cue ID refuses, non-finite position/config
  refuse, and variable-step input refuses
  (`Saved/CodexConductor/P52PendulumSwing_20261009/test_pendulum_offline.py:89-113`).
- **measured:** the harness wrote `harness_result.json` and the braking preview
  `pendulum_braking_preview.ppm`; the result records offline-only, Unreal false,
  Blender false (`Saved/CodexConductor/P52PendulumSwing_20261009/test_pendulum_offline.py:115-158`).

## Unproven / acceptance boundary

- **inferred:** the Unreal Python calls and C++ held patch should compile/run in
  UE 5.8 based on current project precedents, but this brief forbade Unreal and
  builds. First live DRY, APPLY read-back, automation build, rendered swing and
  Gary's look acceptance remain unproven.
- **inferred:** chain links can share the same rigid pendulum angle with a small
  deterministic per-link time delay, parented from the support pivot. This is
  documented but not implemented because the Hyper3D mesh/link hierarchy is
  absent (`Saved/CodexConductor/P52PendulumSwing_20261009/README.md:38-46`).
- **inferred:** no worktree commit was created. The conductor brief says the
  conductor reviews/commits, and this sandbox cannot create the external worktree
  index lock at `E:/PussStage/.git/worktrees/PussStage5/index.lock`. Delivery is
  therefore an explicit-path working-tree change on HEAD `89c3268`.

## Conductor command order

1. Run the offline harness again.
2. Review the held patch, then apply/build it only in a conductor build window.
3. Edit the args for the placed prop and run DRY.
4. Review angle peaks/cue proximity/preview and Gary-owned defaults.
5. APPLY with `APPLY P52_PENDULUM`; later use CHECK after any retime.
6. REBUILD with `REBUILD P52_PENDULUM`, or remove with `REVERT P52_PENDULUM`.

Harness result lines:

`P52_PENDULUM_HARNESS|PASS=10|FAIL=0|TOTAL=10`

`P52_PENDULUM_CONTROLS|POSITIVE=5|NEGATIVE=5|OFFLINE=1|UNREAL=0|BLENDER=0`
