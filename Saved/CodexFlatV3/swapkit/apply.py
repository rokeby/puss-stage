"""Apply one configured Flat V3 plan, materialize one passage, save Show and level only."""
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
import common as c
c = importlib.reload(c)
import revert as revert_module
revert_module = importlib.reload(revert_module)


def run(config_path=None):
    config = c.load_config(config_path)
    report = {"run": config["run_id"], "mode": "apply"}
    show_touched = False
    saved_roots = []
    try:
        c.assert_context(config, clean=True)
        originals = c.read_json(config, "preflight")
        plan = c.read_json(config, "dry_run")
        if plan.get("lateral_mode", "backbone") != config["lateral_mode"]:
            raise RuntimeError("PLAN_LATERAL_MODE_MISMATCH|config=%s|plan=%s" %
                               (config["lateral_mode"],
                                plan.get("lateral_mode", "backbone")))
        configured_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                                 for entry in config["keep_old_sides"])
        planned_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                              for entry in plan.get("kept_old_sides", []))
        if planned_keep != configured_keep:
            raise RuntimeError("PLAN_KEEP_OLD_SIDES_MISMATCH")
        for name in config.get("backup_files", [
                "DA_InfinityStage_V1Show.uasset", "L_InfinityStage_V1VerticalSlice.umap"]):
            if not os.path.isfile(os.path.join(config["backup_path"], name)):
                raise RuntimeError("BACKUP_FILE_MISSING|" + name)
        show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
        cues = list(show.get_editor_property("cues"))
        originals_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
        for row in plan["rows"]:
            original = originals_by_guid[row["cue_guid"]]
            cue = cues[row["cue_index"]]
            c.assert_occurrence(cue, row["cue_index"], row,
                                config["passage_label_prefix"])
            pair = cue.get_editor_property("wing_pair")
            for side in ("left", "right", "top"):
                if c.panel_plain(pair.get_editor_property(side)) != original[side]:
                    raise RuntimeError("ORIGINALS_DRIFT|label=%s|side=%s" %
                                       (row["cue_label"], side))
            if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
                raise RuntimeError("MECHANISM_DRIFT_BEFORE|" + row["cue_label"])
            for side in row["changed_sides"]:
                pair.set_editor_property(side, c.set_panel(pair.get_editor_property(side), row[side]))
            pair.set_editor_property(
                "occurrence_offset", c.transform_from_plain(original["occurrence_offset"]))
            cue.set_editor_property("wing_pair", pair)
            cues[row["cue_index"]] = cue
        show.modify()
        show.set_editor_property("cues", cues)
        show_touched = True
        unreal.log("%s run=%s passage=%s ordinal=1" %
                   (c.marker(config, "MATERIALIZE_CALL"), config["run_id"], config["passage"]))
        if not c.passage_actor(config, show).materialize_passage():
            raise RuntimeError("PASSAGE_MATERIALIZE_FAIL|" + config["passage"])
        expected_dirty = {"content": [c.SHOW], "maps": [c.WORLD]}
        before_save = c.census()
        if before_save != expected_dirty:
            raise RuntimeError("DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                               (json.dumps(expected_dirty, sort_keys=True),
                                json.dumps(before_save, sort_keys=True)))
        if not unreal.EditorAssetLibrary.save_asset(c.SHOW, only_if_is_dirty=False):
            raise RuntimeError("SHOW_SAVE_FAIL")
        saved_roots.append(c.SHOW)
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            raise RuntimeError("LEVEL_SAVE_FAIL")
        saved_roots.append(c.WORLD)
        if c.census() != c.CLEAN:
            raise RuntimeError("POST_SAVE_DIRTY|" + json.dumps(c.census(), sort_keys=True))
        cues2 = list(unreal.EditorAssetLibrary.load_asset(c.SHOW).get_editor_property("cues"))
        readback = []
        for row in plan["rows"]:
            original = originals_by_guid[row["cue_guid"]]
            readback_cue = cues2[row["cue_index"]]
            c.assert_occurrence(readback_cue, row["cue_index"], row,
                                config["passage_label_prefix"], "READBACK_CUE_IDENTITY_FAIL")
            pair = readback_cue.get_editor_property("wing_pair")
            actual = {side: c.panel_plain(pair.get_editor_property(side))
                      for side in ("left", "right", "top")}
            kept_sides = {entry["side"] for entry in row.get("kept_old_sides", [])}
            for side in row["changed_sides"]:
                if not c.panel_matches(actual[side], row[side]):
                    raise RuntimeError("PANEL_READBACK_FAIL|label=%s|side=%s|actual=%s" %
                                       (row["cue_label"], side,
                                        json.dumps(actual[side], sort_keys=True)))
            for side in kept_sides:
                if not c.panel_matches(actual[side], original[side]):
                    raise RuntimeError("APPLY_KEPT_OLD_SIDE_CHANGED|label=%s|side=%s" %
                                       (row["cue_label"], side))
            for side in (set(("left", "right", "top")) - set(row["changed_sides"]) -
                         kept_sides):
                if not c.panel_matches(actual[side], original[side]):
                    raise RuntimeError("UNTOUCHED_PANEL_CHANGED|label=%s|side=%s" %
                                       (row["cue_label"], side))
            if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
                raise RuntimeError("MECHANISM_CHANGED|" + row["cue_label"])
            if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
                                     original["occurrence_offset"]):
                raise RuntimeError("OCCURRENCE_OFFSET_CHANGED|" + row["cue_label"])
            readback.append({"cue_guid": row["cue_guid"],
                             "cue_index": row["cue_index"],
                             "cue_label": row["cue_label"],
                             "changed_sides": row["changed_sides"],
                             "kept_old_sides": row.get("kept_old_sides", []),
                             "panels": actual})
        report.update({"status": "PASS", "backup": config["backup_path"],
                       "lateral_mode": config["lateral_mode"],
                       "centre_gap_gate": plan.get("centre_gap_gate"),
                       "rows": len(readback), "materialize_calls": [config["passage"]],
                       "kept_old_sides": plan.get("kept_old_sides", []),
                       "dirty_before_save": before_save, "dirty_after_save": c.census(),
                       "readback": readback, "saved_roots": sorted(set(saved_roots))})
        path = c.write_json(config, "apply", report)
        unreal.log("%s run=%s rows=%d saved_roots=%s census=%s report=%s" %
                   (c.marker(config, "APPLY_SAVED"), config["run_id"], len(readback),
                    json.dumps(sorted(set(saved_roots))),
                    json.dumps(c.census(), separators=(",", ":"), sort_keys=True), path))
        return report
    except Exception as exc:
        reason = "apply:" + str(exc)
        report.update({"status": "FAIL", "reason": reason,
                       "traceback": traceback.format_exc(), "census": c.census()})
        c.write_json(config, "apply", report, failure=True)
        if show_touched:
            try:
                saved_roots = revert_module.revert(reason, config["_path"])
            except Exception as revert_exc:
                reason += "|REVERT_FAIL:" + str(revert_exc)
        c.log_release(config, "FAIL", saved_roots, reason)
        raise


if __name__ == "__main__":
    run(globals().get("FLATV3_CONFIG"))
