"""Import and gate the eleven P03 Flat V3 assets without touching Show or level."""
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
import importlib.util
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
    """Load the proven Slot A functions while deliberately omitting its final main call."""
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_slot_a_p03_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = "P03_LIBRARY_ONLY"
    module.TARGETS = {"P03": "/Game/Scenes/Wings/FlatV3/Passage03"}
    module.EXPECTED_COUNTS = {"P03": 11}
    module.SOURCE_ROOTS = (os.path.join(
        PROJECT, "DerivedAssets", "FlatV3", "Overnight", "P03", "flats"),)
    module.SAVED = HERE
    return module


def p03_inventory(config, slot_a):
    tools_dir = os.path.join(PROJECT, "Tools", "FlatV3")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import socket_contract
    import importlib as _importlib
    socket_contract = _importlib.reload(socket_contract)

    root = c._project_path(config["import_source_root"])
    rows = []
    contracts = {}
    if not os.path.isdir(root):
        raise RuntimeError("P03_SOURCE_ROOT_MISSING|" + root)
    for folder_name in sorted(os.listdir(root)):
        folder = os.path.join(root, folder_name)
        status_path = os.path.join(folder, "status.json")
        if not os.path.isdir(folder) or not os.path.isfile(status_path):
            continue
        status = slot_a.load_json(status_path)
        if status.get("passage") != "P03":
            continue
        if status.get("status") != "built" or not bool(status.get("validation_pass")):
            raise RuntimeError("P03_SOURCE_NOT_BUILT|folder=%s|status=%s|validation=%s" %
                               (folder, status.get("status"), status.get("validation_pass")))
        mesh_name = str(status["asset_name"])
        owner = str(status["asset_suffix"])
        validation_path = os.path.join(folder, "validation.json")
        validation = slot_a.load_json(validation_path)
        lod_gate = validation.get("checks", {}).get("fbx_lod_group", {})
        if not bool(validation.get("pass")) or not bool(lod_gate.get("pass")) or \
                lod_gate.get("mechanism") != "FBX LodGroup NodeAttribute":
            raise RuntimeError("P03_LODGROUP_GATE_FAIL|asset=" + owner)
        manifest_path = str(status.get("build_manifest", ""))
        if not os.path.isfile(manifest_path):
            matches = sorted(Path(folder).glob("*_build.json"))
            if len(matches) != 1:
                raise RuntimeError("P03_BUILD_MANIFEST_FAIL|asset=" + owner)
            manifest_path = str(matches[0])
        manifest = slot_a.load_json(manifest_path)
        socket_path = os.path.join(folder, "sockets_" + mesh_name + ".json")
        expected_socket = socket_contract.make_socket_payload(
            asset=mesh_name, side=str(status["build_side"]), mount=str(status["mount"]),
            height_cm=float(status["height_cm"]),
            width_m=float(manifest["dimensions_m"]["width"]),
            pole_positions_y_m=socket_contract.as_pole_list(manifest.get("pole_positions_y_m")))
        payload = socket_contract.load_json(Path(socket_path))
        failures = socket_contract.validate_socket_payload(payload, expected_socket)
        if failures:
            raise RuntimeError("P03_SOCKET_CONTRACT_FAIL|asset=%s|failures=%s" %
                               (owner, json.dumps(failures)))
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
            raise RuntimeError("P03_SOURCE_FILES_MISSING|asset=%s|missing=%s" %
                               (owner, json.dumps(missing)))
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
        rows.append({"passage": "P03", "folder": folder, "owner": owner,
                     "mesh_name": mesh_name, "side": str(status["build_side"]),
                     "mount": str(status["mount"]),
                     "baked_poles": bool(status["baked_poles"]),
                     "sources": sources, "destinations": destinations,
                     "validation": validation})
        contracts[owner] = {"sidecar": socket_path, "failures": failures,
                            "fbx_lod_group": lod_gate}
    expected = int(config["import_expected_count"])
    if len(rows) != expected:
        raise RuntimeError("P03_SOURCE_COUNT_FAIL|expected=%d|actual=%d" % (expected, len(rows)))
    return rows, contracts


