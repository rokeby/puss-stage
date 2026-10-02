"""Read-only W2 actor inventory after the six _v2 packages are imported."""
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
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import import_failure_cleanup as ifc
import w2_common as c


def main(config_path=None):
    config = c.load_config(config_path)
    c.assert_context(config, clean=True)
    c.assert_run_unused(config["run_id"])
    marker = "%s run=%s" % (config["import_success_marker"], config["import_run_id"])
    if not c.log_has(marker):
        raise RuntimeError("W2_IMPORT_MARKER_MISSING|marker=" + marker)
    missing = []
    for path in c.all_destination_paths(config):
        reasons = []
        if not ifc.package_exists_on_disk(path):
            reasons.append("DISK")
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            reasons.append("REGISTRY")
        if reasons:
            missing.append({"path": path, "missing": reasons})
    if missing:
        raise RuntimeError("W2_IMPORTED_PACKAGE_MISSING|" + json.dumps(missing))
    actors = c.wave_actors(config)
    widths = c.load_probe_widths(config)
    rows = []
    for key in c.PAIR_KEYS:
        actor = actors[key]
        record = c.actor_record(key, actor)
        record["new_mesh"] = c.mesh_path(config, key)
        record["expected_world_bounds_width_cm"] = widths[key]
        if record["old_mesh"] == record["new_mesh"]:
            raise RuntimeError("W2_ACTOR_ALREADY_SWAPPED|actor=" + record["actor_path"])
        rows.append(record)
    report = {
        "run": config["run_id"], "mode": "w2_preflight", "status": "PASS",
        "world": config["world"], "actor_count": len(rows), "rows": rows,
        "ls_devscene_03_package": c.assert_ls_not_dirty(config),
        "census": c.census(), "import_marker": marker,
    }
    path = c.write_report(config, "preflight", report)
    unreal.log("FLATV3_W2_PREFLIGHT_OK run=%s actors=6 census=%s report=%s" %
               (config["run_id"],
                json.dumps(c.census(), separators=(",", ":"), sort_keys=True), path))
    return report


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
