"""Entrypoint for p04_glint_practical.py via ExecuteProjectPythonFile.

Reads p04_glint_practical_args.json, e.g.
  {"mode": "DRY"}
  {"mode": "ADD", "confirm": "ADD P04GLINT",
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"]}
  {"mode": "REMOVE", "confirm": "REMOVE P04GLINT", "ack_records": [...]}
ADD and REMOVE refuse unless "confirm" repeats "<MODE> P04GLINT" exactly, so a stale args file cannot turn a dry
run into a write. The tool checks it again (check_args). runpy.run_path executes a fresh copy every call, and cached
modules from Saved/CodexConductor are purged first so edited helpers never run stale
(ue58-python-stale-module-cache, 2 Oct). Pattern copied from p01_rig_pattern_run.py.
"""
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

with open(os.path.join(HERE, "p04_glint_practical_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P04GLINT" % mode:
    unreal.log_error("P04GLINT_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P04GLINT_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p04_glint_practical.py"), run_name="__p04_glint_practical_runner__",
               init_globals={"P04GLINT_ARGS": args})
