"""Runner for s4_hangar_hold.py via ExecuteProjectPythonFile (relativeSavedPath CodexConductor/s4_hangar_hold_run.py).
7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache)."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "s4_hangar_hold_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "s4_hangar_hold.py"), init_globals={"S4HOLD_ARGS": ARGS})
