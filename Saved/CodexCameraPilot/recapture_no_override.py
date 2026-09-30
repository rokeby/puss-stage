"""Re-take the camera stills with NO exposure override (30 Sep).

Rig found that every stream's capture exposure override corrupted the result: a
SceneCapture2D picks up the unbound global PostProcessVolume by itself, and with
no override it is byte-identical to the show. This re-takes, STEPWISE (one MCP
call per step):
  step 0: the five PLACED transition stalls cameras (by tag) plus the Opening
          camera, static (no Sequencer), now that the mouth lanterns exist; then
          opens LS_DevScene_04 and scrubs to the first Scene 4 time
  steps 1..: Scene 4 v2 at each time, from the Entry camera's position and yaw,
          at each listed pitch
The capture sets no post-process override. Show flags are as before (volumetric
fog on, editor and billboards off). Hidden actors: the rigs and the shadow cat
(primitives only; lights are NOT hidden, see project memory).
One ZZ_TransientCapture per still, destroyed at once. Nothing is saved. Run the
same request until PUSS_RECAPTURE_DONE.
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE_PREFIX = "Scene 4"
STALLS_TAG = "InfinityStage.TransitionStalls"
OPENING_CAMERA_LABEL = "Opening — Stalls Camera"
STATE_VERSION = 1
S4_SHOTS = [
    (6.0, [0.0, -15.0]), (11.0, [0.0, -15.0]), (14.0, [0.0, -15.0]),
    (17.8, [0.0, 30.0, 48.0]), (21.5, [30.0, 48.0]), (26.5, [22.0]), (29.5, [0.0]),
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
        # Deliberately NO post-process override: the global volume applies itself.
        for hidden in hidden_actors:
            component.hide_actor_components(hidden, True)
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)
    path = os.path.join(out_dir, name + ".png")
    return os.path.getsize(path) if os.path.exists(path) else 0


def hfov(component):
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    return math.degrees(2.0 * math.atan(width / (2.0 * component.get_editor_property("current_focal_length"))))


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world (or PIE is running)")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")

    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "NoOverride")
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
        return start_frame + int(round(S4_SHOTS[index][0] * fps))

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    hidden = [a for a in actors if "Camera + Shadow Figures" in a.get_actor_label()
              or a.get_class().get_name() == "InfinityStageShadowCatActor"]
    target = unreal.RenderingLibrary.create_render_target2d(
        world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

    if state is None or state.get("version") != STATE_VERSION:
        others = [p for p in dirty() if p != EXPECTED_WORLD]
        if others:
            raise RuntimeError(f"Refusing: packages other than the map are dirty {others}")
        if [a for a in actors if a.get_actor_label().startswith("ZZ_")]:
            raise RuntimeError("Refusing: ZZ_ actors present")
        stills = []
        seats = [a for a in actors if isinstance(a, unreal.CineCameraActor)
                 and (a.actor_has_tag(STALLS_TAG) or a.get_actor_label() == OPENING_CAMERA_LABEL)]
        for camera in sorted(seats, key=lambda a: a.get_actor_label()):
            component = camera.get_cine_camera_component()
            name = "Seat_" + camera.get_actor_label().split(" —")[0].replace(" ", "")
            size = capture(world, target, component.get_world_location(), component.get_world_rotation(),
                           hfov(component), hidden, out_dir, name)
            stills.append({"name": name, "label": camera.get_actor_label(), "bytes": size})
        del actors, seats
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(frame_for(0))
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"version": STATE_VERSION, "index": 0, "stills": stills}, handle, indent=2)
        unreal.log("PUSS_RECAPTURE_STEP|seats=%d|opened scene 4|scrubbed_to=%d" % (len(stills), frame_for(0)))
        return

    index = state["index"]
    current = sequencer.get_current_level_sequence()
    if current is None or current.get_path_name() != sequence.get_path_name():
        raise RuntimeError("Sequencer is not open on the Scene 4 sequence; delete state.json and restart")
    if sequencer.get_current_time() != frame_for(index):
        raise RuntimeError(f"Sequencer at {sequencer.get_current_time()}, expected {frame_for(index)}")
    entries = [a for a in actors if isinstance(a, unreal.CineCameraActor)
               and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(SCENE_PREFIX + " ")]
    component = entries[0].get_cine_camera_component()
    location = component.get_world_location()
    yaw = entries[0].get_actor_rotation().yaw
    fov = hfov(component)
    del actors, entries
    t, pitches = S4_SHOTS[index]
    for pitch in pitches:
        name = "S4v2_t%04.1f_p%+05.1f" % (t, pitch)
        size = capture(world, target, location, unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw), fov, hidden, out_dir, name)
        state["stills"].append({"name": name, "t": t, "pitch": pitch, "bytes": size})

    if index + 1 < len(S4_SHOTS):
        sequencer.set_current_time(frame_for(index + 1))
        state["index"] = index + 1
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        unreal.log("PUSS_RECAPTURE_STEP|t=%.1f|next=%d" % (t, index + 1))
        return

    sequencer.close_level_sequence()
    os.remove(state_path)
    with open(os.path.join(out_dir, "stills.json"), "w", encoding="utf-8") as handle:
        json.dump({"stills": state["stills"], "dirty_after": dirty()}, handle, indent=2)
    unreal.log("PUSS_RECAPTURE_DONE|stills=%d|empty=%d|dirty_after=%s"
               % (len(state["stills"]), sum(1 for s in state["stills"] if s["bytes"] == 0), dirty()))


main()
