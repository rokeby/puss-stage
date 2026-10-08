"""Wrapper: grease_v2_ue.py with {'GV2_MODE': 'REVERT_DRY'}.

runpy.run_path executes the file fresh each call (no stale editor module cache).
"""
import os
import runpy

import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "GreaseV2_20261008", "grease_v2_ue.py"), init_globals={'GV2_MODE': 'REVERT_DRY'})
