"""Restore only panels changed by the plan plus occurrence_offset, then save narrowly."""
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

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)


def revert(reason, config_path=None):
    config = c.load_config(config_path)
    c.assert_context(config, clean=False)
    originals = c.read_json(config, "preflight")
    plan = c.read_json(config, "dry_run")
    configured_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                             for entry in config["keep_old_sides"])
    planned_keep = sorted((entry["cue_guid"], entry["side"], entry["reason"])
                          for entry in plan.get("kept_old_sides", []))
    if planned_keep != configured_keep:
        raise RuntimeError("REVERT_KEEP_OLD_SIDES_MISMATCH")
    original_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
    show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
    cues = list(show.get_editor_property("cues"))
    untouched = {}
    restored = set(["occurrence_offset"])
    for row in plan["rows"]:
        original = original_by_guid[row["cue_guid"]]
        cue = cues[row["cue_index"]]
        c.assert_occurrence(cue, row["cue_index"], original,
                            config["passage_label_prefix"], "REVERT_CUE_IDENTITY_FAIL")
        pair = cue.get_editor_property("wing_pair")
        kept_sides = {entry["side"] for entry in row.get("kept_old_sides", [])}
        for side in kept_sides:
            if not c.panel_matches(c.panel_plain(pair.get_editor_property(side)), original[side]):
                raise RuntimeError("REVERT_KEPT_OLD_SIDE_DRIFT|label=%s|side=%s" %
                                   (original["cue_label"], side))
        untouched[row["cue_guid"]] = {
            side: c.panel_plain(pair.get_editor_property(side))
            for side in ("left", "right", "top") if side not in row["changed_sides"]}
        untouched[row["cue_guid"]]["mechanism"] = c.mechanism_plain(
            pair.get_editor_property("mechanism"))
        for side in row["changed_sides"]:
            pair.set_editor_property(
                side, c.set_panel(pair.get_editor_property(side), original[side]))
            restored.add(side)
        pair.set_editor_property(
            "occurrence_offset", c.transform_from_plain(original["occurrence_offset"]))
        cue.set_editor_property("wing_pair", pair)
        cues[row["cue_index"]] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    if not c.passage_actor(config, show).materialize_passage():
        raise RuntimeError("REVERT_PASSAGE_MATERIALIZE_FAIL|" + config["passage"])
    expected = {"content": [c.SHOW], "maps": [c.WORLD]}
    if c.census() != expected:
        raise RuntimeError("REVERT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected, sort_keys=True), json.dumps(c.census(), sort_keys=True)))
    saved_roots = []
    if not unreal.EditorAssetLibrary.save_asset(c.SHOW, only_if_is_dirty=False):
        raise RuntimeError("REVERT_SHOW_SAVE_FAIL")
    saved_roots.append(c.SHOW)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("REVERT_LEVEL_SAVE_FAIL")
    saved_roots.append(c.WORLD)
    if c.census() != c.CLEAN:
        raise RuntimeError("REVERT_POST_SAVE_DIRTY|" + json.dumps(c.census(), sort_keys=True))
    cues2 = list(unreal.EditorAssetLibrary.load_asset(c.SHOW).get_editor_property("cues"))
    for row in plan["rows"]:
        original = original_by_guid[row["cue_guid"]]
        readback_cue = cues2[row["cue_index"]]
        c.assert_occurrence(readback_cue, row["cue_index"], original,
                            config["passage_label_prefix"], "REVERT_READBACK_IDENTITY_FAIL")
        pair = readback_cue.get_editor_property("wing_pair")
        kept_sides = {entry["side"] for entry in row.get("kept_old_sides", [])}
        for side in row["changed_sides"]:
            if not c.panel_matches(c.panel_plain(pair.get_editor_property(side)), original[side]):
                raise RuntimeError("REVERT_READBACK_FAIL|label=%s|side=%s" %
                                   (original["cue_label"], side))
        if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
                                 original["occurrence_offset"]):
            raise RuntimeError("REVERT_OFFSET_READBACK_FAIL|label=" + original["cue_label"])
        for side, expected_panel in untouched[row["cue_guid"]].items():
            if side == "mechanism":
                continue
            if not c.panel_matches(c.panel_plain(pair.get_editor_property(side)), expected_panel):
                error = ("REVERT_KEPT_OLD_SIDE_CHANGED" if side in kept_sides
                         else "REVERT_UNTOUCHED_FIELD_CHANGED")
                raise RuntimeError("%s|label=%s|side=%s" %
                                   (error, original["cue_label"], side))
        if c.mechanism_plain(pair.get_editor_property("mechanism")) != \
                untouched[row["cue_guid"]]["mechanism"]:
            raise RuntimeError("REVERT_UNTOUCHED_MECHANISM_CHANGED|" + original["cue_label"])
    saved_roots = sorted(set(saved_roots))
    report = {"run": config["run_id"], "mode": "revert", "status": "PASS",
              "reason": str(reason), "rows": len(plan["rows"]),
              "kept_old_sides": plan.get("kept_old_sides", []),
              "restored_fields": sorted(restored), "saved_roots": saved_roots,
              "census": c.census()}
    c.write_json(config, "revert", report)
    unreal.log("%s run=%s reason=%s rows=%d saved_roots=%s census=%s" %
               (c.marker(config, "REVERTED"), config["run_id"],
                str(reason).replace(" ", "_"), len(plan["rows"]),
                json.dumps(saved_roots, separators=(",", ":")),
                json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
    return saved_roots


if __name__ == "__main__":
    revert(str(globals().get("FLATV3_REVERT_REASON", "manual")),
           globals().get("FLATV3_CONFIG"))
