"""Fresh-import the six extended Scene 3 wave halves under _v2 names."""
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
import import_failure_cleanup as ifc
import w2_common as c


def load_slot_a_library():
    """Load the proven Slot A implementation without executing its main call."""
    path = os.path.join(os.path.dirname(HERE), "slot_a_import.py")
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and
        isinstance(node.value.func, ast.Name) and node.value.func.id == "main")]
    module = types.ModuleType("flatv3_slot_a_w2_library")
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)
    module.RUN = "W2_LIBRARY_ONLY"
    module.SAVED = HERE
    return module


def _all_declared_gates_pass(status, validation, owner):
    if not bool(status.get("v3_gates_pass")):
        raise RuntimeError("W2_SOURCE_V3_GATES_FAIL|asset=" + owner)
    failed = sorted(name for name, gate in validation.get("checks", {}).items()
                    if isinstance(gate, dict) and gate.get("pass") is False)
    if not bool(validation.get("pass")) or failed:
        raise RuntimeError("W2_SOURCE_VALIDATION_FAIL|asset=%s|failed=%s" %
                           (owner, json.dumps(failed)))
    lod = validation.get("checks", {}).get("fbx_lod_group", {})
    if not bool(lod.get("pass")) or lod.get("mechanism") != "FBX LodGroup NodeAttribute":
        raise RuntimeError("W2_SOURCE_LODGROUP_FAIL|asset=" + owner)
    slots = validation.get("checks", {}).get("material_slots_exact", {})
    lod1_slots = validation.get("checks", {}).get("lod1_slots_exact", {})
    if slots.get("value") != c.EXPECTED_SLOTS or lod1_slots.get("value") != c.EXPECTED_SLOTS:
        raise RuntimeError("W2_SOURCE_SLOT_ORDER_FAIL|asset=" + owner)
    uv = validation.get("checks", {}).get("front_flap_uv0_axis_contract", {})
    if not bool(uv.get("pass")):
        raise RuntimeError("W2_SOURCE_UV_SIGN_FAIL|asset=" + owner)


def inventory(config, slot_a):
    rows = []
    expected_folders = {"S3_WaveRow%s_%s" % tuple(key.split("_")) for key in c.PAIR_KEYS}
    actual_folders = {path.name for path in Path(config["source_root"]).iterdir()
                      if path.is_dir() and path.name.startswith("S3_WaveRow")}
    if actual_folders != expected_folders:
        raise RuntimeError("W2_SOURCE_FOLDER_SET_FAIL|expected=%s|actual=%s" %
                           (json.dumps(sorted(expected_folders)),
                            json.dumps(sorted(actual_folders))))
    for key in c.PAIR_KEYS:
        number, half = key.split("_")
        source_owner = "S3_WaveRow%s_%s" % (number, half)
        new_owner = source_owner + "_v2"
        folder = os.path.join(config["source_root"], source_owner)
        status = slot_a.load_json(os.path.join(folder, "status.json"))
        validation_path = os.path.join(folder, "validation.json")
        validation = slot_a.load_json(validation_path)
        if (status.get("asset") != source_owner or status.get("status") != "built" or
                not bool(status.get("validation_pass"))):
            raise RuntimeError("W2_SOURCE_STATUS_FAIL|asset=" + source_owner)
        _all_declared_gates_pass(status, validation, source_owner)
        manifest_path = str(status.get("build_manifest", ""))
        if not os.path.isfile(manifest_path):
            matches = sorted(Path(folder).glob("*_build.json"))
            if len(matches) != 1:
                raise RuntimeError("W2_BUILD_MANIFEST_FAIL|asset=" + source_owner)
            manifest_path = str(matches[0])
        manifest = slot_a.load_json(manifest_path)
        old_mesh_name = "SM_FlatV3_" + source_owner
        sources = {
            "mesh": os.path.join(folder, old_mesh_name + ".fbx"),
            "socket": os.path.join(folder, "sockets_" + old_mesh_name + ".json"),
            "validation": validation_path,
            "mi_params": os.path.join(folder, "skin", source_owner + "_mi_params.json"),
            "SkinColor": os.path.join(folder, "skin", "T_%s_SkinColor.png" % source_owner),
            "SkinMask": os.path.join(folder, "skin", "T_%s_SkinMask.png" % source_owner),
            "SkinNormal": os.path.join(folder, "skin", "T_%s_SkinNormal.png" % source_owner),
            "AgedStencil": os.path.join(
                folder, "aged", "T_FlatV3_AgedPlywood_Stencil_Color.png"),
        }
        missing = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing:
            raise RuntimeError("W2_SOURCE_FILES_MISSING|asset=%s|missing=%s" %
                               (source_owner, json.dumps(missing)))
        root = config["destination_root"].rstrip("/")
        destinations = {
            "mesh": root + "/StaticMeshes/SM_FlatV3_" + new_owner,
            "SkinColor": root + "/Textures/%s/T_%s_SkinColor" % (new_owner, new_owner),
            "SkinMask": root + "/Textures/%s/T_%s_SkinMask" % (new_owner, new_owner),
            "SkinNormal": root + "/Textures/%s/T_%s_SkinNormal" % (new_owner, new_owner),
            "AgedStencil": root + "/Textures/%s/T_%s_AgedPlywood_Stencil_Color" %
                            (new_owner, new_owner),
            "Front": root + "/Materials/Instances/MI_FlatV3_%s_Front" % new_owner,
            "Flap": root + "/Materials/Instances/MI_FlatV3_%s_Flap" % new_owner,
        }
        rows.append({
            "key": key, "passage": "S3", "folder": folder,
            "owner": new_owner, "source_owner": source_owner,
            # The socket sidecar header names the source FBX. It is empty for wave rows.
            "mesh_name": old_mesh_name, "side": str(manifest.get("side", "L")),
            "mount": str(manifest.get("mount", "wave-row")), "baked_poles": False,
            "sources": sources, "destinations": destinations,
            "validation": validation,
        })
    planned = sorted(path for row in rows for path in slot_a.asset_paths(row))
    if planned != c.all_destination_paths(config):
        raise RuntimeError("W2_PLANNED_PATH_SET_FAIL")
    return rows, planned


