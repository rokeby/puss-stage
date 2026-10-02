"""Flat V3 Slot A: import and save only fully gated new passage assets."""
import hashlib
import importlib.util
import json
import math
import os
import traceback

import unreal


RUN = "FV3A-20261002-02"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TARGETS = {
    "P01": "/Game/Scenes/Wings/FlatV3/Passage01",
    "P04": "/Game/Scenes/Wings/FlatV3/Passage04",
    "P05": "/Game/Scenes/Wings/FlatV3/Passage05",
}
EXPECTED_COUNTS = {"P01": 6, "P04": 8, "P05": 21}
PARENTS = {
    "Front": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Front",
    "Flap": "/Game/Scenes/Wings/PaintedSurface/Billboard/MI_Billboard_Flap",
    "Timber": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master",
    "Edge": "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master",
}
SLOTS = ("Front", "Flap", "Timber", "Edge")
COMMON_AGED = (
    "T_FlatV3_AgedSoftwood_Color",
    "T_FlatV3_AgedSoftwood_Roughness",
    "T_FlatV3_AgedSoftwood_NormalDX",
    "T_FlatV3_AgedPlywood_Roughness",
    "T_FlatV3_AgedPlywood_NormalDX",
    "T_FlatV3_AgedSteel_Color",
)


PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_dir()))
SAVED = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexFlatV3"))
SOURCE_ROOTS = (
    os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Overnight", "flats"),
    os.path.join(PROJECT, "DerivedAssets", "FlatV3", "Overnight", "Kept", "flats"),
)


