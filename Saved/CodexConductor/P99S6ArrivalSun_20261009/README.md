# Job 99 — S6 arrival parcan and sun disc

Offline delivery only. Nothing here has been run in Unreal, PIE, MCP, or Blender.

## Split DRY and PIE evidence

Run `p99_request.json` with PIE stopped. This non-PIE DRY records the editor
actor/component census, existing sun/sky settings, and S6 property bindings.
It emits `P99_S6_DRY_OK` with `pie=0` and must leave the dirty census unchanged.

The conductor separately schedules `p99_pie_probe_request.json` after manually
pausing in the first six seconds of Scene 6. The probe never starts, stops,
scrubs, or quits PIE. It records:

- the live PlayerCameraManager pose/FOV and a 3 x 3 central frustum trace;
- every on-screen `SM_Lantern_ParCan` ISM instance, ranked by distance from frame
  centre, including its actor, component and instance index;
- for a Structure fixture, the exact cue GUID, attachment GUID and attachment
  label reconstructed in the same Station/attachment order as
  `GatherFixturePlacements`;
- matches against the Puss-light, Job 35, Jobs 30/43, P06 fixture/FX/scaffold,
  and P01-practicals records;
- every sky/sun component, hidden/visible state, sun intensity/source angle,
  S6 visibility/property tracks, and whether the sun direction is inside the
  live camera frustum.

Success is `P99_S6_PIE_PROBE_OK`. APPLY requires paths and SHA-256 hashes for
both reports.

## Choose one obstruction action from the DRY

- `HIDE_ACTOR_S6`: only for a standalone one-mesh actor. APPLY adds an exact
  `("bHidden", "bHidden")` visibility track to `LS_DevScene_06`; the bool
  channel stores VISIBLE, so `False` hides. A multi-instance actor is refused.
- `MOVE_SHOW_ATTACHMENT`: for the likely Structure fixture case. Copy the exact
  cue/attachment GUIDs from `selected_obstruction.structure_instance` and set an
  approved `obstruction_move_delta_cm`. APPLY moves that one authoritative Show
  light row, rematerializes only Passage 6 and its Structure, and records the
  original transform. It never deletes a row.

The second route necessarily changes the corresponding fixture during P06 too;
the S6-only hide route cannot address one ISM instance independently.

## Sun route

APPLY reuses the named S6 SkyAtmosphere or creates `P99 S6 SkyAtmosphere` hidden
by default. S6 tracks show the sky and existing dusk sun, restore state on exit,
rotate the sun to args elevation/azimuth, and override only S6 intensity and
SourceAngle. The editor sky remains hidden under P18. Creative values are args;
the shipped 4 degrees / 2 lux / 1.22 degrees are review defaults, not approval.

## Ordered runbook

1. Run the offline harness.
2. With PIE stopped, run `p99_request.json`; require `P99_S6_DRY_OK` and review
   the actor/component, sun/sky, and S6 binding censuses.
3. Manually reach and pause in the first six seconds of S6, then run
   `p99_pie_probe_request.json`; require `P99_S6_PIE_PROBE_OK`.
4. Stop PIE manually. Put both report paths and SHA-256 hashes in args, select
   the exact obstruction target/action, and obtain Gary's creative approval.
5. APPLY from a clean editor, verify named-package read-back, then capture the
   planned stills. REVERT remains a separate non-PIE operation.

### Superseded pass-1 sequence (kept only as failure history)

1. `python Saved/CodexConductor/P99S6ArrivalSun_20261009/test_p99_offline.py`
2. In PIE, manually reach Scene 6 arrival and pause within 0–6 s. Run
   `p99_request.json`. Review `selected_obstruction`, `provenance`,
   `projected_parcan_instances`, `sun_in_camera`, `sky_sun_census`, and
   `s6_binding_census`.
3. Stop PIE manually. Do not let this tool do it. Copy the exact DRY report path
   and SHA-256 into args; select one obstruction action and exact target IDs.
4. Obtain Gary's approval for the move delta and sun values. Set mode `APPLY`
   and confirm `APPLY P99 S6 ARRIVAL SUN`; run once from a clean editor world.
5. Require `P99_S6_APPLY_OK`, named-package read-back and `dirty=0+0`.
6. Capture the stills below, then let Gary judge. Automation is not visual
   acceptance.
7. To undo, set mode `REVERT`, confirm `REVERT P99 S6 ARRIVAL SUN`, and run.
   Require `P99_S6_REVERT_OK` and clean read-back.

## Stills plan and harness controls

- Before/after at S6 +0.25 s, identical live camera: frame-centre parcan.
- After at S6 +0.25 s and +2.0 s: sun disc and its reflection together; record
  reported sun UV, source angle, lux and exposure.
- Negative controls: P05/S5 and the editor viewport show no sky/disc; after S6,
  restore-state leaves the sky hidden.
- Revert still at S6 +0.25 s reproduces the original parcan/sky state.

Offline harness: `P99_HARNESS|pass=29|fail=0`. Positive controls cover enum/GUID
normalization, centre-frustum projection, both APPLY routes, and REVERT. Negative
controls cover malformed GUIDs, behind-camera sun, missing confirms/report,
unset target, zero move, inert `bHiddenInGame`, broad saves, and editor-control
calls.

