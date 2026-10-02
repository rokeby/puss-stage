# Editor chain, 2 Oct (Conductor 4). Gary approved every step in his own words in the Conductor 4 session.
Run ONLY after Wings and Textures have released the editor (the conductor launches you then). Steps in order; STOP
the chain at the first failure, revert that step with its own revert mode, and report. Every step: PIE/SIE check
first, and if PIE is active STOP (never end PIE); never quit or restart the editor; never Save All; census before
and after; read every marker back from Saved/Logs/PussStage.log by run id (never tail -1).
Transport: Saved/CodexMocap/mcp_request.py with request JSONs in the existing pattern (copy
Saved/CodexConductor/s3_shotlist_apply request JSONs; the vamp tool has none yet: create
s3_vamp_{dry,apply}_run.py + _request.json wrappers in Saved/CodexConductor/).

STEP 1 — S3 vamp (Saved/CodexConductor/s3_vamp_apply.py, spec specs/S3_VAMP_ORBIT.md incl. Revision 2).
  DRY: expect S3_VAMP_DRY_RUN_OK, mutated=0, 721 keys, yaw 0 at 3480 / 180 at 3840 / 360 at 4200, seam 0.
  APPLY: expect S3_VAMP_DONE ... applied, backup Backups/PreS3Vamp-<stamp>, census = LS_DevScene_03 only, saved.
  Then queue SINGLY with exact names: InfinityStage.Editor.SavedMasterMatchesShow, then
  InfinityStage.Editor.SceneCutBindingsResolve (filter = the exact test name, NEVER "PussStage"). Both Success.
  Final census empty.
STEP 2 — LEVEL SAVED WITH THE HANGARS LANDED (Gary: "letting the hangars be available fully up in editor mode").
  a. Backup the level .umap (+ its _BuiltData if present) to Backups/PreLevelLanded-<stamp>.
  b. s3_landed_preview STATUS for hangars 1-6 (read-only); report each one's pose.
  c. UP for hangars 1,2,3,4,5,6 (root, roof hinge, lattice fly at their LAST keys; S6 roofless). Expect pose errors
     <= 0.01 cm / 0.001 deg per mover. Census must show ONLY the level dirty; anything else dirty -> DOWN and STOP.
  d. Save ONLY the level (the house narrow-save, not the save-check refusal path). Expect the level's .umap timestamp
     to change and a final census empty.
  e. Read back: STATUS again must report every hangar UP with the same pose errors; log marker
     CONDUCTOR_LEVEL_LANDED_SAVED|run=<id>|hangars=1,2,3,4,5,6.
  f. Invert s3_landed_preview_save_check.py: it now REFUSES while any hangar is DOWN (sunk) and passes while UP;
     keep its message format. Update test_s3_landed_preview.py's cases accordingly and run it.
  Do NOT run a PIE; the conductor asks Gary to PIE afterwards (HL sinks every hangar at BeginPlay in game worlds).
STEP 3 — HANGAR ROOF EARLY (Saved/CodexStructure/hangar_roof_early_apply.py, spec specs/HANGAR_ROOF_EARLY.md).
  DRY first: report per scene include/skip, the clearance minimum, and every camera/light/exposure key it reports for
  Gary. STOP if any clearance fails. APPLY only the scenes the dry run included; expect its DONE marker, backup
  Backups/PreHangarRoofEarly-<stamp>, census = exactly the touched rise assets; then SavedMasterMatchesShow alone.
  NOTE: the level was saved LANDED in STEP 2 at the LAST keys, which this step does not change (roof 0, lattice 1200).
STEP 4 — S3 WAVE SLIDES (Saved/CodexConductor/s3_wave_slides_apply.py, spec specs/S3_WAVE_SLIDES.md incl. Revision 2).
  Run ONLY if the strike-frame gate (Revision 2) is implemented in the tool (look for it; if absent, SKIP and report).
  DRY: the strike gate must read 147 +/- 1; the vamp seam is 0. APPLY: backup Backups/PreS3WaveSlides-<stamp>; census =
  LS_DevScene_03 (+ the level only if a possessable binding dirtied it: report it). Then SavedMasterMatchesShow and
  SceneCutBindingsResolve singly.
FINAL MESSAGE: each step's marker lines verbatim, the backups, the censuses, the save-check diff; each claim
tagged measured/declaration-proven/inferred. Commit nothing.
