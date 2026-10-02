"""Fresh Slot-A-path import of the rebuilt P05 CloudRef02 left Flat V3 asset."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
import ast
import json
import os
from pathlib import Path
import sys
import traceback
import types

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import c3_support as s
import import_failure_cleanup as ifc


def load_slot_a_library(config):
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_slot_a_c3_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = config["import_run_id"]
    module.TARGETS = {"P05": config["destination_root"]}
    module.EXPECTED_COUNTS = {"P05": 1}
    module.SOURCE_ROOTS = (config["source_root"],)
    module.SAVED = HERE
    return module


def source_inventory(config, slot_a):
    tools_dir = os.path.join(s.PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import importlib
    import socket_contract
    socket_contract = importlib.reload(socket_contract)

    folder = config["source_root"]
    status_path = os.path.join(folder, "status.json")
    if not os.path.isfile(status_path):
        raise RuntimeError("C3_SOURCE_STATUS_MISSING|" + status_path)
    status = slot_a.load_json(status_path)
    if (status.get("passage") != "P05" or status.get("status") != "built" or
            not bool(status.get("validation_pass")) or
            status.get("asset_name") != config["asset_name"] or
            status.get("asset_suffix") != config["asset_owner"] or
            status.get("build_side") != "L" or status.get("mount") != "wing" or
            not bool(status.get("baked_poles"))):
        raise RuntimeError("C3_SOURCE_STATUS_FAIL|status=" +
                           json.dumps(status, sort_keys=True, default=str))
    validation_path = os.path.join(folder, "validation.json")
    validation = slot_a.load_json(validation_path)
    lod_group = validation.get("checks", {}).get("fbx_lod_group", {})
    triangulated = validation.get("checks", {}).get("triangulated_export", {})
    counts = validation.get("triangle_counts", {})
    if (not bool(validation.get("pass")) or not bool(lod_group.get("pass")) or
            lod_group.get("mechanism") != "FBX LodGroup NodeAttribute" or
            not bool(triangulated.get("pass")) or not bool(triangulated.get("enabled")) or
            int(counts.get("lod0", -1)) != int(config["expected_lod0_triangles"]) or
            int(counts.get("lod1", -1)) != int(config["expected_lod1_triangles"])):
        raise RuntimeError("C3_OFFLINE_GATE_FAIL|lod_group=%s|triangulated=%s|counts=%s" %
                           (json.dumps(lod_group, sort_keys=True),
                            json.dumps(triangulated, sort_keys=True),
                            json.dumps(counts, sort_keys=True)))
    manifests = sorted(Path(folder).glob("*_build.json"))
    if len(manifests) != 1:
        raise RuntimeError("C3_BUILD_MANIFEST_COUNT_FAIL|actual=%d" % len(manifests))
    manifest = slot_a.load_json(str(manifests[0]))
    socket_path = os.path.join(folder, "sockets_" + config["asset_name"] + ".json")
    expected_socket = socket_contract.make_socket_payload(
        asset=config["asset_name"], side="L", mount="wing",
        height_cm=float(status["height_cm"]),
        width_m=float(manifest["dimensions_m"]["width"]),
        pole_positions_y_m=socket_contract.as_pole_list(manifest.get("pole_positions_y_m")))
    socket_payload = socket_contract.load_json(Path(socket_path))
    socket_failures = socket_contract.validate_socket_payload(socket_payload, expected_socket)
    if socket_failures:
        raise RuntimeError("C3_SOCKET_CONTRACT_FAIL|" + json.dumps(socket_failures))

    owner = config["asset_owner"]
    sources = {
        "mesh": os.path.join(folder, config["asset_name"] + ".fbx"),
        "socket": socket_path,
        "validation": validation_path,
        "mi_params": os.path.join(folder, "skin", owner + "_mi_params.json"),
        "SkinColor": os.path.join(folder, "skin", "T_%s_SkinColor.png" % owner),
        "SkinMask": os.path.join(folder, "skin", "T_%s_SkinMask.png" % owner),
        "SkinNormal": os.path.join(folder, "skin", "T_%s_SkinNormal.png" % owner),
        "AgedStencil": os.path.join(
            folder, "aged", "T_FlatV3_AgedPlywood_Stencil_Color.png"),
    }
    for name in slot_a.COMMON_AGED:
        sources[name] = os.path.join(folder, "aged", name + ".png")
    missing = sorted(path for path in sources.values() if not os.path.isfile(path))
    if missing:
        raise RuntimeError("C3_SOURCE_FILES_MISSING|" + json.dumps(missing))
    target = config["destination_root"]
    destinations = {
        "mesh": config["new_left_mesh"],
        "SkinColor": target + "/Textures/%s/T_%s_SkinColor" % (owner, owner),
        "SkinMask": target + "/Textures/%s/T_%s_SkinMask" % (owner, owner),
        "SkinNormal": target + "/Textures/%s/T_%s_SkinNormal" % (owner, owner),
        "AgedStencil": target + "/Textures/Aged/%s/T_%s_AgedPlywood_Stencil_Color" %
                        (owner, owner),
        "Front": target + "/Materials/Instances/MI_FlatV3_%s_Front" % owner,
        "Flap": target + "/Materials/Instances/MI_FlatV3_%s_Flap" % owner,
    }
    row = {
        "passage": "P05", "folder": folder, "owner": owner,
        "mesh_name": config["asset_name"], "side": "L", "mount": "wing",
        "baked_poles": True, "sources": sources, "destinations": destinations,
        "validation": validation,
    }
    return row, {"sidecar": socket_path, "failures": [],
                 "fbx_lod_group": lod_group, "triangulated_export": triangulated}


def main(config_path=None):
    config = s.load_config(config_path)
    run = config["import_run_id"]
    report = {"run": run, "mode": "c3_import", "status": "RUNNING"}
    final_status = "FAIL"
    saved_roots = []
    tracker = None
    cleanup_result = {"status": "NOT_NEEDED", "created": [], "deleted": []}
    try:
        if s.log_has("FLATV3_SLOT_RELEASED run=" + run):
            raise RuntimeError("C3_IMPORT_RUN_ALREADY_RELEASED")
        s.assert_context(config, clean=True)
        slot_a = load_slot_a_library(config)
        row, contract = source_inventory(config, slot_a)
        assets = [row]
        common, common_hashes = slot_a.common_inventory(assets)
        planned = slot_a.all_planned_paths(assets, common)
        existing_assets, existing_common = slot_a.destination_state(assets, common)
        if existing_assets:
            raise RuntimeError("C3_FRESH_IMPORT_DESTINATION_EXISTS|" +
                               json.dumps(sorted(existing_assets)))
        tracker = ifc.ImportRunTracker("C3", planned, s.census(), s.census)
        tracker.install_deferred_cleanup(slot_a)
        report.update({
            "dirty_at_start": s.CLEAN, "source_count": 1, "socket_contract": contract,
            "common_hashes": common_hashes, "planned_packages": planned,
            "existing_assets_at_start": [],
            "existing_common_at_start": sorted(existing_common),
            "cleanup_tracking": tracker.start_report(),
        })
        common_reports, common_paths, failures = slot_a.import_common_textures(
            common, existing_common)
        tracker.observe_created()
        if failures:
            raise RuntimeError("C3_COMMON_IMPORT_FAIL|" + json.dumps(failures))
        try:
            asset_report = slot_a.import_asset(row)
            tracker.observe_created()
        except Exception:
            tracker.observe_created()
            raise
        save_paths = sorted(common_paths + slot_a.asset_paths(row))
        tracker.observe_created()
        save_report = slot_a.save_narrow(save_paths)
        saved_roots.extend(save_paths)
        slot_a.pilot.reload_new_packages(save_paths)
        fresh_asset = slot_a.verify_asset_fresh(row)
        fresh_common = slot_a.verify_common_fresh(common, {"P05"})
        if s.census() != s.CLEAN:
            raise RuntimeError("C3_IMPORT_DIRTY_AFTER_FRESH_READBACK|" +
                               json.dumps(s.census(), sort_keys=True))
        report.update({
            "status": "PASS", "asset_report": asset_report,
            "common_reports": common_reports, "fresh_asset": fresh_asset,
            "fresh_common": fresh_common, "save_report": save_report,
            "saved_roots": sorted(set(saved_roots)), "dirty_after": s.census(),
        })
        path = s.write_json(config, "import", report, run=run)
        unreal.log("%s run=%s asset=%s lod0=%d lod1=%d saved_count=%d saved_roots=%s report=%s" %
                   (config["import_success_marker"], run, config["asset_name"],
                    config["expected_lod0_triangles"], config["expected_lod1_triangles"],
                    len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")), path))
        final_status = "OK"
        return report
    except Exception as exc:
        original_traceback = traceback.format_exc()
        cleanup_result, cleanup_error = ifc.cleanup_after_failure(
            "C3", run, tracker, s.census)
        if cleanup_error is not None:
            final_status = "CLEANUP_FAIL"
            raise cleanup_error from exc
        final_status = "FAIL_CLEANED"
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": original_traceback, "census": s.census(),
                       "saved_roots": sorted(set(saved_roots)), "cleanup": cleanup_result})
        s.write_json(config, "import", report, run=run, failure=True)
        unreal.log_error("FLATV3_C3_IMPORT_FAIL run=%s reason=%s cleanup=%s census=%s" %
                         (run, str(exc).replace("\n", "\\n"),
                          json.dumps(cleanup_result, separators=(",", ":"), sort_keys=True),
                          json.dumps(s.census(), separators=(",", ":"), sort_keys=True)))
        raise
    finally:
        s.log_release(config, final_status, sorted(set(saved_roots)),
                      run=run, reason=None if final_status == "OK" else final_status)


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
