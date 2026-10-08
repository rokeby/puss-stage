"""Guarded project-Python runner for s4_backcloth_hold.py."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "s4_backcloth_hold_args.json"), encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "s4_backcloth_hold.py"), init_globals={"S4BACKCLOTH_ARGS": ARGS})
