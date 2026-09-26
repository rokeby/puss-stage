"""Read-only: why no light shafts render in the corridor.

The conductor's offscreen captures at P01 beam bays (5, 9, 13) show no shafts
with MegaLights on or off. Checks, in order: the fog medium actually present at
eye height, fog albedo/emissive (the celestial rig owns fog colour), the
volumetric-fog console variables and scalability, the exposure the post-process
pins, and the live beam lamps themselves (on? how bright? scattering reaching
them? pointing where?). Mutates nothing.
"""
import json
import math
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = list(sub.get_all_level_actors())


def prop(obj, name):
    try:
        v = obj.get_editor_property(name)
    except Exception as exc:
        return f"unreadable:{exc.__class__.__name__}"
    if isinstance(v, (unreal.Vector, unreal.LinearColor, unreal.Color, unreal.Rotator)):
        return str(v)
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    return v if isinstance(v, (int, float, bool, str)) or v is None else str(v)


report = {"fog": [], "cvars": {}, "post_process": [], "beam_lamps": [], "celestial": []}

for a in actors:
    if a.get_class().get_name() == "ExponentialHeightFog":
        fc = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fog_z = a.get_actor_location().z
        density = fc.get_editor_property("fog_density")
        falloff = fc.get_editor_property("fog_height_falloff")
        # UE height fog: density scales by 2^(-falloff * (z - fogZ) / 1000) for z above the fog actor.
        at_eye = density * math.pow(2.0, -falloff * max(0.0, 170.0 - fog_z) / 1000.0)
        rec = {"label": a.get_actor_label(), "actor_z": round(fog_z), "density_at_eye_est": at_eye}
        for n in ["fog_density", "fog_height_falloff", "fog_max_opacity", "start_distance", "fog_cutoff_distance",
                  "enable_volumetric_fog", "volumetric_fog_scattering_distribution", "volumetric_fog_albedo",
                  "volumetric_fog_emissive", "volumetric_fog_extinction_scale", "volumetric_fog_distance",
                  "volumetric_fog_start_distance", "volumetric_fog_near_fade_in_distance",
                  "fog_inscattering_luminance", "directional_inscattering_luminance", "hidden_in_game", "visible"]:
            rec[n] = prop(fc, n)
        report["fog"].append(rec)
    cls = a.get_class().get_name()
    if cls == "PostProcessVolume":
        s = a.get_editor_property("settings")
        report["post_process"].append({
            "label": a.get_actor_label(), "unbound": prop(a, "unbound"), "enabled": prop(a, "enabled"),
            "priority": prop(a, "priority"),
            "auto_exposure_method": prop(s, "auto_exposure_method") if prop(s, "override_auto_exposure_method") else "not overridden",
            "auto_exposure_bias": prop(s, "auto_exposure_bias") if prop(s, "override_auto_exposure_bias") else "not overridden",
            "min_ev100": prop(s, "auto_exposure_min_brightness") if prop(s, "override_auto_exposure_min_brightness") else "not overridden",
            "max_ev100": prop(s, "auto_exposure_max_brightness") if prop(s, "override_auto_exposure_max_brightness") else "not overridden",
            "apply_physical_camera_exposure": prop(s, "auto_exposure_apply_physical_camera_exposure"),
        })
    if "Celestial" in cls:
        report["celestial"].append({"label": a.get_actor_label(), "class": cls})

for name in ["r.VolumetricFog", "r.VolumetricFog.GridPixelSize", "r.VolumetricFog.GridSizeZ",
             "r.VolumetricFog.HistoryWeight", "r.VolumetricFog.InjectShadowedLightsSeparately",
             "r.VolumetricFog.LightScatteringSampleJitterMultiplier", "sg.ShadowQuality", "sg.PostProcessQuality",
             "r.MegaLights.EnableForProject", "r.MegaLights.Volume", "r.Fog", "r.EyeAdaptationQuality"]:
    report["cvars"][name] = unreal.SystemLibrary.get_console_variable_float_value(name)

beam_slot = re.compile(r"^P01 Wing (\d{3}) Cross [+-]Y$")
for a in actors:
    m = beam_slot.match(a.get_actor_label())
    if not m or int(m.group(1)) not in (5, 9, 13):
        continue
    lc = a.get_component_by_class(unreal.LightComponent)
    loc = a.get_actor_location()
    fwd = a.get_actor_forward_vector()
    report["beam_lamps"].append({
        "label": a.get_actor_label(),
        "location": [round(loc.x), round(loc.y), round(loc.z)],
        "forward": [round(fwd.x, 2), round(fwd.y, 2), round(fwd.z, 2)],
        "visible": lc.is_visible() if lc else None,
        "intensity": prop(lc, "intensity"), "units": prop(lc, "intensity_units"),
        "volumetric_scattering_intensity": prop(lc, "volumetric_scattering_intensity"),
        "cast_volumetric_shadow": prop(lc, "cast_volumetric_shadow"),
        "cast_shadows": prop(lc, "cast_shadows"),
        "attenuation_radius": prop(lc, "attenuation_radius"),
        "outer_cone": prop(lc, "outer_cone_angle"), "inner_cone": prop(lc, "inner_cone_angle"),
        "mobility": prop(lc, "mobility"),
        "light_function": prop(lc, "light_function_material"),
        "use_temperature": prop(lc, "use_temperature"), "light_color": prop(lc, "light_color"),
        "max_draw_distance": prop(lc, "max_draw_distance"),
    })

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "shaft_probe.json")
json.dump(report, open(out, "w"), indent=1, default=str)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"SHAFT_PROBE_OK|fog={len(report['fog'])}|ppv={len(report['post_process'])}|beam_lamps={len(report['beam_lamps'])}"
           f"|dirty={dirty}|mutated=0")