def load_pilot_module():
    path = os.path.join(SAVED, "phase1_import.py")
    spec = importlib.util.spec_from_file_location("flatv3_pilot_reuse", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot = load_pilot_module()


def census():
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(name, value):
    path = os.path.join(SAVED, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_context_clean():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_path = world.get_outermost().get_name() if world else None
    if world_path != WORLD:
        raise RuntimeError("WRONG_WORLD|world=%s" % world_path)
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    current = census()
    if current != {"maps": [], "content": []}:
        raise RuntimeError("DIRTY_AT_IMPORT_START|census=" + json.dumps(current, sort_keys=True))


def built_source_inventory():
    result = []
    excluded = []
    for source_root in SOURCE_ROOTS:
        is_kept = os.path.basename(os.path.dirname(source_root)).lower() == "kept"
        for folder_name in sorted(os.listdir(source_root)):
            folder = os.path.join(source_root, folder_name)
            status_path = os.path.join(folder, "status.json")
            if not os.path.isdir(folder) or not os.path.isfile(status_path):
                continue
            status = load_json(status_path)
            passage = status.get("passage")
            in_scope = ((not is_kept and passage in ("P04", "P05") and
                         not folder_name.startswith("S3_")) or
                        (is_kept and passage in ("P01", "P05")))
            if not in_scope:
                continue
            if status.get("status") != "built":
                excluded.append({
                    "folder": folder,
                    "passage": passage,
                    "status": status.get("status"),
                    "reason": status.get("reason"),
                })
                continue
            mesh_name = str(status["asset_name"])
            owner = str(status["asset_suffix"])
            validation_path = os.path.join(folder, "validation.json")
            socket_path = os.path.join(folder, "sockets_" + mesh_name + ".json")
            mi_path = os.path.join(folder, "skin", owner + "_mi_params.json")
            sources = {
                "mesh": os.path.join(folder, mesh_name + ".fbx"),
                "socket": socket_path,
                "validation": validation_path,
                "mi_params": mi_path,
                "SkinColor": os.path.join(folder, "skin", "T_%s_SkinColor.png" % owner),
                "SkinMask": os.path.join(folder, "skin", "T_%s_SkinMask.png" % owner),
                "SkinNormal": os.path.join(folder, "skin", "T_%s_SkinNormal.png" % owner),
                "AgedStencil": os.path.join(folder, "aged", "T_FlatV3_AgedPlywood_Stencil_Color.png"),
            }
            for name in COMMON_AGED:
                sources[name] = os.path.join(folder, "aged", name + ".png")
            missing = sorted(path for path in sources.values() if not os.path.isfile(path))
            validation = load_json(validation_path) if os.path.isfile(validation_path) else {}
            if (missing or not bool(status.get("validation_pass")) or
                    not bool(validation.get("pass"))):
                raise RuntimeError("BUILT_SOURCE_CONTRACT_FAIL|folder=%s|missing=%s|status_validation=%s|validation=%s" %
                                   (folder, json.dumps(missing), status.get("validation_pass"),
                                    validation.get("pass")))
            target = TARGETS[passage]
            destinations = {
                "mesh": target + "/StaticMeshes/" + mesh_name,
                "SkinColor": target + "/Textures/%s/T_%s_SkinColor" % (owner, owner),
                "SkinMask": target + "/Textures/%s/T_%s_SkinMask" % (owner, owner),
                "SkinNormal": target + "/Textures/%s/T_%s_SkinNormal" % (owner, owner),
                "AgedStencil": target + "/Textures/Aged/%s/T_%s_AgedPlywood_Stencil_Color" %
                                (owner, owner),
                "Front": target + "/Materials/Instances/MI_FlatV3_%s_Front" % owner,
                "Flap": target + "/Materials/Instances/MI_FlatV3_%s_Flap" % owner,
            }
            result.append({
                "passage": passage,
                "folder": folder,
                "owner": owner,
                "mesh_name": mesh_name,
                "side": str(status.get("build_side")),
                "mount": str(status.get("mount")),
                "baked_poles": bool(status.get("baked_poles")),
                "sources": sources,
                "destinations": destinations,
                "validation": validation,
            })
    actual_counts = {passage: sum(1 for row in result if row["passage"] == passage)
                     for passage in TARGETS}
    if actual_counts != EXPECTED_COUNTS:
        raise RuntimeError("SOURCE_COUNT_FAIL|expected=%s|actual=%s" %
                           (json.dumps(EXPECTED_COUNTS, sort_keys=True),
                            json.dumps(actual_counts, sort_keys=True)))
    return result, excluded


def common_inventory(assets):
    result = {}
    hashes = {}
    for passage in sorted(TARGETS):
        rows = [row for row in assets if row["passage"] == passage]
        result[passage] = {}
        hashes[passage] = {}
        for name in COMMON_AGED:
            values = {sha256_file(row["sources"][name]): row["sources"][name] for row in rows}
            hashes[passage][name] = sorted(values)
            if len(values) != 1:
                raise RuntimeError("COMMON_AGED_HASH_MISMATCH|passage=%s|name=%s|hashes=%s" %
                                   (passage, name, json.dumps(sorted(values))))
            source = rows[0]["sources"][name]
            result[passage][name] = {
                "source": source,
                "destination": TARGETS[passage] + "/Textures/Aged/Common/" + name,
            }
    return result, hashes


def all_planned_paths(assets, common):
    paths = []
    for row in assets:
        paths.extend(row["destinations"].values())
    for passage in common.values():
        paths.extend(value["destination"] for value in passage.values())
    if len(paths) != len(set(paths)):
        raise RuntimeError("DUPLICATE_DESTINATION_PATH")
    return sorted(paths)


def destination_state(assets, common):
    existing_assets = set()
    existing_common = set()
    for row in assets:
        paths = asset_paths(row)
        existing = [path for path in paths
                    if unreal.EditorAssetLibrary.does_asset_exist(path)]
        if existing and len(existing) != len(paths):
            raise RuntimeError("PARTIAL_EXISTING_ASSET|owner=%s|paths=%s" %
                               (row["owner"], json.dumps(existing)))
        if len(existing) == len(paths):
            existing_assets.add(row["owner"])
    for passage in common:
        paths = [common[passage][name]["destination"] for name in COMMON_AGED]
        existing = [path for path in paths
                    if unreal.EditorAssetLibrary.does_asset_exist(path)]
        if existing and len(existing) != len(paths):
            raise RuntimeError("PARTIAL_EXISTING_COMMON|passage=%s|paths=%s" %
                               (passage, json.dumps(existing)))
        if len(existing) == len(paths):
            existing_common.add(passage)
    missing_parents = sorted(path for path in set(PARENTS.values())
                             if not unreal.EditorAssetLibrary.does_asset_exist(path))
    if missing_parents:
        raise RuntimeError("MISSING_PARENTS|paths=" + json.dumps(missing_parents))
    return existing_assets, existing_common


def import_one(source, destination, options=None):
    task = pilot.import_task(source, destination, options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(destination)
    if asset is None:
        raise RuntimeError("IMPORT_FAILED|destination=" + destination)
    return asset


def socket_payload(path, expected_asset):
    payload = load_json(path)
    expected_contract = {
        "ue_rotator_order": "roll-pitch-yaw",
        "hinge_local_x_axis": "base-edge Y; either sign is the same hinge line",
        "pivot_local_x_axis": "+Z",
        "fbx_interchange_y_reflected": True,
    }
    if (payload.get("schema_version") != 1 or payload.get("asset") != expected_asset or
            payload.get("coordinate_space") != "Unreal static-mesh local" or
            payload.get("location_units") != "cm" or
            payload.get("rotation_units") != "degrees" or
            payload.get("rotation_order") != "roll-pitch-yaw" or
            payload.get("contract") != expected_contract):
        raise RuntimeError("SOCKET_JSON_HEADER_FAIL|path=" + path)
    rows = payload.get("sockets")
    if not isinstance(rows, list):
        raise RuntimeError("SOCKET_JSON_ROWS_FAIL|path=" + path)
    by_name = {}
    for row in rows:
        name = str(row.get("name", ""))
        location = row.get("relative_location_cm")
        rotation = row.get("relative_rotation_deg")
        if (name in by_name or not isinstance(location, list) or len(location) != 3 or
                not isinstance(rotation, dict) or sorted(rotation) != ["pitch", "roll", "yaw"]):
            raise RuntimeError("SOCKET_JSON_RECORD_FAIL|path=%s|record=%s" %
                               (path, json.dumps(row, sort_keys=True)))
        by_name[name] = row
    return by_name


def verify_socket_rows(mesh, by_name):
    report = pilot.socket_report(mesh)
    if sorted(report) != sorted(by_name):
        raise RuntimeError("SOCKET_NAMES_FAIL|mesh=%s|actual=%s|expected=%s" %
                           (mesh.get_path_name(), sorted(report), sorted(by_name)))
    for name, row in by_name.items():
        if mesh.find_socket(name) is None:
            raise RuntimeError("SOCKET_FIND_FAIL|mesh=%s|socket=%s" %
                               (mesh.get_path_name(), name))
        actual = report[name]
        expected_location = [float(value) for value in row["relative_location_cm"]]
        expected_rotation = row["relative_rotation_deg"]
        if any(abs(a - b) > 0.01 for a, b in
               zip(actual["location_cm"], expected_location)):
            raise RuntimeError("SOCKET_LOCATION_FAIL|mesh=%s|socket=%s|actual=%s|expected=%s" %
                               (mesh.get_path_name(), name, actual["location_cm"],
                                expected_location))
        for index, axis in enumerate(("roll", "pitch", "yaw")):
            if pilot.rotation_delta_degrees(actual["rotation_deg"][index],
                                             expected_rotation[axis]) > 0.01:
                raise RuntimeError("SOCKET_ROTATION_FAIL|mesh=%s|socket=%s|actual=%s|expected=%s" %
                                   (mesh.get_path_name(), name,
                                    actual["rotation_deg"], expected_rotation))
    return report


def apply_sockets(mesh, row):
    by_name = socket_payload(row["sources"]["socket"], row["mesh_name"])
    names = set(by_name)
    pole_names = sorted(name for name in names if name.startswith("SOCKET_Pole_"))
    if row["baked_poles"]:
        if not {"SOCKET_Hinge", "SOCKET_Pivot"}.issubset(names) or not pole_names:
            raise RuntimeError("WING_SOCKET_CONTRACT_FAIL|mesh=%s|sockets=%s" %
                               (row["mesh_name"], sorted(names)))
        if names != set(("SOCKET_Hinge", "SOCKET_Pivot") + tuple(pole_names)):
            raise RuntimeError("WING_SOCKET_UNEXPECTED_NAME|mesh=%s|sockets=%s" %
                               (row["mesh_name"], sorted(names)))
    elif names:
        raise RuntimeError("TOP_SOCKET_CONTRACT_FAIL|mesh=%s|sockets=%s" %
                           (row["mesh_name"], sorted(names)))
    existing = pilot.socket_report(mesh)
    if existing:
        raise RuntimeError("UNEXPECTED_IMPORTED_SOCKETS|mesh=%s|sockets=%s" %
                           (mesh.get_path_name(), sorted(existing)))
    mesh.modify()
    for name in sorted(by_name):
        data = by_name[name]
        socket = unreal.StaticMeshSocket(outer=mesh)
        socket.set_editor_property("socket_name", name)
        socket.set_editor_property("relative_location", unreal.Vector(
            *[float(value) for value in data["relative_location_cm"]]))
        rotation = data["relative_rotation_deg"]
        socket.set_editor_property("relative_rotation", unreal.Rotator(
            roll=float(rotation["roll"]), pitch=float(rotation["pitch"]),
            yaw=float(rotation["yaw"])))
        mesh.add_socket(socket)
    return verify_socket_rows(mesh, by_name), by_name


def expected_import_bounds(validation):
    bounds = validation["bounds_m"]
    return (
        [bounds["min"][0] * 100.0, -bounds["max"][1] * 100.0,
         bounds["min"][2] * 100.0],
        [bounds["max"][0] * 100.0, -bounds["min"][1] * 100.0,
         bounds["max"][2] * 100.0],
    )


def verify_top(mesh, row):
    validation = row["validation"]
    slots = [str(value.get_editor_property("material_slot_name"))
             for value in mesh.get_editor_property("static_materials")]
    if slots != list(SLOTS):
        raise RuntimeError("SLOT_ORDER_FAIL|mesh=%s|slots=%s" %
                           (mesh.get_path_name(), slots))
    lod_count = int(mesh.get_num_lods())
    if lod_count != 2:
        raise RuntimeError("LOD_COUNT_FAIL|mesh=%s|lods=%d" %
                           (mesh.get_path_name(), lod_count))
    expected_min, expected_max = expected_import_bounds(validation)
    box = mesh.get_bounding_box()
    actual_min = [float(box.min.x), float(box.min.y), float(box.min.z)]
    actual_max = [float(box.max.x), float(box.max.y), float(box.max.z)]
    if any(abs(a - b) > 1.5 for a, b in
           zip(actual_min + actual_max, expected_min + expected_max)):
        raise RuntimeError("BOUNDS_MISMATCH|mesh=%s|actual=%s|expected=%s" %
                           (mesh.get_path_name(), [actual_min, actual_max],
                            [expected_min, expected_max]))
    sections = {}
    for lod in (0, 1):
        _, by_slot = pilot.lod_section_slots(mesh, lod)
        front = pilot.section_uv0(mesh, lod, by_slot[0]) if 0 in by_slot else None
        flap = pilot.section_uv0(mesh, lod, by_slot[1]) if 1 in by_slot else None
        if front is None or front["du_dY"] <= 0.0 or front["dv_dZ"] >= 0.0:
            raise RuntimeError("FRONT_UV0_SIGN_FAIL|mesh=%s|lod=%d|data=%s" %
                               (mesh.get_path_name(), lod,
                                json.dumps(front, sort_keys=True)))
        if (front["normal"][0] > -0.99 or abs(front["normal"][1]) > 0.02 or
                abs(front["normal"][2]) > 0.02):
            raise RuntimeError("FRONT_NORMAL_FAIL|mesh=%s|lod=%d|normal=%s" %
                               (mesh.get_path_name(), lod, front["normal"]))
        if lod == 0 and (flap is None or flap["du_dY"] <= 0.0 or flap["dv_dZ"] >= 0.0):
            raise RuntimeError("FLAP_UV0_SIGN_FAIL|mesh=%s|data=%s" %
                               (mesh.get_path_name(), json.dumps(flap, sort_keys=True)))
        if lod == 1 and flap is not None:
            raise RuntimeError("LOD1_FLAP_SURVIVED|mesh=%s" % mesh.get_path_name())
        sections[str(lod)] = {"Front": front, "Flap": flap,
                              "triangles": front["triangles"] +
                              (flap["triangles"] if flap else 0)}
    if pilot.socket_report(mesh):
        raise RuntimeError("TOP_SOCKET_FAIL|mesh=" + mesh.get_path_name())
    if bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
        raise RuntimeError("NANITE_ENABLED|mesh=" + mesh.get_path_name())
    return {"bounds_cm": {"min": actual_min, "max": actual_max},
            "num_lods": lod_count, "slots": slots, "sockets": {},
            "baked_poles": "NOT_APPLICABLE_TOP", "sections": sections}


def verify_flat_general(mesh, row, socket_rows):
    validation = row["validation"]
    slots = [str(value.get_editor_property("material_slot_name"))
             for value in mesh.get_editor_property("static_materials")]
    if slots != list(SLOTS):
        raise RuntimeError("SLOT_ORDER_FAIL|mesh=%s|slots=%s" %
                           (mesh.get_path_name(), slots))
    lod_count = int(mesh.get_num_lods())
    if lod_count != 2:
        raise RuntimeError("LOD_COUNT_FAIL|mesh=%s|lods=%d" %
                           (mesh.get_path_name(), lod_count))
    expected_min, expected_max = expected_import_bounds(validation)
    box = mesh.get_bounding_box()
    actual_min = [float(box.min.x), float(box.min.y), float(box.min.z)]
    actual_max = [float(box.max.x), float(box.max.y), float(box.max.z)]
    if any(abs(a - b) > 1.5 for a, b in
           zip(actual_min + actual_max, expected_min + expected_max)):
        raise RuntimeError("BOUNDS_MISMATCH|mesh=%s|actual=%s|expected=%s" %
                           (mesh.get_path_name(), [actual_min, actual_max],
                            [expected_min, expected_max]))
    if row["side"] == "L" and (actual_min[1] < -1.0 or actual_max[1] < 100.0):
        raise RuntimeError("LEFT_SIDE_EXTENSION_FAIL|bounds_y=%s" %
                           [actual_min[1], actual_max[1]])
    if row["side"] == "R" and (actual_max[1] > 1.0 or actual_min[1] > -100.0):
        raise RuntimeError("RIGHT_SIDE_EXTENSION_FAIL|bounds_y=%s" %
                           [actual_min[1], actual_max[1]])
    sockets = verify_socket_rows(mesh, socket_rows)
    expected_socket_names = sorted(
        row["validation"]["checks"]["socket_contract"]["details"])
    if sorted(sockets) != expected_socket_names:
        raise RuntimeError("SOCKET_SPEC_NAMES_FAIL|mesh=%s|actual=%s|expected=%s" %
                           (mesh.get_path_name(), sorted(sockets), expected_socket_names))
    hinge = sockets["SOCKET_Hinge"]
    pivot = sockets["SOCKET_Pivot"]
    expected_pivot_z = float(row["validation"]["checks"]["height"]["expected_m"]) * 50.0
    if (max(abs(value) for value in hinge["location_cm"]) > 1.0 or
            abs(hinge["local_x_axis"][1]) < 0.99):
        raise RuntimeError("HINGE_SOCKET_FAIL|mesh=%s|data=%s" %
                           (mesh.get_path_name(), hinge))
    if (abs(pivot["location_cm"][0]) > 1.0 or
            abs(pivot["location_cm"][2] - expected_pivot_z) > 1.0 or
            pivot["local_x_axis"][2] < 0.99):
        raise RuntimeError("PIVOT_SOCKET_FAIL|mesh=%s|expected_z=%g|data=%s" %
                           (mesh.get_path_name(), expected_pivot_z, pivot))
    sections = {}
    pole_names = sorted(name for name in sockets if name.startswith("SOCKET_Pole_"))
    for lod in (0, 1):
        _, by_slot = pilot.lod_section_slots(mesh, lod)
        front = pilot.section_uv0(mesh, lod, by_slot[0]) if 0 in by_slot else None
        flap = pilot.section_uv0(mesh, lod, by_slot[1]) if 1 in by_slot else None
        if front is None or front["du_dY"] <= 0.0 or front["dv_dZ"] >= 0.0:
            raise RuntimeError("FRONT_UV0_SIGN_FAIL|mesh=%s|lod=%d|data=%s" %
                               (mesh.get_path_name(), lod,
                                json.dumps(front, sort_keys=True)))
        if (front["normal"][0] > -0.99 or abs(front["normal"][1]) > 0.02 or
                abs(front["normal"][2]) > 0.02):
            raise RuntimeError("FRONT_NORMAL_FAIL|mesh=%s|lod=%d|normal=%s" %
                               (mesh.get_path_name(), lod, front["normal"]))
        if lod == 0 and (flap is None or flap["du_dY"] <= 0.0 or flap["dv_dZ"] >= 0.0):
            raise RuntimeError("FLAP_UV0_SIGN_FAIL|mesh=%s|data=%s" %
                               (mesh.get_path_name(), json.dumps(flap, sort_keys=True)))
        if lod == 1 and flap is not None:
            raise RuntimeError("LOD1_FLAP_SURVIVED|mesh=%s" % mesh.get_path_name())
        dynamic = pilot.dynamic_lod(mesh, lod)
        expected_triangles = int(validation["triangle_counts"]["lod%d" % lod])
        triangle_delta = int(dynamic["triangles"]) - expected_triangles
        # Blender's FBX import and UE Interchange differ by one triangle on
        # seven measured Slot A meshes (six -1, one +1).  Bounds, sections,
        # normals, UVs, vertex colours and baked-pole geometry are gated
        # separately, so reject actual geometry loss while allowing only this
        # measured cross-importer triangulation variance.
        if abs(triangle_delta) > 1:
            raise RuntimeError("TRIANGLE_COUNT_FAIL|mesh=%s|lod=%d|actual=%d|expected=%d|tolerance=1" %
                               (mesh.get_path_name(), lod, dynamic["triangles"],
                                expected_triangles))
        raw_timber = dynamic["_raw"][2]
        foot_ys = [float(position.y)
                   for color, position in zip(raw_timber["colors"],
                                              raw_timber["positions"])
                   if float(color.r) > 0.99 and float(position.z) < -90.0]
        if not foot_ys:
            raise RuntimeError("BAKED_POLE_FOOT_VERTICES_MISSING|mesh=%s|lod=%d" %
                               (mesh.get_path_name(), lod))
        for name in pole_names:
            y = sockets[name]["location_cm"][1]
            if y < min(foot_ys) - 2.0 or y > max(foot_ys) + 2.0:
                raise RuntimeError("POLE_SOCKET_OUTSIDE_FOOT_RANGE|mesh=%s|lod=%d|socket=%s|y=%g|range=%s" %
                                   (mesh.get_path_name(), lod, name, y,
                                    [min(foot_ys), max(foot_ys)]))
        sections[str(lod)] = {
            "Front": front, "Flap": flap,
            "pole_foot_y_range_cm": [min(foot_ys), max(foot_ys)],
            "pole_sockets": pole_names,
        }
    if bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
        raise RuntimeError("NANITE_ENABLED|mesh=" + mesh.get_path_name())
    return {"bounds_cm": {"min": actual_min, "max": actual_max},
            "num_lods": lod_count, "slots": slots, "sockets": sockets,
            "baked_poles": "PASS", "sections": sections}


def verify_geometry(mesh, row, socket_rows):
    return (verify_flat_general(mesh, row, socket_rows)
            if row["baked_poles"] else verify_top(mesh, row))


def configure_and_verify_texture(texture, kind):
    pilot.configure_texture(texture, kind)
    return pilot.verify_texture(texture, kind)


def create_instance(path, parent_path, textures, scalars):
    folder, name = path.rsplit("/", 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew())
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError("MI_CREATE_FAIL|path=" + path)
    parent = unreal.EditorAssetLibrary.load_asset(parent_path)
    instance.modify()
    unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
    for parameter, texture in textures.items():
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, parameter, texture)
    for parameter, value in scalars.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, parameter, float(value))
    # UE 5.8 returns None on success; do not interpret it as a failure.
    unreal.MaterialEditingLibrary.update_material_instance(instance)
    return instance


def verify_instance(instance, path, parent, texture_paths, scalars):
    actual_parent = pilot.asset_package(instance.get_editor_property("parent"))
    actual_textures = pilot.serialized_texture_parameters(instance)
    actual_scalars = pilot.serialized_scalar_parameters(instance)
    if actual_parent != parent or actual_textures != texture_paths:
        raise RuntimeError("MI_READBACK_FAIL|path=%s|parent=%s|textures=%s" %
                           (path, actual_parent, json.dumps(actual_textures, sort_keys=True)))
    if set(actual_scalars) != set(scalars) or any(
            abs(actual_scalars[name] - float(value)) > 0.0001
            for name, value in scalars.items()):
        raise RuntimeError("MI_SCALAR_READBACK_FAIL|path=%s|scalars=%s" %
                           (path, json.dumps(actual_scalars, sort_keys=True)))
    return {"parent": actual_parent, "textures": actual_textures,
            "scalars": actual_scalars}


def asset_paths(row):
    return sorted(row["destinations"].values())


def delete_unsaved_created(paths):
    failures = []
    # Break references first: MIs, mesh, then textures.
    ordered = [path for path in paths if "/Materials/Instances/" in path]
    ordered += [path for path in paths if "/StaticMeshes/" in path]
    ordered += [path for path in paths if path not in ordered]
    for path in ordered:
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            try:
                if not unreal.EditorAssetLibrary.delete_asset(path):
                    failures.append(path)
            except Exception as exc:
                failures.append(path + "|" + str(exc))
    return failures


def import_common_textures(common, existing_common):
    reports = {}
    passing_paths = []
    failures = []
    for passage in sorted(common):
        reports[passage] = {}
        passage_paths = []
        try:
            for name in COMMON_AGED:
                item = common[passage][name]
                kind = pilot.texture_kind(name, "aged")
                if passage in existing_common:
                    texture = unreal.EditorAssetLibrary.load_asset(item["destination"])
                    if not isinstance(texture, unreal.Texture2D):
                        raise RuntimeError("EXISTING_COMMON_LOAD_FAIL|path=" +
                                           item["destination"])
                    reports[passage][name] = pilot.verify_texture(texture, kind)
                else:
                    texture = import_one(item["source"], item["destination"])
                    passage_paths.append(item["destination"])
                    reports[passage][name] = configure_and_verify_texture(texture, kind)
            if passage not in existing_common:
                passing_paths.extend(passage_paths)
        except Exception as exc:
            failures.append({"passage": passage, "gate": "SHARED_TEXTURES",
                             "error": str(exc), "traceback": traceback.format_exc()})
            failures[-1]["cleanup_failures"] = delete_unsaved_created(passage_paths)
    return reports, sorted(passing_paths), failures


def import_asset(row):
    destinations = row["destinations"]
    created = []
    mesh = import_one(row["sources"]["mesh"], destinations["mesh"],
                      pilot.fbx_options(True))
    created.append(destinations["mesh"])
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("MESH_CLASS_FAIL|path=" + destinations["mesh"])
    mesh.modify()
    nanite = mesh.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nanite)
    socket_report, socket_rows = apply_sockets(mesh, row)

    textures = {}
    texture_reports = {}
    for key, kind in (("SkinColor", "SkinColor"), ("SkinMask", "SkinMask"),
                      ("SkinNormal", "SkinNormal"), ("AgedStencil", "AgedColor")):
        texture = import_one(row["sources"][key], destinations[key])
        created.append(destinations[key])
        if not isinstance(texture, unreal.Texture2D):
            raise RuntimeError("TEXTURE_CLASS_FAIL|path=" + destinations[key])
        texture_reports[key] = configure_and_verify_texture(texture, kind)
        textures[key] = texture

    params = load_json(row["sources"]["mi_params"])
    scalars = params["scalar_parameters"]
    skin_textures = {key: textures[key] for key in
                     ("SkinColor", "SkinMask", "SkinNormal")}
    texture_paths = {key: destinations[key] for key in
                     ("SkinColor", "SkinMask", "SkinNormal")}
    instances = {}
    instance_reports = {}
    for slot in ("Front", "Flap"):
        path = destinations[slot]
        instances[slot] = create_instance(path, PARENTS[slot], skin_textures, scalars)
        created.append(path)
        instance_reports[slot] = verify_instance(
            instances[slot], path, PARENTS[slot], texture_paths, scalars)

    mesh.set_material(0, instances["Front"])
    mesh.set_material(1, instances["Flap"])
    mesh.set_material(2, unreal.EditorAssetLibrary.load_asset(PARENTS["Timber"]))
    mesh.set_material(3, unreal.EditorAssetLibrary.load_asset(PARENTS["Edge"]))
    geometry = verify_geometry(mesh, row, socket_rows)
    actual_materials = [pilot.asset_package(value.get_editor_property("material_interface"))
                        for value in mesh.get_editor_property("static_materials")]
    expected_materials = [destinations["Front"], destinations["Flap"],
                          PARENTS["Timber"], PARENTS["Edge"]]
    if actual_materials != expected_materials:
        raise RuntimeError("SLOT_MATERIAL_READBACK_FAIL|mesh=%s|actual=%s|expected=%s" %
                           (destinations["mesh"], actual_materials, expected_materials))
    return {
        "created": sorted(created), "geometry": geometry,
        "textures": texture_reports, "instances": instance_reports,
        "slot_materials": actual_materials, "socket_writeback": socket_report,
    }


