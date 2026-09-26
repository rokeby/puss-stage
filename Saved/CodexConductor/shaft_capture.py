"""Capture bay005 with an explicit VolumetricFog show-flag override.

Control for the shaft A/B: if forcing the flag on and off produces identical
frames, the capture path is not rendering volumetric fog at all and no fog
conclusion can be drawn from any capture.
"""
import unreal, os
from collections import defaultdict

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
TAG = "D"
FOG_FLAG = True

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("CAPTURE_WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p1 = next((p for p in ps if "01" in p.get_actor_label()), ps[0])
by_cue = defaultdict(dict)
for ref in p1.get_editor_property("materialized_panels"):
    g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
    side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
    by_cue[g][side] = ref.get_editor_property("base_world_transform").translation
stations = []
for sides in by_cue.values():
    if "LEFT" in sides and "RIGHT" in sides:
        L, R = sides["LEFT"], sides["RIGHT"]
        stations.append(unreal.Vector((L.x + R.x) / 2.0, (L.y + R.y) / 2.0, (L.z + R.z) / 2.0))
stations.sort(key=lambda v: v.x)
st = stations[4]  # bay 005

OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

setting = unreal.EngineShowFlagsSetting()
setting.set_editor_property("show_flag_name", "VolumetricFog")
setting.set_editor_property("enabled", FOG_FLAG)

cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.SceneCapture2D,
    unreal.Vector(st.x - 500.0, st.y, st.z + 170.0),
    unreal.Rotator(roll=0.0, pitch=10.0, yaw=0.0))
try:
    comp = cap.capture_component2d
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
    comp.set_editor_property("fov_angle", 80.0)
    comp.set_editor_property("capture_every_frame", False)
    comp.set_editor_property("capture_on_movement", False)
    comp.set_editor_property("show_flag_settings", [setting])
    comp.capture_scene()
    name = "SHAFT_%s_fog%d" % (TAG, 1 if FOG_FLAG else 0)
    unreal.RenderingLibrary.export_render_target(world, rt, OUT, name + ".png")
    unreal.log("CAPTURE|%s|flag=%s" % (name, FOG_FLAG))
finally:
    unreal.EditorLevelLibrary.destroy_actor(cap)
