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

## Revision 2 — ALL hangars (Gary, 1 Oct: "I will need the possibility of such previews for every
## hangar scene, so the default mode in editor might as well be fully setup rig")
- Generalise to every hangar: discover each `LS_S{N}_HangarRise` (or whatever the hangar tools
  name them: read Saved/CodexStructure/hangar_build.py and hangar_retime_apply.py) and its moving
  bindings; per-hangar record; modes STATUS / UP <ids|all> / DOWN <ids|all>. Same maths, same
  rest-pose composition check per hangar (0 cm), same never-save rule and the save-check script
  covering ALL hangars.
- Report per hangar which actors move and their landed values; refuse a hangar whose rise does not
  fit the root/hinge/lattice pattern (S6 roofless, S4 roof — name what differs) rather than guess.
- Separately, DRAFT (do not build) a held C++ patch for the next build window:
  `Scripts/patches/2026-10-01_HL_hangars_landed_in_editor.patch`. Goal: the level is SAVED with
  hangars LANDED; in GAME worlds only, every hangar's moving actors are set to their rise
  sequence's FIRST key at BeginPlay (before the first rendered frame), so play is unchanged.
  Find where hangars are owned in C++ (if they are not, propose the smallest owner), state the
  tick/BeginPlay ordering relative to the transport and the Arrival pre-drives, and add an
  automation test (new file) that a game world starts sunk and an editor world is untouched.
  Every inference tagged (engine .cpp is not shipped).
