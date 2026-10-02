"""Read-only clean census and index+GUID identity gate for P05 FLOAT."""
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
    if f.log_has("FLATV3_SLOT_RELEASED run=" + config["run_id"]):
        raise RuntimeError("RUN_ALREADY_RELEASED")
    f.assert_context(config, clean=True)
    present = [value for value in config["required_previous_markers"] if f.log_has(value)]
    if not present:
        raise RuntimeError("P05FLOAT_PREVIOUS_MARKER_NOT_FOUND|accepted=" +
                           json.dumps(config["required_previous_markers"]))
    show = unreal.EditorAssetLibrary.load_asset(f.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    f.passage_actor(config, show)
    rows = [f.occurrence_row(index, cue) for index, cue in f.target_rows(config, show)]
    end = f.census()
    if end != f.CLEAN:
        raise RuntimeError("P05FLOAT_PREFLIGHT_DIRTIED_EDITOR|census=" +
                           json.dumps(end, sort_keys=True))
    report = {
        "run": config["run_id"], "slot": config["slot"], "passage": config["passage"],
        "mode": "preflight", "status": "PASS", "world": f.WORLD, "show": f.SHOW,
        "accepted_previous_markers": config["required_previous_markers"],
        "observed_previous_markers": present, "row_count": len(rows), "rows": rows,
        "index_range": [rows[0]["cue_index"], rows[-1]["cue_index"]],
        "dirty_at_start": f.CLEAN, "dirty_after": end,
    }
    path = f.write_json(config, "preflight", report)
    unreal.log("%s run=%s rows=%d indices=%d-%d previous=%s census=%s report=%s" %
               (f.marker(config, "PREFLIGHT_OK"), config["run_id"], len(rows),
                rows[0]["cue_index"], rows[-1]["cue_index"], json.dumps(present),
                json.dumps(end, separators=(",", ":"), sort_keys=True), path))
    return report


def main(config_path=None):
    config = None
    try:
        config = f.load_config(config_path)
        return run(config["_path"])
    except Exception as exc:
        if config is not None:
            f.write_json(config, "preflight", {
                "run": config["run_id"], "mode": "preflight", "status": "FAIL",
                "reason": str(exc), "traceback": traceback.format_exc(), "census": f.census(),
            }, failure=True)
            f.log_release(config, "FAIL", reason="preflight:" + str(exc))
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
