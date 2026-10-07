"""Runner for klara_pendulum_s4.py via ExecuteProjectPythonFile (relativeSavedPath
CodexConductor/KlaraIngest/klara_pendulum_s4_run.py). 7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules
first (memory ue58-python-stale-module-cache), reads klara_pendulum_s4_args.json, runs the tool with KLARAPENDULUM_ARGS.
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
HERE = os.path.join(SAVED, "CodexConductor", "KlaraIngest")
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "klara_pendulum_s4_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "klara_pendulum_s4.py"), init_globals={"KLARAPENDULUM_ARGS": ARGS})
