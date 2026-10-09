# P52b - multi-link chandelier chain pendulum report

Date: 9 October 2026. Scope: offline only. Unreal, PIE, MCP, Blender and builds
were not opened or run.

## Delivered

- **declaration-proven:** `chain_pendulum_core.py` imports job 52's core and
  reuses its fixed-step row validation, support-acceleration kinematics,
  decimator, reconstruction-error calculation, fingerprinting and drift
  comparison; it does not copy them
  (`Saved/CodexConductor/P52BChainPendulum_20261009/chain_pendulum_core.py:9-18,216-262`).
- **declaration-proven:** the Hyper3D fixture contract is strict: exact root,
  link and body keys; ordered count; finite positive dimensions/masses; top
  origin; continuous pivot geometry; and declared/summed total length. Null link
  masses resolve to `body.mass_kg * null_link_mass_ratio`; the documented
  Gary-owned default is 0.05
  (`Saved/CodexConductor/P52BChainPendulum_20261009/chain_pendulum_core.py:21-111`).
- **declaration-proven:** the solver is an N-link small-angle compound pendulum
  of uniform rigid links plus an end body mass, independently driven in Passage
  forward/lateral planes by job 52's support acceleration. It uses deterministic
  semi-implicit fixed steps, coupled mass/stiffness matrices, damping, per-link
  and rigid-body keys, error-bounded decimation, a pre-run `dt * omega_max`
  refusal, and explicit refuse/clip state guards whose dt and clip count are
  reported (`Saved/CodexConductor/P52BChainPendulum_20261009/chain_pendulum_core.py:114-256`).
- **declaration-proven:** N=1 delegates directly to job 52 for exact compatibility;
  for N>1 the body is the rigid end mass and receives the final link orientation,
  while upstream link orientations remain independently coupled
  (`Saved/CodexConductor/P52BChainPendulum_20261009/chain_pendulum_core.py:200-256`).
- **declaration-proven:** the later-live tool has DRY/APPLY/REVERT/REBUILD/CHECK
  with exact confirms, fingerprints schema/config/actor mapping plus the absolute
  speed input, reuses P52's dirty census/backup/narrow save, writes one named
  owned transform track per link and body, reads each back numerically, validates
  every owned track before any REBUILD/REVERT removal, and emits run-id markers
  (`Saved/CodexConductor/P52BChainPendulum_20261009/chain_pendulum.py:52-105,177-245,254-345`).

## Offline proof

- **measured:** Python byte-compilation exited 0 for the core, editor tool,
  runner and harness; offline import plus fixture argument validation printed
  `P52B_OFFLINE_IMPORT_OK|MODE=DRY|LINKS=3|BODY=Chandelier Body`.
- **measured:** the P52b harness passed 10/10: six positive controls cover null
  mass inference, exact N=1 reduction, braking with different link lag and body
  following the final link, deterministic speed-change rebuild, bounded
  decimation/stability reporting, and explicit clipping; four negative controls
  cover strict schema refusal, hand-edited-key drift, non-finite refusal, and
  unstable-dt refusal with dt in the error
  (`Saved/CodexConductor/P52BChainPendulum_20261009/test_chain_pendulum_offline.py:65-160`).
- **measured:** the unchanged P52 harness reran 10/10, and `git diff --check`
  exited 0. P52b wrote `harness_result.json` and `chain_braking_preview.ppm`;
  the result records offline-only, Unreal false and Blender false.

## Unproven / acceptance boundary

- **inferred:** the Unreal Python track calls should work in UE 5.8 because they
  deliberately reuse job 52's current implementation, but the brief forbade an
  editor and build. First live DRY, package backup, APPLY/read-back, CHECK,
  REBUILD, REVERT, rendered chain separation, and Gary's visual acceptance remain
  unproven.
- **inferred:** the pending Hyper3D JSON and meshes may expose a contract or pivot
  mismatch. The delivered fixture is synthetic and is intentionally replaced only
  after strict validation. The schema supplies body mass but no centre of mass or
  inertia tensor, so the supported deterministic interpretation is an end mass
  rigidly oriented with the last link; a delivered inertia requirement would need
  a schema revision rather than an assumed value.
- **measured:** no delivery commit could be created: the sandbox denied the Git
  worktree index lock at `E:/PussStage/.git/worktrees/PussStage11/index.lock`.
  The explicit-path changes remain in this worktree on base commit `afd18abd2c23`.
  **declaration-proven:** `.gitignore:43` ignores `Saved/Codex*/**`, so the
  conductor must force-add only the named P52b support artifacts when committing;
  the report and Python files already have narrower unignore rules.

## Conductor command order

1. **declaration-proven:** rerun the offline harness command from the P52b README.
2. **declaration-proven:** replace the fixture with delivered JSON, update ordered
   actor labels, then run DRY from a clean production world with Sequencer closed.
3. **declaration-proven:** review resolved masses, dt/stability, clips, key counts
   and preview; Gary chooses look values before APPLY.
4. **declaration-proven:** APPLY with `APPLY P52B_CHAIN_PENDULUM`; use CHECK after
   speed/schema changes, REBUILD with its exact confirm, or REVERT with its exact
   confirm (`Saved/CodexConductor/P52BChainPendulum_20261009/README.md:21-43`).

Harness result lines:

`P52B_CHAIN_PENDULUM_HARNESS|PASS=10|FAIL=0|TOTAL=10`

`P52B_CHAIN_PENDULUM_CONTROLS|POSITIVE=6|NEGATIVE=4|OFFLINE=1|UNREAL=0|BLENDER=0`