def assert_destinations_absent(planned):
    present = []
    for path in planned:
        object_path = "%s.%s" % (path, path.rsplit("/", 1)[-1])
        reasons = []
        if ifc.package_exists_on_disk(path):
            reasons.append("DISK")
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            reasons.append("REGISTRY")
        if unreal.find_object(None, object_path) is not None:
            reasons.append("LOADED")
        if reasons:
            present.append({"path": path, "reasons": reasons})
    if present:
        raise RuntimeError("W2_NEW_PATH_ALREADY_EXISTS|" + json.dumps(present, sort_keys=True))


def lod1_timber_gate(slot_a, mesh, path):
    """Gate imported (post-sRGB-conversion) LOD1 plywood IDs against P04's 0.5."""
    dynamic = slot_a.pilot.dynamic_lod(mesh, 1)
    timber = dynamic.get("materials", {}).get("2", {})
    values = timber.get("r_range")
    if (not isinstance(values, (list, tuple)) or len(values) != 2 or
            any(float(value) < 0.49 or float(value) > 0.51 for value in values)):
        raise RuntimeError("W2_LOD1_TIMBER_R_FAIL|mesh=%s|r=%s|required=[0.49,0.51]" %
                           (path, json.dumps(values)))
    return [float(values[0]), float(values[1])]


def assert_slot_a_geometry_report(result, path):
    """Make the reused Slot A live gates explicit at the W2 run boundary."""
    geometry = result.get("geometry", {})
    if int(geometry.get("num_lods", -1)) != 2:
        raise RuntimeError("W2_SLOT_A_LOD_COUNT_FAIL|mesh=" + path)
    if geometry.get("slots") != c.EXPECTED_SLOTS:
        raise RuntimeError("W2_SLOT_A_SLOT_ORDER_FAIL|mesh=%s|slots=%s" %
                           (path, json.dumps(geometry.get("slots"))))
    sections = geometry.get("sections", {})
    for lod in (0, 1):
        row = sections.get(str(lod), {})
        front = row.get("Front")
        flap = row.get("Flap")
        if (not isinstance(front, dict) or float(front.get("du_dY", 0.0)) <= 0.0 or
                float(front.get("dv_dZ", 0.0)) >= 0.0):
            raise RuntimeError("W2_SLOT_A_FRONT_UV_SIGN_FAIL|mesh=%s|lod=%d|data=%s" %
                               (path, lod, json.dumps(front, sort_keys=True)))
        if lod == 0 and (not isinstance(flap, dict) or
                         float(flap.get("du_dY", 0.0)) <= 0.0 or
                         float(flap.get("dv_dZ", 0.0)) >= 0.0):
            raise RuntimeError("W2_SLOT_A_FLAP_UV_SIGN_FAIL|mesh=%s|data=%s" %
                               (path, json.dumps(flap, sort_keys=True)))
        if lod == 1 and flap is not None:
            raise RuntimeError("W2_SLOT_A_LOD1_FLAP_FAIL|mesh=" + path)
    return geometry


