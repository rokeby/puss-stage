"""Enable volumetric fog on the Infinity Stage height fog and report before/after. No save."""
import json, os, unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# Identity guard: two Unreal editors run on this machine. Never mutate without
# first proving this is the Puss world, or a port mix-up edits the wrong project.
world = ed.get_editor_world()
assert world is not None, "no editor world"
actual = world.get_path_name().split(".", 1)[0]
assert actual == EXPECTED_WORLD, f"wrong project: {actual}"
assert ed.get_game_world() is None, "PIE active"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
fogs = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "ExponentialHeightFog" and a.get_actor_label().startswith("Infinity Stage")]
assert len(fogs) == 1, f"expected one Infinity Stage fog, found {len(fogs)}"
fog = fogs[0]; c = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
KEYS = ["fog_density","fog_height_falloff","fog_max_opacity","start_distance","enable_volumetric_fog",
        "volumetric_fog_scattering_distribution","volumetric_fog_extinction_scale","volumetric_fog_distance",
        "volumetric_fog_static_lighting_scattering_intensity"]
def snap():
    d = {}
    for k in KEYS:
        try:
            v = c.get_editor_property(k); d[k] = v if isinstance(v,(int,float,bool,str)) else str(v)
        except Exception as e: d[k] = f"ERR {e}"
    try:
        col = c.get_editor_property("volumetric_fog_albedo"); d["volumetric_fog_albedo"] = [col.r, col.g, col.b]
    except Exception: pass
    return d
before = snap()
fog.modify()
c.set_editor_property("enable_volumetric_fog", True)
# Dense exponential fog reads as flat colour; volumetric wants a thin medium plus
# a long enough range to reach down the corridor.
c.set_editor_property("fog_density", 0.035)
c.set_editor_property("volumetric_fog_distance", 20000.0)
c.set_editor_property("volumetric_fog_extinction_scale", 1.0)
c.set_editor_property("volumetric_fog_scattering_distribution", 0.55)   # forward scatter = beams
c.set_editor_property("volumetric_fog_albedo", unreal.Color(r=255, g=255, b=255, a=255))
after = snap()
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "volumetrics_result.json")
json.dump({"before": before, "after": after}, open(out, "w"), indent=1)
unreal.log(f"VOLUMETRICS_ON|on={after['enable_volumetric_fog']}|density={after['fog_density']}|distance={after['volumetric_fog_distance']}|aniso={after['volumetric_fog_scattering_distribution']}|saved=0")
