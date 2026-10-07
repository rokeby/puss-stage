"""Runner for hangar_resize_s4.py (7 Oct, offline-written, NOT RUN).

Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads hangar_resize_s4_args.json and runs
the tool with HANGARRESIZES4_ARGS. The tool re-checks confirm ("<MODE> HANGARRESIZES4"), PIE, world, Sequencer, ZZ_
actors and the census. DRY writes nothing to Unreal (hangar_resize_s4_dry.json here).
"""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
HERE = os.path.join(SAVED, "CodexStructure")
with open(os.path.join(HERE, "hangar_resize_s4_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "hangar_resize_s4.py"), init_globals={"HANGARRESIZES4_ARGS": ARGS})
