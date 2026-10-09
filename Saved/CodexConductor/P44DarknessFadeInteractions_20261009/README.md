# P44 darkness, fade, and interaction-transition runbook

Offline-authored only. Nothing in this bundle has been run in Unreal, and no
rendered look is accepted. `p44_probe.py` is read-only with respect to Unreal;
`p44_action.py` dispatches one guarded item at a time to its owner tool.

## Items and owners

| Item | Owner tool | Written package |
| --- | --- | --- |
| F4 | `KlaraIngest/vis_fix.py` | `LS_DevScene_01` only |
| F5 | `S1RigFade_20261009/s1_rig_fade.py` | `LS_DevScene_01` only |
| I1/I3/I4/I5 | `interaction_shadow_transition.py` | selected Interaction sequence only |

All items support `DRY`, `APPLY`, and `REVERT`. The P44 confirmation is exactly
`<MODE> P44 <ITEM>`; the dispatcher supplies the owner tool's independent
confirmation. Each owner tool refuses PIE/SIE, an open Sequencer, a dirty census,
or state drift; APPLY and REVERT back up before mutation, write a transaction
record, save only the named sequence, and read it back.

## Ordered conductor run

1. Stop PIE/SIE, close Sequencer, load the vertical-slice world, and require zero
   dirty content and map packages.
2. Give `p44_probe_args.json` a unique run id and execute
   `p44_probe_request.json`. Require:
   `P44_PROBE_OK|...|mutated=0|dirty=0|s1_frame=783|...`.
   Inspect every Interaction's present/missing cards, spots, and light function.
3. F4 first: set `p44_action_args.json` to `F4`, `DRY`, `DRY P44 F4`, unique id.
   Execute `p44_action_request.json`; require `VISFIX_DRY_OK`. Review every inert
   `bHiddenInGame` target. Then use a new id with `APPLY` / `APPLY P44 F4` and
   require `VISFIX_APPLY_OK`. Run the existing S1 `vis_fix_pie_probe.py`; only
   that and a rendered review can accept total darkness.
4. Re-run the P44 probe. F5: `DRY P44 F5`, then `APPLY P44 F5`, fresh ids.
   Require target frame 783, source frames 269/282, a 38-frame default ramp,
   `S1_RIG_FADE_DRY_OK`, then `S1_RIG_FADE_APPLY_OK`. Review Master 3:44 with at
   least two seconds on both sides.
5. Ensure gobo run 007 is APPLY+VERIFY complete and
   `/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_BoyPussRub` loads. It remains
   I2's gobo; the other four use it only as a stand-in.
6. In order I1, I3, I4, I5: run P44 `DRY`, inspect the global per-Interaction
   inventory and preview, then `APPLY` with a fresh id. Require the corresponding
   `INTERACTION_SHADOW_TRANSITION_<MODE>_OK` marker after each call. Do not batch
   the four named saves.
7. Run saved-sequence binding tests, then rendered reviews. Automation proves
   structure and persistence, not total darkness, fade feel, curtain framing,
   or the gobo look.

## Revert

Revert in reverse apply order. For each item, set `mode` to `REVERT`, confirm
`REVERT P44 <ITEM>`, and use a fresh id. Every owner tool drift-checks against
its APPLY record and takes `Backups/Pre...Revert-<run>` before restoring.

## Offline harness

From project root:

```powershell
python Saved\CodexConductor\P44DarknessFadeInteractions_20261009\run_offline_harness.py
```

Expected terminal line: `P44_OFFLINE_HARNESS|pass=109|fail=0|total=109`.
