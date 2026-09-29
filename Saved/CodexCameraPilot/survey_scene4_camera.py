"""Read-only: what the Scene 4 look-up will be keyed against.

Reports the Scene 4 cue (owner, retain flag, sequence), its camera cuts, the
Entry handoff camera (actor pose, camera component relative rotation, filmback,
lens), every sub-sequence section in the Scene sequence (the fold, its start and
time scale), the bindings and their track types, and the structure actors
within 200 m of the camera. It writes nothing and does not open Sequencer. It
refuses to run in PIE and reports dirty packages before and after.

Design: Docs/Scene4RevealTilt_2026-09-29.md
Success marker: PUSS_SCENE4_CAMERA_SURVEY
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def guid_text(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)


def vec(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def rot(r):
    return {"pitch": round(r.pitch, 3), "yaw": round(r.yaw, 3), "roll": round(r.roll, 3)}


def safe(fn):
    try:
        return fn()
    except Exception as error:  # read-only survey: report API drift, never fail on it
        return {"error": str(error)}


def frame_value(frame):
    return safe(lambda: frame.frame_number.value if hasattr(frame, "frame_number") else frame.value)


def describe_sequence(sequence):
    rate = sequence.get_display_rate()
    out = {
        "path": sequence.get_path_name(),
        "display_rate": [rate.numerator, rate.denominator],
        "playback": [safe(lambda: sequence.get_playback_start()), safe(lambda: sequence.get_playback_end())],
        "camera_cuts": [],
        "sub_sections": [],
        "bindings": [],
    }
    bindings = {guid_text(b.get_id()): b for b in sequence.get_bindings()}
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            binding = bindings.get(guid_text(section.get_camera_binding_id().get_editor_property("guid")))
            out["camera_cuts"].append({
                "camera": str(binding.get_display_name()) if binding else None,
                "start": safe(section.get_start_frame),
                "end": safe(section.get_end_frame),
            })
    for track_type in (unreal.MovieSceneSubTrack, unreal.MovieSceneCinematicShotTrack):
        for track in sequence.find_tracks_by_type(track_type):
            for section in track.get_sections():
                sub = safe(section.get_sequence)
                params = safe(lambda: section.get_editor_property("parameters"))
                out["sub_sections"].append({
                    "track": track.get_class().get_name(),
                    "sequence": sub.get_path_name() if hasattr(sub, "get_path_name") else str(sub),
                    "start": safe(section.get_start_frame),
                    "end": safe(section.get_end_frame),
                    "time_scale": safe(lambda: str(params.get_editor_property("time_scale"))),
                })
    for binding in sequence.get_bindings():
        children = safe(binding.get_child_possessables)
        out["bindings"].append({
            "name": str(binding.get_display_name()),
            "tracks": sorted({t.get_class().get_name() for t in binding.get_tracks()}),
            "children": [str(c.get_display_name()) for c in children] if isinstance(children, list) else children,
        })
    return out


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    dirty_before = dirty()

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
            and "SCENE" in str(c.get_editor_property("type")).upper()]
    if len(cues) != 1:
        raise RuntimeError(f"Expected one '{SCENE_PREFIX}' Scene cue, found {len(cues)}")
    cue = cues[0]
    scene = cue.get_editor_property("scene")
    sequence = scene.get_editor_property("sequence")
    report = {
        "cue": {
            "label": str(cue.get_editor_property("label")),
            "guid": guid_text(cue.get_editor_property("cue_guid")),
            "camera_owner": str(scene.get_editor_property("camera_owner")),
            "retain_previous_camera": bool(scene.get_editor_property("retain_previous_camera")),
        },
        "sequence": describe_sequence(sequence) if sequence else None,
    }

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    handoff = []
    entry_location = None
    for actor in actors:
        if not isinstance(actor, unreal.CineCameraActor) or not actor.get_actor_label().startswith(SCENE_PREFIX + " "):
            continue
        lens = actor.get_cine_camera_component()
        filmback = lens.get_editor_property("filmback")
        row = {
            "label": actor.get_actor_label(),
            "tags": [str(t) for t in actor.tags],
            "location": vec(actor.get_actor_location()),
            "rotation": rot(actor.get_actor_rotation()),
            "component_relative_rotation": rot(lens.get_editor_property("relative_rotation")),
            "filmback_mm": [filmback.get_editor_property("sensor_width"), filmback.get_editor_property("sensor_height")],
            "focal_mm": lens.get_editor_property("current_focal_length"),
            "focus_cm": lens.get_editor_property("focus_settings").get_editor_property("manual_focus_distance"),
        }
        handoff.append(row)
        if actor.actor_has_tag("InfinityStage.SceneEntry"):
            entry_location = actor.get_actor_location()
    report["handoff_cameras"] = handoff

    structures = []
    for actor in actors:
        if "Structure" not in actor.get_class().get_name():
            continue
        location = actor.get_actor_location()
        if entry_location is not None and (location - entry_location).length() > 20000.0:
            continue
        structures.append({"label": actor.get_actor_label(), "class": actor.get_class().get_name(),
                           "location": vec(location)})
    report["structures_within_200m"] = structures
    report["dirty_before"] = dirty_before
    report["dirty_after"] = dirty()

    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "survey_scene4_camera.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    unreal.log(
        "PUSS_SCENE4_CAMERA_SURVEY"
        f"|cuts={len(report['sequence']['camera_cuts']) if report['sequence'] else 0}"
        f"|subs={len(report['sequence']['sub_sections']) if report['sequence'] else 0}"
        f"|handoff={len(handoff)}|structures={len(structures)}"
        f"|dirty_before={len(dirty_before)}|dirty_after={len(report['dirty_after'])}")


main()
