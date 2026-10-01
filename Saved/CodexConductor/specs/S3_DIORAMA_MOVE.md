# S3 diorama move — tool + DRY RUN only this pass (Conductor 3, 1 Oct)

**Gary's rulings (his session, 1 Oct):** the pedestal goes to the MIDDLE of the landed box
floor; the six figures form a **loose ring around the clam, thinner on the camera side** so
the arrival wide sees the clam between them. Heights unchanged. Lighting is NOT part of this.

## Measured inputs (probes 125725, 130916; S3 dock frame, origin world (10921.973,160000,0), yaw 0)
- Landed floor centre: dock (3500, 0), floor top z -5. Inner walls y ±1000; front x 500; far wall x 6500.
- Arrival camera: dock (0,0,180), looking +x.
- `Clam_Pedastal` (renamed from tg0pfjxda_tier_0) at dock (1729.898,-137.546,1.784).
- On it: `Clam_with_Pearl_Clam_with_Pearl_0` (StaticMeshActor) and `source_Anim` (SkeletalMeshActor).
- `PointLight` (the reveal light) dock (2062.875,-630.524,450.515).
- Figures: `Shore01_M56 Clam` .. `Shore06_F25 Clam` (BP_Shore0N_*_Draped_C), z ≈ -27.4.
- LS_Clams keys NO location on any of these (measured), so their animation follows the actors.

## Layout (deterministic; print it in the dry run)
- Group delta D = (3500 - 1729.898, 0 - (-137.546), 0) applied in x,y ONLY to the pedestal,
  both clams and PointLight (keep each one's z and rotation).
- Figures: on a circle around the NEW pedestal centre, angle θ measured from +x (away from
  camera; θ = 180° points at the camera). Six slots: θ = 0°, +55°, -55°, +110°, -110°, +160°.
  So θ = 180° stays open, with one figure off-axis on the camera side ("thinner"). Radius alternates 260 / 320 cm by index for looseness. Keep each
  figure's z. Yaw each figure to face the pedestal centre, preserving its current yaw offset
  between mesh forward and actor forward (measure that offset from its current yaw vs. its
  current bearing to the clam; if ambiguous, report and use bearing-to-centre).
- Assign figures to slots by nearest current position (stable, deterministic tie-break by label).
- Check: no two figure AABBs overlap at the new spots; every AABB inside y ±900, x 900..6100.

## Guards (each a STOP, marker `S3_DIORAMA_STOPPED|run=..|reason`)
- Any target label missing or non-unique.
- Any target referenced by the Show asset `DA_InfinityStage_V1Show` (attachments, cues,
  any soft path) — moving it would write back to the Show. Report which.
- Any target attached to a parent (it would ride something else). Report the parent.
- PIE running; map or content dirty before.

## Also REPORT (no change): the six S3 Strike lights' aim error to the NEW ring centroid,
landed pose (degrees off-axis), so Gary can judge whether the strike needs re-aiming later.

## Tool shape (copy the house pattern of `Saved/CodexStructure/s3_pit_deck_apply.py`)
`Saved/CodexConductor/s3_diorama_move.py` with dry-run / apply / revert modes and run
wrappers + request jsons. Apply = backup (`Backups/PreS3DioramaMove-YYYYMMDD-HHMM`, the
level's .umap and external-actor files it touches) → record file with before transforms →
set transforms → read back each actor (≤0.1 cm, ≤0.01°) → census must be exactly the level
→ save ONLY the level → `S3_DIORAMA_DONE|run=..|applied|backup=..|census=..`. Revert
restores from the record the same way. Dry run: `S3_DIORAMA_DRY_RUN_OK|run=..|mutated=0|plan=<json>`.
Offline harness `test_s3_diorama_move_plan.py`: + case passes; − cases (overlap; outside box;
Show-referenced target; attached target) each FAIL as required.

## THIS PASS: write the tool and harness, run the harness, run the DRY RUN ONCE in the editor.
Do NOT run apply. Commit nothing. Final message: harness result, the dry-run marker line,
the planned positions table, the strike aim report, each tagged measured/inferred.

## Crash rules
No Sequencer UI/evaluation, no SequencerTools, no get_bound_objects with open ranges, no
unreal objects in module globals, no reload, no PIE, no Save All, no deleting anything.
