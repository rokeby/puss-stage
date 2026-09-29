"""Scene 4: key the camera's look-up score and nest it inside Rig's fold.

Design: Docs/Scene4RevealTilt_2026-09-29.md. The cap is 30° (lit by Rig's uplight;
48° is black). Keys go on the Entry Handoff Camera's COMPONENT, never its actor,
because the handoff stale check reads the actor transform. They live in this
stream's own sequence, hosted as a sub-sequence INSIDE LS_S4_HangarFold (Rig
approved), so the fold's Time Scale retimes both.

Beats (fold seconds, pitch degrees). Every key has flat tangents, so each segment
is a smoothstep, matching the hinges' cubic ease:
  0.0-2.3  0      arrival, still
  2.3-4.3  0->8   the practicals strike; the beams go up and the eye follows
  4.3-8.8  8      the side walls rise through the frame on their own
  8.8-11.0 8->30  chase the rising plate; it outgrows the frame at ~10.5 s
  11.0-18.8 30    STILL for the roof swing (12.5-18.5)
  18.8-23.9 30->0 follow the lattice down, and land level before the Exit cut at 24 s
Peaks: ~6, ~15 and ~9 deg/s.

DRY_RUN = True only reports. Set it False to write. The write creates
SCORE_PATH, adds one sub-track to the fold, and saves those two assets only; the
map is never saved. Refuses if the score already exists or the fold already
hosts it. Revert: revert_scene4_score.py.
Backup of the fold's .uasset: Backups/PreS4CameraScore-<stamp>/.
Success markers: PUSS_S4_SCORE_DRYRUN / PUSS_S4_SCORE_KEYED
"""

import json
import os

import unreal

DRY_RUN = True

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOLD_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarFold"
SCORE_DIR = "/Game/InfinityStage/CameraScores"
SCORE_NAME = "LS_S4_CameraScore"
SCORE_PATH = SCORE_DIR + "/" + SCORE_NAME
SCENE_PREFIX = "Scene 4"
KEYS = [(0.0, 0.0), (2.3, 0.0), (4.3, 8.0), (8.8, 8.0), (11.0, 30.0), (18.8, 30.0), (23.9, 0.0)]
SUB_TRACK_NAME = "Look & camera: Scene 4 score"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def peak_rates():
    rates = []
    for (t0, p0), (t1, p1) in zip(KEYS, KEYS[1:]):
        if p1 != p0:
            rates.append(round(1.5 * abs(p1 - p0) / (t1 - t0), 1))
    return rates


