"""READ-ONLY saved/read-back verification of the P05 FLOAT pass."""
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


def run_verify(config_path=None, source_run=None, verification_run=None,
               emit_report=True, require_token=True):
    config = f.load_config(config_path)
    source_run = source_run or config["run_id"]
    verification_run = verification_run or source_run
    f.assert_context(config, clean=True)
    originals = f.read_json(config, "preflight", run=source_run)
    plan = f.read_json(config, "dry_run", run=source_run)
    if originals.get("status") != "PASS" or plan.get("status") != "PASS":
        raise RuntimeError("P05FLOAT_VERIFY_PLAN_NOT_PASS")
    original_by_guid = {row["cue_guid"]: row for row in originals["rows"]}
    show = unreal.EditorAssetLibrary.load_asset(f.SHOW)
    if show is None:
        raise RuntimeError("SHOW_LOAD_FAIL")
    f.target_rows(config, show)
    cues = list(show.get_editor_property("cues"))
    actor = f.passage_actor(config, show)
    placed = []
    tolerance = config["bottom_tolerance_cm"]
    for row in plan["rows"]:
        original = original_by_guid[row["cue_guid"]]
        cue = cues[row["cue_index"]]
        f.assert_row_state(
            cue, row["cue_index"], original, config,
            {side: row["sides"][side]["new_local_z_cm"] for side in f.SIDES},
            "P05FLOAT_VERIFY")
        refs = f.refs_for(actor, row["cue_guid"])
        for side in f.SIDES:
            expected = row["sides"][side]
            actual = f.world_bounds(refs[side])
            bottom = float(actual["world_min"][2])
            top = float(actual["world_max"][2])
            target = float(expected["target_world_bottom_cm"])
            if abs(bottom - target) > tolerance:
                raise RuntimeError(
                    "P05FLOAT_BOTTOM_FAIL|index=%d|guid=%s|side=%s|expected=%.9f|actual=%.9f|tolerance=%.9f" %
                    (row["cue_index"], row["cue_guid"], side, target, bottom, tolerance))
            if top > config["max_world_top_cm"] + 0.000001:
                raise RuntimeError(
                    "P05FLOAT_WORLD_TOP_LIMIT_FAIL|index=%d|guid=%s|side=%s|actual=%.9f|limit=%.9f" %
                    (row["cue_index"], row["cue_guid"], side, top,
                     config["max_world_top_cm"]))
            for axis in (0, 1):
                if (abs(float(actual["world_min"][axis]) -
                        float(expected["measured_world_min"][axis])) > tolerance or
                        abs(float(actual["world_max"][axis]) -
                            float(expected["measured_world_max"][axis])) > tolerance):
                    raise RuntimeError(
                        "P05FLOAT_WORLD_XY_CHANGED|index=%d|guid=%s|side=%s|axis=%d|before=%s|after=%s" %
                        (row["cue_index"], row["cue_guid"], side, axis,
                         json.dumps([expected["measured_world_min"][axis],
                                     expected["measured_world_max"][axis]]),
                         json.dumps([actual["world_min"][axis], actual["world_max"][axis]])))
            if actual["mesh"] != expected["mesh"]:
                raise RuntimeError("P05FLOAT_PLACED_MESH_CHANGED|index=%d|side=%s" %
                                   (row["cue_index"], side))
            placed.append({"cue_index": row["cue_index"], "cue_guid": row["cue_guid"],
                           "cue_label": row["cue_label"], "side": side, "mesh": actual["mesh"],
                           "target_world_bottom_cm": target, "actual_world_bottom_cm": bottom,
                           "actual_world_top_cm": top, "world_min": actual["world_min"],
                           "world_max": actual["world_max"]})
    if len(placed) != 186:
        raise RuntimeError("P05FLOAT_VERIFY_SCOPE_FAIL|placed=%d" % len(placed))
    if require_token and not f.log_has(config["verify_token"]):
        raise RuntimeError("VERIFY_TOKEN_NOT_FOUND|" + config["verify_token"])
    end = f.census()
    if end != f.CLEAN:
        raise RuntimeError("P05FLOAT_VERIFY_DIRTIED_EDITOR|census=" + json.dumps(end, sort_keys=True))
    report = {
        "run": verification_run, "source_run": source_run, "mode": "verify", "status": "PASS",
        "rows": len(plan["rows"]), "placed_panels": len(placed), "placed": placed,
        "bottom_tolerance_cm": tolerance, "max_world_top_cm": config["max_world_top_cm"],
        "verify_token": config["verify_token"], "dirty_after": end,
    }
    if emit_report:
        report["report_path"] = f.write_json(config, "verify", report, run=verification_run)
    return report


def main(config_path=None):
    config = f.load_config(config_path)
    try:
        report = run_verify(config["_path"], config["run_id"], config["run_id"], True, True)
        unreal.log("%s run=%s rows=%d placed_panels=%d census=%s report=%s" %
                   (f.marker(config, "READBACK_OK"), config["run_id"], report["rows"],
                    report["placed_panels"],
                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True),
                    report["report_path"]))
        unreal.log(config["success_marker"] + " run=" + config["run_id"])
        f.log_release(config, "OK", run=config["run_id"], artifact_run=config["run_id"])
        return report
    except Exception as exc:
        reason = "verify:" + str(exc)
        f.write_json(config, "verify", {
            "run": config["run_id"], "mode": "verify", "status": "FAIL", "reason": reason,
            "traceback": traceback.format_exc(), "census": f.census(),
        }, failure=True)
        f.log_release(config, "FAIL", reason=reason, run=config["run_id"],
                      artifact_run=config["run_id"])
        raise


if __name__ == "__main__":
    main(globals().get("FLATV3_CONFIG"))
