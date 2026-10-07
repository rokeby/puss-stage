"""Runner for p06_bee_glints.py via ExecuteProjectPythonFile (request: p06_bee_glints_request.json).
7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads
p06_bee_glints_args.json and runs the tool with P06BEEGLINTS_ARGS. The tool re-checks confirm ("<MODE> P06BEEGLINTS"),
PIE, world, Sequencer, the dirty census and (choreo_subtrack APPLY) the cueing stream's ack.
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
HERE = os.path.join(SAVED, "CodexConductor", "Effects_20261007")
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p06_bee_glints_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p06_bee_glints.py"), init_globals={"P06BEEGLINTS_ARGS": ARGS})
