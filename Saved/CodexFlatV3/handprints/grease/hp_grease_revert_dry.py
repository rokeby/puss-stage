"""Wrapper: hp_place_grease.py with {'HP_GREASE_MODE': 'REVERT_DRY'}.

runpy.run_path executes the file fresh each call (no stale editor module cache).
"""
import os
import runpy

import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "handprints", "grease", "hp_place_grease.py"), init_globals={'HP_GREASE_MODE': 'REVERT_DRY'})
