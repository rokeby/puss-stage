"""Render a frame sequence along a Passage route, offscreen.

Unlike record_clip.py (Desktop Duplication, needs PIE and an unlocked display),
this drives a transient SceneCapture2D along the route and writes numbered PNGs
that ffmpeg assembles. It works with the editor behind another window.

Config comes from Saved/CodexConductor/flythrough_job.json so the same script
serves passages, curtains and later hangars.
"""
import unreal, os, json

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

JOB = json.load(open(unreal.Paths.project_saved_dir() + "CodexConductor/flythrough_job.json"))
name = JOB["name"]
passage_key = JOB.get("passage", "01")
frac0, frac1 = JOB.get("from", 0.05), JOB.get("to", 0.75)
frames = JOB.get("frames", 120)
height = JOB.get("height", 170.0)
pitch = JOB.get("pitch", 0.0)
fov = JOB.get("fov", 80.0)

ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p = next((a for a in ps if passage_key in a.get_actor_label()), None)
if p is None:
    unreal.log_error("PASSAGE_NOT_FOUND|%s" % passage_key)
    raise SystemExit
route = next(iter(p.get_components_by_class(unreal.SplineComponent)), None)
length = route.get_spline_length()
unreal.log("FLY_ROUTE|%s|len=%.0f|frames=%d" % (p.get_actor_label(), length, frames))

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Frames/" + name + "/"
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(".png"):
        os.remove(OUT + f)

rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SceneCapture2D, unreal.Vector(0, 0, 0), unreal.Rotator())
try:
    cap.set_actor_label("ZZ_TransientCapture")
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

    for i in range(frames):
        t = frac0 + (frac1 - frac0) * (i / max(1, frames - 1))
        d = length * t
        loc = route.get_location_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
        rot = route.get_rotation_at_distance_along_spline(d, unreal.SplineCoordinateSpace.WORLD)
        cap.set_actor_location_and_rotation(
            unreal.Vector(loc.x, loc.y, loc.z + height),
            unreal.Rotator(roll=0.0, pitch=pitch, yaw=rot.yaw), False, False)
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, "f%04d.png" % i)
    unreal.log("FLY_DONE|%s|%d frames|%s" % (name, frames, OUT))
finally:
    unreal.EditorLevelLibrary.destroy_actor(cap)
