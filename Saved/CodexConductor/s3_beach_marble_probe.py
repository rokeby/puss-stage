"""READ-ONLY Scene 3 beach asset, shot-camera, plinth, and wall probe.

No setters, saves, Sequencer evaluation, PIE controls, spawned actors, or
transient components. The dirty-package census must be byte-for-byte unchanged.
"""
import datetime
import json
import math
import os
import re

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
DOCK_YAW = 0.0
ACTOR_LABELS = (
    "Clam_Pedastal",
    "S3 Hangar Left Wall",
    "S3 Hangar Right Wall",
    "S3 Hangar Far Wall",
)


def project_file(*parts):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, *parts))


def path_of(value):
    if value is None:
        return None
    try:
        value = value.get_path_name()
    except Exception:
        pass
    return str(value).split(".", 1)[0]


def error_row(exc):
    return {"error_type": type(exc).__name__, "error": str(exc)}


def package_census():
    def names(packages):
        return sorted(str(package.get_path_name()).split(".", 1)[0] for package in packages)
    return {
        "dirty_maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def asset_registry_tags(asset):
    try:
        data = unreal.EditorAssetLibrary.find_asset_data(asset.get_path_name())
        return {str(key): str(value) for key, value in data.tags_and_values.items()}
    except Exception as exc:
        return {"__error__": "%s: %s" % (type(exc).__name__, exc)}


def parse_integer(raw):
    match = re.search(r"\d[\d,]*", str(raw))
    return int(match.group(0).replace(",", "")) if match else None


def lod0_triangles(mesh):
    report = {"value": None, "source": None, "attempts": []}
    try:
        value = int(mesh.get_num_triangles(0))
        report.update({"value": value, "source": "mesh.get_num_triangles(0)"})
        return report
    except Exception as exc:
        report["attempts"].append({"source": "mesh.get_num_triangles(0)", **error_row(exc)})
    tags = asset_registry_tags(mesh)
    relevant = {key: value for key, value in tags.items() if "tri" in key.lower()}
    report["triangle_asset_tags"] = relevant
    for key, raw in relevant.items():
        value = parse_integer(raw)
        if value is not None:
            report.update({"value": value, "source": "asset_registry:" + key})
            return report
    try:
        total = 0
        section_count = int(mesh.get_num_sections(0))
        for section_index in range(section_count):
            section = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, section_index)
            total += len(list(section[1])) // 3
        report.update({"value": total, "source": "ProceduralMeshLibrary LOD0 sections"})
    except Exception as exc:
        report["attempts"].append({"source": "ProceduralMeshLibrary", **error_row(exc)})
    return report


def nanite_report(mesh):
    report = {"enabled": None, "source": None, "attempts": []}
    try:
        settings = mesh.get_editor_property("nanite_settings")
        report["enabled"] = bool(settings.get_editor_property("enabled"))
        report["source"] = "StaticMesh.nanite_settings.enabled"
        return report
    except Exception as exc:
        report["attempts"].append({"source": "nanite_settings.enabled", **error_row(exc)})
    tags = asset_registry_tags(mesh)
    report["nanite_asset_tags"] = {key: value for key, value in tags.items() if "nanite" in key.lower()}
    for key, raw in report["nanite_asset_tags"].items():
        text = str(raw).strip().lower()
        if text in ("true", "false", "1", "0"):
            report["enabled"] = text in ("true", "1")
            report["source"] = "asset_registry:" + key
            break
    return report


def static_material_slots(mesh):
    rows = []
    try:
        slots = list(mesh.get_editor_property("static_materials"))
    except Exception as exc:
        return {"rows": [], "error": error_row(exc)}
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
    return {"rows": rows}


def bounds_row(mesh):
    try:
        box = mesh.get_bounding_box()
        return {"min_cm": [float(box.min.x), float(box.min.y), float(box.min.z)],
                "max_cm": [float(box.max.x), float(box.max.y), float(box.max.z)]}
    except Exception as exc:
        return error_row(exc)


def inspect_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        return {"path": asset_path, "exists": False}
    class_name = str(asset.get_class().get_name())
    row = {"path": path_of(asset), "exists": True, "class": class_name}
    if isinstance(asset, unreal.StaticMesh):
        row.update({"lod0_triangles": lod0_triangles(asset), "nanite": nanite_report(asset),
                    "material_slots": static_material_slots(asset), "bounds": bounds_row(asset)})
    if "MaterialInstance" in class_name:
        try:
            row["parent"] = path_of(asset.get_editor_property("parent"))
        except Exception as exc:
            row["parent_error"] = error_row(exc)
        for property_name in ("scalar_parameter_values", "vector_parameter_values", "texture_parameter_values"):
            try:
                row[property_name + "_count"] = len(list(asset.get_editor_property(property_name)))
            except Exception as exc:
                row[property_name + "_error"] = error_row(exc)
    return row


