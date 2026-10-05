"""Runner for passage_retime_to_music.py (5 Oct, offline-written, NOT RUN).

Reads passage_retime_to_music_args.json and runs the tool with RETIME_ARGS. The tool re-checks confirm
("<MODE> RETIME"), PIE, Sequencer, census, world, Master-in-sync. DRY writes nothing to Unreal
(passage_retime_to_music_dry.json here). APPLY writes lead/interval/tail timing of the listed Passages, rebuilds the
Master, saves the Show + Master only. REVERT restores the recorded timing tick-exact. Purges cached Saved/ modules
first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "passage_retime_to_music_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "passage_retime_to_music.py"), init_globals={"RETIME_ARGS": ARGS})
