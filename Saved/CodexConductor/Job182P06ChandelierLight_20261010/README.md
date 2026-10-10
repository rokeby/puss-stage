# Job 182: P06 chandelier candle light

Offline-built, live-ready Unreal project-Python tool. This job did not access
Unreal, MCP, PIE, Blender, `E:/PussStage`, or any Niagara swarm actor.

The JSON defaults are proposals for Gary to tune, not approved look values:

- eight shadowless point lights, four groups of six candle tips and four groups
  of five, each placed at its group mean;
- 260 cd, 2050 K, 225 cm attenuation, 6 cm source radius;
- one shadowless soft iron fill at body-local `[90, 0, -95]` cm, 110 cd,
  2000 K, 280 cm attenuation and 35 cm source radius;
- 1.75 cm flame-tip offset, 0.5 cm candle/socket tolerance;
- 1.25x mesh-bounds framing margin and 1600x900 review still.

`DRY` and `REVIEW` require an owned PIE. They scan P06, choose a frame where the
Iron3 mesh bounds are on screen, and restore transport/view state. `REVIEW`
uses `Shore Cast Review Camera` only in the PIE copy, approaches the mesh from
the active P06 passage camera side, fits the body-only bounds, sets post-process
blend weight to zero, and never sets an exposure value. It requires all 44 exact
`ChandelierFlameFX` components to be active, visible, registered (where exposed)
and `was_recently_rendered(2.0)`.

`APPLY`, `READBACK` and `REVERT` require PIE stopped and the exact clean editor
world. APPLY backs up the level, adds nine exactly tagged PointLight actors,
attaches them to `P75 P06 Chandelier Body`, saves only the level, and reads every
property back. REVERT checks the active record and exact saved state, backs up
again, removes only those nine tagged actors, saves only the level, proves their
absence, and archives the record. No file is deleted.

## Offline harness

```powershell
python Saved/CodexConductor/Job182P06ChandelierLight_20261010/test_job182_offline.py
python -m py_compile Saved/CodexConductor/Job182P06ChandelierLight_20261010/job182_core.py Saved/CodexConductor/Job182P06ChandelierLight_20261010/job182_chandelier_light.py Saved/CodexConductor/Job182P06ChandelierLight_20261010/job182_run.py
```

## Live run order

1. With a clean editor, start an owned PIE at P06. Leave `mode=DRY`, confirmation
   and reviewed hash blank. Submit `job182_request.json`. Require
   `JOB182_CHANDELIER_LIGHT_DRY_OK`, 44 socket rows, 44 `actor_at_socket=true`
   rows, the exact Iron3 mesh, a chosen on-screen frame, and `dirty=0+0`.
2. Copy the reported `plan_sha256` into `reviewed_plan_sha256`. Review every
   value as a Gary-tunable proposal. Stop PIE without saving playback state.
3. Set `mode=APPLY`, `confirm="APPLY JOB182 CHANDELIER LIGHT"`. Submit. Require
   the APPLY marker, `group_lights=8`, `fill_lights=1`, `shadows=0`, a backup,
   exact level-only save, read-back and `dirty=0+0`.
4. Set `mode=READBACK`, clear confirmation. Submit in a fresh call. Require nine
   lights and `drift=false`.
5. Start a fresh owned PIE. Change the review output if the default already
   exists. Set `mode=REVIEW`, confirmation blank. Submit. Require the review
   marker, `active_niagara=44`, `recently_rendered=44`,
   `exposure_override=0`, restored state, the PNG and `dirty=0+0`.
6. Gary reviews/tunes the proposal from the still. The tool does not claim
   visual acceptance.
7. If rejected, stop PIE, set `mode=REVERT`,
   `confirm="REVERT JOB182 CHANDELIER LIGHT"`, and submit. Require nine removed
   lights, a second backup, targeted save, absence read-back and `dirty=0+0`.

At no point select, move, hide or delete a Niagara swarm actor. Never Save All.
