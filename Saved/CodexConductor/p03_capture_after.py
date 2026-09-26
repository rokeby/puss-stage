"""P03 before/after captures from fixed, reproducible positions.

Stations come from MaterializedPanels so the same bays are framed both times.
Set PHASE to 'before' or 'after'; nothing else changes between runs.
NOTE: spawning a transient SceneCapture2D leaves the map flagged dirty with no
content change, and UE 5.8's Python cannot clear it. Report it; do not save the
level to tidy it.
"""
import unreal, os, json
from collections import defaultdict

WORLD_EXPECTED = "L_InfinityStage_V1VerticalSlice"
PHASE = "after"

els = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = els.get_editor_world()
if WORLD_EXPECTED not in world.get_name():
    unreal.log_error("CAPTURE_WRONG_WORLD|%s" % world.get_name())
    raise SystemExit

ps = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStagePassageActor)
p3 = next((p for p in ps if "03" in p.get_actor_label() or "3" in p.get_actor_label().split()[1:2]), None)
if p3 is None:
    for p in ps:
        unreal.log("PASSAGE_LABEL|%s" % p.get_actor_label())
    unreal.log_error("P03_NOT_FOUND")
    raise SystemExit
unreal.log("P03_ACTOR|%s" % p3.get_actor_label())

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
unreal.log("P03_STATIONS|%d|x %.0f..%.0f" % (len(stations), stations[0].x, stations[-1].x))

# Bays chosen to straddle the composed troughs (route bays ~4, ~12, ~17).
PICKS = [1, 3, 5, 11, 13, 16, 18]
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Captures/"
os.makedirs(OUT, exist_ok=True)
rt = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)

recorded = []
for b in PICKS:
    if b >= len(stations):
        continue
    st = stations[b]
    loc = unreal.Vector(st.x - 500.0, st.y, st.z + 170.0)
    name = "P03_%s_bay%02d" % (PHASE, b + 1)
    cap = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, loc, unreal.Rotator(roll=0.0, pitch=5.0, yaw=0.0))
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
        recorded.append({"bay": b + 1, "x": loc.x, "y": loc.y, "z": loc.z, "file": name + ".png"})
        unreal.log("CAPTURE|%s|x=%.0f" % (name, loc.x))
    finally:
        unreal.EditorLevelLibrary.destroy_actor(cap)

with open(OUT + "p03_positions.json", "w") as f:
    json.dump(recorded, f, indent=1)
unreal.log("P03_CAPTURE_DONE|%s|%d shots" % (PHASE, len(recorded)))
