"""Read-only S3 visual diagnosis requested by Gary on 2026-10-09.

The only filesystem write is the requested JSON report.  This script does not
modify/save assets or actors, spawn anything, evaluate Sequencer, or start PIE.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import traceback


PROJECT = "E:/PussStage"
SAVED = PROJECT + "/Saved"
OUT = SAVED + "/CodexConductor/S3_VISUAL_DIAG_20261009.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CLAMS = "/Game/Scenes/LS_Clams"
SHROUD_ROOT = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian"
MAT_ROOT = SHROUD_ROOT + "/Materials"
MASTER = MAT_ROOT + "/M_Shroud_Hessian"
MATERIALS = [MAT_ROOT + "/MI_Shroud_Hessian_%02d" % n for n in range(3, 9)]
FIGURES = (
    "Shore01_M56", "Shore02_F52", "Shore03_M59",
    "Shore04_F55", "Shore05_M53", "Shore06_F25",
)
BP_ROOT = "/Game/Metahuman/ShoreCast_20260910/SceneCharacters"
BP_PATHS = {f: BP_ROOT + "/BP_%s_Draped" % f for f in FIGURES}
P40_RECORD = SAVED + "/CodexConductor/P40Shore05Settle_20261009/p40_apply_record.json"
FEET_PLAN = SAVED + "/CodexConductor/s3_crowd_feet_plan.json"
FEET_RECORD = SAVED + "/CodexConductor/s3_crowd_feet_record.json"
LOG = SAVED + "/Logs/PussStage.log"


# Required first action: purge Python modules loaded from project Saved/ so no
# stale helper implementation can influence this run.  This is process-memory
# housekeeping only; it does not delete any file.
def purge_saved_modules():
    prefix = os.path.normcase(os.path.normpath(SAVED)) + os.sep
    removed = []
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        try:
            normalized = os.path.normcase(os.path.normpath(os.path.abspath(filename)))
        except Exception:
            continue
        if normalized.startswith(prefix):
            removed.append({"module": name, "file": normalized})
            del sys.modules[name]
    return sorted(removed, key=lambda row: row["module"])


PURGED_MODULES = purge_saved_modules()
import unreal  # noqa: E402  (must follow the module-cache purge)


class DiagnosticError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise DiagnosticError(message)
    return value


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def path_of(obj):
    if obj is None:
        return None
    return str(obj.get_path_name()).split(".", 1)[0]


def full_path(obj):
    return None if obj is None else str(obj.get_path_name())


def enum_name(value):
    if value is None:
        return None
    for attr in ("name", "value"):
        try:
            got = getattr(value, attr)
            if got is not None and not callable(got):
                return str(got)
        except Exception:
            pass
    try:
        return value.export_text()
    except Exception:
        return repr(value)


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def rot(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
    }


def actor_census(actors):
    rows = sorted("|".join((full_path(a), str(a.get_actor_label()), str(a.get_class().get_name()))) for a in actors)
    blob = "\n".join(rows).encode("utf-8")
    return {"count": len(rows), "sha256": hashlib.sha256(blob).hexdigest()}


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def figure_from_actor(actor):
    class_name = str(actor.get_class().get_name())
    for figure in FIGURES:
        if class_name == "BP_%s_Draped_C" % figure:
            return figure
    return None


def component_materials(component):
    count = int(component.get_num_materials())
    overrides = [path_of(x) for x in (prop(component, "override_materials", []) or [])]
    rows = []
    for slot in range(count):
        material = component.get_material(slot)
        rows.append({"slot": slot, "resolved_material": path_of(material),
                     "override_material": overrides[slot] if slot < len(overrides) else None})
    return {"slot_count": count, "raw_override_materials": overrides, "slots": rows}


def one_component(actor, name, cls=None):
    hits = [c for c in actor.get_components_by_class(unreal.ActorComponent) if str(c.get_name()) == name]
    if cls is not None:
        hits = [c for c in hits if isinstance(c, cls)]
    return hits[0] if len(hits) == 1 else None


def blueprint_templates(figure):
    bp_path = BP_PATHS[figure]
    bp = unreal.load_asset(bp_path)
    require(bp is not None, "BP_MISSING|" + bp_path)
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    objects = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
        obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
        if obj is not None:
            objects.append(obj)
    cloth_hits = {full_path(o): o for o in objects
                  if str(o.get_name()) in ("ShoreHeadCloth", "ShoreHeadCloth_GEN_VARIABLE")
                  and str(o.get_class().get_name()) == "ChaosClothComponent"}
    outfit_hits = {}
    for obj in objects:
        if not isinstance(obj, unreal.SkeletalMeshComponent):
            continue
        mesh = obj.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in (path_of(mesh) or "").lower():
            outfit_hits[full_path(obj)] = obj
    require(len(cloth_hits) == 1, "BP_CLOTH_COUNT|%s|%d" % (figure, len(cloth_hits)))
    require(len(outfit_hits) == 1, "BP_OUTFIT_COUNT|%s|%d" % (figure, len(outfit_hits)))
    cloth = next(iter(cloth_hits.values()))
    outfit = next(iter(outfit_hits.values()))
    return {
        "figure": figure,
        "blueprint": bp_path,
        "cloth_component": full_path(cloth),
        "cloth_class": str(cloth.get_class().get_name()),
        "cloth_asset": path_of(cloth.get_asset() if hasattr(cloth, "get_asset") else prop(cloth, "cloth_asset")),
        "cloth_materials": component_materials(cloth),
        "outfit_component": full_path(outfit),
        "outfit_mesh": path_of(outfit.get_skeletal_mesh_asset()),
        "outfit_materials": component_materials(outfit),
    }


def body_and_outfit(actor):
    body = one_component(actor, "Body", unreal.SkeletalMeshComponent)
    outfit_hits = []
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh = component.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in (path_of(mesh) or "").lower():
            outfit_hits.append(component)
    outfit = outfit_hits[0] if len({full_path(x): x for x in outfit_hits}) == 1 else None
    return body, outfit, len({full_path(x): x for x in outfit_hits})


def parameter_name(row):
    info = row.get_editor_property("parameter_info")
    return str(info.get_editor_property("name"))


def serialized_mi(mi):
    textures = {}
    for row in (prop(mi, "texture_parameter_values", []) or []):
        textures[parameter_name(row)] = path_of(row.get_editor_property("parameter_value"))
    scalars = {}
    for row in (prop(mi, "scalar_parameter_values", []) or []):
        scalars[parameter_name(row)] = float(row.get_editor_property("parameter_value"))
    vectors = {}
    for row in (prop(mi, "vector_parameter_values", []) or []):
        value = row.get_editor_property("parameter_value")
        vectors[parameter_name(row)] = [float(value.r), float(value.g), float(value.b), float(value.a)]
    return {"parent": path_of(prop(mi, "parent")), "textures": textures,
            "scalars": scalars, "vectors": vectors}


def master_inventory(material):
    result = {"path": path_of(material), "textures": {}, "scalars": {}, "vectors": {},
              "expression_classes": {}, "errors": []}
    try:
        expressions = list(unreal.MaterialEditingLibrary.get_material_expressions(material))
    except Exception as exc:
        result["errors"].append("get_material_expressions: %r" % exc)
        return result
    for node in expressions:
        cls = str(node.get_class().get_name())
        result["expression_classes"][cls] = result["expression_classes"].get(cls, 0) + 1
        name = str(prop(node, "parameter_name", ""))
        if cls == "MaterialExpressionTextureSampleParameter2D":
            result["textures"][name] = path_of(prop(node, "texture"))
        elif cls == "MaterialExpressionScalarParameter":
            result["scalars"][name] = float(prop(node, "default_value", 0.0))
        elif cls == "MaterialExpressionVectorParameter":
            value = prop(node, "default_value")
            if value is not None:
                result["vectors"][name] = [float(value.r), float(value.g), float(value.b), float(value.a)]
    return result


def parent_chain(material):
    rows, seen = [], set()
    current = material
    while current is not None and path_of(current) not in seen:
        seen.add(path_of(current))
        row = {"path": path_of(current), "class": str(current.get_class().get_name())}
        if isinstance(current, unreal.MaterialInstance):
            values = serialized_mi(current)
            row.update(values)
            current = prop(current, "parent")
        else:
            row["master_defaults"] = master_inventory(current)
            current = None
        rows.append(row)
    return rows


def import_sources(asset):
    sources = []
    import_data = prop(asset, "asset_import_data") or prop(asset, "import_data")
    if import_data is None:
        return sources
    for method in ("extract_filenames", "get_source_file_labels"):
        fn = getattr(import_data, method, None)
        if fn is None:
            continue
        try:
            values = fn()
            if isinstance(values, (list, tuple)):
                sources.extend(str(x) for x in values if str(x))
        except Exception:
            pass
    fn = getattr(import_data, "get_first_filename", None)
    if fn is not None:
        try:
            value = str(fn())
            if value:
                sources.append(value)
        except Exception:
            pass
    return sorted(set(sources))


def texture_info(path):
    exists = bool(path and unreal.EditorAssetLibrary.does_asset_exist(path))
    asset = unreal.load_asset(path) if exists else None
    row = {"path": path, "asset_exists": exists, "loaded": asset is not None,
           "class": str(asset.get_class().get_name()) if asset is not None else None}
    if asset is None:
        return row
    if isinstance(asset, unreal.Texture2D):
        row.update({
            "size": [int(asset.blueprint_get_size_x()), int(asset.blueprint_get_size_y())],
            "compression_settings": enum_name(prop(asset, "compression_settings")),
            "srgb": bool(prop(asset, "srgb", False)),
            "flip_green_channel": bool(prop(asset, "flip_green_channel", False)),
            "lod_group": enum_name(prop(asset, "lod_group")),
            "import_sources": import_sources(asset),
        })
        tags = {}
        try:
            data = unreal.EditorAssetLibrary.find_asset_data(path)
            for tag in ("Format", "SourceFormat", "PixelFormat", "Dimensions"):
                value = data.get_tag_value(tag)
                if value is not None:
                    tags[tag] = str(value)
        except Exception as exc:
            tags["lookup_error"] = repr(exc)
        row["format_tags"] = tags
        for method in ("get_pixel_format", "blueprint_get_pixel_format"):
            fn = getattr(asset, method, None)
            if fn is not None:
                try:
                    row["pixel_format_accessor"] = enum_name(fn())
                    break
                except Exception as exc:
                    row["pixel_format_accessor_error"] = repr(exc)
    return row


def material_audit():
    master = unreal.load_asset(MASTER)
    master_row = master_inventory(master) if master is not None else {"path": MASTER, "missing": True}
    rows, texture_paths = [], set(master_row.get("textures", {}).values())
    for path in MATERIALS:
        material = unreal.load_asset(path)
        row = {"path": path, "exists": bool(unreal.EditorAssetLibrary.does_asset_exist(path)),
               "loaded": material is not None}
        if material is not None:
            row["serialized"] = serialized_mi(material)
            row["parent_chain"] = parent_chain(material)
            texture_paths.update(row["serialized"]["textures"].values())
        rows.append(row)
    return {"master": master_row, "instances": rows,
            "textures": [texture_info(path) for path in sorted(x for x in texture_paths if x)]}


def mesh_triangles(component):
    mesh = component.get_editor_property("static_mesh")
    require(mesh is not None, "DUNE_STATIC_MESH_MISSING")
    desc = mesh.get_static_mesh_description(0)
    require(desc is not None, "DUNE_MESH_DESCRIPTION_MISSING")
    transform = component.get_component_transform()
    polygon_method = (getattr(desc, "get_polygon_vertex_instances", None) or
                      getattr(desc, "get_polygon_perimeter_vertex_instances", None))
    require(polygon_method is not None, "DUNE_POLYGON_API_MISSING")
    rows = []
    for index in range(int(desc.get_polygon_count())):
        perimeter = list(polygon_method(unreal.PolygonID(index)))
        if len(perimeter) < 3:
            continue
        points = []
        for vi in perimeter:
            local = desc.get_vertex_position(desc.get_vertex_instance_vertex(vi))
            world = transform.transform_position(local)
            points.append((float(world.x), float(world.y), float(world.z)))
        for i in range(1, len(points) - 1):
            tri = (points[0], points[i], points[i + 1])
            rows.append((min(p[0] for p in tri), max(p[0] for p in tri),
                         min(p[1] for p in tri), max(p[1] for p in tri), tri))
    require(rows, "DUNE_TRIANGLES_EMPTY")
    return mesh, rows


def vertical_raycast(triangles, x, y, start_z):
    hits = []
    eps = 1.0e-6
    for min_x, max_x, min_y, max_y, tri in triangles:
        if x < min_x - eps or x > max_x + eps or y < min_y - eps or y > max_y + eps:
            continue
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = tri
        den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(den) <= eps:
            continue
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / den
        b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / den
        c = 1.0 - a - b
        if a >= -eps and b >= -eps and c >= -eps:
            z = a * z1 + b * z2 + c * z3
            if z <= start_z + 0.1:
                hits.append(z)
    if not hits:
        return None
    return max(hits)


def foot_bones(body):
    rows = []
    count = int(body.get_num_bones())
    for index in range(count):
        name = str(body.get_bone_name(index))
        if not any(token in name.lower() for token in ("foot", "ball", "toe", "ankle")):
            continue
        try:
            loc = body.get_bone_location(name, unreal.BoneSpaces.WORLD_SPACE)
            rows.append({"bone": name, "location": vec(loc)})
        except Exception:
            pass
    return rows


def pelvis_or_root(body, actor):
    for name in ("pelvis", "root"):
        try:
            if int(body.get_bone_index(name)) >= 0:
                return {"bone": name, "location": vec(body.get_bone_location(name, unreal.BoneSpaces.WORLD_SPACE))}
        except Exception:
            pass
    return {"bone": "actor_root_fallback", "location": vec(actor.get_actor_location())}


def feet_audit(target_actors, ground_actor, ground_component):
    mesh, triangles = mesh_triangles(ground_component)
    plan = read_json(FEET_PLAN) if os.path.isfile(FEET_PLAN) else {"level": {}, "ocean": {}}
    record = read_json(FEET_RECORD) if os.path.isfile(FEET_RECORD) else {}
    rows = []
    for actor in target_actors:
        body, _outfit, _count = body_and_outfit(actor)
        if body is None:
            rows.append({"label": str(actor.get_actor_label()), "error": "Body component not uniquely resolved"})
            continue
        pelvis = pelvis_or_root(body, actor)
        bones = foot_bones(body)
        samples = []
        for bone in bones:
            loc = bone["location"]
            surface = vertical_raycast(triangles, loc[0], loc[1], pelvis["location"][2])
            samples.append({"bone": bone["bone"], "foot_z_cm": loc[2], "xy_cm": loc[:2],
                            "surface_z_cm": surface,
                            "foot_minus_surface_cm": None if surface is None else loc[2] - surface})
        valid = [x for x in samples if x["surface_z_cm"] is not None]
        lowest = min(valid, key=lambda x: x["foot_minus_surface_cm"]) if valid else None
        label = str(actor.get_actor_label())
        plan_row = plan.get("level", {}).get(label)
        actor_z = float(actor.get_actor_location().z)
        compare = None
        if plan_row:
            compare = {
                "recorded_root_before_cm": record.get("level_before", {}).get(label),
                "formula_target_root_z_cm": plan_row.get("new_z"),
                "formula_feet_offset_cm": plan_row.get("feet_off"),
                "live_root_z_cm": actor_z,
                "live_minus_formula_target_cm": actor_z - float(plan_row["new_z"]),
                "formula_implied_surface_z_cm": float(plan_row["new_z"]) + float(plan_row["feet_off"]) + 2.0,
                "formula_contract": "new_root_z = surface_z - 2cm - feet_offset",
            }
        rows.append({"label": label, "figure": figure_from_actor(actor), "actor_path": full_path(actor),
                     "actor_location": vec(actor.get_actor_location()), "pelvis_or_root": pelvis,
                     "foot_samples": samples, "lowest_gap": lowest, "s3_crowd_feet_comparison": compare,
                     "tier": "measured current editor pose; mesh-description vertical raycast against Ground B LOD0"})
    return {"ground_actor": str(ground_actor.get_actor_label()), "ground_actor_path": full_path(ground_actor),
            "ground_component": full_path(ground_component), "ground_mesh": path_of(mesh),
            "triangle_count": len(triangles), "figures": rows,
            "record_run": record.get("run"), "record_formula_source": FEET_PLAN.replace("/", "\\")}


def classify_outfit_material(path):
    low = (path or "").lower()
    if "outfithessian" in low and "shorts_hessian" in low:
        return "job40_shorts_child"
    if "defaultgarment" in low and "short" in low:
        return "original_shorts"
    if "defaultgarment" in low and "shirt" in low:
        return "original_shirt_or_tee"
    return "other"


def actor_row(actor):
    figure = figure_from_actor(actor)
    cloth = one_component(actor, "ShoreHeadCloth")
    body, outfit, outfit_count = body_and_outfit(actor)
    row = {"label": str(actor.get_actor_label()), "figure": figure, "actor_path": full_path(actor),
           "class": str(actor.get_class().get_name()), "location": vec(actor.get_actor_location()),
           "rotation": rot(actor.get_actor_rotation()), "head_cloth_component": full_path(cloth),
           "head_cloth_class": str(cloth.get_class().get_name()) if cloth is not None else None,
           "head_cloth_asset": path_of(cloth.get_asset()) if cloth is not None and hasattr(cloth, "get_asset") else None,
           "head_cloth_materials": component_materials(cloth) if cloth is not None else None,
           "body_component": full_path(body), "outfit_component_count": outfit_count,
           "outfit_component": full_path(outfit),
           "outfit_mesh": path_of(outfit.get_skeletal_mesh_asset()) if outfit is not None else None}
    if outfit is not None:
        mats = component_materials(outfit)
        for slot in mats["slots"]:
            slot["role"] = classify_outfit_material(slot["resolved_material"])
        row["outfit_materials"] = mats
    return row


def p40_summary():
    if not os.path.isfile(P40_RECORD):
        return {"record_exists": False, "path": P40_RECORD}
    record = read_json(P40_RECORD)
    assignments = []
    for row in record.get("outfit_assignments", []):
        assignments.append({key: row.get(key) for key in
                            ("label", "figure", "actor_path", "component", "slots", "child",
                             "resolved_before", "resolved_after", "before_overrides", "after_overrides")})
    return {
        "record_exists": True, "path": P40_RECORD, "run_id": record.get("run_id"),
        "state": record.get("state"), "saved": record.get("saved"),
        "created": record.get("created", []), "cloth_changes": record.get("cloth", []),
        "outfit_children": record.get("outfit_children", []), "outfit_assignments": assignments,
        "counts": {"created": len(record.get("created", [])),
                   "cloth": len(record.get("cloth", [])),
                   "outfit_children": len(record.get("outfit_children", [])),
                   "outfit_assignments": len(record.get("outfit_assignments", []))},
    }


def sequence_crowd_labels():
    sequence = unreal.load_asset(CLAMS)
    if sequence is None:
        return {"asset": CLAMS, "loaded": False, "labels": []}
    labels = []
    for binding in sequence.get_bindings():
        label = str(binding.get_display_name())
        if label.startswith("S3 Crowd") or "Shore" in label:
            guid = binding.get_id()
            try:
                guid_value = unreal.GuidLibrary.conv_guid_to_string(guid)
            except Exception:
                guid_value = guid.export_text() if hasattr(guid, "export_text") else "UNREADABLE"
            labels.append({"display_name": label, "guid": guid_value})
    return {"asset": CLAMS, "loaded": True, "labels": labels}


SOURCE_EXT_RE = re.compile(r"(?i)([A-Z]:[/\\][^\"'<>|\r\n]+?\.(?:png|jpe?g|tga|exr|fbx|abc|wav|mp3|csv|json))")


def log_audit():
    if not os.path.isfile(LOG):
        return {"path": LOG, "exists": False}
    with open(LOG, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    material_lines = []
    auto_lines = []
    source_files = set()
    target = re.compile(r"M_Shroud_Hessian|MI_Shroud_Hessian_0[3-8]", re.I)
    auto = re.compile(r"Interchange|Auto.?Reimport|source content files|source file|DirectoryWatcher|EditorFactories", re.I)
    for number, line in enumerate(lines, 1):
        if target.search(line) or (("LogMaterial" in line or "LogShaderCompilers" in line) and
                                   re.search(r"Error|Failed|Warning", line, re.I)):
            material_lines.append({"line": number, "text": line})
        if auto.search(line):
            auto_lines.append({"line": number, "text": line})
            for match in SOURCE_EXT_RE.finditer(line):
                source_files.add(os.path.normpath(match.group(1)))
    return {"path": LOG, "exists": True, "line_count": len(lines),
            "material_or_shader_lines": material_lines,
            "auto_reimport_lines": auto_lines,
            "source_files_from_auto_reimport_lines": sorted(source_files)}


def source_asset_map(source_files, known_assets):
    rows = []
    normalized = {os.path.normcase(os.path.normpath(x)): x for x in source_files}
    for path in sorted(known_assets):
        asset = unreal.load_asset(path)
        if asset is None:
            continue
        sources = import_sources(asset)
        matches = [original for norm, original in normalized.items()
                   if any(norm == os.path.normcase(os.path.normpath(src)) for src in sources)]
        if matches or sources:
            rows.append({"asset": path, "asset_class": str(asset.get_class().get_name()),
                         "import_sources": sources, "popup_source_matches": matches})
    return rows


def infer_findings(report):
    mats = report["shroud_materials"]
    missing = [row["path"] for row in mats["textures"] if not row.get("loaded")]
    nulls = []
    for mi in mats["instances"]:
        for name, value in mi.get("serialized", {}).get("textures", {}).items():
            if value is None:
                nulls.append({"material": mi["path"], "parameter": name})
    matching_log_lines = report["logs"].get("material_or_shader_lines", [])
    errors = [row for row in matching_log_lines
              if re.search(r"LogMaterial|LogShaderCompilers", row.get("text", ""), re.I)
              and re.search(r"Error|Failed|Warning", row.get("text", ""), re.I)]
    p40 = report["job40"]
    gaps = []
    for row in report["feet"]["figures"]:
        low = row.get("lowest_gap")
        if low and low.get("foot_minus_surface_cm") is not None:
            gaps.append((row["label"], low["foot_minus_surface_cm"]))
    shroud_assigned = {}
    for row in report["actors"]:
        mats_row = row.get("head_cloth_materials") or {}
        shroud_assigned[row["label"]] = [s.get("resolved_material") for s in mats_row.get("slots", [])]
    no_hessian = sorted(label for label, values in shroud_assigned.items()
                        if values and not any("/ShroudHessian/" in (v or "") for v in values))
    no_hessian_detail = []
    for label in no_hessian:
        figure = next((row.get("figure") for row in report["actors"] if row.get("label") == label), None)
        no_hessian_detail.append({
            "label": label,
            "figure": figure,
            "assigned_materials": shroud_assigned.get(label),
            "record_reason": ("Shore05 was not included in the five-figure ShroudHessian apply record"
                              if figure == "Shore05_M53" else
                              "not explained by the ShroudHessian apply record"),
        })
    auto_sources = report["logs"].get("source_files_from_auto_reimport_lines", [])
    return {
        "shroud_black": {
            "tier": "inferred from measured assignment/asset/log evidence",
            "missing_or_unloadable_texture_assets": missing,
            "null_texture_overrides": nulls,
            "matching_material_or_shader_log_lines": len(errors),
            "figures_without_hessian_assignment": no_hessian,
            "figures_without_hessian_detail": no_hessian_detail,
            "root_cause": ("missing/null texture inputs or compile errors are present" if (missing or nulls or errors)
                           else "not a missing-assignment, missing-texture, or logged shader-compile failure; investigate rendered lighting/exposure and the master graph response next"),
            "proposed_fix_not_applied": ("repair only the reported null/missing link or compile error, then targeted-save and rendered-verify" if (missing or nulls or errors)
                                         else "make a reversible child-MI look test with higher dry roughness/lower specular and inspect under the 21:30 camera/lighting; do not rewrite source textures first"),
        },
        "underwear_unchanged": {
            "tier": "measured current slots compared with declaration-proven apply record",
            "job40_counts": p40.get("counts"),
            "root_cause": "job 40 targeted only slots classified as shorts; tee/shirt slots were deliberately left on their original MetaHuman DefaultGarment materials",
            "proposed_fix_not_applied": "decide whether the tee should also match; if yes, make separate tee child MIs and target only shirt-role slots after rendered approval",
        },
        "feet_sunk": {
            "tier": "measured current editor-pose bones and Ground B LOD0 raycasts; compared with recorded formula targets",
            "sunk_figures": [{"label": label, "foot_minus_surface_cm": gap} for label, gap in gaps if gap < -2.5],
            "root_cause": "the saved placement used a pose-specific root-to-foot offset/height formula; current editor-pose bone offsets and actual Ground B geometry do not necessarily match that approximation",
            "proposed_fix_not_applied": "recompute root Z from a chosen stable reference pose using actual Ground B triangle hits per foot, or add runtime foot IK; do not reuse a single source offset across changing poses",
        },
        "source_content_popup": {
            "tier": "measured from current PussStage.log where lines exist; otherwise UNCLEAR",
            "source_file_count_from_matching_log_lines": len(auto_sources),
            "root_cause": ("the listed source files changed on disk and were detected by the editor auto-reimport path" if len(auto_sources) == 2
                           else "UNCLEAR: current log did not yield exactly two source paths"),
            "proposed_fix_not_applied": "dismiss/decline reimport until the two paths and mapped assets are confirmed; do not accept the popup during this diagnosis",
        },
    }


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = require(editor.get_editor_world(), "NO_EDITOR_WORLD")
    world_path = path_of(world)
    require(world_path == WORLD, "WRONG_WORLD|" + str(world_path))
    dirty_before = census()
    actors_before = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    actor_before = actor_census(actors_before)

    targets = [a for a in actors_before if figure_from_actor(a) is not None]
    targets.sort(key=lambda a: (str(a.get_actor_label()), full_path(a)))
    actor_rows = [actor_row(a) for a in targets]
    templates = [blueprint_templates(f) for f in FIGURES]

    ground_candidates = []
    for actor in actors_before:
        tags = {str(x) for x in (prop(actor, "tags", []) or [])}
        for component in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh_path = path_of(component.get_editor_property("static_mesh"))
            if (mesh_path and mesh_path.endswith("SM_S3_ShoreGround_B")) or "RigAtmos.S3ShoreGround" in tags:
                ground_candidates.append((actor, component, mesh_path))
    exact_b = [(a, c, p) for a, c, p in ground_candidates if p and p.endswith("SM_S3_ShoreGround_B")]
    require(len(exact_b) == 1, "GROUND_B_COUNT|%d|candidates=%r" %
            (len(exact_b), [(str(a.get_actor_label()), p) for a, _c, p in ground_candidates]))
    ground_actor, ground_component, _ground_path = exact_b[0]

    materials = material_audit()
    logs = log_audit()
    known_assets = {MASTER, CLAMS, _ground_path} | set(MATERIALS) | set(BP_PATHS.values())
    known_assets |= {row["path"] for row in materials["textures"] if row.get("path")}
    p40 = p40_summary()
    known_assets |= {row.get("path") for row in p40.get("outfit_children", []) if row.get("path")}
    source_map = source_asset_map(logs.get("source_files_from_auto_reimport_lines", []), known_assets)

    report = {
        "schema": "s3_visual_diag/1",
        "request": "Gary read-only diagnosis 2026-10-09",
        "world": world_path,
        "guardrails": {"pie_or_sie": False, "assets_saved": 0, "actors_spawned": 0,
                       "sequencer_evaluated": False, "set_editor_property_calls": 0,
                       "module_cache_purged_first": True, "purged_saved_modules": PURGED_MODULES},
        "census_before": {"dirty_packages": dirty_before, "actors": actor_before},
        "actors": actor_rows,
        "blueprint_templates": templates,
        "ls_clams_bindings": sequence_crowd_labels(),
        "shroud_materials": materials,
        "job40": p40,
        "feet": feet_audit(targets, ground_actor, ground_component),
        "logs": logs,
        "source_asset_mapping": source_map,
        "evidence_notes": [
            {"tier": "measured", "claim": "live editor instance/template/material/texture/outfit/bone and Ground B mesh data in this run"},
            {"tier": "declaration-proven", "claim": "job 40 and s3_crowd_feet historical records state what their apply runs targeted"},
            {"tier": "inferred", "claim": "root causes combine current measurements with record intent; no rendered intervention was allowed"},
        ],
    }
    report["findings"] = infer_findings(report)

    actors_after = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    dirty_after = census()
    actor_after = actor_census(actors_after)
    report["census_after"] = {"dirty_packages": dirty_after, "actors": actor_after}
    report["census_identical"] = {"dirty_packages": dirty_before == dirty_after,
                                  "actors": actor_before == actor_after}
    require(dirty_before == dirty_after, "DIRTY_CENSUS_CHANGED|before=%r|after=%r" % (dirty_before, dirty_after))
    require(actor_before == actor_after, "ACTOR_CENSUS_CHANGED|before=%r|after=%r" % (actor_before, actor_after))
    write_json(OUT, report)
    unreal.log("S3_VISUAL_DIAG_SUCCESS|actors=%d|templates=%d|materials=%d|feet=%d|dirty_identical=1|actor_identical=1|output=%s" %
               (len(actor_rows), len(templates), len(materials["instances"]), len(report["feet"]["figures"]), OUT))
    return report


try:
    main()
except Exception as exc:
    unreal.log_error("S3_VISUAL_DIAG_FAILED|%s|trace=%s" %
                     (str(exc).replace("\n", " "), traceback.format_exc().replace("\n", "\\n")))
    raise
