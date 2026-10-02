"""READ-ONLY Scene 3 cast/pearl census.

No setters, saves, Sequencer APIs, PIE, spawned actors, or transient components.
The sole output is one compact JSON marker in the Unreal log.
"""
import datetime
import json
import re

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SKELETAL_PEARL = (
    "/Game/Fab/Clam_with_Pearl_V2_-_Realistic_Scallop_Seashell_with_Gemstone/"
    "source/SkeletalMeshes/Clam_with_Pearl_002_Clam_with_Pearl_0"
)
STATIC_PEARL = (
    "/Game/Fab/Clam_with_Pearl_V2_-_Realistic_Scallop_Seashell_with_Gemstone/"
    "source/StaticMeshes/Clam_with_Pearl_Clam_with_Pearl_0"
)
CAST = (
    ("Shore01_M56 Clam", "BP_Shore01_M56_Draped_C"),
    ("Shore02_F52 Clam", "BP_Shore02_F52_Draped_C"),
    ("Shore03_M59 Clam", "BP_Shore03_M59_Draped_C"),
    ("Shore04_F55 Clam", "BP_Shore04_F55_Draped_C"),
    ("Shore05_M53 Clam", "BP_Shore05_M53_Draped_C"),
    ("Shore06_F25 Clam", "BP_Shore06_F25_Draped_C"),
)
PARAMETER_TERMS = ("skin", "melanin", "tone", "albedo", "tint", "color", "redness")


def path_of(value):
    if value is None:
        return None
    try:
        return str(value.get_path_name())
    except Exception:
        return str(value)


def error_row(exc):
    return {"error_type": type(exc).__name__, "error": str(exc)}


