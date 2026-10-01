# Spec: `Saved/CodexStructure/s3_pit_deck_apply.py`: S3 pit-hole, pit liner and an oak deck in the S3 box

Gary (1 Oct, Rig & atmosphere session): "Yes, pit + deck". S3's box rises out of a dark slot like S1/S5/S6. Its cast
(hidden until landing by `s3_cast_reveal_apply.py`) then stand on an oak deck inside the box, at today's ground height.

## Why the deck (declaration-proven)
- `hangar_s3_plan.json` has `floor: false` and `hinge_z: −120`: S3's box has NO floor of its own, and its hinge is
  about 1.2 m below the ground. `hangar_ground_survey.json` S3 reads the ground at +120.1…+121.0 relative to the hinge.
- P03's ground is now the oak plane `Passage 03 - Floor` (`landscape_floors_record.json`; trimmed at the lip by
  `p03_mouth_floor_record.json`; top −5.0, bottom −6.0).
- Cutting the pit removes the cast's ground, so the box needs a deck.

## Writes (all level actors, tagged, recorded)
1. **TRIM + STRIPS:** give `Passage 03 - Floor` a hole over S3's swept footprint, by the SAME rule as the S1/S5/S6
   pit-holes.
   - Footprint: x = hinge .. hinge + reach + 25 cm, by ±(half_w + wall_t + 100 + 25) in the dock frame, with reach
     from `hangar_s3_plan.json`.
   - Trim the plane to end at the hinge (its near part, lip → hinge, keeps the actor). Add LEFT, RIGHT and FAR strips
     with the same mesh, material, thickness and z.
   - Tags `RigAtmos.PitFloor`, `RigAtmos.Scene3PitFloor`.
   - References: `plane_trim_record.json` (and the script that wrote it) for the trim; `plane_pithole_apply.py` for the
     strips.
2. **LINER:** a black open-topped liner under the hole, by `plane_pitliner_apply.py`'s rule.
   - Account for S3's `hinge_z −120`: the hanging box reaches 1.2 m lower than at S1.
   - Assert that the hanging box's lowest point (the builder geometry at pitch −90) clears the liner floor by at least
     50 cm.
3. **DECK** `S3 Hangar Deck`:
   - Engine Cube slab(s) ATTACHED to `S3 Hangar Root`, set in ROOT-RELATIVE coordinates. The level's saved root pose
     is HANGING (pitch −90; `hangar_build.py` sets it after spawning), so never place by world position at rest, and
     never rotate the root to place it.
   - Extent: x 0 .. depth (inside the box), y ±half_w, thickness 20 cm.
   - Top = the MEASURED oak floor top. In the dry run, trace or read it at the six Shore actors' XY BEFORE any write,
     then convert to root-relative z through the root's LANDED transform (hinge world location, pitch 0, the dock's
     yaw). Expect about +115 relative to the hinge. Print the measured value; refuse if the six disagree by more than
     2 cm.
   - Material: read it from `Passage 03 - Floor`.
   - Tag `RigAtmos.S3Deck`; cast shadows on.
   - Swing check (`hangar_build.py` ~211–213): over pitch −90 → 0, no deck point goes below `hinge_x − 25` in the dock
     frame, and the deck doesn't grow the plan's `reach_cm`.

## Guards and blockers
- Prerequisite: `s3_cast_reveal_record.json` exists, and the nine cast/clam actors and four removals are saved
  Hidden-in-Game. Otherwise REFUSE: a pit under visible figures is the fault we're avoiding.
- **Blocker sweep:** after the plan, list EVERY actor whose bounds intersect the hole prism, from floor top down to the
  liner floor, beyond the hinge. Mirror the builder's single sweep at `hangar_build.py:224` and
  `blocker_positive_control.py`.
  - Allowed: the S3 hangar pieces, the nine hidden cast/clam actors, the four hidden removals, `GroupActor0`,
    `LS_OrtalanSheetSway`, the hidden landscape `Passage 3 - Wet Ground`, and the plane being trimmed.
  - Anything else: REFUSE and print it.
- Standard guards:
  - world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
  - no PIE;
  - BOTH dirty lists empty;
  - no ZZ_/TEMP_ actors;
  - record absent.
- Back up first to `Backups/PreS3PitDeck-<stamp>/` (the level, the record). Save the LEVEL ONLY. Never Save All.
- Read-back before saving:
  - every new actor's bounds against the plan (±1 cm);
  - the trimmed plane's new extent;
  - the deck's relative transform (±0.1 cm) and its landed-pose world top against the measured floor top (±1 cm).
  - Any mismatch: stop, no save.
- The done line `S3_PIT_DECK_DONE|run=<HHMMSS>|...` carries a post-run census of BOTH packages.
- The revert destroys the recorded actors and restores the plane's recorded transform, gated on a read-back.

## Harness `Saved/CodexStructure/test_s3_pit_deck_plan.py` (plain Python)
Use pure functions for: the hole, the strips, the liner, the deck's root-relative transform, and the swing check.
- **POSITIVE:** with S3's plan numbers and a floor top at −5.0:
  - the deck's landed top is −5.0 ±0.01;
  - the strips tile the old plane minus the hole exactly (area check ±1 cm²·m);
  - the liner floor is under the hanging box with ≥ 50 cm clearance.
- **NEGATIVE, each must FAIL:**
  - a) a deck placed by world position with the root at −90;
  - b) six floor readings spread 5 cm;
  - c) a liner at S1's depth (ignoring hinge_z);
  - d) an unknown actor inside the hole prism.

Deliver: the script, apply/revert/dry-run runners with request JSONs, and the harness. Run the harness and report its
lines verbatim. Don't run Unreal.

Final message:
- files;
- harness output;
- what the dry run will print;
- what you couldn't verify.
