"""Runner for mrq_fallbacks.py via ExecuteProjectPythonFile (relativeSavedPath CodexConductor/MRQ/mrq_fallbacks_run.py).
7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads
mrq_fallbacks_args.json and runs the tool with MRQFB_ARGS. No UE objects are kept at module level.
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
HERE = os.path.join(SAVED, "CodexConductor", "MRQ")
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "mrq_fallbacks_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "mrq_fallbacks.py"), init_globals={"MRQFB_ARGS": ARGS})
