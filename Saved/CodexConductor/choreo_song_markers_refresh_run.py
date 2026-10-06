"""Runner for choreo_song_markers_refresh.py (5 Oct, offline-written, NOT RUN).

Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads
choreo_song_markers_refresh_args.json and runs the tool with SONGMARKER_ARGS. The tool re-checks confirm
("<MODE> SONGMARKERS"), world, PIE, Sequencer, census. DRY writes only choreo_song_markers_refresh_dry.json here.
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "choreo_song_markers_refresh_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "choreo_song_markers_refresh.py"), init_globals={"SONGMARKER_ARGS": ARGS})
