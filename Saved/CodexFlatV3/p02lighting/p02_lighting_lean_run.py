"""Guarded runner for p02_lighting_lean.py."""
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
if HERE not in sys.path:  # live 10 Oct: same-folder imports failed (job 162)
    sys.path.insert(0, HERE)
with open(os.path.join(HERE, "p02_lighting_lean_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P02LIGHTLEAN" % mode:
    unreal.log_error("P02LIGHTLEAN_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING_SAVED" % mode)
    raise RuntimeError("P02LIGHTLEAN CONFIRM_MISSING")
runpy.run_path(os.path.join(HERE, "p02_lighting_lean.py"),
               run_name="__p02_lighting_lean_runner__",
               init_globals={"P02_LIGHTING_LEAN_ARGS": args})
