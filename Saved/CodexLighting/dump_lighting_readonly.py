"""Read-only dump of the level's lighting actors, celestial rig, post-process volumes and Show stage-light attachments."""
import json, os, re
import unreal
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None
def props(obj, names):
    out = {}
    for n in names:
        try:
            v = obj.get_editor_property(n)
            if isinstance(v, (unreal.Vector, unreal.Rotator)): v = str(v)
            elif isinstance(v, (unreal.LinearColor, unreal.Color)): v = str(v)
            elif hasattr(v, "get_path_name"): v = pkg(v)
            elif not isinstance(v, (int, float, bool, str)) and v is not None: v = str(v)
            out[n] = v
        except Exception: pass
    return out
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = []
for a in sub.get_all_level_actors():
    cls = a.get_class().get_name()
    if not any(k in cls for k in ("Light", "Sky", "Fog", "Cloud", "Celestial", "PostProcess", "Volume")): continue
    if cls in ("InfinityStagePassageActor",): continue
    rec = {"label": a.get_actor_label(), "class": cls, "folder": str(a.get_folder_path()),
           "location": str(a.get_actor_location()), "rotation": str(a.get_actor_rotation()),
           "hidden_editor": bool(a.is_temporarily_hidden_in_editor()), "hidden_game": bool(a.get_editor_property("hidden"))}
    comp = a.get_component_by_class(unreal.LightComponentBase) if hasattr(unreal, "LightComponentBase") else None
    if comp:
        rec["light"] = props(comp, ["intensity", "light_color", "temperature", "use_temperature", "cast_shadows", "mobility",
                                    "forward_shading_priority", "atmosphere_sun_light", "atmosphere_sun_light_index",
                                    "inner_cone_angle", "outer_cone_angle", "attenuation_radius", "intensity_units",
                                    "light_source_angle", "cast_volumetric_shadow", "volumetric_scattering_intensity"])
        try: rec["light"]["visible"] = bool(comp.get_editor_property("visible"))
        except Exception: pass
    for cname in ("SkyLightComponent", "SkyAtmosphereComponent", "ExponentialHeightFogComponent", "VolumetricCloudComponent", "PostProcessComponent"):
        cl = getattr(unreal, cname, None)
        if cl:
            c = a.get_component_by_class(cl)
            if c:
                rec[cname] = props(c, ["intensity", "real_time_capture", "source_type", "visible", "fog_density", "fog_height_falloff",
                                       "fog_inscattering_luminance", "start_distance", "volumetric_fog", "layer_bottom_altitude", "layer_height"])
    if cls == "PostProcessVolume":
        try:
            s = a.get_editor_property("settings")
            rec["pp"] = props(s, ["override_auto_exposure_method", "auto_exposure_method", "override_auto_exposure_bias", "auto_exposure_bias",
                                   "override_auto_exposure_min_brightness", "auto_exposure_min_brightness", "override_auto_exposure_max_brightness", "auto_exposure_max_brightness"])
            rec["unbound"] = bool(a.get_editor_property("unbound")); rec["enabled"] = bool(a.get_editor_property("enabled"))
        except Exception as exc: rec["pp_error"] = repr(exc)
    if "Celestial" in cls:
        rec["celestial"] = props(a, ["initial_phase_cycles", "use_manual_editor_lighting", "editor_preview_time_hours",
            "sun_azimuth_degrees", "maximum_sun_intensity", "maximum_moon_intensity", "day_sky_light_intensity",
            "night_sky_light_intensity", "maximum_stars_brightness", "show_built_in_stars", "twilight_altitude_band",
            "current_normalized_phase", "current_daylight_amount", "current_stars_amount", "auto_bind_actors_by_tag",
            "sun_light_actor", "moon_light_actor", "sky_light_actor", "height_fog_actor"])
    actors.append(rec)
# Show stage-light attachments
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
lights = {}
LABEL_RE = re.compile(r"^P(\d{2}) Wing")
for cue in show.get_editor_property("cues"):
    m = LABEL_RE.match(str(cue.get_editor_property("label")))
    if not m: continue
    try:
        atts = cue.get_editor_property("wing_pair").get_editor_property("attachments")
    except Exception:
        atts = []
    n = 0
    for att in atts:
        try:
            k = str(att.get_editor_property("kind"))
            if "LIGHT" in k.upper(): n += 1
        except Exception:
            n += 1 if "light" in str(att).lower() else 0
    lights[m.group(1)] = lights.get(m.group(1), 0) + n
world_settings = props(world.get_world_settings(), ["global_gravity_z"])
payload = {"actors": actors, "stage_light_attachments_per_passage": lights}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "lighting_dump.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(payload, fh, indent=1, sort_keys=True, default=str)
unreal.log(f"PUSS_LIGHTING_DUMP_SUCCESS|actors={len(actors)}")
