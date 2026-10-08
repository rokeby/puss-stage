"""READ-ONLY editor: render flags on clam/millstone/figure components. PROBE_RFLAGS_OK|json"""
import json
FLAGS = ["render_in_main_pass", "render_in_depth_pass", "visible_in_scene_capture_only", "hidden_in_scene_capture",
         "owner_no_see", "only_owner_see", "visible_in_reflection_captures", "visible_in_ray_tracing",
         "cast_hidden_shadow", "use_as_occluder", "translucency_sort_priority", "bounds_scale", "never_distance_cull",
         "ld_max_draw_distance", "allow_cull_distance_volume", "visible_in_real_time_sky_captures"]
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(a.get_actor_label())
        if not (l.startswith("S3 PearlClam") or "Millstone" in l or l.startswith("Shore01") or l.startswith("S3 WaveV3 L1")):
            continue
        c = a.get_component_by_class(unreal.PrimitiveComponent)
        row = {}
        for f in FLAGS:
            try:
                row[f] = c.get_editor_property(f)
            except Exception:
                row[f] = "?"
        out[l] = row
    cdv = [x.get_actor_label() for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.CullDistanceVolume)]
    out["_cull_volumes"] = cdv
    unreal.log("PROBE_RFLAGS_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_RFLAGS_FAILED|%r" % (exc,))
