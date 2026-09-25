"""Read-only: Blueprint-class actors in the level and every actor able to drive lights, plus current rig/light state."""
import json, os
import unreal
def pkg(v): return v.get_path_name().split(".",1)[0] if v is not None and hasattr(v,"get_path_name") else None
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
bp_actors, light_state = [], {}
for a in sub.get_all_level_actors():
    cls = a.get_class(); name = cls.get_name(); folder = str(a.get_folder_path())
    if name.endswith("_C") or "Director" in name or "Cycle" in name or "Sky" in name or "DayNight" in name:
        bp_actors.append({"label": a.get_actor_label(), "class": name, "class_path": pkg(cls), "folder": folder,
                          "hidden": bool(a.get_editor_property("hidden"))})
    if name in ("DirectionalLight", "SkyLight") and a.get_actor_label().startswith("Infinity Stage"):
        try:
            c = a.get_component_by_class(unreal.LightComponentBase)
            light_state[a.get_actor_label()] = {"intensity": float(c.get_editor_property("intensity")), "visible": bool(c.get_editor_property("visible"))}
        except Exception as exc:
            light_state[a.get_actor_label()] = {"error": repr(exc)}
    if name == "InfinityStageCelestialRig":
        light_state["rig"] = {n: a.get_editor_property(n) for n in ("use_manual_editor_lighting","editor_preview_time_hours","initial_phase_cycles","maximum_sun_intensity","maximum_moon_intensity","night_sky_light_intensity","day_sky_light_intensity","show_built_in_stars","current_daylight_amount")}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "bp_actors.json")
with open(out, "w", encoding="utf-8") as fh: json.dump({"bp_actors": bp_actors, "light_state": light_state}, fh, indent=1, default=str)
unreal.log(f"PUSS_BP_ACTORS_SUCCESS|bp_actors={len(bp_actors)}")
