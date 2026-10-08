"""Guarded ExecuteProjectPythonFile runner for P16 P03 lighting-as-P01."""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p03_lighting_as_p01_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P03ASP01" % mode:
    unreal.log_error("P03ASP01_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING_SAVED" % mode)
    raise RuntimeError("P03ASP01 CONFIRM_MISSING")

runpy.run_path(os.path.join(HERE, "p03_lighting_as_p01.py"),
               run_name="__p03_lighting_as_p01_runner__", init_globals={"P03ASP01_ARGS": args})
