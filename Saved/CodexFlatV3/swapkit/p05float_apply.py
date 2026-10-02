"""Apply only P05 side-panel local Z, materialize P05, narrowly save."""
import hashlib
import importlib
import json
import os
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p05float_support as f
f = importlib.reload(f)
import p05float_revert as revert_module
revert_module = importlib.reload(revert_module)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def validate_backup(config):
    backup_report = f.read_json(config, "backup")
    if backup_report.get("status") != "PASS" or backup_report.get("file_count") != 2:
        raise RuntimeError("P05FLOAT_BACKUP_REPORT_FAIL")
    expected_names = set(config["backup_files"] + ["p05float_backup_manifest.json"])
    if not os.path.isdir(config["backup_path"]):
        raise RuntimeError("P05FLOAT_BACKUP_MISSING|" + config["backup_path"])
    actual_names = set(os.listdir(config["backup_path"]))
    if actual_names != expected_names:
        raise RuntimeError("P05FLOAT_BACKUP_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(sorted(expected_names)), json.dumps(sorted(actual_names))))
    manifest_path = os.path.join(config["backup_path"], "p05float_backup_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("run") != config["run_id"] or manifest.get("status") != "PASS":
        raise RuntimeError("P05FLOAT_BACKUP_MANIFEST_FAIL")
    by_name = {row["name"]: row for row in manifest.get("files", [])}
    if set(by_name) != set(config["backup_files"]):
        raise RuntimeError("P05FLOAT_BACKUP_MANIFEST_SCOPE_FAIL")
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        copy = os.path.join(config["backup_path"], name)
        if (not os.path.isfile(source) or not os.path.isfile(copy) or
                os.path.getsize(copy) <= 0 or sha256_file(copy) != by_name[name]["sha256"] or
                sha256_file(source) != by_name[name]["sha256"]):
            raise RuntimeError("P05FLOAT_BACKUP_VALIDATION_FAIL|" + name)
    return backup_report


def set_local_z(pair, side, value):
    panel = pair.get_editor_property(side)
    transform = panel.get_editor_property("local_transform")
    transform.translation = unreal.Vector(
        transform.translation.x, transform.translation.y, float(value))
    panel.set_editor_property("local_transform", transform)
    pair.set_editor_property(side, panel)
    return pair


def run(config_path=None):
    config = f.load_config(config_path)
    saved_roots = []
    show_touched = False
    try:
        f.assert_context(config, clean=True)
        originals = f.read_json(config, "preflight")
        plan = f.read_json(config, "dry_run")
        if originals.get("status") != "PASS" or plan.get("status") != "PASS":
            raise RuntimeError("P05FLOAT_PLAN_NOT_PASS")
        validate_backup(config)
        original_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
        show = unreal.EditorAssetLibrary.load_asset(f.SHOW)
        cues = list(show.get_editor_property("cues"))
        for row in plan["rows"]:
            original = original_by_guid[row["cue_guid"]]
            cue = cues[row["cue_index"]]
            pair = f.assert_row_state(
                cue, row["cue_index"], original, config,
                {side: row["sides"][side]["old_local_z_cm"] for side in f.SIDES},
                "P05FLOAT_APPLY_DRIFT")
            for side in f.SIDES:
                pair = set_local_z(pair, side, row["sides"][side]["new_local_z_cm"])
            cue.set_editor_property("wing_pair", pair)
            cues[row["cue_index"]] = cue
        show.modify()
        show.set_editor_property("cues", cues)
        show_touched = True
        unreal.log("%s run=%s passage=P05 ordinal=1" %
                   (f.marker(config, "MATERIALIZE_CALL"), config["run_id"]))
        if not f.passage_actor(config, show).materialize_passage():
            raise RuntimeError("P05FLOAT_MATERIALIZE_FAIL")
        expected_dirty = {"content": [f.SHOW], "maps": [f.WORLD]}
        before_save = f.census()
        if before_save != expected_dirty:
            raise RuntimeError("P05FLOAT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                               (json.dumps(expected_dirty, sort_keys=True),
                                json.dumps(before_save, sort_keys=True)))
        if not unreal.EditorAssetLibrary.save_asset(f.SHOW, only_if_is_dirty=False):
            raise RuntimeError("P05FLOAT_SHOW_SAVE_FAIL")
        saved_roots.append(f.SHOW)
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError("P05FLOAT_LEVEL_SAVE_FAIL")
        saved_roots.append(f.WORLD)
        if f.census() != f.CLEAN:
            raise RuntimeError("P05FLOAT_POST_SAVE_DIRTY|" + json.dumps(f.census(), sort_keys=True))
        cues2 = list(unreal.EditorAssetLibrary.load_asset(f.SHOW).get_editor_property("cues"))
        for row in plan["rows"]:
            original = original_by_guid[row["cue_guid"]]
            f.assert_row_state(
                cues2[row["cue_index"]], row["cue_index"], original, config,
                {side: row["sides"][side]["new_local_z_cm"] for side in f.SIDES},
                "P05FLOAT_APPLY_READBACK")
        saved_roots = sorted(set(saved_roots))
        report = {
            "run": config["run_id"], "mode": "apply", "status": "PASS",
            "rows": len(plan["rows"]), "panels": 186, "changed_field": "local_transform.location.z",
            "materialize_calls": ["P05"], "backup": config["backup_path"],
            "dirty_before_save": before_save, "dirty_after_save": f.census(),
            "saved_roots": saved_roots,
        }
        path = f.write_json(config, "apply", report)
        unreal.log("%s run=%s rows=%d panels=186 saved_count=%d saved_roots=%s census=%s report=%s" %
                   (f.marker(config, "APPLY_SAVED"), config["run_id"], len(plan["rows"]),
                    len(saved_roots), json.dumps(saved_roots, separators=(",", ":")),
                    json.dumps(f.census(), separators=(",", ":"), sort_keys=True), path))
        return report
    except Exception as exc:
        reason = "apply:" + str(exc)
        f.write_json(config, "apply", {
            "run": config["run_id"], "mode": "apply", "status": "FAIL", "reason": reason,
            "traceback": traceback.format_exc(), "census": f.census(),
        }, failure=True)
        if show_touched:
            try:
                saved_roots = revert_module.revert(reason, config["_path"])
            except Exception as revert_exc:
                reason += "|REVERT_FAIL:" + str(revert_exc)
        f.log_release(config, "FAIL", saved_roots, reason=reason)
        raise


if __name__ == "__main__":
    run(globals().get("FLATV3_CONFIG"))
