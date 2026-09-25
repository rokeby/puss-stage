import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); out = {}
def col(c): return [round(c.r,3), round(c.g,3), round(c.b,3)]
for a in sub.get_all_level_actors():
    n = a.get_class().get_name(); lbl = a.get_actor_label()
    if n == "ExponentialHeightFog" and lbl.startswith("Infinity Stage"):
        c = a.get_component_by_class(unreal.ExponentialHeightFogComponent)
        out["fog"] = {"density": c.get_editor_property("fog_density"), "falloff": c.get_editor_property("fog_height_falloff"), "inscattering": col(c.get_editor_property("fog_inscattering_luminance")),
                      "directional_inscattering": col(c.get_editor_property("directional_inscattering_luminance")), "max_opacity": c.get_editor_property("fog_max_opacity"), "start_distance": c.get_editor_property("start_distance"), "visible": c.get_editor_property("visible")}
    if n == "InfinityStageCelestialRig":
        out["rig"] = {"night_fog_color": col(a.get_editor_property("night_fog_color")), "day_fog_color": col(a.get_editor_property("day_fog_color")), "moon_color": col(a.get_editor_property("moon_color")), "night_sky_light_color": col(a.get_editor_property("night_sky_light_color"))}
    if n == "SkyAtmosphere" and lbl.startswith("Infinity Stage"):
        c = a.get_component_by_class(unreal.SkyAtmosphereComponent); out["atmosphere_visible"] = c.get_editor_property("visible")
    if n == "SkyLight" and lbl.startswith("Infinity Stage"):
        c = a.get_component_by_class(unreal.SkyLightComponent); out["skylight"] = {"intensity": c.get_editor_property("intensity"), "color": col(c.get_editor_property("light_color")) if hasattr(c.get_editor_property("light_color"), "r") else str(c.get_editor_property("light_color"))}
unreal.log("PUSS_FOG|" + str(out))
