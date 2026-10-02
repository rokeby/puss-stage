"""Create and SHA-256 verify the exact Show+level backup for an inner shift."""
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
import importlib
import json
import os
import shutil
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shift_common as s
s = importlib.reload(s)


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight")
    dry = s.read_json(config, "dry_run")
    if preflight.get("status") != "PASS" or dry.get("status") != "PASS":
        raise RuntimeError("SHIFT_BACKUP_PLAN_NOT_PASS")
    backup = config["backup_path"]
    if os.path.exists(backup):
        raise RuntimeError("SHIFT_BACKUP_ALREADY_EXISTS|" + backup)
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        if not os.path.isfile(source) or os.path.getsize(source) <= 0:
            raise RuntimeError("SHIFT_BACKUP_SOURCE_FAIL|" + source)
    os.makedirs(backup)
    rows = []
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        destination = os.path.join(backup, name)
        shutil.copy2(source, destination)
        source_hash = s.sha256_file(source)
        backup_hash = s.sha256_file(destination)
        if source_hash != backup_hash:
            raise RuntimeError("SHIFT_BACKUP_HASH_FAIL|" + name)
        rows.append({"name": name, "source": source, "backup": destination,
                     "size": os.path.getsize(destination), "sha256": backup_hash})
    manifest = {"run": config["run_id"], "status": "PASS", "files": rows}
    manifest_path = os.path.join(backup, "shift_backup_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    report = {"run": config["run_id"], "mode": "backup", "status": "PASS",
              "backup_path": backup, "file_count": len(rows), "files": rows,
              "manifest": manifest_path, "dirty_after": s.census()}
    if report["dirty_after"] != s.CLEAN:
        raise RuntimeError("SHIFT_BACKUP_DIRTIED_EDITOR")
    path = s.write_json(config, "backup", report)
    unreal.log("%s run=%s files=%d backup=%s census=%s report=%s" %
               (s.marker(config, "BACKUP_OK"), config["run_id"], len(rows), backup,
                json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
    return report


def main(config_path=None):
    config = None
    try:
        config = s.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            s.write_json(config, "backup", {
                "run": config["run_id"], "mode": "backup", "status": "FAIL",
                "reason": str(exc), "traceback": traceback.format_exc(),
                "census": s.census()}, failure=True)
            s.log_release(config, "FAIL", reason="backup:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