def package_census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)

    return {
        "dirty_maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def material_slot_structs(mesh, property_name):
    rows = []
    try:
        slots = list(mesh.get_editor_property(property_name))
    except Exception as exc:
        return [], error_row(exc)
    for index, slot in enumerate(slots):
        row = {"slot": index}
        for name in ("material_slot_name", "imported_material_slot_name"):
            try:
                row[name] = str(slot.get_editor_property(name))
            except Exception:
                pass
        try:
            row["material"] = path_of(slot.get_editor_property("material_interface"))
        except Exception as exc:
            row["material_error"] = error_row(exc)
        rows.append(row)
    return rows, None


def skeletal_sections(mesh):
    rows = []
    try:
        subsystem = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
        count = int(subsystem.get_num_sections(mesh, 0))
        if count < 0:
            raise RuntimeError("get_num_sections returned %d" % count)
        for section_index in range(count):
            rows.append({
                "section": section_index,
                "material_slot": int(subsystem.get_lod_material_slot(mesh, 0, section_index)),
            })
        return rows, None
    except Exception as exc:
        return rows, error_row(exc)


def component_bones(component):
    try:
        count = int(component.get_num_bones())
        rows = []
        for index in range(count):
            name = str(component.get_bone_name(index))
            parent = str(component.get_parent_bone(name))
            rows.append({"index": index, "name": name, "parent": None if parent == "None" else parent})
        return {"count": count, "bones": rows}
    except Exception as exc:
        return error_row(exc)


def asset_registry_tags(asset):
    try:
        data = unreal.EditorAssetLibrary.find_asset_data(asset.get_path_name())
        tags = {str(key): str(value) for key, value in data.tags_and_values.items()}
        return tags
    except Exception as exc:
        return {"__error__": "%s: %s" % (type(exc).__name__, exc)}


def parse_triangle_value(raw):
    text = str(raw).strip()
    match = re.search(r"\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else None


def lod0_triangles(mesh):
    report = {"value": None, "source": None, "attempts": []}
    try:
        method = getattr(mesh, "get_num_triangles")
        value = int(method(0))
        report.update({"value": value, "source": "mesh.get_num_triangles(0)"})
        return report
    except Exception as exc:
        report["attempts"].append({"source": "mesh.get_num_triangles(0)", **error_row(exc)})

    tags = asset_registry_tags(mesh)
    relevant = {key: value for key, value in tags.items() if "tri" in key.lower()}
    report["triangle_asset_tags"] = relevant
    candidates = ("LOD0Triangles", "Triangles", "TriangleCount", "NumTriangles")
    for key in candidates:
        if key in tags:
            value = parse_triangle_value(tags[key])
            if value is not None:
                report.update({"value": value, "source": "asset_registry:%s" % key})
                return report
    for key, raw in relevant.items():
        value = parse_triangle_value(raw)
        if value is not None:
            report.update({"value": value, "source": "asset_registry:%s" % key})
            return report
    report["attempts"].append({"source": "asset_registry", "error": "no parseable triangle tag"})
    return report


def static_sections(mesh, slots):
    try:
        count = int(mesh.get_num_sections(0))
        count_source = "mesh.get_num_sections(0)"
    except Exception:
        count = len(slots)
        count_source = "material_slot_count_fallback"
    try:
        subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    except Exception:
        subsystem = None
    rows = []
    for section_index in range(count):
        row = {"section": section_index}
        material_slot = section_index
        if subsystem is not None:
            try:
                material_slot = int(subsystem.get_lod_material_slot(mesh, 0, section_index))
            except Exception as exc:
                row["material_slot_error"] = error_row(exc)
        row["material_slot"] = material_slot
        if 0 <= material_slot < len(slots):
            row["material_slot_name"] = slots[material_slot].get("material_slot_name")
            row["imported_material_slot_name"] = slots[material_slot].get("imported_material_slot_name")
            row["material"] = slots[material_slot].get("material")
        try:
            section = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, section_index)
            vertices = list(section[0])
            indices = list(section[1])
            row["vertices"] = len(vertices)
            row["triangles"] = len(indices) // 3
            if vertices:
                row["bounds_cm"] = {
                    "min": [min(float(v.x) for v in vertices), min(float(v.y) for v in vertices), min(float(v.z) for v in vertices)],
                    "max": [max(float(v.x) for v in vertices), max(float(v.y) for v in vertices), max(float(v.z) for v in vertices)],
                }
            else:
                row["bounds_cm"] = None
        except Exception as exc:
            row["geometry_error"] = error_row(exc)
        rows.append(row)
    return {"count": count, "count_source": count_source, "rows": rows}


def parameter_identity(info):
    name = str(info.get_editor_property("name"))
    try:
        association = str(info.get_editor_property("association"))
    except Exception:
        association = None
    try:
        index = int(info.get_editor_property("index"))
    except Exception:
        index = None
    return name, association, index


def color_row(value):
    return [float(value.r), float(value.g), float(value.b), float(value.a)]


def matching_material_parameters(material):
    chain = []
    current = material
    seen_paths = set()
    depth = 0
    while current is not None:
        current_path = path_of(current)
        if current_path in seen_paths:
            chain.append({"path": current_path, "cycle": True})
            break
        seen_paths.add(current_path)
        chain.append({"path": current_path, "class": str(current.get_class().get_name())})
        try:
            current = current.get_editor_property("parent")
        except Exception:
            current = None
        depth += 1
        if depth > 64:
            break

    effective = {}
    for depth, chain_row in enumerate(chain):
        source = unreal.load_asset(chain_row["path"])
        if source is None:
            chain_row["load_error"] = "load returned None"
            continue
        for kind, property_name in (("scalar", "scalar_parameter_values"), ("vector", "vector_parameter_values")):
            try:
                entries = list(source.get_editor_property(property_name))
            except Exception:
                continue
            for entry in entries:
                try:
                    name, association, index = parameter_identity(entry.get_editor_property("parameter_info"))
                    if not any(term in name.lower() for term in PARAMETER_TERMS):
                        continue
                    key = (kind, name, association, index)
                    if key in effective:
                        continue
                    value = entry.get_editor_property("parameter_value")
                    effective[key] = {
                        "type": kind,
                        "name": name,
                        "association": association,
                        "index": index,
                        "value": float(value) if kind == "scalar" else color_row(value),
                        "defined_on": chain_row["path"],
                        "source_depth": depth,
                    }
                except Exception as exc:
                    chain_row.setdefault("parameter_errors", []).append(error_row(exc))
    rows = sorted(effective.values(), key=lambda row: (row["type"], row["name"].lower(), str(row["association"]), row["index"] or -1))
    return {"instance": path_of(material), "parent_chain": chain, "matching_effective_serialized_parameters": rows}


def component_material_rows(component, mesh):
    materials = list(component.get_materials())
    slots, slots_error = material_slot_structs(mesh, "materials")
    rows = []
    for index, material in enumerate(materials):
        row = {"slot": index, "material": path_of(material)}
        if index < len(slots):
            row["material_slot_name"] = slots[index].get("material_slot_name")
            row["imported_material_slot_name"] = slots[index].get("imported_material_slot_name")
            row["asset_default_material"] = slots[index].get("material")
        rows.append(row)
    result = {"slots": rows}
    if slots_error:
        result["mesh_slots_error"] = slots_error
    return result


def inspect_cast_actor(actor, expected_class):
    actual_class = str(actor.get_class().get_name())
    row = {
        "label": actor.get_actor_label(),
        "class": actual_class,
        "expected_class": expected_class,
        "class_matches": actual_class == expected_class,
        "components": [],
        "skeletal_mesh_component_count": 0,
        "lod0_triangles_total": 0,
        "lod0_triangles_complete": True,
        "body_face_skin_material_instances": [],
    }
    skin_materials = {}
    for component in actor.get_components_by_class(unreal.ActorComponent):
        component_row = {"name": str(component.get_name()), "class": str(component.get_class().get_name())}
        if isinstance(component, unreal.SkeletalMeshComponent):
            row["skeletal_mesh_component_count"] += 1
            mesh = component.get_skeletal_mesh_asset()
            component_row["skeletal_mesh"] = path_of(mesh)
            if mesh is not None:
                component_row["materials"] = component_material_rows(component, mesh)
                triangles = lod0_triangles(mesh)
                component_row["lod0_triangles"] = triangles
                if triangles["value"] is None:
                    row["lod0_triangles_complete"] = False
                else:
                    row["lod0_triangles_total"] += int(triangles["value"])
                if "body" in component_row["name"].lower() or "face" in component_row["name"].lower():
                    for slot in component_row["materials"]["slots"]:
                        material_path = slot.get("material")
                        if material_path and material_path not in skin_materials:
                            material = unreal.load_asset(material_path)
                            if material is not None and "MaterialInstance" in str(material.get_class().get_name()):
                                skin_materials[material_path] = matching_material_parameters(material)
        row["components"].append(component_row)
    row["body_face_skin_material_instances"] = [skin_materials[key] for key in sorted(skin_materials)]
    return row


def inspect_pearl(actors):
    skeletal = unreal.load_asset(SKELETAL_PEARL)
    static = unreal.load_asset(STATIC_PEARL)
    if skeletal is None or not isinstance(skeletal, unreal.SkeletalMesh):
        raise RuntimeError("skeletal pearl mesh did not load as SkeletalMesh")
    if static is None or not isinstance(static, unreal.StaticMesh):
        raise RuntimeError("static pearl mesh did not load as StaticMesh")

    skeletal_slots, skeletal_slots_error = material_slot_structs(skeletal, "materials")
    skeletal_section_rows, skeletal_sections_error = skeletal_sections(skeletal)
    placed = []
    bone_source = None
    for actor in actors:
        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
            mesh = component.get_skeletal_mesh_asset()
            mesh_path = path_of(mesh)
            if mesh_path is not None and mesh_path.split(".", 1)[0] == SKELETAL_PEARL:
                placed.append({"actor": actor.get_actor_label(), "component": component.get_name()})
                if bone_source is None:
                    bone_source = component
    bones = component_bones(bone_source) if bone_source is not None else {"error": "no placed component uses target mesh"}
    bone_names = [entry["name"] for entry in bones.get("bones", [])]
    pearl_named_bones = [name for name in bone_names if "pearl" in name.lower()]

    static_slots, static_slots_error = material_slot_structs(static, "static_materials")
    report = {
        "skeletal_mesh": {
            "path": path_of(skeletal),
            "skeleton": path_of(skeletal.get_editor_property("skeleton")),
            "placed_components": placed,
            "bones": bones,
            "pearl_named_bones": pearl_named_bones,
            "vertex_weights": {
                "readable": False,
                "reason": "UE 5.8 reflected read-only Python API exposes bones/sections here, not imported per-vertex skin influences",
            },
            "material_slots": skeletal_slots,
            "lod0_sections": skeletal_section_rows,
        },
        "static_mesh": {
            "path": path_of(static),
            "material_slots": static_slots,
            "lod0_sections": static_sections(static, static_slots),
            "lod0_triangles": lod0_triangles(static),
        },
    }
    if skeletal_slots_error:
        report["skeletal_mesh"]["material_slots_error"] = skeletal_slots_error
    if skeletal_sections_error:
        report["skeletal_mesh"]["sections_error"] = skeletal_sections_error
    if static_slots_error:
        report["static_mesh"]["material_slots_error"] = static_slots_error
    report["independence_evidence"] = {
        "dedicated_pearl_bone_names": pearl_named_bones,
        "skeletal_section_count": len(skeletal_section_rows),
        "skeletal_material_slot_count": len(skeletal_slots),
        "static_section_count": report["static_mesh"]["lod0_sections"]["count"],
        "static_material_slot_count": len(static_slots),
    }
    return report


def emit(run, report):
    compact = json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    unreal.log("S3_CAST_PEARL_PROBE|run=%s|%s" % (run, compact))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    report = {"mode": "read_only", "run": run}
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world is not None else None
    report["world"] = world_path
    report["pie_or_sie_active"] = editor.get_game_world() is not None
    report["dirty_before"] = package_census()
    if world_path != EXPECTED_WORLD or report["pie_or_sie_active"] or any(report["dirty_before"].values()):
        report["fatal"] = "context guard failed"
        report["dirty_after"] = package_census()
        emit(run, report)
        raise RuntimeError("S3 cast/pearl probe context guard failed")

    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by_label = {}
    for actor in actors:
        by_label.setdefault(actor.get_actor_label(), []).append(actor)
    cast_rows = []
    for label, expected_class in CAST:
        matches = by_label.get(label, [])
        if len(matches) != 1:
            cast_rows.append({"label": label, "expected_class": expected_class, "match_count": len(matches), "error": "expected exactly one actor"})
        else:
            cast_rows.append(inspect_cast_actor(matches[0], expected_class))
    report["pearl"] = inspect_pearl(actors)
    report["cast"] = cast_rows
    report["dirty_after"] = package_census()
    report["ok"] = (
        all(not row.get("error") and row.get("class_matches") for row in cast_rows)
        and not any(report["dirty_after"].values())
    )
    emit(run, report)
    if any(report["dirty_after"].values()):
        raise RuntimeError("read-only probe dirtied packages: " + json.dumps(report["dirty_after"], sort_keys=True))


if __name__ == "__main__":
    main()
