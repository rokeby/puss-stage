"""Enforce the P04 three-spot p95 gate and auto-revert above +10 percent."""
from __future__ import annotations

import datetime
import importlib.util
import json
import os

try:
    import unreal  # type: ignore
except ImportError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "job186_p04_perf_gate_args.json")
CONFIRM = "ENFORCE JOB186 P04 SHADOW REACH PERF"


def require(value, message):
    if not value:
        raise RuntimeError(str(message))


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "job186_p04_shadow_reach_gate", os.path.join(HERE, "job186_p04_shadow_reach.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_samples(paths, saved_dir=None):
    require(paths, "SAMPLE_PATHS_EMPTY")
    root = saved_dir or (unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
                         if unreal is not None else HERE)
    out = {}
    for path in paths:
        full = path if os.path.isabs(path) else os.path.join(root, path)
        row = json.load(open(full, encoding="utf-8"))
        label = str(row["label"])
        require(label.startswith("P04:"), "NON_P04_SAMPLE|" + label)
        require(label not in out, "DUPLICATE_SAMPLE|" + label)
        out[label] = float(row["p95_ms"])
    return out


def write_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def run(raw):
    require(unreal is not None, "UNREAL_MODULE_REQUIRED")
    require(raw.get("confirm") == CONFIRM, "CONFIRM_MISSING|need=" + CONFIRM)
    require(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None,
            "PIE_MUST_BE_ENDED_BEFORE_GATE")
    tool = load_tool()
    before = load_samples(raw.get("before_reports"))
    after = load_samples(raw.get("after_reports"))
    result = tool.evaluate_perf(before, after, ["P04"], float(raw.get("max_regression", 0.10)))
    require(os.path.isfile(tool.RECORD), "P04_SHADOW_RECORD_MISSING")
    record = json.load(open(tool.RECORD, encoding="utf-8"))
    require(record.get("status") == "saved_readback_verified", "P04_SHADOW_RECORD_NOT_READY")
    require(record.get("run") == raw.get("expected_apply_run"), "P04_APPLY_RUN_MISMATCH")
    run_id = "J186P04PERF-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output = os.path.join(HERE, "job186_p04_shadow_perf_%s.json" % run_id)
    if result["auto_revert"]:
        reverted = tool.run({"mode": "REVERT", "confirm": tool.CONFIRM["REVERT"],
                             "params": record["args"]["params"], "allow_dirty": []})
        result.update({"reverted": True, "revert_run": reverted["run"]})
        marker = "JOB186_P04_SHADOW_PERF_AUTO_REVERT_OK"
    else:
        record["perf_gate"] = dict(result, status="PASS", gate_run=run_id)
        write_json(tool.RECORD, record)
        result["reverted"] = False
        marker = "JOB186_P04_SHADOW_PERF_OK"
    write_json(output, {"run": run_id, "apply_run": record["run"], "result": result})
    unreal.log("%s|run=%s|apply_run=%s|max_regression=%.4f|reverted=%d|report=%s" %
               (marker, run_id, record["run"], result["max_regression_fraction"],
                int(result["reverted"]), output))
    return result


if unreal is not None:
    run(json.load(open(ARGS, encoding="utf-8")))
