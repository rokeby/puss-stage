# P21B — Scene 3 clustered-crowd re-plan (8 October 2026)

## Outcome

- **[measured offline]** The planner read only the two analysis JSONs under
  `E:/PussStage/DerivedAssets/S3MocapIntensity`, recorded their SHA-256 hashes,
  and generated a 20-member plan from the five retained actors plus 15 copies
  (`Tools/Mocap/s3_crowd_structure.py:244`,
  `Tools/Mocap/s3_crowd_structure.py:297`). Shore05 is not a planned source.
- **[measured offline]** The harness passes **39/39**: 25 positive and 14
  negative controls. It covers count, clusters, spacing, exclusions, facing,
  determinism, quarter-period offsets, source removal, shot order, the final
  15 seconds of B06, original-glint preservation, B03 resumption, cut coverage,
  preview generation, baseline gating and mutation order
  (`Tools/Mocap/test_s3_crowd_structure.py:44`,
  `Tools/Mocap/test_s3_crowd_structure.py:123`).
- **[measured offline]** The three review PNGs were regenerated and inspected:
  [`P21_S3_CROWD_PLACEMENT_preview.png`](Previews/P21_S3_CROWD_PLACEMENT_preview.png),
  [`P21_S3_CROWD_TIMELINE_preview.png`](Previews/P21_S3_CROWD_TIMELINE_preview.png),
  and [`P21_S3_CROWD_SHOTS_preview.png`](Previews/P21_S3_CROWD_SHOTS_preview.png).
  Their deterministic renderers are in the planner
  (`Tools/Mocap/s3_crowd_structure.py:358`,
  `Tools/Mocap/s3_crowd_structure.py:413`).
- **[inferred; Gary to judge]** Camera poses, the three cluster centres, 2.5°
  roll amplitude and the selected 35/50 mm lenses are review defaults, not
  rendered acceptance (`Tools/Mocap/s3_crowd_structure.py:58`,
  `Tools/Mocap/s3_crowd_structure.py:86`).

## Plan

- **[declaration-proven]** The plan is exactly three clusters: A = 5 retained
  actors, B = 7 copies, C = 8 copies. Nearest-neighbour spacing is constrained
  to 80–150 cm; members face the clam with a bounded ±4° variation
  (`Tools/Mocap/s3_crowd_structure.py:58`,
  `Tools/Mocap/s3_crowd_structure.py:179`,
  `Tools/Mocap/s3_crowd_structure.py:318`).
- **[declaration-proven]** A small phase ripple runs within each cluster. The
  cluster bases are 0°, 90° and 180°, so adjacent clusters differ by one
  quarter of the 3.6-second period (`Tools/Mocap/s3_crowd_structure.py:58`,
  `Tools/Mocap/s3_crowd_structure.py:211`).
- **[declaration-proven]** Establishing is Scene frames `[360,552)` at 35 mm.
  Subtracting the known 22-frame nested offset gives live B03 `[398,838)`;
  cutting out the establishing interval makes B03 resume at frame 552
  (`Tools/Mocap/s3_crowd_structure.py:74`,
  `Tools/Mocap/s3_crowd_structure.py:86`,
  `Saved/CodexConductor/s3_crowd_structure.py:113`).
- **[declaration-proven]** Chorus coverage is a 35 mm cluster wide
  `[2806,3360)`, then 50 mm group close-ups `[3360,3720)` and
  `[3720,4166)`. The wide bridges the live B07 end and includes the chorus
  start at frame 3072 (`Tools/Mocap/s3_crowd_structure.py:90`).
- **[declaration-proven]** B06 becomes `[4166,4526)`: exactly 360 frames / 15 s,
  ending at its existing end frame. B08 remains on its live range, including
  the existing 10-frame overlap (`Tools/Mocap/s3_crowd_structure.py:303`,
  `Tools/Mocap/s3_crowd_structure.py:337`).

## Guarded editor tool

