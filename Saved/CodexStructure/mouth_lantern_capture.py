"""Read-only capture of one transition mouth (default P04, Interaction 3) as the show
frames it: the stalls camera's pose and lens, at the show's own pinned exposure
(EV100 -3, the unbound PPV; no stalls camera overrides it), with the transition drape
hanging (GC_CurtainDrop_Opening at frame 0, the hold the Interaction plays).

The drape is a TRANSIENT GeometryCacheActor spawned at the mouth exactly as
fit_transition_drapes.py places the spawnable (route start, yaw from the route), so
Sequencer is never opened. Two frames: with the mouth lantern, and with it hidden from a second
capture only (the before). Each view is captured twice and the second kept, so shadows and GI have a
frame to settle. Every transient actor is destroyed in a finally; dirty must not change.
Writes Saved/CodexStructure/Captures/MouthLantern/. Lean: all work in main().
"""
import math
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
OUT = os.path.join(HERE, "Captures", "MouthLantern")
PASSAGE = globals().get("MOUTH_PASSAGE", "04")
EV100 = globals().get("MOUTH_EV100", -3.0)
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    assert not unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence(), "Sequencer open"
    c0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m0 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    s = next(a for a in actors if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label().endswith(PASSAGE))
    route = s.get_editor_property("passage").get_editor_property("route")
    frame = route.get_transform_at_distance_along_spline(0.0, unreal.SplineCoordinateSpace.WORLD, False)
    yaw = frame.rotation.rotator().yaw
    cam = next(a for a in actors if isinstance(a, unreal.CineCameraActor)
               and f"InfinityStage.Mouth.P{PASSAGE}" in [str(t) for t in a.get_editor_property("tags")])
    cc = cam.get_cine_camera_component()
    sensor = cc.get_editor_property("filmback").get_editor_property("sensor_width")
    hfov = math.degrees(2.0 * math.atan(sensor / (2.0 * cc.get_editor_property("current_focal_length"))))
    lanterns = [a for a in actors if f"RigAtmos.MouthLantern.P{PASSAGE}" in [str(t) for t in a.get_editor_property("tags")]]
    os.makedirs(OUT, exist_ok=True)
    rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    temps = []
    try:
        drape = sub.spawn_actor_from_class(unreal.GeometryCacheActor, frame.translation, unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw), True)
        temps.append(drape)
        drape.set_actor_label("ZZ_MouthCapture_Drape")
        gcc = drape.get_component_by_class(unreal.GeometryCacheComponent)
        gcc.set_editor_property("geometry_cache", unreal.load_asset(GC))
        gcc.set_editor_property("running", False)         # frame 0: the drape as it hangs through the Interaction
        gcc.set_editor_property("looping", False)
        shots = []
        # Exposure variants. "show": exactly the unbound PPV's setting (Histogram, min = max
        # = EV100 -3), so the frame is what the show renders. "world": no override at all.
        # "bias": the old P0x-capture convention (Manual + Exposure Compensation), kept only
        # to calibrate against earlier captures. A light cannot be hidden from a capture
        # (HiddenComponents is primitives only), so "before" is a capture run without lanterns.
        for variant in globals().get("MOUTH_VARIANTS", ("show", "world", "bias")):
            cap = sub.spawn_actor_from_class(unreal.SceneCapture2D, cam.get_actor_location(), cam.get_actor_rotation(), True)
            temps.append(cap)
            cap.set_actor_label(f"ZZ_MouthCapture_{variant}")
            comp = cap.capture_component2d
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
            comp.set_editor_property("fov_angle", hfov)
            pp = comp.post_process_settings
            if variant == "show":
                pp.set_editor_property("override_auto_exposure_method", True)
                pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
                pp.set_editor_property("override_auto_exposure_min_brightness", True)
                pp.set_editor_property("auto_exposure_min_brightness", EV100)
                pp.set_editor_property("override_auto_exposure_max_brightness", True)
                pp.set_editor_property("auto_exposure_max_brightness", EV100)
                pp.set_editor_property("override_auto_exposure_bias", True)
                pp.set_editor_property("auto_exposure_bias", 0.0)
            elif variant == "bias":
                pp.set_editor_property("override_auto_exposure_method", True)
                pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
                pp.set_editor_property("override_auto_exposure_bias", True)
                pp.set_editor_property("auto_exposure_bias", EV100)
            comp.set_editor_property("post_process_settings", pp)
            for _ in range(4):
                comp.capture_scene()
            name = f"Mouth_P{PASSAGE}_{variant}{globals().get('MOUTH_SUFFIX', '')}.png"
            unreal.RenderingLibrary.export_render_target(world, rt, OUT, name)
            shots.append(name)
    finally:
        for t in temps:
            sub.destroy_actor(t)
    c1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m1 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"MOUTH_CAPTURE_OK|passage=P{PASSAGE}|camera={cam.get_actor_label()}|hfov={hfov:.1f}|ev100={EV100}|lanterns={len(lanterns)}"
               f"|shots={shots}|dirty_before={c0}+{m0}|dirty_after={c1}+{m1}")


main()
