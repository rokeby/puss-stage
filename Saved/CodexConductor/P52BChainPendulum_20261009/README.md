# P52b multi-link chandelier chain pendulum

Offline delivery only. Nothing in this folder has been run in Unreal or Blender.

`chain_pendulum_core.py` imports job 52's fixed-step input validation,
support-acceleration kinematics, decimator, reconstruction-error calculation,
fingerprinting and numeric drift comparison. It adds a small-angle coupled
compound-pendulum solve independently in the Passage-forward and lateral planes.
Each chain link is a uniform rigid rod; the rigid chandelier body is represented
as the end mass and takes the final link's orientation. A one-link schema delegates
directly to job 52 and is exact, not an approximation.

The fixture is the exact pending Hyper3D `chandelier_chain_v1` contract: root keys
`count`, `length_cm`, `links`, `body`; exact link/body keys; centimetres in UE frame;
origin at the top hang point. Unknown keys, missing keys, unordered indices,
non-finite/non-positive values, count mismatches, discontinuous pivots, and total
length mismatches refuse. Each null link mass resolves to
`body.mass_kg * null_link_mass_ratio`; the Gary-owned default is `0.05`, and every
resolved value is written into DRY/APPLY records.

## Conductor order for the later live run

1. Replace only `chandelier_chain_v1_fixture.json` with the delivered JSON after
   confirming it has the same exact schema. Update the ordered link/body actor
   labels in `chain_pendulum_args.json`; actor pivots must be authored at joints.
2. Keep the production world open with PIE and Sequencer closed and require an
   exact zero dirty-package census. Run the request in `DRY` mode.
3. Inspect resolved masses, stability `dt_seconds` / `dt_times_omega_max`, clip
   count, link/body key counts and decimation error. Gary owns damping, idle sway,
   angle/velocity caps, mass ratio and the final look. Default guard mode refuses;
   `clip` is available only as an explicit reviewed choice and reports every clip.
4. Set mode `APPLY`, confirm exactly `APPLY P52B_CHAIN_PENDULUM`, and run once.
   The tool reuses P52's backup and save gate, writes one named owned transform
   track per link plus body, reads every track back numerically, and saves only
   Master/level if those named packages are dirty.
5. After Passage speed edits, run `CHECK`; `stale=1` means schema, physics config,
   actor mapping, Passage range or absolute speed score changed.
6. Set `REBUILD` with `REBUILD P52B_CHAIN_PENDULUM` to update. It validates all
   live owned keys against the record before removing any. Hand edits refuse.
7. Set `REVERT` with `REVERT P52B_CHAIN_PENDULUM` to remove only owned tracks;
   the record is archived after clean narrow save.

APPLY/REBUILD/REVERT create a record and `Backups/PrePendulumSwing-<run>` before
mutation through the shared P52 implementation. Every mode emits a run-id marker.

## Offline harness

Run:

`python Saved/CodexConductor/P52BChainPendulum_20261009/test_chain_pendulum_offline.py`

It runs six positive and four negative controls and writes
`harness_result.json` plus `chain_braking_preview.ppm`.
