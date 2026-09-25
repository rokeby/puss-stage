import json, unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
out = {}
for a in sub.get_all_level_actors():
    n = a.get_class().get_name(); lbl = a.get_actor_label()
    if n == "ExponentialHeightFog" and lbl.startswith("Infinity Stage"):
        c = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
        keys = ["fog_density","fog_height_falloff","fog_max_opacity","start_distance","second_fog_data",
                "volumetric_fog","volumetric_fog_scattering_distribution","volumetric_fog_albedo",
                "volumetric_fog_emissive","volumetric_fog_extinction_scale","volumetric_fog_distance",
                "volumetric_fog_static_lighting_scattering_intensity"]
        d = {}
        for k in keys:
            try:
                v = c.get_editor_property(k)
                d[k] = v if isinstance(v,(int,float,bool,str)) else str(v)
            except Exception as e: d[k] = f"ERR {e}"
        out["fog"] = d
lights = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.Light) and " Wing " in a.get_actor_label()]
out["wing_light_count"] = len(lights)
if lights:
    c = lights[0].get_component_by_class(unreal.LightComponent)
    out["sample_light"] = {k: c.get_editor_property(k) for k in ("volumetric_scattering_intensity","cast_volumetric_shadow","intensity")}
unreal.log("PUSS_ATMOS|" + json.dumps(out, default=str))
