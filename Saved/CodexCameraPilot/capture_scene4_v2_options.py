"""Scene 4 v2: stills comparing the three rise options, STEPWISE (one MCP call per step).

Rig's v2 (29 Sep, late): the whole hangar hangs below a 5 m apron ahead of the
Entry camera and rises -90 -> 0 deg over 1-16 s (smoothstep). The practicals
strike from 16.5 s, the roof swings over 18.5-24.5 s, the lattice flies in
24.5-28.5 s, and the exit cut is at 30.0 s. Options for the rise:
  A  level throughout (a creature watching the room arrive into a still frame)
  B  Gary's horizon illusion: pitch eases 0 -> -8 in step with the box, so the
     horizon rises in frame with it (a device, locked to the box)
  C  look down into the glowing pit (0 -> -15, 0.5-3 s), hold, then rise with
     the light to level at landing (-15 -> 0, 10-16 s)
After landing, all options share: up to 30 for the roof swing, then down with
the lattice.

Each call captures, at the time the previous call scrubbed to, one TRUE still
(EV100 0.5, as the hangar volume) per listed pitch, from the Entry camera's
position and yaw. Plain property reads only. One ZZ_TransientCapture per still,
destroyed at once. Nothing is saved; Sequencer closes on the last step. Run the
same request until PUSS_S4V2_STILLS_DONE.
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
STATE_VERSION = 1
# (seconds from Scene 4 start, [(option label, pitch)]). Options that share a pitch share a still.
SHOTS = [
    (2.0, [("A-B", 0.0), ("C", -9.7)]),
    (6.0, [("A", 0.0), ("B", -2.1), ("C", -15.0)]),
    (9.0, [("A", 0.0), ("B", -4.4), ("C", -15.0)]),
    (11.0, [("A", 0.0), ("B", -5.9), ("C", -13.9)]),
    (12.5, [("A", 0.0), ("B", -6.9), ("C", -9.3)]),
    (14.0, [("A", 0.0), ("B", -7.6), ("C", -3.9)]),
    (16.0, [("A-C", 0.0), ("B", -8.0)]),
    (17.5, [("A-C", 0.0), ("B", -8.0)]),
    (21.5, [("all", 30.0)]),
    (26.5, [("all", 22.0)]),
    (29.5, [("all", 0.5)]),
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


def capture(world, target, location, rotation, fov, hidden_actors, out_dir, name):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        component.set_editor_property("show_flag_settings", show_flags())
        post = component.get_editor_property("post_process_settings")
        for key, value in (("auto_exposure_min_brightness", 0.5), ("auto_exposure_max_brightness", 0.5),
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


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Scene4V2")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "state.json")
    state = None
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
            and "SCENE" in str(c.get_editor_property("type")).upper()]
    sequence = cues[0].get_editor_property("scene").get_editor_property("sequence")
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start_frame = sequence.get_playback_start()
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    def frame_for(index):
        return start_frame + int(round(SHOTS[index][0] * fps))

    if state is None or state.get("version") != STATE_VERSION:
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
            json.dump({"version": STATE_VERSION, "index": 0, "stills": []}, handle)
        unreal.log("PUSS_S4V2_STEP|opened|fps=%.1f|scrubbed_to=%d" % (fps, frame_for(0)))
        return

    index = state["index"]
    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name():
        raise RuntimeError("Sequencer is not open on the Scene 4 sequence; delete state.json and restart")
    if sequencer.get_current_time() != frame_for(index):
        raise RuntimeError(f"Sequencer at {sequencer.get_current_time()}, expected {frame_for(index)}")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    del actors
    component = entries[0].get_cine_camera_component()
    location = component.get_world_location()
    yaw = entries[0].get_actor_rotation().yaw
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    fov = math.degrees(2.0 * math.atan(width / (2.0 * component.get_editor_property("current_focal_length"))))
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    t, options = SHOTS[index]
    for label, pitch in options:
        name = "S4v2_t%04.1f_%s_p%+05.1f" % (t, label, pitch)
        size = capture(world, target, location, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), fov, hidden, out_dir, name)
        state["stills"].append({"t": t, "option": label, "pitch": pitch, "name": name, "bytes": size})
        unreal.log("PUSS_S4V2_STILL|%s|bytes=%d" % (name, size))

    if index + 1 < len(SHOTS):
        sequencer.set_current_time(frame_for(index + 1))
        state["index"] = index + 1
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        return

    sequencer.close_level_sequence()
    os.remove(state_path)
    with open(os.path.join(out_dir, "stills.json"), "w", encoding="utf-8") as handle:
        json.dump({"stills": state["stills"], "dirty_after": dirty()}, handle, indent=2)
    unreal.log("PUSS_S4V2_STILLS_DONE|stills=%d|empty=%d|dirty_after=%s"
               % (len(state["stills"]), sum(1 for s in state["stills"] if s["bytes"] == 0), dirty()))


main()
