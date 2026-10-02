"""Restore only Y values changed by an inner-edge shift, then save narrowly."""
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
import copy
import importlib
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import shift_common as s
s = importlib.reload(s)


def revert(reason, config_path=None):
    config = s.load_config(config_path)
    s.assert_context(config, clean=False)
    preflight = s.read_json(config, "preflight")
    dry = s.read_json(config, "dry_run")
    originals = s.rows_by_identity(preflight["rows"])
    plans = s.rows_by_identity(dry["rows"])
    show = unreal.EditorAssetLibrary.load_asset(s.SHOW)
    cues = list(show.get_editor_property("cues"))
    live_rows = s.occurrence_rows(config, show)
    for live in live_rows:
        key = (int(live["cue_index"]), str(live["cue_guid"]))
        original = originals[key]
        normalized = copy.deepcopy(live)
        plan = plans.get(key)
        if plan:
            for side in plan["shifted_sides"]:
                expected_non_y = copy.deepcopy(live["pair"][side])
                expected_non_y["local_transform"]["location"][1] = \
                    original["pair"][side]["local_transform"]["location"][1]
                if expected_non_y != original["pair"][side]:
                    raise RuntimeError("SHIFT_REVERT_NON_Y_DRIFT|label=%s|side=%s" %
                                       (live["cue_label"], side))
                normalized["pair"][side]["local_transform"]["location"][1] = \
                    original["pair"][side]["local_transform"]["location"][1]
        if normalized != original:
            raise RuntimeError("SHIFT_REVERT_UNTOUCHED_FIELD_DRIFT|label=" + live["cue_label"])

    for plan in dry["rows"]:
        key = (int(plan["cue_index"]), str(plan["cue_guid"]))
        original = originals[key]
        cue = cues[key[0]]
        s.assert_occurrence(cue, original, config, "SHIFT_REVERT_IDENTITY_FAIL")
        pair = cue.get_editor_property("wing_pair")
        for side in plan["shifted_sides"]:
            panel = pair.get_editor_property(side)
            transform = copy.deepcopy(original["pair"][side]["local_transform"])
            panel.set_editor_property("local_transform", s.shared.transform_from_plain(transform))
            pair.set_editor_property(side, panel)
        cue.set_editor_property("wing_pair", pair)
        cues[key[0]] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    if not s.passage_actor(config, show).materialize_passage():
        raise RuntimeError("SHIFT_REVERT_MATERIALIZE_FAIL|" + config["passage"])
    expected_dirty = {"content": [s.SHOW], "maps": [s.WORLD]}
    if s.census() != expected_dirty:
        raise RuntimeError("SHIFT_REVERT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected_dirty, sort_keys=True),
                            json.dumps(s.census(), sort_keys=True)))
    saved_roots = []
    if not unreal.EditorAssetLibrary.save_asset(s.SHOW, only_if_is_dirty=False):
        raise RuntimeError("SHIFT_REVERT_SHOW_SAVE_FAIL")
    saved_roots.append(s.SHOW)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("SHIFT_REVERT_LEVEL_SAVE_FAIL")
    saved_roots.append(s.WORLD)
    if s.census() != s.CLEAN:
        raise RuntimeError("SHIFT_REVERT_POST_SAVE_DIRTY|" + json.dumps(s.census(), sort_keys=True))
    if s.occurrence_rows(config, unreal.EditorAssetLibrary.load_asset(s.SHOW)) != preflight["rows"]:
        raise RuntimeError("SHIFT_REVERT_READBACK_FAIL")
    saved_roots = sorted(set(saved_roots))
    report = {"run": config["run_id"], "mode": "revert", "status": "PASS",
              "reason": str(reason), "rows": len(dry["rows"]),
              "restored_field": "left/right local_transform.location.y only",
              "materialize_calls": [config["passage"]],
              "saved_roots": saved_roots, "census": s.census()}
    path = s.write_json(config, "revert", report)
    unreal.log("%s run=%s passage=%s rows=%d saved_count=%d saved_roots=%s census=%s report=%s" %
               (s.marker(config, "REVERTED"), config["run_id"], config["passage"],
                len(dry["rows"]), len(saved_roots),
                json.dumps(saved_roots, separators=(",", ":")),
                json.dumps(s.census(), separators=(",", ":"), sort_keys=True), path))
    s.log_release(config, "REVERTED", saved_roots)
    return saved_roots


if __name__ == "__main__":
    revert(str(globals().get("FLATV3_REVERT_REASON", "manual")),
           globals().get("FLATV3_CONFIG"))
