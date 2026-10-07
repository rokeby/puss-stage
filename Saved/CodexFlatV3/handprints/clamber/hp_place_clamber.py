"""APPLY: hp_place_decals.py in clamber mode (backup, record, spawn, read back, save current level only).

runpy.run_path executes the placer fresh each call (no stale editor module cache).
"""
import os
import runpy

import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "handprints", "hp_place_decals.py"), init_globals={"HP_PLACE_MODE": "clamber"})
