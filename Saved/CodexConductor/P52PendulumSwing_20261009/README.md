# P52 motion-driven pendulum

Offline delivery only. Nothing in this folder has been run in Unreal or Blender.

The editor tool samples the Infinity Stage camera evaluator at a deterministic
fixed step. That evaluator reads the Passage route and the managed Master's
absolute `Camera.SpeedMultiplier` score, so section moves carried by patch K are
already reflected. The pure core converts support acceleration into damped
forward/lateral pendulum motion, adds the existing idle sway, and jointly
decimates pitch/yaw under an error bound.

## Run order (for the conductor, later)

1. Review `Scripts/patches/2026-10-09_sway_kick.patch`; it is held and unbuilt.
2. Place and name the prop, then edit `pendulum_swing_args.json`. Gary owns the
   look values: chain length, damping, idle amplitudes/period and decimation error.
3. Keep the editor on the production world with zero dirty packages and no
   Sequencer open. Run `pendulum_swing_request.json` in `DRY` mode.
4. Inspect the report's maximum angles, peak times against nearest cue IDs, key
   count, reconstruction error, and input fingerprint.
5. Set mode `APPLY` and confirm exactly `APPLY P52_PENDULUM`; run once. The tool
   records and backs up Master + level before mutation, writes only its named
   transform track, reads keys back numerically, and narrowly saves named packages.
6. After Passage length/speed work, run `CHECK` (no confirm). `stale=1` means the
   recorded speed-key fingerprint differs.
7. To update, set `REBUILD` and confirm `REBUILD P52_PENDULUM`. It first refuses
   any hand edit to the owned keys, then removes, re-simulates, and reapplies.
8. To remove, set `REVERT` and confirm `REVERT P52_PENDULUM`. It refuses drift,
   removes only the owned track/binding, saves narrowly, and archives the record.

`DRY`/`CHECK` never mutate Unreal. APPLY/REBUILD/REVERT require exact confirm
strings. Any unexpected dirty package, wrong project/world, PIE, open Sequencer,
duplicate target/binding, non-owned transform track, missing record, or numerical
drift stops before save.

## Chain look (not authored)

A cheap non-physics chain can share the prop's pendulum rotation: parent rigid
link actors beneath one support pivot, copy the same yaw/pitch to each link, and
apply a small link-index time delay (for example 0.02-0.04 s per link) sampled
from the same deterministic curve. Do not rotate each link independently around
its own centre; that shortens/breaks the chain. This remains inferred design,
not implemented, because the pending Hyper3D mesh and link hierarchy are absent.

## Offline harness

Run:

`python Saved/CodexConductor/P52PendulumSwing_20261009/test_pendulum_offline.py`

It writes `harness_result.json` and `pendulum_braking_preview.ppm` and prints the
two `P52_PENDULUM_*` result lines.
