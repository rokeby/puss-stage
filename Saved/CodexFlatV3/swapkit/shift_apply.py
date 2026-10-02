"""Apply Y-only inner-edge shifts, materialize one passage, and save narrowly."""
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
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shift_common as s
s = importlib.reload(s)
import shift_revert as revert_module
revert_module = importlib.reload(revert_module)


def run(config_path=None):
    config = s.load_config(config_path)
    report = {"run": config["run_id"], "mode": "apply"}
    show_touched = False
    saved_roots = []
    try:
        s.assert_context(config, clean=True)
        preflight = s.read_json(config, "preflight")
        dry = s.read_json(config, "dry_run")
        backup = s.read_json(config, "backup")
        if any(doc.get("status") != "PASS" for doc in (preflight, dry, backup)):
            raise RuntimeError("SHIFT_APPLY_PREREQUISITE_NOT_PASS")
        for file_row in backup["files"]:
            path = file_row["backup"]
            if not os.path.isfile(path) or s.sha256_file(path) != file_row["sha256"]:
                raise RuntimeError("SHIFT_BACKUP_READBACK_FAIL|" + path)
        show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
        if show is None:
            raise RuntimeError("SHIFT_SHOW_LOAD_FAIL")
        if s.occurrence_rows(config, show) != preflight["rows"]:
            raise RuntimeError("SHIFT_APPLY_PREFLIGHT_DRIFT")
        cues = list(show.get_editor_property("cues"))
        originals = s.rows_by_identity(preflight["rows"])
        for plan in dry["rows"]:
            key = (int(plan["cue_index"]), str(plan["cue_guid"]))
            original = originals[key]
            cue = cues[key[0]]
            s.assert_occurrence(cue, original, config)
            pair = cue.get_editor_property("wing_pair")
            for side in plan["shifted_sides"]:
                panel = pair.get_editor_property(side)
                panel = s.set_panel_y(panel, original["pair"][side], plan[side])
                pair.set_editor_property(side, panel)
            cue.set_editor_property("wing_pair", pair)
            cues[key[0]] = cue
        show.modify()
        show.set_editor_property("cues", cues)
        show_touched = True
        unreal.log("%s run=%s passage=%s ordinal=1" %
                   (s.marker(config, "MATERIALIZE_CALL"), config["run_id"], config["passage"]))
        if not s.passage_actor(config, show).materialize_passage():
            raise RuntimeError("SHIFT_MATERIALIZE_FAIL|" + config["passage"])
        expected_dirty = {"content": [s.SHOW], "maps": [s.WORLD]}
        before_save = s.census()
        if before_save != expected_dirty:
            raise RuntimeError("SHIFT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                               (json.dumps(expected_dirty, sort_keys=True),
                                json.dumps(before_save, sort_keys=True)))
        if not unreal.EditorAssetLibrary.save_asset(s.SHOW, only_if_is_dirty=False):
            raise RuntimeError("SHIFT_SHOW_SAVE_FAIL")
        saved_roots.append(s.SHOW)
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError("SHIFT_LEVEL_SAVE_FAIL")
        saved_roots.append(s.WORLD)
        if s.census() != s.CLEAN:
            raise RuntimeError("SHIFT_POST_SAVE_DIRTY|" + json.dumps(s.census(), sort_keys=True))
        actual = s.occurrence_rows(config, unreal.EditorAssetLibrary.load_asset(s.SHOW))
        expected = s.expected_shifted_rows(preflight, dry)
        if actual != expected:
            raise RuntimeError("SHIFT_SAVED_AUTHORING_READBACK_FAIL")
        saved_roots = sorted(set(saved_roots))
        report.update({"status": "PASS", "backup": config["backup_path"],
                       "rows": len(dry["rows"]),
                       "shifted_sides": dry["nonzero_delta_count"],
                       "materialize_calls": [config["passage"]],
                       "dirty_before_save": before_save, "dirty_after_save": s.census(),
                       "saved_roots": saved_roots})
        path = s.write_json(config, "apply", report)
        unreal.log("%s run=%s passage=%s rows=%d shifted_sides=%d saved_count=%d saved_roots=%s census=%s report=%s" %
                   (s.marker(config, "APPLY_SAVED"), config["run_id"], config["passage"],
                    len(dry["rows"]), dry["nonzero_delta_count"], len(saved_roots),
                    json.dumps(saved_roots, separators=(",", ":")),
                    json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
        return report
    except Exception as exc:
        reason = "apply:" + str(exc)
        report.update({"status": "FAIL", "reason": reason,
                       "traceback": traceback.format_exc(), "census": s.census()})
        s.write_json(config, "apply", report, failure=True)
        if show_touched:
            try:
                saved_roots = revert_module.revert(reason, config["_path"])
            except Exception as revert_exc:
                reason += "|REVERT_FAIL:" + str(revert_exc)
        s.log_release(config, "FAIL", saved_roots, reason)
        raise


if __name__ == "__main__":
    run(globals().get("FLATV3_CONFIG"))
