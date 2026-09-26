"""Show P01's new ground by lifting exposure, to separate 'not built' from 'not lit'.

A geometry probe already confirms 848 Ground instances within 30 m of this point.
This proves the same thing visually: same camera, exposure raised well above the
show's pinned EV100 -3.
"""
import unreal, os
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((p for p in ps if "01" in p.get_actor_label()), ps[0])
route = next(iter(p1.get_components_by_class(unreal.SplineComponent)), None)
d = route.get_spline_length() * 0.30
loc = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
rot = route.get_rotation_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

for name, pitch, ev in (("P01_ground_lit_down", -35.0, 9.0), ("P01_ground_lit_fwd", -12.0, 9.0)):
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(loc.x, loc.y, loc.z + 170.0),
        unreal.Rotator(roll=0.0, pitch=pitch, yaw=rot.yaw))
    try:
        c = cap.capture_component2d
        c.set_editor_property("texture_target", rt)
        c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        c.set_editor_property("fov_angle", 90.0)
        c.set_editor_property("capture_every_frame", False)
        c.set_editor_property("capture_on_movement", False)
        pp = c.get_editor_property("post_process_settings")
        pp.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_bias", ev)
        pp.set_editor_property("override_auto_exposure_bias", True)
        c.set_editor_property("post_process_settings", pp)
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        unreal.log("CAPTURE|%s|ev=%.0f" % (name, ev))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)
unreal.log("P01_LIT_PROBE_DONE")
