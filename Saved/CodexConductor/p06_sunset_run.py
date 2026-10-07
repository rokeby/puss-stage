"""Runner for p06_sunset.py (7 Oct, offline-written, NOT RUN).

Reads p06_sunset_args.json and runs the tool with P06SUNSET_ARGS. The tool re-checks confirm ("<MODE> P06SUNSET"), PIE,
Sequencer, world, census, record. DRY writes nothing to Unreal (p06_sunset_dry.json here). APPLY writes P06's
CelestialCycle (Show) and four rig properties (level), probes the real C++ evaluation, saves the Show + level only.
REVERT restores both from p06_sunset_record.json. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p06_sunset_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p06_sunset.py"), init_globals={"P06SUNSET_ARGS": ARGS})
