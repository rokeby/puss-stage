# S3 landed-box probe — READ-ONLY (Conductor 3, 1 Oct)

Gary wants the clam + figure ring centred in the LANDED Scene 3 hangar. Probe 125725
(`Saved/CodexConductor/s3_blocking_probe.py`, reuse its helpers) read the hangar in the
level's REST pose (sunk, root pitch -90), so its "landed" numbers are wrong. Compute the
landed geometry ANALYTICALLY from `LS_S3_HangarRise`'s keys. Change nothing.

Write `Saved/CodexConductor/s3_landed_box_probe.py` + request json (same shape as
`Saved/CodexStructure/s3_pit_deck_dryrun_run_request.json`), run once via
`Saved/CodexMocap/mcp_request.py`, read the log by marker + run id.

## Method
1. In `LS_S3_HangarRise` (asset channels only), find the bindings that move the hangar:
   the root (pitch -90 -> 0 by 4.133 s), the roof hinge (pitch -90 -> 0 by 12.633 s), the
   lattice (Z 2800 -> 1200 by 16.633 s). Name the bound actors and the property/track.
   Read each channel's LAST key value = landed value (all channels, including location).
2. For each S3 hangar actor (walls, far wall, roof, lattice beams/rails, deck, strike lights,
   practicals), get its attach parent chain and its RELATIVE transform to the moving actor
   that carries it. Compose with the landed values from (1) to get the LANDED world transform
   and landed world AABB (transform the 8 corners of the local bounds). Do not set anything.
3. Sanity check, must hold or report MISMATCH: compose the REST values (first keys) the same
   way and compare with the actors' current world transforms (which are the rest pose);
   max error <= 1 cm. If it fails, the method is wrong: report and stop.

## Report (world cm and S3 dock frame; dock origin world (10921.973,160000,0), yaw 0)
- Landed interior box: floor top z, ceiling (roof underside) z, lattice z, inner walls y,
  front opening x and far wall inner face x. Is the roof above the lattice once landed?
- Box centre on the floor (dock x,y), and its distance from the arrival camera at dock (0,0,180).
- Current cast ring centroid and Clam_Pedastal (dock), and the vector needed to move that
  group so the pedestal sits at the box floor centre.

Markers: `S3_LANDED_BOX|run=<id>|<json>` then `S3_LANDED_BOX_DONE|run=<id>|census=...`;
census empty before and after, or say so first.

## Crash and dirt rules
- NEVER open Sequencer, scrub, play, evaluate a sequence; no `SequencerTools`; no
  `get_bound_objects`/`locate_bound_objects` with an open range (resolve bindings the way
  probe 125725 did).
- No `unreal` objects in module globals. No reload, no PIE, no save, no setters, no Modify().
- If PIE is running: STOP. One run, plus one more if the PROBE SCRIPT errors.

## Final message
Short. Every number tagged measured or inferred; the rest-pose check result first.
