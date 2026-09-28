"""Rehearse p01_opening_apply.py against the live Show without writing to it:
every guard, the revert record, then stop before the first write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "p01_opening_apply.py"), init_globals={"P01_DRY_RUN": True})
except RuntimeError as exc:
    if "P01_OPENING_DRY_RUN_COMPLETE" not in str(exc):
        raise
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"P01_OPENING_DRY_RUN_FINISHED|dirty={dirty}")