def verify_asset_fresh(row):
    destinations = row["destinations"]
    mesh = unreal.EditorAssetLibrary.load_asset(destinations["mesh"])
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("FRESH_MESH_LOAD_FAIL|path=" + destinations["mesh"])
    socket_rows = socket_payload(row["sources"]["socket"], row["mesh_name"])
    geometry = verify_geometry(mesh, row, socket_rows)
    textures = {}
    kinds = {"SkinColor": "SkinColor", "SkinMask": "SkinMask",
             "SkinNormal": "SkinNormal", "AgedStencil": "AgedColor"}
    for key, kind in kinds.items():
        texture = unreal.EditorAssetLibrary.load_asset(destinations[key])
        if not isinstance(texture, unreal.Texture2D):
            raise RuntimeError("FRESH_TEXTURE_LOAD_FAIL|path=" + destinations[key])
        textures[key] = pilot.verify_texture(texture, kind)
    params = load_json(row["sources"]["mi_params"])
    texture_paths = {key: destinations[key] for key in
                     ("SkinColor", "SkinMask", "SkinNormal")}
    instances = {}
    for slot in ("Front", "Flap"):
        path = destinations[slot]
        instance = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(instance, unreal.MaterialInstanceConstant):
            raise RuntimeError("FRESH_MI_LOAD_FAIL|path=" + path)
        instances[slot] = verify_instance(instance, path, PARENTS[slot],
                                          texture_paths,
                                          params["scalar_parameters"])
    actual_materials = [pilot.asset_package(value.get_editor_property("material_interface"))
                        for value in mesh.get_editor_property("static_materials")]
    expected_materials = [destinations["Front"], destinations["Flap"],
                          PARENTS["Timber"], PARENTS["Edge"]]
    if actual_materials != expected_materials:
        raise RuntimeError("FRESH_SLOT_MATERIAL_FAIL|mesh=" + destinations["mesh"])
    return {"geometry": geometry, "textures": textures,
            "instances": instances, "slot_materials": actual_materials}


