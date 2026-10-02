# Scene 3 shot-list DRAFT cameras (Conductor 3, 1 Oct night). Gary: "Draft from beats, you adjust."
Authority: Docs/Scene3BeatSheet_2026-10-01.md (12 beats, rulings, BUILT state, vamp). Static cameras only.
Structure (Look & camera, declaration-proven): every camera a SPAWNABLE CineCamera with a ROOT camera-cut section
in /Game/InfinityStage/Dev/Sequences/LS_DevScene_03 (never nested); one set_range call per section; the transport
picks the LATEST-STARTING containing cut, so each beat's cut starts at its marker and ends at the last-cut end
6216 (S3 Wide stays [95,6216] underneath); afterwards run the extend tool with rematch_only so the Exit re-copies
from the camera that ENDS LAST (make the B12 camera end at 6216 and all others end at their next marker, so B12 is last).
Layout (dock frame cm; dock origin world (10921.973,160000,0), yaw 0; camera stop (0,0,180) looking +x; floor top -5;
pedestal/clam centre (3500,0), clam top ~z 100; figure ring r 260/320 cm around it, gap toward -x):
| beat | marker frame | camera | lens | focus |
| B01 | 0 | (keep Entry + S3 Wide) | | |
| B02 | 360 | (2700,-250,170) look at ring centre | 35 mm | ring centre |
| B03 | 960 | (3050,40,160) through the camera-side gap, look at clam | 50 mm | clam |
| B04 | 1440 | (3500,-750,120) side, low, toward +y so waves (x 4200-5800) are behind figures | 35 mm | nearest figure |
| B05 | 2880 | (3200,0,140) look at clam | 85 mm | clam |
| B06 | 3000 | (3380,0,115) close on clam opening | 100 mm | clam |
| B07 | 3480 | (3300,60,120) pearl glow | 85 mm | clam |
| B08 | 4200 | (3360,-40,110) past the clam toward figures (figures soft) | 50 mm | clam |
| B09 | 4680 | (2600,0,170) calm ring | 35 mm | ring centre |
| B10 | 5040 | same pose as B09 | 35 mm | focus pulled to 300 cm (defocus) |
| B11 | 5520 | (3420,0,105) at clam height, looking at the clam/pearl | 50 mm | clam |
| B12 | 5880 | same as B11 (the float-out move is designed later) | 50 mm | clam |
All poses must be inside the landed box (x 500..6500, y ±1000) and none inside a figure AABB (read live). Look-at =
yaw/pitch computed to the target point; roll 0. Labels `S3 Shot B02`..`S3 Shot B12`, tag `S3.ShotDraft`.
Tool `Saved/CodexConductor/s3_shotlist_apply.py` (dry / apply / revert), house pattern of s3_beats_apply.py
(backup LS_DevScene_03 to Backups/PreS3ShotDraft-<stamp>, record, suffix-stripped channel names, GUID-based
section exclusion, camera_component + root-relative template reads, modify() before setters, exact census = the
sequence only, save_asset that one). Revert removes ONLY its own bindings/sections by tag+record.
Harness test_s3_shotlist_plan.py: + case; − cases: pose outside box; pose inside a figure; a nested cut; B12 not last.
THIS PASS: write tool + harness, run harness, run the DRY RUN once in the editor (PIE check from the log first;
use only existing request jsons; never invent request files). Apply nothing. Commit nothing.
Crash rules: no Sequencer UI/eval/scrub, no SequencerTools, no get_bound_objects with open ranges, no unreal objects
in module globals, no reload, no PIE, never Save All, no deletes of pre-existing things.
Final message: harness, dry-run marker, the planned table with computed rotations, tagged measured/inferred.
