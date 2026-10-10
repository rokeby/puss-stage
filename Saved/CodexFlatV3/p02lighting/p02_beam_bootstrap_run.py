"""Guarded project-Python runner for Job 105 P02 beam bootstrap."""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexFlatV3", "p02lighting")
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p02_beam_bootstrap_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P02BEAMBOOTSTRAP" % mode:
    unreal.log_error("P02BEAMBOOTSTRAP_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING_SAVED" % mode)
    raise RuntimeError("P02BEAMBOOTSTRAP CONFIRM_MISSING")

runpy.run_path(os.path.join(HERE, "p02_beam_bootstrap.py"),
               run_name="__p02_beam_bootstrap_runner__", init_globals={"P02_BEAM_BOOTSTRAP_ARGS": args})
