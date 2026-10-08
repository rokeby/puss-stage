"""READ-ONLY: PostProcessVolumes near S3 (and unbound ones): Lumen / reflection settings + overrides. PROBE_S3PPV_OK|json"""
import json
KEYS = ["dynamic_global_illumination_method", "reflection_method", "lumen_scene_lighting_quality", "lumen_scene_detail",
        "lumen_scene_view_distance", "lumen_final_gather_quality", "lumen_max_trace_distance", "lumen_reflection_quality",
        "lumen_ray_lighting_mode", "lumen_front_layer_translucency_reflections", "lumen_max_roughness_to_trace_reflections",
        "lumen_surface_cache_resolution", "lumen_full_skylight_leaking_distance"]
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    out = {}
    for v in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.PostProcessVolume):
        l = str(v.get_actor_label())
        loc = v.get_actor_location()
        unb = v.get_editor_property("unbound")
        if not (unb or (11000 < loc.x < 18000 and 158000 < loc.y < 162000) or "S3" in l):
            continue
        s = v.get_editor_property("settings")
        row = {"unbound": unb, "prio": v.get_editor_property("priority"), "enabled": v.get_editor_property("enabled"),
               "weight": v.get_editor_property("blend_weight")}
        for k in KEYS:
            try:
                row[k] = str(s.get_editor_property(k))
                ov = "override_" + k
                row[ov] = s.get_editor_property(ov)
            except Exception:
                pass
        out[l] = row
    unreal.log("PROBE_S3PPV_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3PPV_FAILED|%r" % (exc,))
