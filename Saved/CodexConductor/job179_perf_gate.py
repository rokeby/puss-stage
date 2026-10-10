"""Job 179 p95 gate coordinator for existing frame_time_probe JSON reports.

Run only after owned PIE has ended. P02 reports the three-spot result and never
auto-reverts. Shadow Reach requires three spots for every P01-P06 and invokes
the guarded REVERT automatically when any after p95 exceeds before by >10%.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

HERE = (os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexConductor") if unreal is not None else os.path.dirname(__file__))
ARGS_PATH = os.path.join(HERE, "job179_perf_gate_args.json")


def require(value, message):
    if not value:
        raise RuntimeError(str(message))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def samples(paths):
    require(paths, "SAMPLE_PATHS_EMPTY")
    out = {}
    for path in paths:
        full = path if os.path.isabs(path) else os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) if unreal else HERE, path)
        row = json.load(open(full, encoding="utf-8"))
        label = str(row["label"])
        require(label not in out, "DUPLICATE_SAMPLE_LABEL|" + label)
        out[label] = float(row["p95_ms"])
    return out


def write(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def run(raw):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    task = str(raw.get("task", "")).upper()
    require(task in ("P02", "SHADOW"), "TASK_INVALID")
    confirm = "REPORT P02TRIM PERF" if task == "P02" else "ENFORCE SHADOWRADIUSREACH PERF"
    require(raw.get("confirm") == confirm, "CONFIRM_MISSING|want=" + confirm)
    require(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,
            "PIE_MUST_BE_ENDED_BEFORE_GATE")
    before, after = samples(raw.get("before_reports")), samples(raw.get("after_reports"))
    run_id = "J179PERF-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if task == "P02":
        root = os.path.normpath(os.path.join(HERE, "..", "CodexFlatV3", "p02lighting"))
        tool = load_module("job179_p02_trim", os.path.join(root, "p02_trim.py"))
        result = tool.evaluate_perf(before, after, float(raw.get("max_regression", 0.10)))
        record_path = tool.RECORD_PATH
        require(os.path.isfile(record_path), "P02_TRIM_RECORD_MISSING")
        record = json.load(open(record_path, encoding="utf-8"))
        require(record.get("status") == "saved_readback_verified", "P02_TRIM_RECORD_NOT_READY")
        require(record.get("run") == raw.get("expected_apply_run"), "P02_APPLY_RUN_MISMATCH")
        record["perf_gate"] = dict(result, status="PASS" if result["pass"] else "FAIL_RETAINED_BY_GARY_REQUEST",
                                   gate_run=run_id)
        write(record_path, record)
        output = os.path.join(root, "p02_trim_perf_%s.json" % run_id)
        write(output, {"task": task, "run": run_id, "expected_apply_run": record["run"], "result": result})
        unreal.log("P02TRIM_PERF_%s|run=%s|apply_run=%s|max_regression=%.4f|auto_revert=0|report=%s" %
                   ("OK" if result["pass"] else "FAIL_RETAINED", run_id, record["run"],
                    result["max_regression_fraction"], output))
        return result

    tool = load_module("job179_shadow_reach", os.path.join(HERE, "shadow_radius_reach.py"))
    result = tool.evaluate_perf(before, after, tool.PASSAGES, float(raw.get("max_regression", 0.10)))
    require(os.path.isfile(tool.RECORD), "SHADOW_RECORD_MISSING")
    record = json.load(open(tool.RECORD, encoding="utf-8"))
    require(record.get("status") == "saved_readback_verified", "SHADOW_RECORD_NOT_READY")
    require(record.get("run") == raw.get("expected_apply_run"), "SHADOW_APPLY_RUN_MISMATCH")
    output = os.path.join(HERE, "shadow_radius_reach_perf_%s.json" % run_id)
    if result["auto_revert"]:
        revert = tool.run({"mode": "REVERT", "confirm": tool.CONFIRM["REVERT"],
                           "params": record["args"]["params"], "allow_dirty": []})
        result["revert_run"] = revert["run"]
        result["reverted"] = True
        write(output, {"task": task, "run": run_id, "expected_apply_run": record["run"], "result": result})
        unreal.log("SHADOWRADIUSREACH_PERF_AUTO_REVERT_OK|run=%s|apply_run=%s|revert_run=%s|max_regression=%.4f|report=%s" %
                   (run_id, record["run"], revert["run"], result["max_regression_fraction"], output))
    else:
        record["perf_gate"] = dict(result, status="PASS", gate_run=run_id)
        write(tool.RECORD, record)
        result["reverted"] = False
        write(output, {"task": task, "run": run_id, "expected_apply_run": record["run"], "result": result})
        unreal.log("SHADOWRADIUSREACH_PERF_OK|run=%s|apply_run=%s|max_regression=%.4f|auto_revert=0|report=%s" %
                   (run_id, record["run"], result["max_regression_fraction"], output))
    return result


if unreal is not None:
    run(json.load(open(ARGS_PATH, encoding="utf-8")))
