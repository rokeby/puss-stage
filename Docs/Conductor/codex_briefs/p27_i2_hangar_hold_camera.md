# P27: I2 hangar hold camera (free world camera for the hangar side of Interaction 2)

Requested 9 Oct by Conductor 5 for Gary (finishing-touches session owns it). Mode: `--worktree`, OFFLINE ONLY. Report to the finishing-touches session.

# House rules (every Codex brief, 8 Oct 2026 overnight)
1. You run in a git WORKTREE. Never write the main tree E:\PussStage. Never git stash, never commit -a. Commit your work in your worktree branch with explicit paths.
2. NO Unreal editor access, NO MCP calls, NO PIE, NEVER start/stop/quit/restart the editor or Blender GUI. Offline only (Python/numpy/PIL is fine). Do not run Blender at all unless the brief says so.
3. Tools must have DRY/APPLY/REVERT modes with confirm strings, a record + Backups/Pre<Thing>-<run> BEFORE any change, an exact dirty-package census, save only named packages, read back, and a success marker with a run id — the conductor runs them later.
4. UE 5.8 traps: never delete nodes on existing materials; values read in the same call as an import/build lie; delete markers by find_marked_frame_by_label; float channel read-back tolerance ~1e-4; set_collision_profile_name("NoCollision") with set_collision_enabled; in PIE use unreal.load_asset.
5. Every tool ships with an offline harness with NEGATIVE and POSITIVE controls; report pass counts.
6. Mark every claim: declaration-proven / binary-proven / measured / inferred, with file:line. Unmarked reports are rejected.
7. Look/creative values are Gary's: put them in args with defaults; produce preview images; apply nothing.
8. Final message: what you built (paths, commit hash in your worktree), how to run it (ordered), harness results, open questions. Under 700 words.
9. NEW TRAPS (8-9 Oct, all measured live; respect them in every tool):
   - Visibility tracks: bind AActor::bHidden ("bHidden","bHidden"); the bool channel stores VISIBLE (True = shown). Tracks bound to "bHiddenInGame" are INERT on actors (MovieScenePropertyTrack.h:53-56; PIE probe PIES2VIS-185717).
   - seq.add_possessable(actor) on an actor ALREADY bound in that sequence returns the EXISTING binding; set_display_name then renames it. Look up existing bindings first and add tracks to them.
   - channel.evaluate_keys(range, rate): build the range with sequence.make_range(start, duration) (display rate). A default SequencerScriptingRange() is 60000 fps and returns ~1 value for ~2000 frames. Assert the count.
   - Channel values are float32 in practice: read back numerically (0.01 cm / 0.001 deg), never by hashing rounded values.
   - New visibility/property tracks get UE default names ("Visibility"), not your display name; match by class + property.


## Problem [measured live 9 Oct, Saved/CodexConductor/I2Order_20261008/i2_drape_probe_I2PROBE-215405.json]
In LS_Interaction_02_Turnips (/Game/InfinityStage/Interactions/, 25 fps display, tick 24000, playback 0-2226) the hangar-side camera "S2 Sleight Hangar Camera" is the view target over [0, 1250) (sleight cut to "I2 Sleight Mouth Camera" at 1250). Its keys (now a constant hold from I2ORDER-DRY-4, record Saved/CodexConductor/I2Order_20261008/i2_order_record.json) say world (13591.6, 78588.2, 444.9) pitch 0, but LIVE in PIE at I2 f200 the camera is at (11427, 80648, -3433) pitch -90: its keys are relative to an ATTACH PARENT that sits sunk/tipped during I2 (the S2 hangar root at REST) [inferred]. So the hangar side shows no curtain. The 18:02 review camera — a FREE world camera — at (13393, 78777, 510), yaw -43.57, pitch 0, HFOV 50 (Saved/CodexConductor/pie_gobo_review.py SHOTS["hangar"]) framed the hangar drape + gobo perfectly (Captures/GOBOREVIEW-20261008-180257/f200..f300_hangar.png).

## Build: Saved/CodexConductor/I2HangarCam_20261009/i2_hangar_cam.py (+ runner, request json, args, harness, README)
- DRY / APPLY (confirm "APPLY I2HANGARCAM") / REVERT (confirm "REVERT I2HANGARCAM").
- APPLY: (1) spawn ONE unattached level CineCameraActor labelled "I2 Hangar Hold Camera" (tag I2HangarHoldCamera) at world (13393, 78777, 510), rotation pitch 0 / yaw -43.57 / roll 0, filmback + focal so HFOV = 50.0 deg (compute focal from the sensor width; read back the FOV), focus manual at the distance to the hangar drape centre if derivable from Saved/CodexConductor/curtain_sleight_record_I2.json (else args default 3000 cm); Movable; NOT attached (assert get_attach_parent_actor() is None after save). All pose/lens values are ARGS (Gary's framing call).
(2) In I2: add a possessable binding for it (look up an existing binding for the actor FIRST — rule 9), and re-point the hangar-side CAMERA CUT section(s) covering [0, 1250) to that binding (find the camera cut track; cut sections bound to "S2 Sleight Hangar Camera" ending at or before the sleight cut). Do NOT touch the mouth-side cut(s) or anything else; the old "S2 Sleight Hangar Camera" binding and all its tracks stay exactly as they are (record its guid + the cut sections' original camera binding ids for REVERT).
(3) Census: exactly the map (L_InfinityStage_V1VerticalSlice) + LS_Interaction_02_Turnips dirty; save those two only; read back (camera world pose/FOV/unattached; cut section binding ids; every other binding/track/cut/marker identical — snapshot before/after like i2_order.py untouched_diff, but WITHOUT its known bugs: match created tracks by class+property, UE names them).
- Guards: refuse in PIE, Sequencer open, dirty census, an existing "I2 Hangar Hold Camera" actor, or if the sleight-cut frame (1250) differs from the live cut track (read it live, report it). AG-I2-TEST-004 MPC track + the GoboSpot templates + the I2 Order Dark/Exposure bindings must read back unchanged (hash, like i2_order guard_view).
- REVERT: restore the cut sections' original camera binding ids exactly, remove only our binding, destroy only the tagged actor, save map + I2, read back. Drift check first.
- Harness (fake unreal; positive + negative + seeded mutations): pose/FOV math (HFOV 50 from the focal + sensor), the camera unattached, only hangar cuts re-pointed, the mouth cut untouched, the old binding untouched, add_possessable returning an existing binding handled, REVERT exact, refusals (PIE, existing actor, cut-frame mismatch, guard changed, extra dirty package).
- README: slot run order: DRY -> (Gary sees the 18:02 stills; already sent) -> APPLY -> SavedMasterMatchesShow + SceneCutBindingsResolve -> I2 stills at 2.7/4.5/6.2/8.0/10.7 s + 50.4 s (scene_stills with passage "I2").
