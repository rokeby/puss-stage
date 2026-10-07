"""Runner for klara_reveal.py S4 v5 (strike_preroll) via ExecuteProjectPythonFile (relativeSavedPath
CodexConductor/KlaraIngest/klara_reveal_s4v5_run.py).
7 Oct, offline-written, NOT RUN. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads
klara_reveal_s4v5_args.json and runs the tool with KLARAREVEAL_ARGS. The tool re-checks confirm ("<MODE> KLARAREVEAL"),
PIE, world, Sequencer, census and that the klara_hookin records are applied.
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
HERE = os.path.join(SAVED, "CodexConductor", "KlaraIngest")
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "klara_reveal_s4v5_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "klara_reveal.py"), init_globals={"KLARAREVEAL_ARGS": ARGS})
