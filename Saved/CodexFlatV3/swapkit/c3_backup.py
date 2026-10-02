"""Create and SHA-256 verify the exact two-file PreFlatV3C3 backup."""
import hashlib
import json
import os
import shutil
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import c3_support as s


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=True)
    preflight = s.read_json(config, "preflight")
    dry = s.read_json(config, "dry_run")
    if (preflight.get("status") != "PASS" or preflight.get("target_count") != 12 or
            dry.get("status") != "PASS" or dry.get("row_count") != 12):
        raise RuntimeError("C3_BACKUP_PLAN_NOT_PASS")
    backup = config["backup_path"]
    if os.path.exists(backup):
        raise RuntimeError("C3_BACKUP_ALREADY_EXISTS|" + backup)
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        if not os.path.isfile(source) or os.path.getsize(source) <= 0:
            raise RuntimeError("C3_BACKUP_SOURCE_FAIL|" + source)
    os.makedirs(backup)
    rows = []
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        destination = os.path.join(backup, name)
        shutil.copy2(source, destination)
        source_hash = sha256_file(source)
        backup_hash = sha256_file(destination)
        if source_hash != backup_hash:
            raise RuntimeError("C3_BACKUP_HASH_FAIL|" + name)
        rows.append({"name": name, "source": source, "backup": destination,
                     "size": os.path.getsize(destination), "sha256": backup_hash})
    manifest = {"run": config["run_id"], "status": "PASS", "files": rows}
    manifest_path = os.path.join(backup, "c3_backup_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    end = s.census()
    if end != s.CLEAN:
        raise RuntimeError("C3_BACKUP_DIRTIED_EDITOR|" + json.dumps(end, sort_keys=True))
    report = {"run": config["run_id"], "mode": "backup", "status": "PASS",
              "backup_path": backup, "file_count": 2, "files": rows,
              "manifest": manifest_path, "dirty_after": end}
    path = s.write_json(config, "backup", report)
    unreal.log("%s run=%s files=2 backup=%s census=%s report=%s" %
               (s.marker("BACKUP_OK"), config["run_id"], backup,
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
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
            s.log_release(config, "FAIL", [], "backup:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