def actor_bounds(actor):
    origin, extent = actor.get_actor_bounds(False, True)
    return {"origin_cm": [float(origin.x), float(origin.y), float(origin.z)],
            "extent_cm": [float(extent.x), float(extent.y), float(extent.z)]}


def actor_report(actor):
    row = {"label": actor.get_actor_label(), "class": actor.get_class().get_name(),
           "object_path": actor.get_path_name(),
           "parent_label": actor.get_attach_parent_actor().get_actor_label() if actor.get_attach_parent_actor() else None,
           "bounds": actor_bounds(actor), "static_mesh_components": []}
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        mesh = component.get_editor_property("static_mesh")
        materials = [path_of(material) for material in component.get_materials()]
        row["static_mesh_components"].append({
            "name": component.get_name(), "mesh": path_of(mesh), "materials": materials,
            "mesh_slots": static_material_slots(mesh) if isinstance(mesh, unreal.StaticMesh) else None,
        })
    return row


def shot_camera_report(sequence):
    dock = unreal.Transform(location=unreal.Vector(*DOCK_ORIGIN),
                            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=DOCK_YAW))
    rows = []
    for binding in sequence.get_spawnables():
        label = str(binding.get_display_name())
        if not label.startswith("S3 Shot B"):
            continue
        template = binding.get_object_template()
        root = template.get_editor_property("root_component") if template is not None else None
        if template is None or root is None:
            rows.append({"label": label, "error": "missing template/root"})
            continue
        world = root.get_editor_property("relative_location")
        dock_location = unreal.MathLibrary.inverse_transform_location(dock, world)
        rows.append({"label": label, "world_cm": [float(world.x), float(world.y), float(world.z)],
                     "dock_cm": [float(dock_location.x), float(dock_location.y), float(dock_location.z)],
                     "tags": sorted(str(tag) for tag in template.get_editor_property("tags"))})
    return sorted(rows, key=lambda row: row["label"])


def inventory_paths():
    with open(project_file("Saved", "CodexConductor", "s3_beach_asset_inventory.json"),
              encoding="utf-8") as handle:
        inventory = json.load(handle)
    selected = inventory["selected_probe_candidates"]
    paths = []
    for key, value in selected.items():
        if isinstance(value, list):
            paths.extend(value)
        elif key == "plinth":
            paths.extend([value["mesh_path"], value["material_path"]])
    return sorted(set(paths))


def emit(run, report):
    unreal.log("S3_BEACH_MARBLE_PROBE|run=%s|%s" %
               (run, json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)))


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world is not None else None
    before = package_census()
    report = {"mode": "read_only", "run": run, "world": world_path,
              "pie_or_sie_active": editor.get_game_world() is not None, "dirty_before": before}
    if world_path != EXPECTED_WORLD:
        report["fatal"] = "wrong editor world"
        report["dirty_after"] = package_census()
        emit(run, report)
        raise RuntimeError("S3 beach/marble probe wrong world")
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    by_label = {}
    for actor in actors:
        by_label.setdefault(actor.get_actor_label(), []).append(actor)
    actor_rows = []
    for label in ACTOR_LABELS:
        matches = by_label.get(label, [])
        if len(matches) != 1:
            actor_rows.append({"label": label, "match_count": len(matches), "error": "expected exactly one"})
        else:
            actor_rows.append(actor_report(matches[0]))
    sequence = unreal.load_asset(ROOT_SEQUENCE)
    if not isinstance(sequence, unreal.LevelSequence):
        raise RuntimeError("LS_DevScene_03 failed to load")
    paths = inventory_paths()
    report["inventory_asset_count"] = len(paths)
    report["assets"] = [inspect_asset(path) for path in paths]
    report["actors"] = actor_rows
    report["shot_cameras"] = shot_camera_report(sequence)
    after = package_census()
    report["dirty_after"] = after
    report["census_unchanged"] = before == after
    report["ok"] = (before == after and all(not row.get("error") for row in actor_rows)
                    and all(row.get("exists") for row in report["assets"])
                    and len(report["shot_cameras"]) == 11)
    emit(run, report)
    if before != after:
        raise RuntimeError("read-only probe changed package census: before=%s after=%s" %
                           (json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True)))
    if not report["ok"]:
        raise RuntimeError("S3 beach/marble probe incomplete; inspect S3_BEACH_MARBLE_PROBE marker")


if __name__ == "__main__":
    main()
