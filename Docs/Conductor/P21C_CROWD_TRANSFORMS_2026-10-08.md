# P21C — preserve the five originals' keyed crowd transforms (8 October 2026)

## Outcome

- **[declaration-proven]** Cluster A's five originals are no longer moved at the
  level or checked against the offline placeholder poses. Their single existing
  `LS_Clams` Transform track is the placement authority; the APPLY loop passes
  that exact track forward without setting actor location or rotation
  (`Saved/CodexConductor/s3_crowd_structure.py:971`).
- **[declaration-proven]** Each original receives only new ADDITIVE roll sections
  on its existing Transform track. `set_blend_type(ADDITIVE)` is immediately read
  back through UE 5.8's `get_blend_type()` field and must contain `ADDITIVE`
  (`Saved/CodexConductor/s3_crowd_structure.py:714`).
- **[declaration-proven]** Each of the 15 copies receives a fresh Transform track
  with an absolute full-range section plus its additive sway sections
  (`Saved/CodexConductor/s3_crowd_structure.py:700`).
- **[measured offline]** The harness passes **49/49**: 31 positive and 18 negative
  controls. New controls prove placement authority, all three census windows,
  acceptance of location-only teleport keys, teleport reporting, roll-key
  conflict ranges and refusal of foreign additive sections
  (`Tools/Mocap/test_s3_crowd_structure.py:49`,
  `Tools/Mocap/test_s3_crowd_structure.py:107`,
  `Tools/Mocap/test_s3_crowd_structure.py:138`).
- **[measured offline]** Planner DRY and APPLY regenerated the plan and three PNG
  previews from read-only `E:/PussStage/DerivedAssets/S3MocapIntensity` inputs.
  The recoverable pre-write snapshot is
  `Backups/PreS3CrowdPlan-P21C-PLAN-20261008-1`; all three PNGs were visually
  inspected. Cluster A is explicitly labelled as reference-only because live
  Transform tracks own its positions (`Tools/Mocap/s3_crowd_structure.py:381`).
- **[inferred; pending conductor live DRY]** No exact original key values,
  teleport distance, or camera-path crossing is claimed here. This offline run
  did not access Unreal, MCP, PIE, Blender, `Content/`, or the main-tree files.

## Guard and read-back design

- **[declaration-proven]** DRY evaluates every original's keyed transform in
  establishing `[360,552)`, frenzy `[552,2160)`, and choir `[2828,4488)` Scene
  frames after applying the +22 `LS_Clams` offset. It logs source keys, evaluated
  positions, teleports and window-local ranges in
  `S3_CROWD_ORIGINAL_TRANSFORMS` (`Saved/CodexConductor/s3_crowd_structure.py:514`,
  `Saved/CodexConductor/s3_crowd_structure.py:941`).
- **[declaration-proven]** DRY samples active live and proposed camera paths per
  frame and reports crossings within the argument-backed 185 cm clearance. The
  teleport reporting threshold is also argument-backed, defaulting to 250 cm
  (`Saved/CodexConductor/s3_crowd_structure.py:600`,
  `Tools/Mocap/s3_crowd_structure.py:499`).
- **[declaration-proven]** APPLY no longer refuses merely because Transform tracks
  exist. It refuses only foreign additive sections or absolute `Rotation.X` keys
  inside the proposed sway windows, reporting half-open frame ranges
  (`Saved/CodexConductor/s3_crowd_structure.py:127`,
  `Saved/CodexConductor/s3_crowd_structure.py:956`). Location/yaw keys, including
  Gary's 1461/1462 teleport, are not conflicts.
- **[declaration-proven]** Original Transform snapshots exclude only the newly
  recorded additive sections and must compare structurally within the required
  `1e-4` float tolerance after save/read-back.
  Copy Transform tracks are separately recorded and compared
  (`Saved/CodexConductor/s3_crowd_structure.py:115`,
  `Saved/CodexConductor/s3_crowd_structure.py:801`,
  `Saved/CodexConductor/s3_crowd_structure.py:821`).
- **[declaration-proven]** REVERT looks up the recorded existing track and removes
  only the recorded additive section names, then requires the untouched original
  snapshot. It does not remove an original track or restore/rewrite an original
  actor transform (`Saved/CodexConductor/s3_crowd_structure.py:904`).
- **[declaration-proven]** APPLY/REVERT still create a record and `Backups/` copy
  before mutation, require the exact three-package dirty census, save only the
  map and two sequences, and finish with run-id success markers
  (`Saved/CodexConductor/s3_crowd_structure.py:631`,
  `Saved/CodexConductor/s3_crowd_structure.py:785`,
  `Saved/CodexConductor/s3_crowd_structure.py:1049`).

## Conductor run order

1. **[declaration-proven]** Run
   `python Tools/Mocap/test_s3_crowd_structure.py E:/PussStage`; require
   `S3_CROWD_HARNESS|passed=49|failed=0|positive=31|negative=18`.
2. **[pending live measurement]** With PIE stopped, Sequencer closed and zero
   dirty packages, execute the checked-in DRY args through
   `ExecuteProjectPythonFile`. Require `writes=0|dirty=0`, five existing tracks,
   empty `transform_conflicts`, and `live_cut_layout=OK`.
3. **[pending live measurement]** Review the full
   `S3_CROWD_ORIGINAL_TRANSFORMS` JSON. Require readable blend-field API data for
   every original section; record the actual 1461/1462 teleport rows and every
   camera-path crossing or explicit unreadable-camera verdict.
4. **[pending live mutation]** Set a fresh run id, mode `APPLY`, confirmation
   `APPLY S3CROWD`. Require a `PreS3Crowd-<run>` backup and
   `S3_CROWD_APPLY_OK|...|copy_poses=15|original_keys_unchanged=5|owned_additive_sections=OK|dirty=0`.
5. **[pending saved read-back]** Restart cleanly and DRY again. Require 15 copy
   poses/tracks, five unchanged original snapshots, owned additive sections,
   zero cut gaps, zero writes and zero dirty packages.
6. **[pending runtime/rendered acceptance]** Run both crowd benchmarks, then
   review the establishing, frenzy/teleport, choir, B06 handoff, cloth/feet and
   every reported camera clearance. Automation does not accept the look.

## Open acceptance

- **[inferred]** The 185 cm camera-clearance and 250 cm teleport thresholds are
  review defaults, not Gary-approved creative values.
- **[inferred]** The tool expects one authoritative existing Transform track per
  original. Live DRY will return `ORIGINAL_TRANSFORM_TRACK_COUNT` rather than
  guessing if that assumption has changed.
- **[inferred]** Performance, cloth stability, planted feet, additive-sway feel,
  saved Unreal state and rendered quality remain unproven until the conductor
  completes the live steps above.
