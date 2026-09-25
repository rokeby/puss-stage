"""Read-only P02 Lumen-reflection probe. Writes only a Saved JSON report."""
import json
import os

import unreal


def prop(obj, name, default=None):
    if obj is None:
        return default
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def value(item):
    if item is None or isinstance(item, (str, int, float, bool)):
        return item
    if hasattr(item, "get_path_name"):
        try:
            return item.get_path_name()
        except Exception:
            pass
    return str(item)


def cvar_int(name):
    try:
        return unreal.SystemLibrary.get_console_variable_int_value(name)
    except Exception as exc:
        return f"ERR:{type(exc).__name__}:{exc}"


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
game_world = editor.get_game_world()
editor_world = editor.get_editor_world()
world = game_world or editor_world
if world is None:
    raise RuntimeError("No Unreal world is available")

report = {
    "world": {
        "path": world.get_path_name(),
        "pie": game_world is not None,
        "dirty_content": [
            str(package)
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ],
        "dirty_maps": [
            str(package)
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ],
    },
    "cvars": {},
    "renderer_settings": {},
    "p02_components": [],
    "forested_landscape": [],
    "post_process_volumes": [],
}

for name in (
    "r.RayTracing",
    "r.ReflectionMethod",
    "r.Lumen.Reflections.Allow",
    "r.Lumen.Reflections.ScreenTraces",
    "r.Lumen.HardwareRayTracing",
    "r.Lumen.HardwareRayTracing.LightingMode",
    "r.RayTracing.Geometry.InstancedStaticMeshes",
    "r.RayTracing.Nanite.Mode",
    "r.Lumen.Reflections.DownsampleFactor",
    "r.Lumen.Reflections.ScreenSpaceReconstruction.NumSamples",
    "sg.ReflectionQuality",
    "r.AntiAliasingMethod",
):
    report["cvars"][name] = cvar_int(name)

renderer_settings_class = unreal.load_class(None, "/Script/Engine.RendererSettings")
settings = unreal.get_default_object(renderer_settings_class) if renderer_settings_class else None
for name in (
    "enable_ray_tracing",
    "use_hardware_ray_tracing_for_lumen",
    "lumen_ray_lighting_mode",
    "dynamic_global_illumination",
    "reflection_method",
):
    report["renderer_settings"][name] = value(prop(settings, name, "UNAVAILABLE"))

all_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
seen_components = set()
for actor in all_actors:
    try:
        label = actor.get_actor_label()
    except Exception:
        label = actor.get_name()

    if "ForestedLandscape" in label:
        row = {"label": label, "class": actor.get_class().get_name(), "components": []}
        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            materials = []
            try:
                for index in range(component.get_num_materials()):
                    materials.append(value(component.get_material(index)))
            except Exception:
                pass
            row["components"].append({
                "name": component.get_name(),
                "class": component.get_class().get_name(),
                "materials": materials,
                "visible_in_ray_tracing": value(prop(component, "visible_in_ray_tracing")),
                "affect_distance_field_lighting": value(prop(component, "affect_distance_field_lighting")),
            })
        report["forested_landscape"].append(row)

    if actor.get_class().get_name() == "PostProcessVolume":
        pp = prop(actor, "settings")
        report["post_process_volumes"].append({
            "label": label,
            "enabled": value(prop(actor, "enabled")),
            "unbound": value(prop(actor, "unbound")),
            "priority": value(prop(actor, "priority")),
            "lumen_reflection_quality": value(prop(pp, "lumen_reflection_quality")),
            "lumen_reflections_screen_traces": value(prop(pp, "lumen_reflections_screen_traces")),
            "lumen_ray_lighting_mode": value(prop(pp, "lumen_ray_lighting_mode")),
            "override_screen_traces": value(prop(pp, "override_lumen_reflections_screen_traces")),
            "override_ray_lighting_mode": value(prop(pp, "override_lumen_ray_lighting_mode")),
        })

    for component in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        identity = component.get_path_name()
        if identity in seen_components:
            continue
        mesh = prop(component, "static_mesh")
        mesh_path = value(mesh)
        if not mesh_path or "/Passage02_AnimalsToShrineV2/" not in mesh_path:
            continue
        seen_components.add(identity)
        nanite = prop(mesh, "nanite_settings")
        report["p02_components"].append({
            "actor": label,
            "component": component.get_name(),
            "mesh": mesh_path,
            "instances": component.get_instance_count(),
            "nanite_enabled": value(prop(nanite, "enabled")),
            "visible_in_ray_tracing": value(prop(component, "visible_in_ray_tracing")),
            "affect_distance_field_lighting": value(prop(component, "affect_distance_field_lighting")),
            "evaluate_world_position_offset": value(prop(component, "evaluate_world_position_offset")),
            "mobility": value(prop(component, "mobility")),
        })

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexRenderDiag",
    "p02_reflection_probe.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True, default=str)

unreal.log(
    "P02_REFLECTION_PROBE_SUCCESS"
    f"|pie={int(game_world is not None)}"
    f"|components={len(report['p02_components'])}"
    f"|forested={len(report['forested_landscape'])}"
    f"|ppv={len(report['post_process_volumes'])}"
)
