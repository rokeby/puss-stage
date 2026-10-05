"""Runner for walking_music_swap.py (5 Oct, offline-written, NOT RUN).

Reads walking_music_swap_args.json and runs the tool with WALKING_ARGS. The tool re-checks confirm
("<MODE> WALKING MUSIC"), PIE, Sequencer, census, world, Master-in-sync. DRY writes nothing to Unreal (a report json
here). APPLY imports the args.apply_passages SoundWaves and writes the Show + Master only. REVERT restores the rails
recorded for that passage set (sounds kept unless "delete_assets": true). Purges cached Saved/ modules first
(memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "walking_music_swap_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "walking_music_swap.py"), init_globals={"WALKING_ARGS": ARGS})
