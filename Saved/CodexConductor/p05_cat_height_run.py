"""Entrypoint for p05_cat_height.py via ExecuteProjectPythonFile.

Reads p05_cat_height_args.json, e.g.
  {"mode": "DRY", "passage_label": "Passage 5", "target_eye_cm": 90.0, "blend_s": 1.5, "cat_mode": "static_interior"}
  {"mode": "APPLY", "confirm": "APPLY P05CATHEIGHT", ...same}
  {"mode": "REVERT", "confirm": "REVERT P05CATHEIGHT"}
  {"mode": "TEST_CUTS", "confirm": "TEST_CUTS P05CATHEIGHT"}   (queues SceneCutBindingsResolve alone)
Non-DRY modes refuse unless "confirm" repeats "<MODE> P05CATHEIGHT". Cached modules from Saved/CodexConductor are
purged first so an edited tool never runs stale (ue58-python-stale-module-cache, 2 Oct).
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

with open(os.path.join(HERE, "p05_cat_height_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P05CATHEIGHT" % mode:
    unreal.log_error("P05CATHEIGHT_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P05CATHEIGHT_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p05_cat_height.py"), run_name="__p05_cat_height_runner__",
               init_globals={"P05CATHEIGHT_ARGS": args})
