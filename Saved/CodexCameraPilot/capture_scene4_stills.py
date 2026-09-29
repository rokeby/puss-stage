"""Stills for Gary's two Scene 4 calls: the tilt cap during the plate rise, and the rest pitch.

Opens the Scene 4 sequence in Sequencer, sets each time in DEFAULT_CONFIG
(seconds from the Scene's playback start), and
captures from the Entry handoff camera's position and yaw at each candidate
pitch, with the handoff camera's own filmback and lens. Sequencer is closed
afterwards and nothing is saved. The camera itself is never moved: each still
comes from a transient SceneCapture2D.

LEVEL ACTIVITY (announce it): one ZZ_TransientCapture actor exists for a moment
per still. Spawning and destroying it marks the map dirty with no net change,
and that flag can't be cleared from Python. So this refuses to start unless
nothing is dirty, and any dirty map afterwards is this spawn/destroy only. No
level save may run while it is going.

Design: Docs/Scene4RevealTilt_2026-09-29.md
Success marker: PUSS_SCENE4_STILLS_DONE
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"

# Seconds from Scene 4's playback start at fold speed 1.0. Revise from
# survey_scene4_camera.json (the fold section's start and time scale) before
# running. capture_scene4_stills.json, if present, overrides this; git ignores it.
DEFAULT_CONFIG = {
    "exposure_bias": 1.0,
    "shots": [
        {"tag": "beams", "t": 3.5, "pitches": [0, 8]},
        {"tag": "plate_rise", "t": 10.5, "pitches": [20, 30, 48]},
        {"tag": "plate_up", "t": 12.2, "pitches": [20, 30, 48]},
        {"tag": "swing", "t": 15.5, "pitches": [20, 30, 48]},
        {"tag": "rest", "t": 23.5, "pitches": [0, 5, 8, 12]},
    ],
}


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


def capture(world, target, location, rotation, fov, exposure_bias, hidden_actors, out_dir, name):
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
        post.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        post.set_editor_property("override_auto_exposure_method", True)
        post.set_editor_property("auto_exposure_bias", exposure_bias)
        post.set_editor_property("override_auto_exposure_bias", True)
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
    if dirty():
        raise RuntimeError(f"Refusing: packages already dirty {dirty()}")

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    config = DEFAULT_CONFIG
    override = os.path.join(saved, "CodexCameraPilot", "capture_scene4_stills.json")
    if os.path.exists(override):
        with open(override, encoding="utf-8") as handle:
            config = json.load(handle)

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_PREFIX)
            and "SCENE" in str(c.get_editor_property("type")).upper()]
    if len(cues) != 1:
        raise RuntimeError(f"Expected one '{SCENE_PREFIX}' Scene cue, found {len(cues)}")
    sequence = cues[0].get_editor_property("scene").get_editor_property("sequence")
    if sequence is None:
        raise RuntimeError("Scene 4 has no sequence")

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry")
               and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    if len(entries) != 1:
        raise RuntimeError(f"Expected one {SCENE_PREFIX} Entry handoff camera, found {len(entries)}")
    entry = entries[0]
    lens = entry.get_cine_camera_component()
    sensor_width = lens.get_editor_property("filmback").get_editor_property("sensor_width")
    focal = lens.get_editor_property("current_focal_length")
    fov = math.degrees(2.0 * math.atan(sensor_width / (2.0 * focal)))
    location = entry.get_actor_location()
    yaw = entry.get_actor_rotation().yaw
    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    del actors

    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    start_frame = sequence.get_playback_start()
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "Scene4")
    os.makedirs(out_dir, exist_ok=True)
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

    sequencer = unreal.LevelSequenceEditorBlueprintLibrary
    written = []
    sequencer.open_level_sequence(sequence)
    try:
        for shot in config["shots"]:
            frame = start_frame + int(round(shot["t"] * fps))
            sequencer.set_current_time(frame)
            for pitch in shot["pitches"]:
                name = "S4_%s_t%05.1f_p%02d" % (shot["tag"], shot["t"], int(round(pitch)))
                size = capture(world, target, location, unreal.Rotator(roll=0.0, pitch=float(pitch), yaw=yaw),
                               fov, float(config.get("exposure_bias", 1.0)), hidden, out_dir, name)
                written.append({"name": name, "frame": frame, "bytes": size})
                unreal.log("PUSS_SCENE4_STILL|%s|frame=%d|bytes=%d" % (name, frame, size))
    finally:
        sequencer.close_level_sequence()

    report = {"fov_h_deg": fov, "focal_mm": focal, "sensor_width_mm": sensor_width,
              "camera": [location.x, location.y, location.z, yaw], "fps": fps,
              "start_frame": start_frame, "stills": written, "dirty_after": dirty()}
    with open(os.path.join(out_dir, "stills.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    unreal.log("PUSS_SCENE4_STILLS_DONE|stills=%d|empty=%d|dirty_after=%s"
               % (len(written), sum(1 for w in written if w["bytes"] == 0), report["dirty_after"]))


main()
