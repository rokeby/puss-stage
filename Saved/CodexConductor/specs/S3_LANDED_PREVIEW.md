# S3 landed-preview toggle (Conductor 3, 1 Oct) — Gary: "I need to start manually editing the
# lights... it's only 'up' when the rig is up mid play."

Tool `Saved/CodexConductor/s3_landed_preview.py`, modes: STATUS (read-only), UP, DOWN.
- UP: pose the S3 hangar's MOVING actors (the hangar root, the roof hinge, the lattice — the
  bindings `LS_S3_HangarRise` animates; find them exactly as `s3_landed_box_probe.py` does) at
  their LANDED values (each channel's LAST key), in the EDITOR world, by setting only those
  actors' relative transforms (modify() first). Children ride along, so the box, lights, deck,
  waves and backdrop appear where they stand in play. Write a record (rest transforms, run, time)
  to `Saved/CodexConductor/s3_landed_preview_record.json` BEFORE changing anything; refuse UP if a
  record exists (already up).
- DOWN: restore the rest transforms from the record exactly (read back ≤ 0.01 cm / 0.001°), then
  rename the record to `.done-<stamp>`. DOWN never saves.
- While UP, Gary edits lights/actors in the viewport; edits to CHILDREN are stored relative to
  their parent, so they survive DOWN unchanged. Tell him: edits to the root/hinge/lattice
  themselves are discarded by DOWN.
- SAVE GUARD: UP and DOWN never save. Also write `s3_landed_preview_save_check.py` (read-only):
  prints `S3_PREVIEW_SAFE_TO_SAVE` only if no UP record exists and the moving actors equal their
  rest pose; else `S3_PREVIEW_UP_DO_NOT_SAVE`. 
- Verify UP by the rest-pose composition check (rest error 0 cm, as run 130916) and that, once up,
  `S3 Hangar Far Wall` lands at dock x≈6500 (inner face) within 1 cm.
- Markers: `S3_PREVIEW|run=..|status|up=<bool>`, `S3_PREVIEW_UP_DONE|run=..|record=..`,
  `S3_PREVIEW_DOWN_DONE|run=..|max_err_cm=..`.
- Offline harness `test_s3_landed_preview.py` for the pure maths (+ and − cases).
Crash rules: no Sequencer UI/evaluation/scrub/PIE; read the rise sequence's channels from the
asset only; no unreal objects in module globals; no reload; never Save All; no deletes.
THIS PASS: write tool, wrappers, request jsons, harness; run the harness. Do NOT touch the editor.
Final message: files, harness result, tagged measured/inferred.
