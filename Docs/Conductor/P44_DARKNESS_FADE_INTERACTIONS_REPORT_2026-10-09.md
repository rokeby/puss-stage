# P44 — S1 darkness/fade and I1/I3/I4/I5 transition handoff

## Outcome

- **declaration-proven:** The worktree now contains one read-only P44 probe and one per-item dispatcher for F4, F5, I1, I3, I4, and I5. The dispatcher excludes I2 because I2 is the reference pattern, and it accepts only explicit `DRY/APPLY/REVERT P44 <item>` confirmations. (`Saved/CodexConductor/P44DarknessFadeInteractions_20261009/p44_action.py:18-55`)
- **measured (offline):** No Unreal or Blender operation was performed. The probe and authoring tools are staged for the conductor; no Content asset, Show asset, level, or sequence was changed in this worktree. (`Saved/CodexConductor/P44DarknessFadeInteractions_20261009/harness_result.json:31-33`)
- **measured (offline):** The aggregate positive/negative harness passed 109/109: P44 dispatch/probe 22, F4 visibility 9, F5 fade 24, interaction transition 54. (`Saved/CodexConductor/P44DarknessFadeInteractions_20261009/harness_result.json:2-27`)

## F4 — total darkness before Klara's strike

- **declaration-proven:** F4 dispatches to the existing S1 visibility repair. That owner selects only `bHiddenInGame`, converts its stored hidden polarity to `bHidden` visible polarity, and leaves existing `bHidden` and `None` tracks untouched. (`Saved/CodexConductor/KlaraIngest/vis_fix.py:120-127`)
- **declaration-proven:** APPLY requires matching unchanged DRY evidence, backs up and records before mutation, permits only `LS_DevScene_01` to become dirty, saves that named sequence, and performs saved read-back; REVERT drift-checks and restores recorded state. (`Saved/CodexConductor/KlaraIngest/vis_fix.py:288-325`, `Saved/CodexConductor/KlaraIngest/vis_fix.py:328-365`)
- **inferred:** Repairing the inert S1 visibility tracks is the evidenced path to the requested pre-strike blackout, but neither offline code inspection nor saved track read-back proves TOTAL DARKNESS. The existing S1 PIE visibility probe and a rendered review remain acceptance gates.

## F5 — resolve 3:44 and retarget the fade

- **measured (saved snapshot):** The Master section containing `LS_DevScene_01` spans ticks 4,624,705–10,553,665 at 24,000 ticks/s. Thus S1 begins at 192.696041667 s (3:12.696); Master 3:44 is 31.303958333 s into S1, or frame 782.598958 at 25 fps, rounded to S1-local frame 783. (`Saved/CodexConductor/S1Snap/LS_Master_sem.json:1215-1221`, `Saved/CodexConductor/S1RigFade_20261009/s1_rig_fade.py:107-122`)
- **inferred (resolved clock authority):** Gary's “3:44” is treated as the Master clock. It lies inside S1 and explains why the earlier local-frame-282 design was about 20 s early; no saved evidence labels it as an S1-local or recording clock.
- **declaration-proven:** DRY/APPLY re-read the live Master section, refuse section-start or mapped-frame drift, and require the target still maps to frame 783. (`Saved/CodexConductor/S1RigFade_20261009/s1_rig_fade.py:314-344`)
- **declaration-proven:** The revised F5 tool retargets the existing visibility-off section from source frame 269/282 to frame 783 and ramps paired intensity/fog to zero over the configured 1–2 s interval. Existing one-frame intensity steps have both the nonzero and zero keys moved, preventing an old zero key from defeating the new fade. (`Saved/CodexConductor/S1RigFade_20261009/s1_rig_fade.py:650-717`)
- **declaration-proven:** APPLY takes its backup and transaction record before changes, asserts the exact scoped diff, saves only S1, and compares saved read-back; REVERT is available with a fresh backup and state-drift refusal. (`Saved/CodexConductor/S1RigFade_20261009/s1_rig_fade.py:814-892`, `Saved/CodexConductor/S1RigFade_20261009/s1_rig_fade.py:928-972`)
- **inferred:** Frame 783 is the correct retarget for the authored event under the Master-clock interpretation. Whether 1.52 s feels right and whether the emissive bulb pixels disappear smoothly are rendered-look decisions owned by Gary.

## I1/I3/I4/I5 — I2 shadow-curtain pattern

- **declaration-proven:** Every Interaction DRY includes a global census of both shadow cards and both shadow spots for I1–I5, including present/missing state. (`Saved/CodexConductor/interaction_shadow_transition.py:577-600`)
- **declaration-proven:** Each selected Interaction disables only cards that exist, creates or rewrites the twin shadow spots, preserves missing-card tolerance, and keys spawn/transform/intensity for the established darkness → curtain → light/shadow → drop order. (`Saved/CodexConductor/interaction_shadow_transition.py:701-733`)
- **declaration-proven:** P44 changes the reference interaction from I4 to the applied I2 pattern and assigns `/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_BoyPussRub` to I1/I3/I4/I5 as the current-best stand-in. (`Saved/CodexConductor/interaction_shadow_transition_args.json:2-31`)
- **declaration-proven:** Each APPLY is a separate named-sequence backup/save/read-back transaction; each REVERT refuses drift and restores or removes only recorded state. (`Saved/CodexConductor/interaction_shadow_transition.py:786-835`, `Saved/CodexConductor/interaction_shadow_transition.py:838-871`)
- **inferred:** The BoyPussRub material path is expected after gobo run 007, but Content is excluded from this worktree and asset existence is not offline-proven. APPLY deliberately refuses if the material cannot load. Final gobo content, softness, four curtain framings, and fade feel remain rendered acceptance.

## Probe and run order

- **declaration-proven:** The probe refuses PIE/SIE, an open Sequencer, the wrong world, or dirty packages; it reads the Master, S1 visibility, and all five Interaction inventories, then requires the dirty census to be unchanged before emitting `P44_PROBE_OK`. (`Saved/CodexConductor/P44DarknessFadeInteractions_20261009/p44_probe.py:197-250`)
- **declaration-proven:** The ordered conductor procedure is probe → F4 → probe → F5 → verified gobo 007 → I1/I3/I4/I5 one at a time, followed by saved-sequence tests and rendered review. Exact confirms, markers, and reverse-order REVERT are in the runbook. (`Saved/CodexConductor/P44DarknessFadeInteractions_20261009/README.md:22-58`)

## Version control

- **measured:** Git staging/commit is blocked by this managed worktree's read-only external git metadata: `Unable to create 'E:/PussStage/.git/worktrees/PussStage50/index.lock': Permission denied`. All deliverables remain present as unstaged worktree changes; no commit hash can be produced from this permission profile.

## Open acceptance boundary

- **inferred:** Until the conductor runs the probe and DRYs, exact live present/missing counts are UNCLEAR; this report does not substitute old records for a current census.
- **inferred:** Until APPLY, saved read-back, PIE checks, and rendered review, F4 darkness, F5 fade quality, and I1/I3/I4/I5 composition remain unverified.
