"""Runner for klara_void_s6.py via ExecuteProjectPythonFile (relativeSavedPath CodexConductor/KlaraIngest/klara_void_s6_run.py).
7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads
klara_void_s6_args.json and runs the tool with KLARAVOIDS6_ARGS. The tool re-checks confirm ("<MODE> KLARAVOIDS6"),
PIE, world, Sequencer and the dirty census.
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
HERE = os.path.join(SAVED, "CodexConductor", "KlaraIngest")
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "klara_void_s6_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "klara_void_s6.py"), init_globals={"KLARAVOIDS6_ARGS": ARGS})
