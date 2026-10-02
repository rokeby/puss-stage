# Scene 3 song vamp: markers + orbit on S3 Shot B07 (Conductor 3, 2 Oct). Gary: vamp REPLACES B07; 30 s per turn;
# orbit radius ~2 m, close-up soft shot, clam sharp; GO1 is NOT engaged in Scenes (no walkability limit).
Built transport (467d2c8): marker pairs `InfinityStage.VampStart` / `InfinityStage.VampEnd` on a Scene's ROOT loop
until RIGHT. Read the FFV patch's marker code to confirm label spelling and that markers are read from the Scene
(child) root, then:
Tool `Saved/CodexConductor/s3_vamp_apply.py` (dry / apply / revert), house pattern of s3_shotlist_apply.py
(backup LS_DevScene_03 to Backups/PreS3Vamp-<stamp>, record, suffix-stripped channel names, GUID section
exclusion, camera_component + root-relative template reads, modify() before setters, exact census = that
sequence only, save_asset it).
1. Add root marked frames `InfinityStage.VampStart` at 3480 and `InfinityStage.VampEnd` at 4200 (24 fps; B07 cut
   is [3480,4200] = 30.000 s). Refuse if any Vamp marker already exists.
2. On the spawnable binding `S3 Shot B07`: a transform track, one key per frame 3480..4200 inclusive, LINEAR,
   orbiting the clam centre C = dock (3500, 0, 105) at radius 200 cm, camera z 120 (dock), angle θ(f) =
   180° + 360°·(f−3480)/720 measured from +x (θ=180° = camera side, continuing B06), counter-clockwise seen from
   above; rotation = look-at C (roll 0). Frame 4200 pose must EQUAL frame 3480 pose (assert ≤ 0.01 cm / 0.01°)
   so the loop seam is invisible. Convert dock → world (origin (10921.973,160000,0), yaw 0); if B07's binding
   has a parent/attach, key in the space the track uses and prove it by composing back.
3. Lens on the B07 template (constant, no tracks): focal 85 mm, aperture f/1.4, manual focus 200 cm.
4. Read back every key count/first/last/seam; markers; census; save.
5. Harness test_s3_vamp_plan.py: + case (seam equal, radius 200±0.5 at every key, 721 keys); − cases: seam
   mismatch, radius drift, existing vamp marker, wrong frame span.
THIS PASS: write tool + harness, run harness, run the DRY RUN once in the editor (PIE check from the log first;
existing request jsons only). Apply nothing, commit nothing. Final message tagged measured/inferred, with the
first/last/mid key poses.
Crash rules as always: no Sequencer UI/eval/scrub, no SequencerTools, no open-range get_bound_objects, no unreal
objects in module globals, no reload, no PIE, never Save All, no deletes of pre-existing things.
