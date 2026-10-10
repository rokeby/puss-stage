"""Job 118 read-only editor probe: why P01 is reflective while the S2 hangar floor is not.

Execute only through ExecuteProjectPythonFile with the editor world already open.  This script
does not load/unload levels, enter PIE, mutate an object, or save a package.  It records what the
editor already has loaded and proves that the dirty-package census is byte-for-byte unchanged.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os

import unreal

MARK = "J118_S2_FLOOR_REFLECTION_PROBE"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
P01 = "Passage 01 - Opening Floor"
S2 = ("S2 Hangar Floor 1", "S2 Hangar Floor 2", "S2 Hangar Floor 3", "S2 Hangar Apron")
P02 = ("Passage 02 - Floor Near", "Passage 02 - Floor Left",
       "Passage 02 - Floor Right", "Passage 02 - Floor Far")
TARGETS = {"S2": S2, "P02": P02}
KLARA_PACKAGES = (
    "/Game/KK_S1_Animals/L_Animals",
    "/Game/L_KK_children",
    "/Game/Japanese_Alley/Maps/Japanese_Alley",
    "/Game/L_KK_Void",
)

PP_FIELDS = (
    "reflection_method",
    "lumen_reflection_quality",
    "lumen_max_roughness_to_trace_reflections",
    "lumen_reflections_screen_traces",
    "screen_space_reflection_intensity",
    "screen_space_reflection_quality",
    "screen_space_reflection_max_roughness",
    "auto_exposure_method",
    "auto_exposure_min_brightness",
    "auto_exposure_max_brightness",
    "auto_exposure_bias",
    "auto_exposure_low_percent",
    "auto_exposure_high_percent",
    "auto_exposure_speed_up",
    "auto_exposure_speed_down",
    "local_exposure_highlight_contrast_scale",
    "local_exposure_shadow_contrast_scale",
)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_path_name() for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_path_name() for p in lib.get_dirty_map_packages()),
    }


def path(obj):
    return obj.get_path_name() if obj is not None else None


def level_path(actor):
    return actor.get_outermost().get_name()


def plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "to_tuple"):
        return [float(x) for x in value.to_tuple()]
    return str(value)


def prop(obj, name, missing=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return missing


def param_name(row):
    info = prop(row, "parameter_info")
    name = prop(info, "name") if info is not None else None
    if name is None:
        name = prop(row, "parameter_name")
    return str(name) if name is not None else None


def serialized_parameters(material):
    """Read local MIC/MID overrides only.  MaterialEditingLibrary getters are deliberately avoided."""
    out = {"scalar": {}, "vector": {}, "texture": {}, "static_switch": {}}
    arrays = (
        ("scalar_parameter_values", "scalar", "parameter_value"),
        ("vector_parameter_values", "vector", "parameter_value"),
        ("texture_parameter_values", "texture", "parameter_value"),
        ("static_parameters", "static_switch", "value"),
    )
    for array_name, kind, value_name in arrays:
        rows = prop(material, array_name, ()) or ()
        # StaticParameters is a container on some builds, not a direct row array.
        if kind == "static_switch" and not isinstance(rows, (list, tuple)):
            rows = prop(rows, "static_switch_parameters", ()) or ()
        for row in rows:
            name = param_name(row)
            if name:
                out[kind][name] = plain(prop(row, value_name))
    return out


def material_chain(material):
    rows, seen = [], set()
    cur = material
    while cur is not None and path(cur) not in seen:
        seen.add(path(cur))
        cls = cur.get_class().get_name()
        local = serialized_parameters(cur)
        rows.append({"path": path(cur), "class": cls, "local_overrides": local})
        cur = prop(cur, "parent") if "MaterialInstance" in cls else None
    return rows


def relevant_parameter_values(material):
    """Resolve visible rough/spec/wet override values through the instance parent chain."""
    resolved, source = {}, {}
    chain = material_chain(material)
    for row in reversed(chain):
        for kind in ("scalar", "vector", "texture", "static_switch"):
            for name, value in row["local_overrides"][kind].items():
                if any(token in name.lower() for token in ("rough", "spec", "wet")):
                    resolved[name] = value
                    source[name] = {"kind": kind, "declared_on": row["path"]}
    # Existing MIDs can have transient values not represented by serialized MIC arrays.  Query only
    # names already proven by the chain; this is a read on the existing MID, not MID creation.
    if material is not None and material.get_class().get_name() == "MaterialInstanceDynamic":
        getter = getattr(material, "get_scalar_parameter_value", None)
        if getter:
            for name in list(resolved):
                if source[name]["kind"] == "scalar":
                    try:
                        resolved[name] = float(getter(name))
                        source[name] = {"kind": "scalar", "declared_on": "runtime_MID"}
                    except Exception as exc:
                        source[name]["mid_read_error"] = repr(exc)
    return {"values": resolved, "sources": source, "chain": chain}


def stable_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def rounded(values, digits=6):
    return [round(float(value), digits) for value in values]


def mesh_geometry(mesh):
    """Read a compact LOD0 signature without changing build settings or mesh assets."""
    result = {
        "status": "UNCLEAR", "mesh": path(mesh), "lod": 0, "polygon_count": None,
        "vertex_count": None, "vertex_instance_count": None, "uv_channel_count": None,
        "uv_channels": [], "normal": None, "vertex_color": None, "errors": [],
    }
    if mesh is None:
        result["errors"].append("NO_STATIC_MESH")
        return result
    try:
        desc = mesh.get_static_mesh_description(0)
    except Exception as exc:
        result["errors"].append("get_static_mesh_description: %r" % (exc,))
        return result
    if desc is None:
        result["errors"].append("LOD0_MESH_DESCRIPTION_UNAVAILABLE")
        return result
    try:
        result["polygon_count"] = int(desc.get_polygon_count())
        try:
            result["vertex_count"] = int(desc.get_vertex_count())
        except Exception as exc:
            result["errors"].append("get_vertex_count: %r" % (exc,))
        try:
            subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
            result["uv_channel_count"] = int(subsystem.get_num_uv_channels(mesh, 0))
        except Exception as exc:
            result["uv_channel_count"] = 0
            result["errors"].append("get_num_uv_channels: %r" % (exc,))
        corners = []
        for polygon_index in range(result["polygon_count"]):
            polygon_id = unreal.PolygonID(polygon_index)
            for vertex_instance in list(desc.get_polygon_vertex_instances(polygon_id)):
                try:
                    normal = desc.get_vertex_instance_normal(vertex_instance)
                    normal_row = rounded((normal.x, normal.y, normal.z))
                except Exception as exc:
                    normal_row = None
                    if not any(str(row).startswith("get_vertex_instance_normal") for row in result["errors"]):
                        result["errors"].append("get_vertex_instance_normal: %r" % (exc,))
                try:
                    color = desc.get_vertex_instance_color(vertex_instance)
                    color_row = rounded((color.r, color.g, color.b, color.a))
                except Exception as exc:
                    color_row = None
                    if not any(str(row).startswith("get_vertex_instance_color") for row in result["errors"]):
                        result["errors"].append("get_vertex_instance_color: %r" % (exc,))
                corners.append({
                    "normal": normal_row,
                    "color": color_row,
                    "uv": [rounded(desc.get_vertex_instance_uv(vertex_instance, channel).to_tuple())
                           for channel in range(result["uv_channel_count"])],
                })
        result["vertex_instance_count"] = len(corners)
        normals = [row["normal"] for row in corners if row["normal"] is not None]
        result["normal"] = {
            "status": "measured" if len(normals) == len(corners) else "UNCLEAR",
            "corner_count": len(normals), "sha256": stable_digest(normals) if normals else None,
            "unique_rounded": len({tuple(row) for row in normals}),
        }
        colors = [row["color"] for row in corners if row["color"] is not None]
        result["vertex_color"] = {
            "status": "measured" if len(colors) == len(corners) else "UNCLEAR",
            "corner_count": len(colors), "sha256": stable_digest(colors) if colors else None,
            "unique_rounded": len({tuple(row) for row in colors}),
            "non_white_corners": sum(1 for row in colors if row != [1.0, 1.0, 1.0, 1.0]),
        }
        for channel in range(result["uv_channel_count"]):
            values = [row["uv"][channel] for row in corners]
            result["uv_channels"].append({
                "channel": channel, "corner_count": len(values), "sha256": stable_digest(values),
                "min": [min(row[axis] for row in values) for axis in range(2)] if values else None,
                "max": [max(row[axis] for row in values) for axis in range(2)] if values else None,
            })
        result["status"] = "measured" if not result["errors"] else "partial"
    except Exception as exc:
        result["errors"].append("LOD0_WALK: %r" % (exc,))
    return result


def render_sections(component, mesh):
    """Resolve each LOD0 render section to its material slot where UE exposes the mapping."""
    rows, errors = [], []
    try:
        subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        count = int(subsystem.get_num_sections(mesh, 0))
        for section_index in range(count):
            slot_index = int(subsystem.get_lod_material_slot(mesh, 0, section_index))
            material = component.get_material(slot_index)
            rows.append({
                "section_index": section_index, "material_slot_index": slot_index,
                "effective_render_material": path(material),
                "is_mid": bool(material and material.get_class().get_name() == "MaterialInstanceDynamic"),
                "parameters": relevant_parameter_values(material) if material is not None else None,
            })
    except Exception as exc:
        errors.append("StaticMeshEditorSubsystem section mapping: %r" % (exc,))
    return {"status": "measured" if not errors else "UNCLEAR", "sections": rows, "errors": errors}


def component_materials(component):
    mesh = prop(component, "static_mesh")
    mesh_slots = []
    if mesh is not None:
        for index, row in enumerate(prop(mesh, "static_materials", ()) or ()):
            interface = prop(row, "material_interface")
            mesh_slots.append({
                "index": index,
                "slot_name": str(prop(row, "material_slot_name")),
                "mesh_material": path(interface),
            })
    overrides = list(prop(component, "override_materials", ()) or ())
    count = max(len(mesh_slots), int(component.get_num_materials()))
    sections = []
    for index in range(count):
        effective = component.get_material(index)
        override = overrides[index] if index < len(overrides) else None
        slot = mesh_slots[index] if index < len(mesh_slots) else {"index": index, "slot_name": None, "mesh_material": None}
        origin = "component_override" if override is not None else "mesh_slot"
        sections.append({
            **slot,
            "component_override": path(override),
            "effective_render_material": path(effective),
            "effective_origin": origin,
            "is_mid": bool(effective and effective.get_class().get_name() == "MaterialInstanceDynamic"),
            "parameters": relevant_parameter_values(effective) if effective is not None else None,
            # UStaticMesh section->material-index remapping is not consistently Python-exposed in 5.8.
            "section_mapping_evidence": "slot_index_fallback; section_info_map reported separately when exposed",
        })
    section_map = None
    if mesh is not None:
        getter = getattr(mesh, "get_section_info_map", None)
        if getter:
            try:
                section_map = str(getter())
            except Exception as exc:
                section_map = "UNCLEAR: %r" % (exc,)
    return {
        "component": path(component), "component_class": component.get_class().get_name(),
        "mesh": path(mesh), "material_slots": sections, "render_sections_lod0": render_sections(component, mesh),
        "section_info_map": section_map, "geometry_lod0": mesh_geometry(mesh),
        "instance_count": int(component.get_instance_count()) if hasattr(component, "get_instance_count") else None,
    }


def actor_bounds(actor):
    origin, extent = unreal.SystemLibrary.get_actor_bounds(actor, False)
    return {
        "origin": [float(origin.x), float(origin.y), float(origin.z)],
        "extent": [float(extent.x), float(extent.y), float(extent.z)],
        "min": [float(origin.x - extent.x), float(origin.y - extent.y), float(origin.z - extent.z)],
        "max": [float(origin.x + extent.x), float(origin.y + extent.y), float(origin.z + extent.z)],
    }


def sample_points(bounds):
    lo, hi, z = bounds["min"], bounds["max"], bounds["max"][2] + 1.0
    return [
        [bounds["origin"][0], bounds["origin"][1], z],
        [lo[0], lo[1], z], [lo[0], hi[1], z], [hi[0], lo[1], z], [hi[0], hi[1], z],
    ]


def pp_contains(volume, point):
    if bool(prop(volume, "unbound", False)):
        return True, "unbound"
    fn = getattr(volume, "encompasses_point", None)
    if fn:
        try:
            got = fn(unreal.Vector(*point), 0.0)
            inside = bool(got[0] if isinstance(got, tuple) else got)
            return inside, "AVolume.encompasses_point"
        except Exception:
            pass
    b = actor_bounds(volume)
    inside = all(b["min"][i] <= point[i] <= b["max"][i] for i in range(3))
    return inside, "axis_aligned_actor_bounds_fallback"


def pp_row(volume, floors):
    settings = prop(volume, "settings")
    fields = {}
    for name in PP_FIELDS:
        value = prop(settings, name, "PROPERTY_UNAVAILABLE")
        override = prop(settings, "override_" + name, "PROPERTY_UNAVAILABLE")
        fields[name] = {"value": plain(value), "override": plain(override)}
    containment = {}
    for floor in floors:
        checks = [pp_contains(volume, p) for p in floor["sample_points"]]
        containment[floor["label"]] = {
            "points_inside": sum(1 for yes, _ in checks if yes),
            "points_tested": len(checks),
            "contains_center": checks[0][0],
            "contains_all_samples": all(yes for yes, _ in checks),
            "method": sorted(set(method for _, method in checks)),
        }
    return {
        "label": str(volume.get_actor_label()), "path": path(volume), "level": level_path(volume),
        "persistent_or_klara": "persistent" if level_path(volume) == WORLD else
            ("klara_streamed" if level_path(volume) in KLARA_PACKAGES else "other_streamed"),
        "enabled": bool(prop(volume, "enabled", True)), "unbound": bool(prop(volume, "unbound", False)),
        "priority": plain(prop(volume, "priority")), "blend_weight": plain(prop(volume, "blend_weight")),
        "blend_radius": plain(prop(volume, "blend_radius")), "bounds": actor_bounds(volume),
        "contains": containment, "settings": fields,
    }


def component_row(component):
    actor = component.get_owner()
    names = (
        "intensity", "light_color", "temperature", "use_temperature", "indirect_lighting_intensity",
        "volumetric_scattering_intensity", "cast_shadows", "mobility", "source_radius", "source_length",
        "attenuation_radius", "inner_cone_angle", "outer_cone_angle", "lower_hemisphere_is_black",
        "source_type", "cubemap", "capture_source", "brightness", "influence_radius",
    )
    return {
        "actor_label": str(actor.get_actor_label()) if actor else None,
        "actor_path": path(actor), "component": path(component), "class": component.get_class().get_name(),
        "level": level_path(actor) if actor else None,
        "location": list(component.get_world_location().to_tuple()),
        "properties": {name: plain(prop(component, name)) for name in names if prop(component, name, "__MISSING__") != "__MISSING__"},
    }


def union_bounds(rows):
    return {
        "min": [min(row["bounds"]["min"][i] for row in rows) for i in range(3)],
        "max": [max(row["bounds"]["max"][i] for row in rows) for i in range(3)],
    }


def comparison_rows(floors):
    source = floors[0]
    source_components = source["components"]
    rows = []
    for target in floors[1:]:
        target_components = target["components"]
        component_pairs = []
        for index in range(max(len(source_components), len(target_components))):
            left = source_components[index] if index < len(source_components) else None
            right = target_components[index] if index < len(target_components) else None
            component_pairs.append({
                "component_index": index,
                "mesh_equal": bool(left and right and left["mesh"] == right["mesh"]),
                "materials_per_section_equal": bool(left and right and
                    left["render_sections_lod0"]["sections"] == right["render_sections_lod0"]["sections"]),
                "uvs_equal": bool(left and right and
                    left["geometry_lod0"]["uv_channels"] == right["geometry_lod0"]["uv_channels"]),
                "normals_equal": bool(left and right and
                    left["geometry_lod0"]["normal"] == right["geometry_lod0"]["normal"]),
                "vertex_colours_equal": bool(left and right and
                    left["geometry_lod0"]["vertex_color"] == right["geometry_lod0"]["vertex_color"]),
                "source": left, "target": right,
            })
        rows.append({"source_label": source["label"], "target_label": target["label"],
                     "component_count_equal": len(source_components) == len(target_components),
                     "components": component_pairs})
    return rows


def main():
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", "J118S2FloorReflection_20261009")
    args_path = os.path.join(here, "j118_floor_reflection_probe_args.json")
    args = {"target": "S2"}
    if os.path.exists(args_path):
        with open(args_path, encoding="utf-8") as handle:
            args = json.load(handle)
    target = str(args.get("target", "S2")).upper()
    if target not in TARGETS:
        raise RuntimeError("BAD_TARGET|%s|expected=S2|P02" % target)
    floors_wanted = (P01,) + TARGETS[target]
    run = "J118%sPROBE-" % target + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    before = census()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != WORLD:
        raise RuntimeError("WRONG_WORLD|%s" % (world.get_outermost().get_name() if world else None,))
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by_label = {}
    for actor in actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)

    floor_rows = []
    for label in floors_wanted:
        found = by_label.get(label, [])
        if len(found) != 1:
            raise RuntimeError("FLOOR_COUNT|label=%s|count=%d" % (label, len(found)))
        actor = found[0]
        components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        if not components:
            raise RuntimeError("NO_STATIC_MESH_COMPONENT|" + label)
        bounds = actor_bounds(actor)
        floor_rows.append({
            "label": label, "actor": path(actor), "level": level_path(actor), "bounds": bounds,
            "sample_points": sample_points(bounds),
            "components": [component_materials(component) for component in components],
        })
    unreal.log("%s_TIER1_MATERIALS|run=%s|floors=%d" % (MARK, run, len(floor_rows)))

    ppvs = []
    for actor in actors:
        if isinstance(actor, unreal.PostProcessVolume):
            row = pp_row(actor, floor_rows)
            if row["unbound"] or any(v["contains_center"] or v["contains_all_samples"] for v in row["contains"].values()):
                ppvs.append(row)
    unreal.log("%s_TIER2_POSTPROCESS|run=%s|volumes=%d" % (MARK, run, len(ppvs)))

    target_union = union_bounds([row for row in floor_rows if row["label"] in TARGETS[target]])
    center = [(target_union["min"][i] + target_union["max"][i]) * 0.5 for i in range(3)]
    radius = max(target_union["max"][0] - target_union["min"][0],
                 target_union["max"][1] - target_union["min"][1]) + 30000.0
    light_rows, capture_rows = [], []
    for actor in actors:
        label, lvl = str(actor.get_actor_label()), level_path(actor)
        for component in actor.get_components_by_class(unreal.LightComponentBase):
            loc = component.get_world_location()
            near = sum((float(loc.to_tuple()[i]) - center[i]) ** 2 for i in range(3)) ** 0.5 <= radius
            is_sky_or_sun = component.get_class().get_name() in ("SkyLightComponent", "DirectionalLightComponent")
            if near or is_sky_or_sun or label.startswith(target) or (target == "S2" and "hangar" in label.lower()) or lvl in KLARA_PACKAGES:
                light_rows.append(component_row(component))
        for component in actor.get_components_by_class(unreal.ReflectionCaptureComponent):
            loc = component.get_world_location()
            near = sum((float(loc.to_tuple()[i]) - center[i]) ** 2 for i in range(3)) ** 0.5 <= radius
            if near or label.startswith(target) or (target == "S2" and "hangar" in label.lower()) or lvl in KLARA_PACKAGES:
                capture_rows.append(component_row(component))

    renderer = unreal.get_default_object(unreal.RendererSettings)
    defaults = {
        "RendererSettings.reflection_method": plain(prop(renderer, "reflection_method")),
        "RendererSettings.dynamic_global_illumination_method": plain(prop(renderer, "dynamic_global_illumination_method")),
        "cvar.r.ReflectionMethod.current": int(unreal.SystemLibrary.get_console_variable_int_value("r.ReflectionMethod")),
        "cvar.r.Lumen.HardwareRayTracing.current": int(unreal.SystemLibrary.get_console_variable_int_value("r.Lumen.HardwareRayTracing")),
        "declaration_config": "Config/DefaultEngine.ini [/Script/Engine.RendererSettings]",
    }
    unreal.log("%s_TIER3_LIGHTING_DEFAULTS|run=%s|lights=%d|captures=%d" %
               (MARK, run, len(light_rows), len(capture_rows)))

    after = census()
    if before != after:
        raise RuntimeError("CENSUS_CHANGED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
    report = {
        "schema": 2, "run": run, "target": target, "world": WORLD, "pie": False, "saved": False,
        "census_before": before, "census_after": after, "census_equal": True,
        "floors": floor_rows, "p01_vs_target": comparison_rows(floor_rows), "post_process_volumes": ppvs,
        "target_lights_and_skylights": sorted(light_rows, key=lambda r: (r["level"], r["actor_label"], r["component"])),
        "target_reflection_captures": sorted(capture_rows, key=lambda r: (r["level"], r["actor_label"], r["component"])),
        "project_defaults": defaults,
        "limitations": [
            "Editor/no-PIE evidence: no future runtime-created MID can exist yet; existing MIDs are reported.",
            "Rendered reflectivity is not proved by property read-back; Gary must visually accept a later APPLY.",
            "Section-to-slot remaps are UNCLEAR where UStaticMesh section_info_map is not Python-exposed.",
        ],
    }
    os.makedirs(here, exist_ok=True)
    output = os.path.join(here, "j118_probe_%s.json" % run)
    with open(output, "x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    with open(output, encoding="utf-8") as handle:
        checked = json.load(handle)
    if checked.get("run") != run or not checked.get("census_equal"):
        raise RuntimeError("REPORT_READBACK_FAILED")
    unreal.log("%s_OK|run=%s|target=%s|floors=%d|ppv=%d|lights=%d|captures=%d|census_before==after=1|saved=0|report=%s" %
               (MARK, run, target, len(floor_rows), len(ppvs), len(light_rows), len(capture_rows), output))


try:
    main()
except Exception as exc:
    unreal.log_error("%s_FAILED|%r" % (MARK, exc))
    raise