def main(config_path=None):
    config = c.load_config(config_path)
    run = config["import_run_id"]
    report = {"run": run, "mode": "w2_fresh_import", "status": "RUNNING"}
    tracker = None
    saved_roots = []
    cleanup = {"status": "NOT_REQUIRED", "created": [], "deleted": []}
    final_status = "FAIL"
    try:
        c.assert_context(config, clean=True)
        # The first live W2 entry point owns the unused-id gate for both run ids.
        c.assert_run_unused(config["import_run_id"])
        c.assert_run_unused(config["run_id"])
        slot_a = load_slot_a_library()
        slot_a.RUN = run
        slot_a.SAVED = HERE
        rows, planned = inventory(config, slot_a)
        assert_destinations_absent(planned)
        tracker = ifc.ImportRunTracker("W2", planned, c.census(), c.census)
        tracker.install_deferred_cleanup(slot_a)
        imported = {}
        for row in rows:
            result = slot_a.import_asset(row)
            tracker.observe_created()
            mesh = unreal.EditorAssetLibrary.load_asset(row["destinations"]["mesh"])
            timber = lod1_timber_gate(slot_a, mesh, row["destinations"]["mesh"])
            geometry = assert_slot_a_geometry_report(
                result, row["destinations"]["mesh"])
            imported[row["key"]] = {"slot_a": result, "geometry_gate": geometry,
                                     "lod1_timber_r": timber}
            unreal.log("FLATV3_W2_IMPORT_ASSET_GATE_PASS run=%s asset=%s lod1_timber_r=%s" %
                       (run, row["owner"], json.dumps(timber)))
        if sorted(tracker.observe_created()) != planned:
            raise RuntimeError("W2_CREATED_SET_FAIL|actual=" +
                               json.dumps(tracker.observe_created()))
        slot_a.save_narrow(planned)
        saved_roots = list(planned)
        slot_a.pilot.reload_new_packages(planned)
        fresh = {}
        for row in rows:
            fresh_result = slot_a.verify_asset_fresh(row)
            mesh = unreal.EditorAssetLibrary.load_asset(row["destinations"]["mesh"])
            fresh[row["key"]] = {
                "slot_a": fresh_result,
                "geometry_gate": assert_slot_a_geometry_report(
                    fresh_result, row["destinations"]["mesh"]),
                "lod1_timber_r": lod1_timber_gate(
                    slot_a, mesh, row["destinations"]["mesh"]),
            }
        if c.census() != c.CLEAN:
            raise RuntimeError("W2_DIRTY_AFTER_FRESH_READBACK|census=" +
                               json.dumps(c.census(), sort_keys=True))
        report.update({
            "status": "PASS", "source_root": config["source_root"],
            "source_count": len(rows), "planned_packages": planned,
            "cleanup_tracking": tracker.start_report(), "imported": imported,
            "fresh_readback": fresh, "saved_roots": saved_roots,
            "dirty_after_fresh_readback": c.census(),
        })
        report_path = c.write_report(config, "import", report)
        unreal.log("%s run=%s assets=6 saved_count=%d saved_roots=%s report=%s" %
                   (config["import_success_marker"], run, len(saved_roots),
                    json.dumps(saved_roots, separators=(",", ":")), report_path))
        final_status = "OK"
        return report
    except Exception as exc:
        original_traceback = traceback.format_exc()
        cleanup, cleanup_error = ifc.cleanup_after_failure("W2", run, tracker, c.census)
        final_status = "CLEANUP_FAIL" if cleanup_error is not None else "FAIL_CLEANED"
        report.update({"status": "FAIL", "reason": str(exc),
                       "traceback": original_traceback, "cleanup": cleanup,
                       "saved_roots": sorted(set(saved_roots)), "census": c.census()})
        c.write_report(config, "import", report, failure=True)
        if cleanup_error is not None:
            raise cleanup_error from exc
        raise
    finally:
        c.log_release(config, final_status, saved_roots, run=run)


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
