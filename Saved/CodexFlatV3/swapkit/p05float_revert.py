"""Restore each P05 side panel's original local Z exactly, then narrowly save."""
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
import p05float_support as f
f = importlib.reload(f)


def set_local_z(pair, side, value):
    panel = pair.get_editor_property(side)
    transform = panel.get_editor_property("local_transform")
    transform.translation = unreal.Vector(
        transform.translation.x, transform.translation.y, float(value))
    panel.set_editor_property("local_transform", transform)
    pair.set_editor_property(side, panel)
    return pair


def revert(reason, config_path=None):
    config = f.load_config(config_path)
    f.assert_context(config, clean=False)
    originals = f.read_json(config, "preflight")
    plan = f.read_json(config, "dry_run")
    original_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
    show = unreal.EditorAssetLibrary.load_asset(f.SHOW)
    cues = list(show.get_editor_property("cues"))
    restored = []
    for row in plan["rows"]:
        original = original_by_guid[row["cue_guid"]]
        cue = cues[row["cue_index"]]
        pair = f.assert_row_non_z_state(
            cue, row["cue_index"], original, config, "P05FLOAT_REVERT_DRIFT")
        for side in f.SIDES:
            old_z = float(row["sides"][side]["old_local_z_cm"])
            pair = set_local_z(pair, side, old_z)
            restored.append({"cue_index": row["cue_index"], "cue_guid": row["cue_guid"],
                             "side": side, "restored_local_z_cm": old_z})
        cue.set_editor_property("wing_pair", pair)
        cues[row["cue_index"]] = cue
    show.modify()
    show.set_editor_property("cues", cues)
    if not f.passage_actor(config, show).materialize_passage():
        raise RuntimeError("P05FLOAT_REVERT_MATERIALIZE_FAIL")
    expected_dirty = {"content": [f.SHOW], "maps": [f.WORLD]}
    if f.census() != expected_dirty:
        raise RuntimeError("P05FLOAT_REVERT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected_dirty, sort_keys=True),
                            json.dumps(f.census(), sort_keys=True)))
    saved_roots = []
    if not unreal.EditorAssetLibrary.save_asset(f.SHOW, only_if_is_dirty=False):
        raise RuntimeError("P05FLOAT_REVERT_SHOW_SAVE_FAIL")
    saved_roots.append(f.SHOW)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("P05FLOAT_REVERT_LEVEL_SAVE_FAIL")
    saved_roots.append(f.WORLD)
    if f.census() != f.CLEAN:
        raise RuntimeError("P05FLOAT_REVERT_POST_SAVE_DIRTY|" + json.dumps(f.census(), sort_keys=True))
    cues2 = list(unreal.EditorAssetLibrary.load_asset(f.SHOW).get_editor_property("cues"))
    for row in plan["rows"]:
        original = original_by_guid[row["cue_guid"]]
        f.assert_row_state(
            cues2[row["cue_index"]], row["cue_index"], original, config,
            {side: row["sides"][side]["old_local_z_cm"] for side in f.SIDES},
            "P05FLOAT_REVERT_READBACK")
    saved_roots = sorted(set(saved_roots))
    report = {"run": config["run_id"], "mode": "revert", "status": "PASS",
              "reason": str(reason), "rows": len(plan["rows"]), "panels": len(restored),
              "restored_field": "local_transform.location.z", "restored": restored,
              "materialize_calls": ["P05"], "saved_roots": saved_roots,
              "census": f.census()}
    f.write_json(config, "revert", report)
    unreal.log("%s run=%s reason=%s rows=%d panels=%d saved_count=%d saved_roots=%s census=%s" %
               (f.marker(config, "REVERTED"), config["run_id"],
                str(reason).replace(" ", "_"), len(plan["rows"]), len(restored),
                len(saved_roots), json.dumps(saved_roots, separators=(",", ":")),
                json.dumps(f.census(), separators=(",", ":"), sort_keys=True)))
    return saved_roots


if __name__ == "__main__":
    revert(str(globals().get("FLATV3_REVERT_REASON", "manual")),
           globals().get("FLATV3_CONFIG"))
