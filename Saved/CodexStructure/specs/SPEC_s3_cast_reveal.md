# Spec: `Saved/CodexStructure/s3_cast_reveal_apply.py`: Scene 3's cast appear at landing; the old set is removed

Gary (1 Oct, confirmed in the Rig & atmosphere session), B0b option 2: "they could just appear when the hangar … is
already in place, but is dark … then they appear and the lights strike up". Also: remove the Celadon pieces (L, L2,
L3) and the old clam PointLight.

Ownership: the cast's hidden flags are Rig & atmosphere's under this decision (conductor, 1 Oct). Do NOT change the
figures themselves: no transforms, components, animation, cloth, or `LS_Clams`.

## Prerequisite (guard)
Step 1 (`hangar_retime_apply.py`) must already be applied to S3. `LS_S3_HangarRise`'s `S3 Hangar Root` pitch keys must
equal `[(W0,−90),(W1,0)]`, with W0/W1 from `s4_rekey_window_record.json`. Otherwise REFUSE.

## Actors (by exact label; REFUSE if any is missing or duplicated)
- **CAST (reveal):**
  - `Shore01_M56 Clam` … `Shore06_F25 Clam` (six `BP_ShoreNN_*_Draped_C`);
  - the clam assembly: `Clam_with_Pearl_Clam_with_Pearl_0`, `source_Anim` (SkeletalMeshActor), `tg0pfjxda_tier_0`
    (the pedestal).
  - Leave `GroupActor0` alone.
- **REMOVE:** `SM_P03_CeladonPalatialAntechamber_01_L`, `_L2`, `_L3`, and `PointLight`.
  - For PointLight, also assert it's within 50 cm of dock + (2063, −631, 322.5). Dock = `hangar_s3_plan.json` dock;
    yaw 0, so dock-frame = world offset. Positions from `landscape_sweep.json`.

## Writes
1. **CAST:**
   - Set the SAVED Hidden-in-Game flag on each (record the old value).
   - In `/Game/InfinityStage/RigAtmos/LS_S3_HangarRise`, add (or reuse) a possessable binding per cast actor with a
     VISIBILITY track: hidden from 0, visible from `REVEAL_S = W1 + 0.5` (4.6261 s); a STEP/constant bool, not
     interpolated.
   - Find the visibility track's key semantics in the UE 5.8 headers (`MovieSceneVisibilityTrack.h` and related: does a
     key value mean "visible" or "hidden"?). Quote the header line in your final message. If the headers don't settle
     it, say UNCLEAR, and make the dry run print the planned keys in BOTH readings.
2. **REMOVE:**
   - Saved Hidden-in-Game on, actor collision off.
   - Tag `RigAtmos.RemovedFromS3`; folder `RigAtmos/RemovedFromS3`.
   - For PointLight, also set its light component's `visible` to False, so the editor view matches the show.
   - Record every old value.
3. **Section coverage (report; refuse in apply if it fails):**
   - Read the nest section of LS_S3_HangarRise in `/Game/InfinityStage/Dev/Sequences/LS_DevScene_03`: its range and
     completion mode (`.name`). Also read LS_DevScene_03's playback range.
   - If the scene plays past the rise section's end with a restore-state completion, the cast (and the box) would
     revert. Print it as a BLOCKER.

## Traps
1. Never open Sequencer: asset API only. Opening or scrubbing a Master-bound sequence dirties the map.
2. Guards:
   - world `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`;
   - no PIE;
   - BOTH dirty lists empty;
   - no ZZ_/TEMP_ actors;
   - record absent.
3. Back up first to `Backups/PreS3CastReveal-<stamp>/`: the level, LS_S3_HangarRise, the record.
4. Save ONLY the level and LS_S3_HangarRise. Never Save All.
5. Read-back before saving:
   - every flag;
   - every visibility channel's keys;
   - binding GUID → the right level actor (resolve it; never by index).
   - Any mismatch: stop, no save.
6. The done line `S3_CAST_REVEAL_DONE|run=<HHMMSS>|...` carries a post-run census of BOTH packages.
7. The revert restores every recorded flag and folder and removes the added bindings and tracks, gated on a read-back.

## Reference implementations
- `s4_predrive_author_apply.py`: structure, guards, record/revert, runners, `.name`, `conv_guid_to_string`.
- `arrivals_apply.py`: adding possessables to a rise sequence.

## Harness `Saved/CodexStructure/test_s3_cast_reveal_plan.py` (plain Python)
Keep the pure `plan(labels_found, root_keys, W0, W1) -> plan`.
- **POSITIVE:** the full label set gives 9 reveals at 4.6261 s and 4 removals.
- **NEGATIVE, each must FAIL:**
  - a) a missing Shore actor;
  - b) two actors labelled `PointLight`;
  - c) root keys still old (−3.567 → 16.0);
  - d) a REVEAL_S before W1 (a reveal while rising).

Deliver: the script, apply/revert/dry-run runners with request JSONs, and the harness. Run the harness and report its
lines verbatim. Don't run Unreal.

Final message:
- files;
- harness output;
- the visibility-semantics finding with its header citation;
- what you couldn't verify.
