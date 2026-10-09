# P52b — Chain pendulum: multi-link chain carrying a rigid chandelier body (Codex, offline)

Read `_house_rules.md`. Offline only. Extends job 52 (committed 513255e2: `Saved/CodexConductor/P52PendulumSwing_20261009/`,
report `Docs/Conductor/P52_PENDULUM_SWING_REPORT_2026-10-09.md`) — reuse its integrator, decimation, owned-track APPLY/
REVERT/REBUILD, drift + staleness checks; do not fork them.
Gary 9 Oct (via Hyper3D): the hanging CHAIN must swing differently from its body.
Input: `chandelier_chain_v1` JSON from Hyper3D job 55 (cm, UE frame, origin = top hang point): count, length_cm,
links[] {index, pivot_cm, length_cm, mass_kg|null}, body {attach_cm, mass_kg}; masses inferred. Mesh not delivered yet:
build and test against a fixture JSON with that exact schema; validate the schema strictly.
Build: an N-link planar×2 (forward + lateral) compound pendulum (links + rigid end body), damped, driven by the support's
acceleration from the Passage motion exactly as job 52; deterministic fixed step; per-link rotation keys + body keys on
OWNED tracks; null masses → a documented default ratio (report). Stability guard (refuse/clip on blow-up, report dt).
Harness: + (N=1 reduces to job 52's single pendulum within tolerance; braking → links lag then body; rebuild after speed
change), − (schema violations refuse; hand-edited keys refuse REBUILD; non-finite refuse). Tiered report; worktree only.