- **[declaration-proven]** APPLY refuses anything other than five visible source
  actors, reports each binding and cloth/body component signature, and stops if
  an existing actor transform track would override the proposed clustered
  placement (`Saved/CodexConductor/s3_crowd_structure.py:293`,
  `Saved/CodexConductor/s3_crowd_structure.py:616`).
- **[declaration-proven]** Before mutation it writes the record and a
  `Backups/PreS3Crowd-<run>` copy of the map and both sequences. It records the
  retained actors' original transforms so REVERT restores them before removing
  only tool-owned actors, bindings and cameras
  (`Saved/CodexConductor/s3_crowd_structure.py:254`,
  `Saved/CodexConductor/s3_crowd_structure.py:583`,
  `Saved/CodexConductor/s3_crowd_structure.py:628`).
- **[declaration-proven]** Save is limited to
  `L_InfinityStage_V1VerticalSlice`, `LS_DevScene_03` and `LS_Clams`, requires
  that exact dirty census, reads back all 20 poses/bindings/cuts, then emits
  `S3_CROWD_APPLY_OK` with the run id and `dirty=0`
  (`Saved/CodexConductor/s3_crowd_structure.py:501`,
  `Saved/CodexConductor/s3_crowd_structure.py:701`).

## Conductor run order

1. **[measured offline in this worktree]** Run
   `python Tools/Mocap/test_s3_crowd_structure.py E:/PussStage`; require
   `passed=39|failed=0|positive=25|negative=14`.
2. **[pending editor read]** With PIE stopped, Sequencer closed and zero dirty
   packages, run `Saved/CodexConductor/s3_crowd_structure.py` in DRY mode through
   `ExecuteProjectPythonFile`.
3. **[pending hard gate]** Require DRY to confirm: the expected world; exactly
   Shore01, 02, 03, 04 and 06 visible; one source binding and its expected
   animation per actor; non-empty live-cloth signatures; no existing actor
   transform tracks; inactive nested cuts; the five root cuts below; the saved
   five-figure baseline gate; `writes=0|dirty=0`. The tool prints cut mismatches
   explicitly (`Saved/CodexConductor/s3_crowd_structure.py:606`).
4. **[pending mutation]** Set a fresh run id, mode `APPLY`, confirmation
   `APPLY S3CROWD`. Require the backup path and
   `S3_CROWD_APPLY_OK|...|total=20|clusters=3|cameras=4|poses=20|...|dirty=0`.
5. **[pending saved read-back]** Restart cleanly, run DRY again and require
   `state=applied`, 15 created actors, four cameras, 30 created possessable
   bindings, 20 matching poses, zero cut gaps, zero writes and zero dirty
   packages.
6. **[pending PIE measurement]** Run both `s3_crowd_bench` windows with stage
   `crowd`; compare median/p90/max frame time and new GPU-timeout lines against
   the recorded five-figure baseline. Revert on instability with confirmation
   `REVERT S3CROWD`.
7. **[pending rendered acceptance]** Review the establishing frame, cluster
   clearance from clam/millstone/live camera paths, feet and cloth, frenzy
   onset, soothing transition, all three choir shots, B06 glint handoff and B08.

Live root cuts DRY must match after the 22-frame conversion:

| Camera | Expected Scene range |
| --- | --- |
| B03 | `[398,838)` |
| B02 | `[834,1711)` |
| B07 | `[1518,2806)` |
| B06 | `[2798,4526)` |
| B08 | `[4516,4836)` |

## Open acceptance

- **[inferred]** The offline exclusion points do not prove clearance from every
  interpolated live camera-path sample; DRY plus rendered review owns that
  decision.
- **[inferred]** Twenty Chaos-cloth figures may exceed the performance budget;
  only the paired PIE bench can accept it.
- **[inferred]** Deterministic animation and additive roll do not prove planted
  feet, stable cloth, invisible crossfades or a convincing choir. Gary owns the
  look decision.
