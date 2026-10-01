# Generalise the walk-in to I2–I5 (Conductor 3, 1 Oct) — Gary: P02 drifts from the curtain onto
# the stage nicely; P01 and the others don't. Extend it.
Read Docs/Conductor/STREAM_STATE_LOOK_AND_CAMERA_2026-10-01.md §1 in full, and
Saved/CodexCameraPilot/{key_walkin_i1_p02.py,revert_walkin_i1_p02.py,walkin_plan.py,test_walkin_plan.py,place_transition_stalls.py}.
Do: move the I1-specific constants into `Saved/CodexCameraPilot/walkin_transitions.json`
(entries I1..I5: sequence_path, camera_label, camera_tags, next passage label, minimum_end_frame,
landed_s, pile_edge_cm) and make key/revert scripts take a transition id. I1's entry must
reproduce today's I1 keys EXACTLY (add a test that diffs the planned I1 keys against the
current planner output). Keep walkin_plan.py unchanged. For I2–I5 fill what is declaration-
proven (sequence paths, stalls camera labels/tags from place_transition_stalls.py:95-104, next
passage) and leave landed_s / minimum_end_frame as null with a note: they come from Soft goods'
lengthening + drape re-fit + bake (DropBake/<bake_id>.json). The key script must REFUSE a null.
Also list, per transition, the Soft goods steps needed (extend_scene_playback.py for the
Interaction, fit_transition_drapes.py with lead_s = new_end − 16.0, verify_transition_fit.py).
Opening→P01 is OUT of scope (unprobed; tied to the opening-curtain design).
Offline only: no editor. Tests must pass. Final message: files, tests, the per-transition table
of what's known vs null, tagged.
