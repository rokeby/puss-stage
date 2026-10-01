# S3 wave rows + Opal Beach backdrop: import and static placement (Conductor 3, 1 Oct)

**Gary (his session, 1 Oct):** start the waves and backdrop; editor is free. Rows go to
**42 / 50 / 58 m** from the camera stop (NOT the 35/45/55 in the import plan: the figure
ring now stands at ~32–39 m). Heights unchanged. Slides (keys) are a LATER pass.

Art (built offline by Wings and Textures, report PASS):
- `DerivedAssets/FlatV3/Scene3/waves/IMPORT_PLAN.md` (+ per-half folders, `*_mi_params.json`)
- `DerivedAssets/FlatV3/Scene3/backdrop/IMPORT_PLAN.md` (+ `mi_params.json`, `textures/`)
Follow both plans EXACTLY for names, import settings, MI parents and parameters, and their
read-back gates. New names only: STOP if any destination exists. If the Timber/Edge V3 parent
materials named in the wave plan do not exist, STOP (do not create a master).

## Tool 1 `Saved/CodexConductor/s3_flats_import.py` (dry / apply)
- Dry: list every destination + its existence, every source file + hash, every MI parent +
  existence. `S3_FLATS_IMPORT_DRY_RUN_OK|run=..|mutated=0|..` or `..._STOPPED`.
- Apply: import, create MIs, run every read-back gate in both plans (dimensions ±1 cm,
  slots, UV0/UV1, no sockets, LOD1, TC_Masks, sRGB flags, MI parents and values).
  Save ONLY the newly created packages (save_asset each). Census after: nothing dirty.
  `S3_FLATS_IMPORT_DONE|run=..|assets=<n>|census=..`.

## Tool 2 `Saved/CodexConductor/s3_flats_place.py` (dry / apply / revert)
THE TRAP: the hangar is stored SUNK (root pitch −90) and only lands during the rise. Anything
attached must be placed by its LANDED pose. Reuse the composition in
`Saved/CodexConductor/s3_landed_box_probe.py` (rest-pose check passed at 0.000 cm, run 130916):
for a wanted LANDED world transform W and parent P, set the actor's relative transform
R = inverse(P_landed) · W, attach (keep relative), and verify by composing the REST values that
the actor's current world transform equals P_rest · R (≤ 1 cm, ≤ 0.05°).
Dock frame: origin world (10921.973,160000,0), yaw 0, camera stop at dock (0,0,180) looking +x.
Landed floor top z = −5; inner walls y ±1000; far wall inner face x = 6500.

- **Waves:** six Movable StaticMeshActors, labels `S3 Wave Row{1,2,3} {A,B}`, folder
  `RigAtmos/S3Waves`, tag `RigAtmos.S3Waves`, attached to `S3 Hangar Root` (find it; STOP if not
  exactly one). Landed: dock x = 4200 / 5000 / 5800 for rows 1/2/3; y = the plan's "Rest local Y"
  per half; bottom-centre at z = −5; rotation such that the Front (mesh −X) faces the camera
  (−x dock); scale 1.
- **Backdrop:** an engine `/Engine/BasicShapes/Plane` StaticMeshActor `S3 Backdrop`, folder
  `RigAtmos/S3Backdrop`, attached to `S3 Hangar Far Wall`. Landed: centred at dock
  (6497, 0, −5+1500), 20 m wide (y) × 30 m tall (z), facing the camera, MI `MI_S3_OpalBeach_Backdrop`.
  **Handedness gate (must pass or STOP):** from the plane's vertex/UV data and its landed
  transform, assert that as seen from the camera, UV u increases toward screen-right (+y dock)
  and v increases DOWNWARD (−z). W&T's check: the cottages are darker on the RIGHT.
  No image flip in a material to fix it — fix the transform.
- Guards: PIE; dirty-before; any label already present; any target outside the box
  (x 500..6500, y ±1000); waves overlapping the figure ring (any wave AABB within 300 cm of the
  ring's outer figure AABB, ring around dock (3500,0)).
- Apply: backup `Backups/PreS3FlatsPlace-YYYYMMDD-HHMM` (level + touched external-actor files),
  record, `modify()` BEFORE every setter (run 132809: without it the level never dirties), set,
  read back, census exactly the level, save only the level. Revert removes ONLY actors this tool
  spawned (by tag + record) — the one deletion allowed, of its own actors.
  Markers `S3_FLATS_PLACE_DRY_RUN_OK|..`, `S3_FLATS_PLACE_DONE|run=..|applied|backup=..|census=..`.
- Offline harness `test_s3_flats_place_plan.py`: + case; − cases: wave inside the ring zone;
  outside the box; flipped backdrop (u toward −y); label already present.

## THIS PASS
Write both tools, wrappers, request jsons and the harness; run the harness; run BOTH DRY RUNS
once in the editor. Apply nothing. Commit nothing. Final message: harness result; both dry-run
markers; the import inventory (counts, any existing destinations, missing parents); the planned
landed transforms table and the handedness verdict; each tagged measured/inferred.

## Crash and dirt rules
No Sequencer UI/evaluation, no SequencerTools, no get_bound_objects with open ranges; no unreal
objects in module globals; never reload a level/package; no PIE; never Save All; never delete
pre-existing assets or actors; NEVER delete material nodes.

## Amendments for the APPLY pass (Wings and Textures, 1 Oct, after pass 1 started)
- Backdrop MI: additionally set scalar `PBacking = 0.55` and `POlder = 0` (peels show backing
  or primer only; the master's "older poster" is a shifted crop of SkinColor, which would show
  beach under beach). Read both back.
- After import, read back each wave mesh's bounds and Front direction (-X), and verify the
  backdrop handedness as above. Mirrored = STOP; never fix with the image-flip flag or a 180°
  rotation.
- The six wave halves may later be rebuilt under the SAME names and dimensions (Gary's Fuser
  job 21); the placement tool must therefore key on actor labels/tags, not on mesh hashes.
