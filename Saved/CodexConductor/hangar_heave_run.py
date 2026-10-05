"""Runner for hangar_heave.py (5 Oct, offline-written, NOT RUN).

Reads hangar_heave_args.json: {"scene": 1..6, "mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S<n>",
"params": {}, "decided_by": "...", "run_id": optional}. The tool itself re-checks confirm, PIE, Sequencer, census.
DRY writes nothing to Unreal (a report json in Saved/CodexConductor). APPLY writes LS_S<n>_HangarRise only.
REVERT undoes exactly that. Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "hangar_heave_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "hangar_heave.py"), init_globals={
    "HANGAR_HEAVE_SCENE": ARGS.get("scene"),
    "HANGAR_HEAVE_MODE": ARGS.get("mode"),
    "HANGAR_HEAVE_CONFIRM": ARGS.get("confirm"),
    "HANGAR_HEAVE_PARAMS": ARGS.get("params") or {},
    "HANGAR_HEAVE_DECIDED_BY": ARGS.get("decided_by"),
    "HANGAR_HEAVE_RUN_ID": ARGS.get("run_id"),
})
