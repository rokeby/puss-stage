"""Guarded project-Python runner for the passage lighting generalisation."""
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

with open(os.path.join(HERE, "passage_lighting_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s PASSAGELIGHT" % mode:
    unreal.log_error("PASSAGELIGHT_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING_SAVED" % mode)
    raise RuntimeError("PASSAGELIGHT CONFIRM_MISSING")

runpy.run_path(os.path.join(HERE, "passage_lighting_as_source.py"),
               run_name="__passage_lighting_runner__", init_globals={"PASSAGE_LIGHTING_ARGS": args})
