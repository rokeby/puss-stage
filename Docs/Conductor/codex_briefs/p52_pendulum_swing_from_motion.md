# P52 — Dramatic hanging swing: cue kick + motion-driven pendulum keys, rebuildable (Codex, offline; HELD C++ part)

Read `_house_rules.md`. Offline only. Dedupe: extends the fixtures bulb sway (built 9 Oct, 7f53ab6; patch
`Scripts/patches/2026-10-08_fixtures_bulb_light_sway.patch`): procedural sin(showSeconds·2π/period + phase), yaw 2.5° /
pitch 1.5° / 7 s, rigid rotation about the cord top, deterministic. First user: the swinging candle chandelier (Hyper3D
mesh pending; Gary wants it on a chain like the wing lights), but build it GENERIC for any hung prop.

## Gary (9 Oct)
Options 1 + 2, "as long as I don't need to key it manually and that wing speed changes will be reflected or rebuildable
so it stays realistic."

## Build
1. **Cue kick (C++, HELD patch)** on the sway settings: `KickAmplitudeDegrees`, `KickDecaySeconds` (exponential), kick
   times from Show data (cue ids, not raw seconds), added on top of the idle sway; still a pure function of show time
   (deterministic under scrub/jump). Automation tests incl. "bit-identical to today's sway when no kick is set".
   Deliver as `Scripts/patches/2026-10-09_sway_kick.patch` (git apply --check clean on HEAD); not built.
2. **Motion-driven pendulum keys (Python, offline + editor tool)**: `pendulum_swing.py` reads the hung prop's support
   motion along the Passage (Passage route + SpeedMultiplier/camera channel keys from the Show/Master, absolute keys;
   memory: patch K carries keys with moved sections), simulates a damped pendulum (length from the cord/chain, damping
   ratio arg) under the support's acceleration in route-forward and lateral, deterministic fixed-step integration, and
   writes yaw/pitch keys (decimated, error-bounded) to an OWNED track — never hand-authored keys. DRY reports max angle,
   peak times vs cues; APPLY/REVERT exact; **REBUILD** mode = REVERT + re-simulate + APPLY, refusing if the owned keys
   were hand-edited since APPLY (drift check). A staleness fingerprint of the input speed keys tells the conductor when a
   rebuild is due (cheap check usable after any passage relength/speed change).
3. Chain look: report how a multi-link chain could follow the pendulum angle (rigid links sharing the swing, slight
   per-link lag) without physics; implement only if cheap.
4. Harness: + (constant speed → only idle sway; braking → forward swing then decay; rebuild after a speed change differs
   and matches a fresh sim), − (hand-edited keys refuse REBUILD; kick without cue id refuses; non-finite input refuses).
Deliver in your worktree; the conductor reviews and commits. Next free job number after this: 53.
