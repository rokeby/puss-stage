"""Runner for passage_end_drape.py (5 Oct, offline-written, NOT RUN).

Reads passage_end_drape_args.json: {"scene": 1..5, "mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S<n>",
"params": {}, "decided_by": "...", "run_id": optional}. The tool itself re-checks confirm, PIE, Sequencer, census.
DRY writes nothing to Unreal. APPLY writes LS_S<n>_HangarRise and the level only. REVERT undoes exactly that.
Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "passage_end_drape_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "passage_end_drape.py"), init_globals={
    "PASSAGE_END_DRAPE_SCENE": ARGS.get("scene"),
    "PASSAGE_END_DRAPE_MODE": ARGS.get("mode"),
    "PASSAGE_END_DRAPE_CONFIRM": ARGS.get("confirm"),
    "PASSAGE_END_DRAPE_PARAMS": ARGS.get("params") or {},
    "PASSAGE_END_DRAPE_DECIDED_BY": ARGS.get("decided_by"),
    "PASSAGE_END_DRAPE_RUN_ID": ARGS.get("run_id"),
})