def verify_common_fresh(common, allowed_passages):
    reports = {}
    for passage in sorted(allowed_passages):
        reports[passage] = {}
        for name in COMMON_AGED:
            path = common[passage][name]["destination"]
            texture = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(texture, unreal.Texture2D):
                raise RuntimeError("FRESH_COMMON_TEXTURE_LOAD_FAIL|path=" + path)
            reports[passage][name] = pilot.verify_texture(
                texture, pilot.texture_kind(name, "aged"))
    return reports


def save_narrow(paths):
    expected = {"maps": [], "content": sorted(paths)}
    before = census()
    if before != expected:
        raise RuntimeError("DIRTY_BEFORE_SAVE_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected, sort_keys=True),
                            json.dumps(before, sort_keys=True)))
    for path in sorted(paths):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAIL|path=" + path)
    after = census()
    settle_saved = []
    if after["maps"]:
        raise RuntimeError("MAP_DIRTY_AFTER_ASSET_SAVE|census=" +
                           json.dumps(after, sort_keys=True))
    if after["content"]:
        if not set(after["content"]).issubset(set(paths)):
            raise RuntimeError("FOREIGN_DIRTY_AFTER_ASSET_SAVE|census=" +
                               json.dumps(after, sort_keys=True))
        settle_saved = list(after["content"])
        for path in settle_saved:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                raise RuntimeError("SETTLE_SAVE_FAIL|path=" + path)
        after = census()
    if after != {"maps": [], "content": []}:
        raise RuntimeError("DIRTY_AFTER_SAVE|census=" + json.dumps(after, sort_keys=True))
    return {"before": before, "after": after, "settle_saved": settle_saved}


