# P46 — Shadow-cat ACTION layer + Master-time-locked gait + bob variation (Codex, offline; HELD C++ patch)

Read `_house_rules.md` first; every rule applies. **C++ must be delivered as a HELD patch**: write it in your
worktree, export it as `Scripts/patches/2026-10-09_shadow_cat_actions.patch`, and do not build. Follow the memory
convention: hold edits as patches, applied later in a build window via `git apply`.

## Context (Gary 9 Oct)
- Puss's walking shadow is the AnimX cat. Gary wants scripted actions such as stretch, startle, look-around, sit,
  shake and arch, mostly during authored breaths.
- The actions are fully SCRIPTED. The GO1 dog is timed to the script. The rehearsal knob is WHEN each action
  happens. "Movement is quite key."
- The repeating gait bob should vary a little.
- Facts and code map: `Docs/Conductor/PUSS_CAT_ANIMATION_OPTIONS_2026-10-09.md`:
  - `InfinityStageCameraRig.cpp:37-80` (walk/idle direct single-node play);
  - `:585-591` and `:655-666` (play rate from camera speed);
  - `InfinityStageCameraRig.h:184-250` (bob settings);
  - `InfinityStageShadowCatComponent.cpp`.
- The current playback is real time (`PlayAnimation` + play rate), not locked to Master time.

## Build (C++ patch + tests)
1. **Master-time-locked playback.** Walk/idle pose = f(Master frame), not wall time:
   - walk phase = the integral of play rate over Master time from the Passage start, so scrubs and re-records land on
     the same pose (deterministic; scrub-safe; reverse-safe);
   - use the single-node instance's explicit position, not playing.
2. **Cat Action layer.** A list of actions, each with: animation asset (soft ref), start time, play rate,
   blend-in/out seconds, and "hold last frame" vs "return to gait".
   - Placement: rehearsal must move WHEN an action happens without touching anything else. Pick the cleanest of:
     (a) Passage-relative frames stored on the Passage section / Show passage settings, so they travel with the
     Passage;
     (b) a keyed Sequencer track on the camera rig.
     Justify the choice with file:line.
   - While an action is active it overrides walk/idle, Master-time-locked: pose = (frame − start) × rate, with
     inertial or crossfade blends at both ends.
   - The camera bob must not jump at the handover: fade the bob weight with the action blend.
3. **Bob variation.** A seeded, Master-time-deterministic slow drift (e.g. ±5 % play rate and bob gain over
   ~8–20 s), with occasional bounded per-stride variance.
   - Off by default: one bool plus amplitude settings.
   - Same seed, same result (memory: never two random draws in one expression; use explicit seeded streams).
4. **Automation tests** (`InfinityStage.Editor.*` style, in the patch):
   - identical pose at the same Master frame via two different scrub paths;
   - action start/end blend continuity;
   - bob variation deterministic and bounded;
   - actions move with their Passage when the Passage moves.
5. **Offline harness (Python):** checks the patch applies cleanly to HEAD (`git apply --check`) and runs a Python
   port of the phase/blend/variation maths with -/+ controls.
6. **README:** build-window steps, test names to run singly, and how to add one action (e.g. Idle_Stretching at
   Passage P03 +42 s).

Arch: no AnimX clip exists. Leave a slot for a custom clip asset path. Don't author animation.
