"""Read-only P05 FLOAT plan from direct placed-instance world bounds."""
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
import p05float_support as f
f = importlib.reload(f)


def run(config_path=None):
    config = f.load_config(config_path)
    f.assert_context(config, clean=True)
    preflight = f.read_json(config, "preflight")
    if preflight.get("status") != "PASS" or preflight.get("row_count") != 93:
        raise RuntimeError("P05FLOAT_PREFLIGHT_NOT_PASS")
    show = unreal.EditorAssetLibrary.load_asset(f.SHOW)
    cues = list(show.get_editor_property("cues"))
    actor = f.passage_actor(config, show)
    measurements = {}
    for record in preflight["rows"]:
        cue = cues[record["cue_index"]]
        f.assert_row_state(cue, record["cue_index"], record, config,
                           {side: record[side]["local_transform"]["location"][2]
                            for side in f.SIDES}, "P05FLOAT_PREFLIGHT_DRIFT")
        refs = f.refs_for(actor, record["cue_guid"])
        measurements[record["cue_guid"]] = {side: f.world_bounds(refs[side]) for side in f.SIDES}
    plan = f.plan_from_measurements(config, preflight["rows"], measurements)
    if len(plan) != 93 or sum(len(row["sides"]) for row in plan) != 186:
        raise RuntimeError("P05FLOAT_PLAN_SCOPE_FAIL")
    end = f.census()
    if end != f.CLEAN:
        raise RuntimeError("P05FLOAT_DRY_DIRTIED_EDITOR|census=" + json.dumps(end, sort_keys=True))
    doc = {
        "run": config["run_id"], "slot": config["slot"], "passage": config["passage"],
        "mode": "dry", "status": "PASS", "hash": "sha256 first 8 bytes big-endian / 2**64",
        "hash_side_tokens": list(f.SIDES), "formula": "H = 150 + 300 * u cm",
        "row_count": len(plan), "panel_count": 186, "rows": plan,
        "max_world_top_cm": config["max_world_top_cm"], "materialize_calls": [],
        "dirty_after": end,
    }
    path = f.write_json(config, "dry_run", doc)
    unreal.log("%s run=%s rows=%d panels=%d top_limit=%.1f census=%s plan=%s" %
               (f.marker(config, "DRY_RUN"), config["run_id"], len(plan), 186,
                config["max_world_top_cm"],
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
    return doc


def main(config_path=None):
    config = None
    try:
        config = f.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            f.write_json(config, "dry_run", {
                "run": config["run_id"], "mode": "dry", "status": "FAIL",
                "reason": str(exc), "traceback": traceback.format_exc(), "census": f.census(),
            }, failure=True)
            f.log_release(config, "FAIL", reason="dry:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
