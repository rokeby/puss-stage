"""Runner for p01_shorten.py (7 Oct, offline-written, NOT RUN).

Reads p01_shorten_args.json and runs the tool with P01SHORTEN_ARGS. The tool re-checks confirm ("<MODE> P01SHORTEN"),
PIE, Sequencer, census, world, Master-in-sync. DRY writes nothing to Unreal (p01_shorten_dry.json here). APPLY disables
the last N P01 cues, moves P01's LastCueGuid, rebuilds the Master, materialises P01 and saves Show + Master + level only.
REVERT re-enables them tick-exact. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p01_shorten_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p01_shorten.py"), init_globals={"P01SHORTEN_ARGS": ARGS})
