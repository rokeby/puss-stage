"""P01 looking down and ahead, to see whether the new C++ ground fills the void.

Before the structure swap, a downward shot from P01's route came back a 225 KB
near-black PNG against 1.6 MB for level shots: there was no floor, because
"Passage 1 - ForestedLandscape" sits at y 54,800-67,400, nowhere near the
corridor. Same framing here, so the two are directly comparable.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("CAPTURE_WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((p for p in ps if "01" in p.get_actor_label()), ps[0])
route = next(iter(p1.get_components_by_class(unreal.SplineComponent)), None)
length = route.get_spline_length()

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

# 0.30 along the route at 170 cm: the same point the original eye/up/down set used.
d = length * 0.30
loc = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
rot = route.get_rotation_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)

for name, pitch, fov in (("P01_after_down", -35.0, 90.0), ("P01_after_eye", 0.0, 80.0)):
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D,
        unreal.Vector(loc.x, loc.y, loc.z + 170.0),
        unreal.Rotator(roll=0.0, pitch=pitch, yaw=rot.yaw))
    try:
        c = cap.capture_component2d
        c.set_editor_property("texture_target", rt)
        c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        c.set_editor_property("fov_angle", fov)
        c.set_editor_property("capture_every_frame", False)
        c.set_editor_property("capture_on_movement", False)
        sf = unreal.EngineShowFlagsSetting()
        sf.set_editor_property("show_flag_name", "VolumetricFog")
        sf.set_editor_property("enabled", True)
        c.set_editor_property("show_flag_settings", [sf])
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        unreal.log("CAPTURE|%s|pitch=%.0f" % (name, pitch))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)
unreal.log("P01_FLOOR_CAPTURE_DONE")

# Up as well: first frame of the C++ gridiron.
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SceneCapture2D,
    unreal.Vector(loc.x, loc.y, loc.z + 170.0),
    unreal.Rotator(roll=0.0, pitch=38.0, yaw=rot.yaw))
try:
    c = cap.capture_component2d
    c.set_editor_property("texture_target", rt)
    c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    c.set_editor_property("fov_angle", 90.0)
    c.set_editor_property("capture_every_frame", False)
    c.set_editor_property("capture_on_movement", False)
    c.capture_scene()
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, "P01_after_up.png")
    unreal.log("CAPTURE|P01_after_up")
finally:
    unreal.EditorLevelLibrary.destroy_actor(cap)
