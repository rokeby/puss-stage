"""Runner for shadow_play_spot.py (5 Oct, offline-written, NOT RUN).

Reads shadow_play_spot_args.json: {"interaction": n, "mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> I<n>",
"params": {...}, "run_id": optional}. The tool refuses unless confirm == "<MODE> I<n>".
DRY is read-only (JSON under Saved/CodexConductor only). APPLY/REVERT write the Interaction sequence asset ONLY.
No PIE (refuses; never ends it), Sequencer closed, clean census.
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
with open(os.path.join(HERE, "shadow_play_spot_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "shadow_play_spot.py"), init_globals={
    "SHADOW_PLAY_SPOT_INTERACTION": int(ARGS["interaction"]),
    "SHADOW_PLAY_SPOT_MODE": str(ARGS["mode"]),
    "SHADOW_PLAY_SPOT_CONFIRM": ARGS.get("confirm"),
    "SHADOW_PLAY_SPOT_PARAMS": ARGS.get("params") or {},
    "SHADOW_PLAY_SPOT_RUN_ID": ARGS.get("run_id"),
})
