"""Runner for s1_redock.py (7 Oct, offline-written, NOT RUN).

Reads s1_redock_args.json and runs the tool with S1REDOCK_ARGS. The tool re-checks confirm ("<MODE> S1REDOCK"), PIE,
Sequencer, ZZ_ actors, census, world. DRY writes nothing to Unreal (s1_redock_dry.json here). APPLY translates the S1
hangar set to the new P01 end, re-keys the rise root defaults and I1's hangar-side spawnables, re-matches Scene 1's
handoff, rebuilds the Master (no-change gate) and saves only the touched packages. Purges cached Saved/ modules first
(memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "s1_redock_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "s1_redock.py"), init_globals={"S1REDOCK_ARGS": ARGS})
