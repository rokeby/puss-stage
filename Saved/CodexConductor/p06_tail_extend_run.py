"""Runner for p06_tail_extend.py (5 Oct, offline-written, NOT RUN).

Reads p06_tail_extend_args.json and runs the tool with P06TAIL_ARGS. The tool re-checks confirm ("<MODE> P06TAIL"),
PIE, Sequencer, census, world, Master-in-sync. DRY writes nothing to Unreal (p06_tail_extend_dry.json here). APPLY
writes P06 TailFrames, rebuilds the Master, saves the Show + Master only. REVERT restores the recorded TailFrames and
requires a tick-exact return. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p06_tail_extend_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p06_tail_extend.py"), init_globals={"P06TAIL_ARGS": ARGS})
