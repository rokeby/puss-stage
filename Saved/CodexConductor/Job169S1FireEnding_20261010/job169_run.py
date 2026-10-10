"""Guarded single entry point for Job 169; invoked through ExecuteProjectPythonFile."""
import importlib.util
import json
import os
import sys

import unreal


HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "Job169S1FireEnding_20261010")
ARGS_PATH = os.path.join(HERE, "job169_args.json")


def _load(name, filename):
    path = os.path.join(HERE, filename)
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
    if args.get("confirm") != "%s JOB169" % mode:
        raise RuntimeError("CONFIRM_MISMATCH")
    if stage == "CAMERA_FIRE":
        return _load("job169_camera_fire", "job169_s1_fire_ending.py").run(args)
    if stage == "LIGHTS_OUT":
        return _load("job169_lights_out", "job169_stage_lights_out.py").run(args)
    if stage == "SHRINK":
        return _load("job169_shrink", "job169_stage_shrink.py").run(args)
    if stage == "VALIDATE":
        if mode != "DRY":
            raise RuntimeError("VALIDATE_IS_READ_ONLY")
        return _load("job169_validate", "job169_validate.py").run(args)
    raise RuntimeError("STAGE_INVALID|%s" % stage)


try:
    main()
except Exception as exc:
    try:
        run_id = json.load(open(ARGS_PATH, "r", encoding="utf-8")).get("run_id", "?")
    except Exception:
        run_id = "?"
    unreal.log_error("JOB169_STOPPED|run=%s|%r" % (run_id, exc))
    raise
