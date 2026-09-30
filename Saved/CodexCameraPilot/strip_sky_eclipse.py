"""Scene 4: "let the box cover the sky" vs the drop as it is now. Stills for Gary's A1, STEPWISE.

Gary (30 Sep): the light should drop "over 5-10 seconds AS the rig is rising,
almost as if it's the shadow of the rig", not switch off. Geometry says the
rising box ECLIPSES THE SKY IN FRAME from about +5 s (the upright roof enters the
frame's centre) to about +12 s (the far-wall top passes the frame top; no sky
left), on the authored curve. So at constant exposure the picture should darken
by itself as the rig rises.

Two rows, captured the SAME way (Histogram, min = max = EV100, bias 0: the method
validated against no-override in validate_exposure_blend.py):
  NO DROP  EV100 -3.0: the passage's exposure held through the rise
  AS NOW   EV100 +0.5: the hangar volume's exposure, already in force at the
           stop (its face is 1 m before the camera's stop)
From the Scene 4 Entry camera at the stop, level, its own lens. Times from the
Scene 4 start. Each call captures at the time the PREVIOUS call scrubbed to
(pose change -> later call), from freshly spawned capture actors. The backcloth
(a GeometryCache) hangs behind the camera, out of frame. Nothing is saved;
Sequencer closes on the last step. Run the same request until
PUSS_SKY_STRIP_DONE.
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
TIMES = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
ROWS = (("nodrop", -3.0), ("asnow", 0.5))
STATE_VERSION = 1


def dirty_content():
    return sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


def capture(world, target, location, rotation, fov, ev100, out_dir, name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation, True)
    try:
        actor.set_actor_label("ZZ_TransientCapture")
        component = actor.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        post = component.post_process_settings
        for key, value in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
                           ("auto_exposure_min_brightness", ev100), ("auto_exposure_max_brightness", ev100),
                           ("auto_exposure_bias", 0.0)):
            post.set_editor_property("override_" + key, True)
            post.set_editor_property(key, value)
        component.set_editor_property("post_process_settings", post)
        for _ in range(2):
            component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        subsystem.destroy_actor(actor)


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "SkyEclipse")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "state.json")
    state = None
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)

    show = unreal.load_asset(SHOW_PATH)
    cue = [c for c in show.get_editor_property("cues")
           if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
           and "SCENE" in str(c.get_editor_property("type")).upper()][0]
    sequence = cue.get_editor_property("scene").get_editor_property("sequence")
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start = sequence.get_playback_start()
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    def frame_for(index):
        return start + int(round(TIMES[index] * fps))

    if state is None or state.get("version") != STATE_VERSION:
        if dirty_content():
            raise RuntimeError(f"Refusing: content dirty {dirty_content()}")
        if sequencer.get_current_level_sequence():
            raise RuntimeError("Sequencer already open")
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(frame_for(0))
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"version": STATE_VERSION, "index": 0, "stills": []}, handle)
        unreal.log("PUSS_SKY_STRIP_STEP|opened|scrubbed_to=%d" % frame_for(0))
        return

    index = state["index"]
    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name() or sequencer.get_current_time() != frame_for(index):
        raise RuntimeError("Sequencer is not at the expected frame; delete state.json and restart")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entry = [a for a in actors if isinstance(a, unreal.CineCameraActor)
             and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")][0]
    root = [a for a in actors if a.get_actor_label() == "S4 Hangar Root"]
    root_pitch = root[0].root_component.get_editor_property("relative_rotation").pitch if root else None
    del actors
    component = entry.get_cine_camera_component()
    location = component.get_world_location()
    yaw = entry.get_actor_rotation().yaw
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    fov = math.degrees(2.0 * math.atan(width / (2.0 * component.get_editor_property("current_focal_length"))))
    target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    t = TIMES[index]
    for row, ev100 in ROWS:
        name = "Sky_%s_t%04.1f" % (row, t)
        capture(world, target, location, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), fov, ev100, out_dir, name)
        state["stills"].append({"row": row, "ev100": ev100, "t": t, "root_pitch": root_pitch, "name": name})

    if index + 1 < len(TIMES):
        sequencer.set_current_time(frame_for(index + 1))
        state["index"] = index + 1
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        unreal.log("PUSS_SKY_STRIP_STEP|t=%.1f|root=%s|next=%d" % (t, root_pitch, index + 1))
        return

    sequencer.close_level_sequence()
    os.remove(state_path)
    with open(os.path.join(out_dir, "strip.json"), "w", encoding="utf-8") as handle:
        json.dump({"stills": state["stills"], "dirty_content_after": dirty_content()}, handle, indent=2)
    unreal.log("PUSS_SKY_STRIP_DONE|stills=%d|dirty_content_after=%s" % (len(state["stills"]), dirty_content()))


main()
