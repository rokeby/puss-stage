"""Look FORWARD at P03's back-light pairs, so any shaft comes toward the lens.

The after-shots at bay12 showed no distinct shaft, but that camera sat roughly
where the shafts cross rather than looking down them. These two positions look
at a back-light pair from a dark stretch upstream.
"""
import unreal, os

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("CAPTURE_WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p3 = next((p for p in ps if "03" in p.get_actor_label()), None)
if p3 is None:
    unreal.log_error("P03_NOT_FOUND")
    raise SystemExit

# P03 does NOT sit on y=0 -- the passages share a world x range and are separated
# in y. Hardcoding y=0 put an earlier attempt in P01's corridor entirely. Derive
# the corridor line from P03's own stations, as the before/after captures do.
from collections import defaultdict
by_cue = defaultdict(dict)
for ref in p3.get_editor_property("materialized_panels"):
    g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
    side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
    by_cue[g][side] = ref.get_editor_property("base_world_transform").translation
stations = []
for sides in by_cue.values():
    if "LEFT" in sides and "RIGHT" in sides:
        L, R = sides["LEFT"], sides["RIGHT"]
        stations.append(unreal.Vector((L.x+R.x)/2.0, (L.y+R.y)/2.0, (L.z+R.z)/2.0))
stations.sort(key=lambda v: v.x)
CORRIDOR_Y = sum(s.y for s in stations) / len(stations)
BASE_Z = stations[0].z
unreal.log("P03_LINE|y=%.0f|z=%.0f|x %.0f..%.0f" % (CORRIDOR_Y, BASE_Z, stations[0].x, stations[-1].x))

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

# Rig's requested framings: looking at the pairs hung at x 6250/6750 and 8750/9250.
for name, x, pitch in (("P03_shaft_a_x4250", 4250.0, 8.0), ("P03_shaft_b_x8250", 8250.0, 8.0)):
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, unreal.Vector(x, CORRIDOR_Y, BASE_Z + 170.0),
        unreal.Rotator(roll=0.0, pitch=pitch, yaw=0.0))
    try:
        c = cap.capture_component2d
        c.set_editor_property("texture_target", rt)
        c.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        c.set_editor_property("fov_angle", 80.0)
        c.set_editor_property("capture_every_frame", False)
        c.set_editor_property("capture_on_movement", False)
        sf = unreal.EngineShowFlagsSetting()
        sf.set_editor_property("show_flag_name", "VolumetricFog")
        sf.set_editor_property("enabled", True)
        c.set_editor_property("show_flag_settings", [sf])
        c.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
        unreal.log("CAPTURE|%s|x=%.0f y=%.0f pitch=%.0f" % (name, x, CORRIDOR_Y, pitch))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)
unreal.log("P03_SHAFT_CAPTURE_DONE")