def hosted_scores(fold):
    found = []
    for track in fold.find_tracks_by_type(unreal.MovieSceneSubTrack):
        for section in track.get_sections():
            sub = section.get_sequence()
            if sub is not None and sub.get_path_name().split(".")[0] == SCORE_PATH:
                found.append(track)
    return found


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    others = [p for p in dirty() if p != EXPECTED_WORLD]
    if others:
        raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")

    fold = unreal.load_asset(FOLD_PATH)
    if fold is None:
        raise RuntimeError("Fold sequence did not load")
    if unreal.EditorAssetLibrary.does_asset_exist(SCORE_PATH):
        raise RuntimeError(f"Refusing: {SCORE_PATH} already exists (revert first)")
    if hosted_scores(fold):
        raise RuntimeError("Refusing: the fold already hosts the score")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    del actors
    if len(entries) != 1:
        raise RuntimeError(f"Expected one {SCENE_PREFIX} Entry handoff camera, found {len(entries)}")
    camera = entries[0]
    component = camera.get_cine_camera_component()
    rel_rot = component.get_editor_property("relative_rotation")
    rel_loc = component.get_editor_property("relative_location")
    rel_scale = component.get_editor_property("relative_scale3d")
    if abs(rel_rot.pitch) > 0.01 or abs(rel_rot.yaw) > 0.01 or abs(rel_rot.roll) > 0.01:
        raise RuntimeError(f"Refusing: the camera component is already rotated {rel_rot}")

    rate = fold.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    fold_start, fold_end = fold.get_playback_start(), fold.get_playback_end()
    plan = {
        "camera": camera.get_actor_label(), "component": component.get_name(),
        "fold": FOLD_PATH, "fold_fps": fps, "fold_range": [fold_start, fold_end],
        "keys_seconds_pitch": KEYS, "key_frames": [(int(round(t * fps)), p) for t, p in KEYS],
        "peak_rates_deg_s": peak_rates(), "score": SCORE_PATH, "dirty_before": dirty(),
    }
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out = os.path.join(saved, "CodexCameraPilot", "key_scene4_score.json")
    if DRY_RUN:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"dry_run": True, "plan": plan}, handle, indent=2, default=str)
        unreal.log("PUSS_S4_SCORE_DRYRUN|%s" % json.dumps(plan, default=str))
        return

    # --- write ---------------------------------------------------------------
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    score = tools.create_asset(SCORE_NAME, SCORE_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if score is None:
        raise RuntimeError("Could not create the score sequence")
    score.set_display_rate(rate)
    score.set_playback_start(fold_start)
    score.set_playback_end(fold_end)

    actor_binding = score.add_possessable(camera)
    component_binding = score.add_possessable(component)
    track = component_binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(fold_start, fold_end)
    defaults = {"Location.X": rel_loc.x, "Location.Y": rel_loc.y, "Location.Z": rel_loc.z,
                "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": 0.0,
                "Scale.X": rel_scale.x, "Scale.Y": rel_scale.y, "Scale.Z": rel_scale.z}
    pitch_channel = None
    for channel in section.get_all_channels():
        name = str(channel.channel_name)
        if name in defaults:
            channel.set_default(defaults[name])
        if name == "Rotation.Y":
            pitch_channel = channel
    if pitch_channel is None:
        raise RuntimeError("No Rotation.Y channel on the transform section")
    for seconds, pitch in KEYS:
        pitch_channel.add_key(unreal.FrameNumber(int(round(seconds * fps))), pitch,
                              interpolation=unreal.MovieSceneKeyInterpolation.USER)

    sub_track = fold.add_track(unreal.MovieSceneSubTrack)
    sub_track.set_display_name(SUB_TRACK_NAME)
    sub_section = sub_track.add_section()
    sub_section.set_sequence(score)
    sub_section.set_range(fold_start, fold_end)

    saved_score = unreal.EditorAssetLibrary.save_loaded_asset(score, False)
    saved_fold = unreal.EditorAssetLibrary.save_loaded_asset(fold, False)

    # --- read back -----------------------------------------------------------
    keys = [(k.get_time().frame_number.value, round(k.get_value(), 3)) for k in pitch_channel.get_keys()]
    parent = component_binding.get_parent()
    readback = {
        "saved_score": saved_score, "saved_fold": saved_fold,
        # Compare Guid strings: unreal.Guid == unreal.Guid is not reliable (the first
        # run failed this check on a correctly parented binding, 29 Sep).
        "component_binding_parent_is_camera": parent is not None and parent.is_valid()
        and unreal.GuidLibrary.conv_guid_to_string(parent.get_id())
        == unreal.GuidLibrary.conv_guid_to_string(actor_binding.get_id()),
        "pitch_keys": keys, "hosted": len(hosted_scores(fold)),
        "dirty_after": dirty(),
    }
    problems = []
    if not (saved_score and saved_fold):
        problems.append("save failed")
    if not readback["component_binding_parent_is_camera"]:
        problems.append("component binding is not parented to the camera binding")
    if keys != [(int(round(t * fps)), float(p)) for t, p in KEYS]:
        problems.append(f"keys read back as {keys}")
    if readback["hosted"] != 1:
        problems.append(f"fold hosts the score {readback['hosted']} times")
    if [p for p in readback["dirty_after"] if p != EXPECTED_WORLD]:
        problems.append(f"left dirty {readback['dirty_after']}")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({"dry_run": False, "plan": plan, "readback": readback, "problems": problems},
                  handle, indent=2, default=str)
    if problems:
        raise RuntimeError(f"Score read-back failed: {problems}")
    unreal.log("PUSS_S4_SCORE_KEYED|keys=%s|hosted=%d|dirty_after=%s"
               % (keys, readback["hosted"], readback["dirty_after"]))


main()
