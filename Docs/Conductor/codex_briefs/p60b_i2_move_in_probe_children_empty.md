# P60b — I2 move-in PROBE found NO child bindings under the mouth camera (Codex, offline)

Read `_house_rules.md`; all rules apply.

Live PROBE (run B1E-I2MOVEIN-PROBE-20261009-085508, report
`E:/PussStage/Saved/CodexConductor/I2SleightMoveIn_20261009/i2_sleight_move_in_probe_B1E-I2MOVEIN-PROBE-20261009-085508.json`,
log `E:/PussStage/Saved/Logs/PussStage.log`) returned `children: []` and `selected_by_tracks: []` for parent binding
`E6CF63464549232FD6CEA88D81178F0D` ("I2 Sleight Mouth Camera") in `LS_Interaction_02_Turnips`, while the expected
component is `...CineCameraActor_29.CameraComponent`. Before job 24 (I2 shrink −276) the child binding
`A4162B8C4B7F601B6D73BF97DB42FD91` "I2 Sleight Mouth Camera/CameraComponent" existed with CurrentFocalLength /
ManualFocusDistance tracks (snapshot_after in `E:/PussStage/Saved/CodexConductor/I2HangarCam_20261009/i2_hangar_cam_record.json`).

Determine which is true, citing file:line, proof tiers:
(a) the PROBE's child enumeration is wrong (UE 5.8 Python: how are child possessables enumerated? `get_bindings()`
    returns all? `binding.get_parent()` vs `get_child_possessables()`; compare with tools that already do this
    successfully, e.g. `E:/PussStage/Saved/CodexConductor/s3_drama_lights.py:104-111` uses get_bindings()+get_parent());
(b) job 24 (find its tool/record/backups: grep I2 shrink / extend_scene_playback / Backups/Pre*I2*) removed,
    re-created or re-parented the child binding — check its record for binding lists before/after.
Then fix the tool: enumerate children via get_bindings()+get_parent() guid match; if the child binding is truly gone,
plan to CREATE it on the parent (look up the existing binding first per house rule 9) and own its lens/focus tracks,
with REVERT removing only what it created. Extend PROBE output to list ALL bindings (name, guid, parent guid,
tracks, bound object paths) so the next live run is conclusive. Harness: add both cases. Same folder, README note.
