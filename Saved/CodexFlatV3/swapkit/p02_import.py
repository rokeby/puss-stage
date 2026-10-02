"""Import/gate passing P02 set flats plus all eight industrial FBXs; do not touch Show."""
import ast
import json
import os
from pathlib import Path
import sys
import traceback
import types

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
import import_failure_cleanup as ifc


def load_slot_a_library():
    """Load proven Slot A helpers without executing that script's main call."""
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_slot_a_p02_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = "P02_LIBRARY_ONLY"
    module.TARGETS = {"P02": "/Game/Scenes/Wings/FlatV3/Passage02"}
    module.EXPECTED_COUNTS = {"P02": 0}
    module.SAVED = HERE
    return module


def _manifest(folder, status, slot_a):
    path = str(status.get("build_manifest", ""))
    if os.path.isfile(path):
        return slot_a.load_json(path)
    matches = sorted(Path(folder).glob("*_build.json"))
    if len(matches) != 1:
        raise RuntimeError("P02_BUILD_MANIFEST_FAIL|folder=" + folder)
    return slot_a.load_json(str(matches[0]))


def plant_inventory(config, slot_a):
    """The explicit admission rule is validation.json pass=true, not status text."""
    tools_dir = os.path.join(PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract
    import importlib as _importlib
    # The editor's Python keeps modules across scripts; reload so on-disk contract edits apply.
    socket_contract = _importlib.reload(socket_contract)

    root = c._project_path(config["import_plant_source_root"])
    rows = []
    rejected = []
    contracts = {}
    if not os.path.isdir(root):
        raise RuntimeError("P02_PLANT_SOURCE_ROOT_MISSING|" + root)
    for folder_name in sorted(os.listdir(root)):
        folder = os.path.join(root, folder_name)
        status_path = os.path.join(folder, "status.json")
        validation_path = os.path.join(folder, "validation.json")
        if not os.path.isdir(folder) or not os.path.isfile(status_path) or not os.path.isfile(validation_path):
            continue
        status = slot_a.load_json(status_path)
        validation = slot_a.load_json(validation_path)
        if status.get("passage") != "P02":
            continue
        mesh_name = str(status["asset_name"])
        if not bool(validation.get("pass")):
            rejected.append({"asset": mesh_name, "reason": "validation.json pass=false"})
            continue
        owner = str(status["asset_suffix"])
        manifest = _manifest(folder, status, slot_a)
        socket_path = os.path.join(folder, "sockets_" + mesh_name + ".json")
        expected_socket = socket_contract.make_socket_payload(
            asset=mesh_name, side=str(status["build_side"]), mount=str(status["mount"]),
            height_cm=float(status["height_cm"]),
            width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=socket_contract.as_pole_list(manifest.get("pole_positions_y_m")))
        socket_failures = socket_contract.validate_socket_payload(
            socket_contract.load_json(Path(socket_path)), expected_socket)
        lod_gate = validation.get("checks", {}).get("fbx_lod_group", {})
        if (not bool(lod_gate.get("pass")) or
                lod_gate.get("mechanism") != "FBX LodGroup NodeAttribute" or socket_failures):
            raise RuntimeError("P02_PLANT_GATE_FAIL|asset=%s|sockets=%s" %
                               (mesh_name, json.dumps(socket_failures)))
        mi_path = os.path.join(folder, "skin", owner + "_mi_params.json")
        sources = {
            "mesh": os.path.join(folder, mesh_name + ".fbx"),
            "socket": socket_path, "validation": validation_path,
            "mi_params": mi_path,
            "SkinColor": os.path.join(folder, "skin", "T_%s_SkinColor.png" % owner),
            "SkinMask": os.path.join(folder, "skin", "T_%s_SkinMask.png" % owner),
            "SkinNormal": os.path.join(folder, "skin", "T_%s_SkinNormal.png" % owner),
            "AgedStencil": os.path.join(folder, "aged", "T_FlatV3_AgedPlywood_Stencil_Color.png"),
        }
        for name in slot_a.COMMON_AGED:
            sources[name] = os.path.join(folder, "aged", name + ".png")
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("P02_PLANT_FILES_MISSING|asset=%s|missing=%s" %
                               (mesh_name, json.dumps(missing)))
        target = config["destination_root"]
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
        side = str(status["build_side"])
        rows.append({"passage": "P02", "folder": folder, "owner": owner,
                     "mesh_name": mesh_name, "side": side,
                     "mount": str(status["mount"]),
                     # C top borders report build_side "L"; poles come from status, never from side.
                     "baked_poles": bool(status.get("baked_poles")) and str(status["mount"]) != "top-border",
                     "sources": sources, "destinations": destinations,
                     "validation": validation})
        contracts[owner] = {"sidecar": socket_path, "failures": socket_failures,
                            "fbx_lod_group": lod_gate,
                            "status_at_admission": status.get("status")}
    if not rows:
        raise RuntimeError("P02_PLANT_SOURCE_EMPTY")
    return rows, rejected, contracts


def industrial_inventory(config, slot_a):
    tools_dir = os.path.join(PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract
    import importlib as _importlib
    # The editor's Python keeps modules across scripts; reload so on-disk contract edits apply.
    socket_contract = _importlib.reload(socket_contract)

    root = c._project_path(config["import_industrial_source_root"])
    validation = slot_a.load_json(os.path.join(root, "validation.json"))
    manifest = slot_a.load_json(os.path.join(root, "manifest.json"))
    if (not validation.get("all_pass") or int(validation.get("passed_assets", 0)) != 8 or
            int(validation.get("asset_count", 0)) != 8):
        raise RuntimeError("P02_INDUSTRIAL_VALIDATION_FAIL")
    validation_by_asset = {row["asset"]: row for row in validation["assets"]}
    rows = []
    for item in manifest.get("assets", []):
        asset = str(item["asset"])
        gate = validation_by_asset.get(asset)
        if gate is None or not bool(gate.get("pass")):
            raise RuntimeError("P02_INDUSTRIAL_ASSET_GATE_FAIL|asset=" + asset)
        sources = {"mesh": os.path.join(root, str(item["fbx"])),
                   "socket": os.path.join(root, "sockets_" + asset + ".json")}
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("P02_INDUSTRIAL_FILES_MISSING|asset=%s|missing=%s" %
                               (asset, json.dumps(missing)))
        socket_payload = socket_contract.load_json(Path(sources["socket"]))
        source_records = [{
            "name": str(record["name"]),
            "location_m": [
                float(record["relative_location_cm"][0]) / 100.0,
                -float(record["relative_location_cm"][1]) / 100.0,
                float(record["relative_location_cm"][2]) / 100.0,
            ],
        } for record in socket_payload.get("sockets", [])]
        height_cm = float(manifest["target_height_cm"])
        expected_socket = socket_contract.make_wing_payload_from_fbx_records(
            asset=asset, side=str(item["side"]), height_cm=height_cm,
            records=source_records)
        bounds = gate["bounds_m"]
        bounds_cm = {
            "y_min": -float(bounds["y_max"]) * 100.0,
            "y_max": -float(bounds["y_min"]) * 100.0,
            "z_min": float(bounds["z_min"]) * 100.0,
            "z_max": float(bounds["z_max"]) * 100.0,
        }
        socket_failures = socket_contract.validate_socket_payload(
            socket_payload, expected_socket, require_metadata=True)
        socket_failures.extend(socket_contract.validate_wing_geometry(
            socket_payload, side=str(item["side"]), height_cm=height_cm,
            bounds_cm=bounds_cm))
        pole_rows = [record for record in socket_payload["sockets"]
                     if str(record["name"]).startswith("SOCKET_Pole_")]
        pole_y = [float(record["relative_location_cm"][1]) for record in pole_rows]
        expected_width_cm = float(item["dimensions_m"]["width"]) * 100.0
        if not pole_y or abs((max(pole_y) - min(pole_y)) - expected_width_cm) > 0.2:
            socket_failures.append("SOURCE_POLE_SPAN_VS_MANIFEST_FAIL")
        if socket_failures:
            raise RuntimeError("P02_INDUSTRIAL_SOCKET_CONTRACT_FAIL|asset=%s|failures=%s" %
                               (asset, json.dumps(socket_failures)))
        rows.append({"owner": asset, "mesh_name": asset, "side": str(item["side"]),
                      "baked_poles": True, "sources": sources, "validation": gate,
                      "socket_count": len(socket_payload["sockets"]),
                      "destination": config["destination_root"] + "/StaticMeshes/" + asset})
    expected = int(config["import_industrial_expected_count"])
    if len(rows) != expected or len({row["mesh_name"] for row in rows}) != expected:
        raise RuntimeError("P02_INDUSTRIAL_SOURCE_COUNT_FAIL|expected=%d|actual=%d" %
                           (expected, len(rows)))
    return rows


def assert_layout_coverage(config, plants, rejected, industrial):
    mapping = c.load_mapping(config)
    plant_names = {row["mesh_name"] for row in plants}
    rejected_names = {row["asset"] for row in rejected}
    industrial_names = {row["mesh_name"] for row in industrial}
    failures = []
    used_industrial = set()
    for row in mapping["occurrences"]:
        for key in ("left", "right", "top"):
            proposal = row["proposal"][key]
            asset = str(proposal["asset"])
            family_class = str(proposal.get("family_class", "")).upper()
            if family_class == "MYSTICAL":
                continue
            if family_class == "INDUSTRIAL":
                used_industrial.add(asset)
                if asset not in industrial_names:
                    failures.append({"asset": asset, "reason": "industrial_not_imported"})
            elif asset in mapping["failed_assets"]:
                if asset not in rejected_names:
                    failures.append({"asset": asset, "reason": "failed_not_rejected"})
            elif asset not in plant_names:
                failures.append({"asset": asset, "reason": "passing_set_not_imported"})
    if failures:
        raise RuntimeError("P02_LAYOUT_IMPORT_COVERAGE_FAIL|" + json.dumps(failures))
    unused_industrial = sorted(industrial_names - used_industrial)
    expected_unused = sorted(name for name in industrial_names if "DuctVent" in name)
    if unused_industrial != expected_unused:
        raise RuntimeError("P02_INDUSTRIAL_UNUSED_SET_FAIL|actual=%s|expected=%s" %
                           (json.dumps(unused_industrial), json.dumps(expected_unused)))
    return {"failed_assets_keep_old": mapping["failed_assets"],
            "used_industrial": sorted(used_industrial),
            "unused_industrial_imported": unused_industrial}


def verify_industrial(mesh, row, slot_a):
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("P02_INDUSTRIAL_MESH_CLASS_FAIL|asset=" + row["mesh_name"])
    validation = row["validation"]
    slots = [str(value.get_editor_property("material_slot_name"))
             for value in mesh.get_editor_property("static_materials")]
    if slots != list(validation["material_slots_lod0"]) or int(mesh.get_num_lods()) != 2:
        raise RuntimeError("P02_INDUSTRIAL_STRUCTURE_FAIL|asset=%s|slots=%s|lods=%s" %
                           (row["mesh_name"], slots, mesh.get_num_lods()))
    socket_rows = slot_a.socket_payload(row["sources"]["socket"], row["mesh_name"])
    sockets = slot_a.verify_socket_rows(mesh, socket_rows)
    if len(sockets) != int(row["socket_count"]):
        raise RuntimeError("P02_INDUSTRIAL_SOCKET_COUNT_FAIL|asset=" + row["mesh_name"])
    box = mesh.get_bounding_box()
    bounds = validation["bounds_m"]
    actual = [float(box.min.y), float(box.max.y), float(box.min.z), float(box.max.z)]
    expected = [-float(bounds["y_max"]) * 100.0, -float(bounds["y_min"]) * 100.0,
                float(bounds["z_min"]) * 100.0, float(bounds["z_max"]) * 100.0]
    if any(abs(a - b) > 1.5 for a, b in zip(actual, expected)):
        raise RuntimeError("P02_INDUSTRIAL_BOUNDS_FAIL|asset=%s|actual=%s|expected=%s" %
                           (row["mesh_name"], actual, expected))
    triangles = {}
    for lod in (0, 1):
        dynamic = slot_a.pilot.dynamic_lod(mesh, lod)
        triangles["lod%d" % lod] = int(dynamic["triangles"])
        if abs(triangles["lod%d" % lod] - int(validation["triangles"]["lod%d" % lod])) > 1:
            raise RuntimeError("P02_INDUSTRIAL_TRIANGLES_FAIL|asset=%s|lod=%d" %
                               (row["mesh_name"], lod))
    if bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")):
        raise RuntimeError("P02_INDUSTRIAL_NANITE_ENABLED|asset=" + row["mesh_name"])
    return {"slots": slots, "lods": 2, "sockets": sorted(sockets),
            "bounds_yz_cm": actual, "triangles": triangles}


def import_industrial(row, slot_a):
    mesh = slot_a.import_one(row["sources"]["mesh"], row["destination"],
                             slot_a.pilot.fbx_options(True))
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("P02_INDUSTRIAL_IMPORT_FAIL|asset=" + row["mesh_name"])
    mesh.modify()
    nanite = mesh.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nanite)
    slot_a.apply_sockets(mesh, row)
    for index, slot in enumerate(slot_a.SLOTS):
        mesh.set_material(index, unreal.EditorAssetLibrary.load_asset(slot_a.PARENTS[slot]))
    return verify_industrial(mesh, row, slot_a)


def main(config_path=None):
    config = c.load_config(config_path)
    run = config["import_run_id"]
    report = {"run": run, "mode": "p02_import", "status": "RUNNING"}
    final_status = "FAIL"
    saved_roots = []
    tracker = None
    cleanup_result = {"status": "NOT_NEEDED", "created": [], "deleted": []}
    try:
        c.assert_context(config, clean=True)
        slot_a = load_slot_a_library()
        slot_a.RUN = run
        slot_a.SAVED = HERE
        plants, rejected, contracts = plant_inventory(config, slot_a)
        industrial = industrial_inventory(config, slot_a)
        layout_coverage = assert_layout_coverage(config, plants, rejected, industrial)
        common, common_hashes = slot_a.common_inventory(plants)
        existing_plants, existing_common = slot_a.destination_state(plants, common)
        existing_industrial = {row["owner"] for row in industrial
                               if unreal.EditorAssetLibrary.does_asset_exist(row["destination"])}
        planned = sorted(set(slot_a.all_planned_paths(plants, common) +
                             [row["destination"] for row in industrial]))
        tracker = ifc.ImportRunTracker("P02", planned, c.census(), c.census)
        tracker.install_deferred_cleanup(slot_a)
        report.update({"plant_source_count": len(plants), "plant_rejected": rejected,
                       "industrial_source_count": len(industrial),
                       "layout_coverage": layout_coverage,
                       "socket_contracts": contracts, "common_hashes": common_hashes,
                       "planned_packages": planned,
                       "cleanup_tracking": tracker.start_report()})
        common_reports, common_paths, failures = slot_a.import_common_textures(
            common, existing_common)
        tracker.observe_created()
        if failures:
            raise RuntimeError("P02_COMMON_IMPORT_FAIL|" + json.dumps(failures))
        new_plants = []
        plant_reports = {}
        for row in plants:
            if row["owner"] in existing_plants:
                plant_reports[row["owner"]] = {"strategy": "verified_existing_saved",
                                                "readback": slot_a.verify_asset_fresh(row)}
            else:
                plant_reports[row["owner"]] = slot_a.import_asset(row)
                tracker.observe_created()
                plant_reports[row["owner"]]["strategy"] = "imported_new"
                new_plants.append(row)
        new_industrial = []
        industrial_reports = {}
        for row in industrial:
            if row["owner"] in existing_industrial:
                mesh = unreal.EditorAssetLibrary.load_asset(row["destination"])
                industrial_reports[row["owner"]] = {"strategy": "verified_existing_saved",
                                                     "readback": verify_industrial(mesh, row, slot_a)}
            else:
                industrial_reports[row["owner"]] = {
                    "strategy": "imported_new", "readback": import_industrial(row, slot_a)}
                tracker.observe_created()
                new_industrial.append(row)
        save_paths = sorted(common_paths +
                            [path for row in new_plants for path in slot_a.asset_paths(row)] +
                            [row["destination"] for row in new_industrial])
        if save_paths:
            tracker.observe_created()
            slot_a.save_narrow(save_paths)
            saved_roots.extend(save_paths)
            slot_a.pilot.reload_new_packages(save_paths)
        fresh_plants = {row["owner"]: slot_a.verify_asset_fresh(row) for row in plants}
        fresh_industrial = {row["owner"]: verify_industrial(
            unreal.EditorAssetLibrary.load_asset(row["destination"]), row, slot_a)
            for row in industrial}
        fresh_common = slot_a.verify_common_fresh(common, {"P02"})
        if c.census() != c.CLEAN:
            raise RuntimeError("P02_DIRTY_AFTER_FRESH_READBACK|census=" +
                               json.dumps(c.census(), sort_keys=True))
        report.update({"status": "PASS", "common_reports": common_reports,
                       "plant_reports": plant_reports,
                       "industrial_reports": industrial_reports,
                       "fresh_plants": fresh_plants, "fresh_industrial": fresh_industrial,
                       "fresh_common": fresh_common, "save_packages": save_paths,
                       "saved_roots": sorted(set(saved_roots)),
                       "dirty_after_fresh_readback": c.census()})
        path = c.write_json(config, "p02_import", report, run=run)
        unreal.log("FLATV3_P02_IMPORT_OK run=%s plant_assets=%d industrial_assets=%d "
                   "saved_count=%d saved_roots=%s report=%s" %
                   (run, len(plants), len(industrial), len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")), path))
        final_status = "OK"
        return report
    except Exception as exc:
        original_traceback = traceback.format_exc()
        cleanup_result, cleanup_error = ifc.cleanup_after_failure(
            "P02", run, tracker, c.census)
        if cleanup_error is not None:
            final_status = "CLEANUP_FAIL"
            raise cleanup_error from exc
        final_status = "FAIL_CLEANED"
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": original_traceback, "census": c.census(),
                       "saved_roots": sorted(set(saved_roots)),
                       "cleanup": cleanup_result})
        c.write_json(config, "p02_import", report, run=run, failure=True)
        unreal.log_error("FLATV3_P02_IMPORT_FAIL run=%s reason=%s census=%s" %
                         (run, str(exc).replace("\n", "\\n"),
                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
        raise
    finally:
        unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s "
                   "cleanup=%s census=%s" %
                   (run, final_status, len(set(saved_roots)),
                     json.dumps(sorted(set(saved_roots)), separators=(",", ":")),
                     json.dumps(cleanup_result, separators=(",", ":"), sort_keys=True),
                     json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
