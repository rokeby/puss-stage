"""Apply exactly the 12 C3 left swaps, materialize P05, save Show and level only."""
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
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
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
import c3_support as s
import c3_compare as compare
import common as c
c = importlib.reload(c)
import p05float_support as f
f = importlib.reload(f)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_backup(config):
    report = s.read_json(config, "backup")
    if report.get("status") != "PASS" or report.get("file_count") != 2:
        raise RuntimeError("C3_BACKUP_REPORT_FAIL")
    expected_names = set(config["backup_files"] + ["c3_backup_manifest.json"])
    if not os.path.isdir(config["backup_path"]):
        raise RuntimeError("C3_BACKUP_MISSING|" + config["backup_path"])
    actual_names = set(os.listdir(config["backup_path"]))
    if actual_names != expected_names:
        raise RuntimeError("C3_BACKUP_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(sorted(expected_names)),
                            json.dumps(sorted(actual_names))))
    manifest_path = os.path.join(config["backup_path"], "c3_backup_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("run") != config["run_id"] or manifest.get("status") != "PASS":
        raise RuntimeError("C3_BACKUP_MANIFEST_FAIL")
    by_name = {row["name"]: row for row in manifest.get("files", [])}
    if set(by_name) != set(config["backup_files"]):
        raise RuntimeError("C3_BACKUP_MANIFEST_SCOPE_FAIL")
    for name in config["backup_files"]:
        source = config["backup_sources"][name]
        copy_path = os.path.join(config["backup_path"], name)
        if (not os.path.isfile(source) or not os.path.isfile(copy_path) or
                os.path.getsize(copy_path) <= 0 or
                sha256_file(copy_path) != by_name[name]["sha256"] or
                sha256_file(source) != by_name[name]["sha256"]):
            raise RuntimeError("C3_BACKUP_VALIDATION_FAIL|" + name)
    return report


def set_left(pair, expected):
    panel = pair.get_editor_property("left")
    panel = c.set_panel(panel, expected)
    pair.set_editor_property("left", panel)
    return pair


def expected_rows(preflight, plan):
    result = {int(row["cue_index"]): row for row in preflight["rows"]}
    for row in plan["rows"]:
        updated = json.loads(json.dumps(result[int(row["cue_index"])]))
        updated["left"] = row["new_left"]
        result[int(row["cue_index"])] = updated
    return result


def assert_rows(config, show, rows_by_index, error):
    cues = list(show.get_editor_property("cues"))
    f.target_rows(config, show)
    for index in range(config["expected_row_index_start"],
                       config["expected_row_index_end"] + 1):
        actual = f.occurrence_row(index, cues[index])
        if not compare.occurrence_matches(actual, rows_by_index[index]):
            raise RuntimeError("%s|index=%d|guid=%s" %
                               (error, index, rows_by_index[index]["cue_guid"]))
    return cues


def run(config_path=None):
    config = s.load_config(config_path)
    saved_roots = []
    show_touched = False
    try:
        s.assert_context(config, clean=True)
        preflight = s.read_json(config, "preflight")
        plan = s.read_json(config, "dry_run")
        if (preflight.get("status") != "PASS" or preflight.get("row_count") != 93 or
                plan.get("status") != "PASS" or plan.get("row_count") != 12):
            raise RuntimeError("C3_APPLY_PLAN_NOT_PASS")
        s.validate_target_rows(plan["rows"], config["targets"], config["target_count"])
        validate_backup(config)
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        if show is None:
            raise RuntimeError("SHOW_LOAD_FAIL")
        before_by_index = {int(row["cue_index"]): row for row in preflight["rows"]}
        cues = assert_rows(config, show, before_by_index, "C3_APPLY_PREFLIGHT_DRIFT")
        for row in plan["rows"]:
            index = int(row["cue_index"])
            cue = cues[index]
            pair = cue.get_editor_property("wing_pair")
            pair = set_left(pair, row["new_left"])
            cue.set_editor_property("wing_pair", pair)
            cues[index] = cue
        show.modify()
        show.set_editor_property("cues", cues)
        show_touched = True
        unreal.log("%s run=%s passage=P05 ordinal=1" %
                   (s.marker("MATERIALIZE_CALL"), config["run_id"]))
        if not f.passage_actor(config, show).materialize_passage():
            raise RuntimeError("C3_MATERIALIZE_FAIL")
        expected_dirty = {"content": [s.SHOW], "maps": [s.WORLD]}
        before_save = s.census()
        if before_save != expected_dirty:
            raise RuntimeError("C3_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                               (json.dumps(expected_dirty, sort_keys=True),
                                json.dumps(before_save, sort_keys=True)))
        if not unreal.EditorAssetLibrary.save_asset(s.SHOW, only_if_is_dirty=False):
            raise RuntimeError("C3_SHOW_SAVE_FAIL")
        saved_roots.append(s.SHOW)
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError("C3_LEVEL_SAVE_FAIL")
        saved_roots.append(s.WORLD)
        if s.census() != s.CLEAN:
            raise RuntimeError("C3_POST_SAVE_DIRTY|" + json.dumps(s.census(), sort_keys=True))
        expected = expected_rows(preflight, plan)
        show2 = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        assert_rows(config, show2, expected, "C3_APPLY_READBACK_FAIL")
        saved_roots = sorted(set(saved_roots))
        report = {
            "run": config["run_id"], "mode": "apply", "status": "PASS",
            "rows": 12, "changed_sides": {"left": 12, "right": 0, "top": 0},
            "materialize_calls": ["P05"], "backup": config["backup_path"],
            "dirty_before_save": before_save, "dirty_after_save": s.census(),
            "saved_roots": saved_roots,
        }
        path = s.write_json(config, "apply", report)
        unreal.log("%s run=%s rows=12 left=12 right=0 top=0 saved_count=%d saved_roots=%s census=%s report=%s" %
                   (s.marker("APPLY_SAVED"), config["run_id"], len(saved_roots),
                    json.dumps(saved_roots, separators=(",", ":")),
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
        return report
    except Exception as exc:
        reason = "apply:" + str(exc)
        s.write_json(config, "apply", {
            "run": config["run_id"], "mode": "apply", "status": "FAIL",
            "reason": reason, "show_touched": show_touched,
            "saved_roots": sorted(set(saved_roots)),
            "traceback": traceback.format_exc(), "census": s.census()}, failure=True)
        # C3 deliberately has no automatic or bundled revert.  Recovery is a
        # separate conductor-requested operation from the verified backup.
        s.log_release(config, "FAIL", sorted(set(saved_roots)), reason)
        raise


if __name__ == "__main__":
    run(globals().get("FLATV3_CONFIG"))
