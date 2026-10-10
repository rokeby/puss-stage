"""Guarded single entry point for Job 168 stages; invoked through ExecuteProjectPythonFile."""
import importlib.util
import json
import os
import sys

import unreal


HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "Job168S1Ending_20261010")
ARGS_PATH = os.path.join(HERE, "job168_args.json")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    with open(ARGS_PATH, "r", encoding="utf-8") as handle:
        args = json.load(handle)
    stage = str(args.get("stage") or "").upper()
    mode = str(args.get("mode") or "").upper()
    if args.get("confirm") != "%s JOB168" % mode:
        raise RuntimeError("CONFIRM_MISMATCH")
    if stage == "ANIMALS":
        module = _load("job168_s1_ending", os.path.join(HERE, "job168_s1_ending.py"))
        return module.run(args)
    if stage == "LIGHTS_OUT":
        module = _load("job168_lights_out", os.path.join(HERE, "job168_stage_lights_out.py"))
        return module.run(args)
    if stage == "SHRINK":
        module = _load("job168_shrink", os.path.join(HERE, "job168_stage_shrink.py"))
        return module.run(args)
    if stage == "VALIDATE":
        if mode != "DRY":
            raise RuntimeError("VALIDATE_IS_READ_ONLY")
        module = _load("job168_validate", os.path.join(HERE, "job168_validate.py"))
        return module.run(args)
    raise RuntimeError("STAGE_INVALID|%s" % stage)


try:
    main()
except Exception as exc:
    try:
        run_id = json.load(open(ARGS_PATH, "r", encoding="utf-8")).get("run_id", "?")
    except Exception:
        run_id = "?"
    unreal.log_error("JOB168_STOPPED|run=%s|%r" % (run_id, exc))
    raise
