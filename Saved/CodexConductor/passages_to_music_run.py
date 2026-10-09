"""Conductor runner for P33 passages_to_music.py.

The tool itself checks world, PIE/SIE, Sequencer, exact dirty census, confirm
string, DRY review hash, backups, named saves, read-back, and run-id marker.
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "passages_to_music_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "passages_to_music.py"), init_globals={"PASSAGES_TO_MUSIC_ARGS": ARGS})