def main(config_path=None):
    config = c.load_config(config_path)
    run = config["import_run_id"]
    report = {"run": run, "mode": "p03_import", "status": "RUNNING"}
    final_status = "FAIL"
    saved_roots = []
    tracker = None
    cleanup_result = {"status": "NOT_NEEDED", "created": [], "deleted": []}
    try:
        c.assert_context(config, clean=True)
        slot_a = load_slot_a_library()
        slot_a.RUN = run
        slot_a.SAVED = HERE
        assets, contracts = p03_inventory(config, slot_a)
        common, common_hashes = slot_a.common_inventory(assets)
        planned = slot_a.all_planned_paths(assets, common)
        existing_assets, existing_common = slot_a.destination_state(assets, common)
        tracker = ifc.ImportRunTracker("P03", planned, c.census(), c.census)
        tracker.install_deferred_cleanup(slot_a)
        report.update({"source_count": len(assets), "socket_contracts": contracts,
                       "common_hashes": common_hashes, "planned_packages": planned,
                       "existing_assets_at_resume": sorted(existing_assets),
                       "existing_common_at_resume": sorted(existing_common),
                       "cleanup_tracking": tracker.start_report()})
        common_reports, common_paths, failures = slot_a.import_common_textures(
            common, existing_common)
        tracker.observe_created()
        if failures:
            raise RuntimeError("P03_COMMON_IMPORT_FAIL|" + json.dumps(failures))
        passing_rows = []
        new_rows = []
        asset_reports = {}
        for row in assets:
            owner = row["owner"]
            imported_new = owner not in existing_assets
            try:
                if not imported_new:
                    asset_reports[owner] = {"strategy": "verified_existing_saved",
                                            "readback": slot_a.verify_asset_fresh(row)}
                else:
                    asset_reports[owner] = slot_a.import_asset(row)
                    tracker.observe_created()
                    asset_reports[owner]["strategy"] = "imported_new"
                    new_rows.append(row)
                passing_rows.append(row)
                unreal.log("FLATV3_P03_IMPORT_ASSET_GATE_PASS run=%s asset=%s" % (run, owner))
            except Exception as exc:
                tracker.observe_created()
                failures.append({"owner": owner, "gate": "ASSET", "error": str(exc),
                                  "traceback": traceback.format_exc(),
                                  "cleanup_deferred_to_run_boundary": imported_new})
                unreal.log_error("FLATV3_P03_IMPORT_ASSET_GATE_FAIL run=%s asset=%s reason=%s" %
                                 (run, owner, str(exc).replace("\n", "\\n")))
                raise RuntimeError("P03_ASSET_GATE_FAIL|asset=%s|reason=%s" %
                                   (owner, str(exc))) from exc
        save_paths = sorted(common_paths + [path for row in new_rows
                                            for path in slot_a.asset_paths(row)])
        if save_paths:
            tracker.observe_created()
            slot_a.save_narrow(save_paths)
            saved_roots.extend(save_paths)
            slot_a.pilot.reload_new_packages(save_paths)
        fresh_assets = {row["owner"]: slot_a.verify_asset_fresh(row) for row in passing_rows}
        fresh_common = slot_a.verify_common_fresh(common, {"P03"})
        if failures or len(passing_rows) != int(config["import_expected_count"]):
            raise RuntimeError("P03_PARTIAL_IMPORT|passing=%d|failures=%d" %
                               (len(passing_rows), len(failures)))
        if c.census() != c.CLEAN:
            raise RuntimeError("P03_DIRTY_AFTER_FRESH_READBACK|census=" +
                               json.dumps(c.census(), sort_keys=True))
        report.update({"status": "PASS", "assets_before_save": asset_reports,
                       "fresh_assets": fresh_assets, "fresh_common": fresh_common,
                       "save_packages": save_paths,
                       "saved_roots": sorted(set(saved_roots)),
                       "dirty_after_fresh_readback": c.census()})
        path = c.write_json(config, "p03_import", report, run=run)
        unreal.log("FLATV3_P03_IMPORT_OK run=%s assets=11 saved_count=%d saved_roots=%s report=%s" %
                   (run, len(set(saved_roots)),
                    json.dumps(sorted(set(saved_roots)), separators=(",", ":")), path))
        final_status = "OK"
        return report
    except Exception as exc:
        original_traceback = traceback.format_exc()
        cleanup_result, cleanup_error = ifc.cleanup_after_failure(
            "P03", run, tracker, c.census)
        if cleanup_error is not None:
            final_status = "CLEANUP_FAIL"
            raise cleanup_error from exc
        final_status = "FAIL_CLEANED"
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": original_traceback, "census": c.census(),
                       "saved_roots": sorted(set(saved_roots)),
                       "cleanup": cleanup_result})
        c.write_json(config, "p03_import", report, run=run, failure=True)
        unreal.log_error("FLATV3_P03_IMPORT_FAIL run=%s reason=%s census=%s" %
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
