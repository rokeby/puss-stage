"""Runner for opening_own_rail.py (5 Oct, offline-written, NOT RUN).

Reads opening_own_rail_args.json and runs the tool with OPENING_RAIL_ARGS. The tool re-checks confirm
("<MODE> OPENINGRAIL"), PIE, Sequencer, census, world and Master-in-sync. DRY writes nothing to Unreal (a report json
here). APPLY imports SW_Opening_Tuning_Sketch2 and writes the Show + Master only. REVERT removes the appended rail and
restores both bindings (the wave is kept unless "delete_asset_on_revert": true). Purges cached Saved/ modules first
(memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "opening_own_rail_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "opening_own_rail.py"), init_globals={"OPENING_RAIL_ARGS": ARGS})
