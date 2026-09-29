"""Stills for Gary's two Scene 4 calls, taken STEPWISE: one MCP call per step.

Why stepwise: the one-call version (capture_scene4_stills.py, first run 29 Sep)
scrubbed and captured inside ONE editor frame. Sequencer moves the fold on the
game thread, but the render thread only receives those transforms at the end of
the frame, so every still showed the pre-script state. Identical byte sizes at
different times gave it away. Here each call captures the time the PREVIOUS
call scrubbed to, a frame or more later. It logs a fingerprint of the
structure's transforms, so a fold that did not move shows in the log.

Run the same request repeatedly until PUSS_SCENE4_STEPWISE_DONE. Progress lives
in Captures/Scene4/step_state.json (a file, not Python state: UE wrappers must
not outlive a call).

LEVEL ACTIVITY (announce it): one ZZ_TransientCapture actor per still, destroyed
at once. Spawn/destroy dirties the map with no net change. The first step
accepts only that map as dirty (this stream's earlier bench), refuses anything
else, and refuses while any ZZ_ actor exists. Nothing is saved. Sequencer stays
open on the Scene 4 sequence between calls and is closed on the last step.

Design: Docs/Scene4RevealTilt_2026-09-29.md
Success marker: PUSS_SCENE4_STEPWISE_DONE
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
# Passes per still: (name, capture source, EV100). "true": the final image with
# exposure pinned like the hangar's own volume (EV100 0.5, local exposure
# neutral), matching Rig's fold captures, which is what the room looks like.
# "geometry": unlit base colour, ONLY to show what is in frame where the true
# pass is black. (A brighter-exposure geometry pass was tried first and changed
# nothing: the room's exposure ignores min/max brightness.) Label it as such.
PASSES = (("geometry", "SCS_BASE_COLOR", 0.5),)
STATE_VERSION = 3

# Seconds from Scene 4's playback start (the fold subsection starts at frame 0,
# speed 1.0, per survey_scene4_camera.json on 29 Sep).
SHOTS = [
    {"tag": "beams", "t": 3.5, "pitches": [0, 8]},
    {"tag": "plate_rise", "t": 10.5, "pitches": [20, 30, 48]},
    {"tag": "plate_up", "t": 12.2, "pitches": [20, 30, 48]},
    {"tag": "swing", "t": 15.5, "pitches": [20, 30, 48]},
    {"tag": "rest", "t": 23.5, "pitches": [0, 5, 8, 12]},
]


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def show_flags():
    flags = []
    for name, on in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
        setting = unreal.EngineShowFlagsSetting()
        setting.set_editor_property("show_flag_name", name)
        setting.set_editor_property("enabled", on)
        flags.append(setting)
    return flags


def capture(world, target, location, rotation, fov, source, ev100, hidden_actors, out_dir, name):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", getattr(unreal.SceneCaptureSource, source))
        component.set_editor_property("fov_angle", fov)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        component.set_editor_property("show_flag_settings", show_flags())
        post = component.get_editor_property("post_process_settings")
        for key, value in (("auto_exposure_min_brightness", ev100), ("auto_exposure_max_brightness", ev100),
                           ("local_exposure_highlight_contrast_scale", 1.0),
                           ("local_exposure_shadow_contrast_scale", 1.0)):
            post.set_editor_property("override_" + key, True)
            post.set_editor_property(key, value)
        component.set_editor_property("post_process_settings", post)
        for hidden in hidden_actors:
            component.hide_actor_components(hidden, True)
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)
    path = os.path.join(out_dir, name + ".png")
    return os.path.getsize(path) if os.path.exists(path) else 0


def fold_signature(actors):
    """Sum of the structure's component transforms. It must differ between fold times."""
    total, count = 0.0, 0
    for actor in actors:
        label = actor.get_actor_label().lower()
        if "structure 04" not in label and "hangar" not in label:
            continue
        for component in actor.get_components_by_class(unreal.SceneComponent):
            rotation = component.get_editor_property("relative_rotation")
            location = component.get_editor_property("relative_location")
            total += abs(rotation.pitch) + abs(rotation.roll) + abs(rotation.yaw) + abs(location.z) * 0.01
            count += 1
    return round(total, 3), count


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Scene4")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "step_state.json")
    state = None
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
            and "SCENE" in str(c.get_editor_property("type")).upper()]
    if len(cues) != 1:
        raise RuntimeError(f"Expected one '{SCENE_PREFIX}' Scene cue, found {len(cues)}")
    sequence = cues[0].get_editor_property("scene").get_editor_property("sequence")
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start_frame = sequence.get_playback_start()
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    def frame_for(index):
        return start_frame + int(round(SHOTS[index]["t"] * fps))

    if state is not None and state.get("version") != STATE_VERSION:
        # A run from an older version of this script: close it and start again.
        sequencer.close_level_sequence()
        os.remove(state_path)
        state = None
        unreal.log("PUSS_SCENE4_STEP|discarded an older run's state")

    if state is None:
        others = [p for p in dirty() if p != EXPECTED_WORLD]
        if others:
            raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
        strays = [a.get_actor_label() for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                  if a.get_actor_label().startswith("ZZ_")]
        if strays:
            raise RuntimeError(f"Refusing: ZZ_ actors present {strays}")
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(frame_for(0))
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"version": STATE_VERSION, "capture_index": 0, "stills": [], "signatures": []}, handle)
        unreal.log("PUSS_SCENE4_STEP|opened|scrubbed_to=%d|next=capture 0" % frame_for(0))
        return

    index = state["capture_index"]
    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name():
        raise RuntimeError("Sequencer is not open on the Scene 4 sequence; delete step_state.json and restart")
    frame = frame_for(index)
    if sequencer.get_current_time() != frame:
        raise RuntimeError(f"Sequencer is at {sequencer.get_current_time()}, expected {frame}")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry")
               and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    if len(entries) != 1:
        raise RuntimeError(f"Expected one {SCENE_PREFIX} Entry handoff camera, found {len(entries)}")
    lens = entries[0].get_cine_camera_component()
    sensor_width = lens.get_editor_property("filmback").get_editor_property("sensor_width")
    focal = lens.get_editor_property("current_focal_length")
    fov = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal)))
    location = entries[0].get_actor_location()
    yaw = entries[0].get_actor_rotation().yaw
    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    signature = fold_signature(actors)
    del actors, entries

    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    shot = SHOTS[index]
    for pitch in shot["pitches"]:
        for pass_name, source, ev100 in PASSES:
            name = "S4_%s_t%05.1f_p%02d_%s" % (shot["tag"], shot["t"], int(round(pitch)), pass_name)
            size = capture(world, target, location, unreal.Rotator(roll=0.0, pitch=float(pitch), yaw=yaw),
                           fov, source, ev100, hidden, out_dir, name)
            state["stills"].append({"name": name, "frame": frame, "bytes": size})
            unreal.log("PUSS_SCENE4_STILL|%s|frame=%d|bytes=%d" % (name, frame, size))
    state["signatures"].append({"t": shot["t"], "frame": frame, "value": signature[0], "components": signature[1]})
    unreal.log("PUSS_SCENE4_FOLD_SIGNATURE|t=%.1f|value=%s|components=%d" % (shot["t"], signature[0], signature[1]))

    if index + 1 < len(SHOTS):
        sequencer.set_current_time(frame_for(index + 1))
        state["capture_index"] = index + 1
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        unreal.log("PUSS_SCENE4_STEP|captured=%d|scrubbed_to=%d|next=capture %d"
                   % (index, frame_for(index + 1), index + 1))
        return

    sequencer.close_level_sequence()
    os.remove(state_path)
    values = [s["value"] for s in state["signatures"]]
    report = {"fov_h_deg": fov, "stills": state["stills"], "signatures": state["signatures"],
              "fold_moved": len(set(values)) == len(values), "dirty_after": dirty()}
    with open(os.path.join(out_dir, "stills.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    unreal.log("PUSS_SCENE4_STEPWISE_DONE|stills=%d|fold_moved=%s|signatures=%s|dirty_after=%s"
               % (len(state["stills"]), report["fold_moved"], values, report["dirty_after"]))


main()
