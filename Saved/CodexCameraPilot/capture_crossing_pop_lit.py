"""The P04 -> Scene 4 camera pop as Gary would see it if the stop were lit. STEPWISE, editor only. (30 Sep)

The PIE crossing runs (scene4_crossing_pop.json, scene1_crossing_pop.json) MEASURED the pop: the live rig
camera, carrying the Shadow Cat's gait bob, sits 15-23 cm low and rolled -1.9 to -2.7 deg in the last 0.35 s
of P04. The Entry handoff camera it cuts to is at z 180.0 with roll 0 (the authored, un-bobbed view). But every
PIE screenshot of the crossing is near black (means <= 1.8/255), so no picture shows it.

Two candidate causes: (a) the show IS black there, because the hangar volume's exposure (EV100 +0.5, Gary's
open A1 question) is already in force at the stop; (b) exposure had not adapted 2 s after the harness's scrub.
This captures BOTH exact poses from the PIE log, in the editor world posed at Scene 4 +0 s, at two exposures
pinned the validated way (Histogram, min = max = EV100, bias 0):
  asnow  EV100 +0.5: the control. If it is as black as PIE, the cause is (a), the look, not adaptation.
  nodrop EV100 -3.0: the passage exposure held, i.e. what Gary would see if the drop moves (A1). The picture.
Call 1 opens LS_DevScene_04 at its first frame; call 2 captures (pose change -> later call). The Scene 4
backcloth (a GeometryCache) hangs behind the camera, out of frame. Nothing is saved. Run the same request
until PUSS_CROSSING_POP_LIT_DONE. Writes Captures/CrossingPop/.
"""
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
POSES = {                                   # from scene4_crossing_pop.json, ticks 46 and 48
    "rig_last": (unreal.Vector(10645.98, 240000.0, 158.74), unreal.Rotator(roll=-2.551, pitch=0.0, yaw=0.0)),
    "entry": (unreal.Vector(10668.47, 240000.0, 180.0), unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)),
}
EXPOSURES = (("asnow", 0.5), ("nodrop", -3.0))


def capture(world, location, rotation, fov, ev100, out_dir, name):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
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
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out_dir = os.path.join(saved, "CodexCameraPilot", "Captures", "CrossingPop")
    os.makedirs(out_dir, exist_ok=True)
    state_path = os.path.join(out_dir, "lit_state.json")
    show = unreal.load_asset(SHOW_PATH)
    cue = [c for c in show.get_editor_property("cues")
           if str(c.get_editor_property("label")).startswith("Scene 4 ")][0]
    sequence = cue.get_editor_property("scene").get_editor_property("sequence")
    sequencer = unreal.LevelSequenceEditorBlueprintLibrary

    if not os.path.exists(state_path):
        if [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]:
            raise RuntimeError("Refusing: content dirty")
        if sequencer.get_current_level_sequence():
            raise RuntimeError("Sequencer already open")
        sequencer.open_level_sequence(sequence)
        sequencer.set_current_time(sequence.get_playback_start())
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"frame": sequence.get_playback_start()}, handle)
        unreal.log("PUSS_CROSSING_POP_LIT_STEP|opened Scene 4 at its first frame")
        return

    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    if sequencer.get_current_time() != state["frame"]:
        raise RuntimeError("Sequencer is not at the expected frame; delete lit_state.json and restart")
    entry = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
             if isinstance(a, unreal.CineCameraActor) and a.get_actor_label().startswith("Scene 4 ")
             and "Entry Handoff" in a.get_actor_label()][0]
    component = entry.get_cine_camera_component()
    width = component.get_editor_property("filmback").get_editor_property("sensor_width")
    focal = component.get_editor_property("current_focal_length")
    fov = math.degrees(2.0 * math.atan(width / (2.0 * focal)))
    names = []
    for row, ev100 in EXPOSURES:
        for pose, (location, rotation) in POSES.items():
            name = "Scene4_crossing_%s_%s" % (row, pose)
            capture(world, location, rotation, fov, ev100, out_dir, name)
            names.append(name)
    sequencer.close_level_sequence()
    os.remove(state_path)
    dirty = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    unreal.log("PUSS_CROSSING_POP_LIT_DONE|focal=%.1f|fov=%.2f|stills=%s|dirty_after=%s" % (focal, fov, names, dirty))


main()