def main():
    report = {"run": RUN, "world": WORLD, "status": "RUNNING"}
    final_status = "FAIL"
    try:
        assert_context_clean()
        assets, excluded = built_source_inventory()
        common, common_hashes = common_inventory(assets)
        planned = all_planned_paths(assets, common)
        existing_assets, existing_common = destination_state(assets, common)
        report.update({
            "dirty_at_start": {"maps": [], "content": []},
            "source_counts": EXPECTED_COUNTS,
            "excluded_non_built": excluded,
            "common_hashes": common_hashes,
            "planned_package_count": len(planned),
            "planned_packages": planned,
            "existing_assets_at_resume": sorted(existing_assets),
            "existing_common_at_resume": sorted(existing_common),
        })

        common_reports, common_paths, failures = import_common_textures(
            common, existing_common)
        failed_passages = {value["passage"] for value in failures}
        passing_rows = []
        new_rows = []
        import_reports = {}
        for row in assets:
            key = row["owner"]
            if row["passage"] in failed_passages:
                failures.append({"passage": row["passage"], "owner": key,
                                 "gate": "SKIPPED_SHARED_TEXTURE_FAILURE"})
                continue
            try:
                if key in existing_assets:
                    import_reports[key] = {
                        "strategy": "verified_existing_saved",
                        "readback": verify_asset_fresh(row),
                    }
                else:
                    import_reports[key] = import_asset(row)
                    import_reports[key]["strategy"] = "imported_new"
                    new_rows.append(row)
                passing_rows.append(row)
                unreal.log("FLATV3_A_ASSET_GATE_PASS run=%s passage=%s asset=%s" %
                           (RUN, row["passage"], key))
            except Exception as exc:
                cleanup = delete_unsaved_created(asset_paths(row))
                failures.append({
                    "passage": row["passage"], "owner": key,
                    "gate": "ASSET", "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "cleanup_failures": cleanup,
                })
                unreal.log_error("FLATV3_A_ASSET_GATE_FAIL run=%s passage=%s asset=%s reason=%s" %
                                 (RUN, row["passage"], key,
                                  str(exc).replace("\n", "\\n")))

        passing_passages = {row["passage"] for row in passing_rows}
        unused_common = [path for path in common_paths
                         if not any(path.startswith(TARGETS[passage] + "/")
                                    for passage in passing_passages)]
        common_cleanup_failures = delete_unsaved_created(unused_common)
        if common_cleanup_failures:
            failures.append({"gate": "UNUSED_COMMON_CLEANUP",
                             "cleanup_failures": common_cleanup_failures})
        common_paths = [path for path in common_paths if path not in unused_common]

        save_paths = sorted(common_paths + [path for row in new_rows
                                            for path in asset_paths(row)])
        counts = {passage: sum(1 for row in passing_rows if row["passage"] == passage)
                  for passage in TARGETS}
        report.update({"common_before_save": common_reports,
                       "assets_before_save": import_reports,
                       "failures": failures, "passing_counts": counts,
                       "save_packages": save_paths})
        if save_paths:
            report["save"] = save_narrow(save_paths)
            # Reload only the new content packages; never reload the open level.
            pilot.reload_new_packages(save_paths)
        fresh_assets = {}
        for row in passing_rows:
            fresh_assets[row["owner"]] = verify_asset_fresh(row)
        fresh_common = verify_common_fresh(common, passing_passages)
        final_census = census()
        if final_census != {"maps": [], "content": []}:
            raise RuntimeError("DIRTY_AFTER_FRESH_READBACK|census=" +
                               json.dumps(final_census, sort_keys=True))
        report["fresh_assets"] = fresh_assets
        report["fresh_common"] = fresh_common
        report["dirty_after_fresh_readback"] = final_census

        if failures or counts != EXPECTED_COUNTS:
            raise RuntimeError("PARTIAL_IMPORT|expected=%s|passing=%s|failures=%d" %
                               (json.dumps(EXPECTED_COUNTS, sort_keys=True),
                                json.dumps(counts, sort_keys=True), len(failures)))
        report["status"] = "PASS"
        final_status = "OK"
        path = write_json("slot_a_import_%s.json" % RUN, report)
        unreal.log("FLATV3_A_OK run=%s counts=%s packages_total=%d packages_new=%d report=%s" %
                   (RUN, json.dumps(counts, separators=(",", ":"), sort_keys=True),
                    len(planned), len(save_paths), path))
    except Exception as exc:
        report.update({"status": "FAIL", "error": str(exc),
                       "traceback": traceback.format_exc(),
                       "failure_census": census()})
        path = write_json("slot_a_import_%s_FAILURE.json" % RUN, report)
        unreal.log_error("FLATV3_A_FAIL run=%s reason=%s census=%s report=%s" %
                         (RUN, str(exc).replace("\n", "\\n"),
                          json.dumps(census(), separators=(",", ":"), sort_keys=True), path))
    finally:
        unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s census=%s" %
                   (RUN, final_status,
                    json.dumps(census(), separators=(",", ":"), sort_keys=True)))


main()
