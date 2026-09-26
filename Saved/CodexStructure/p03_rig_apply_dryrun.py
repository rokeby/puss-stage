"""Rehearse p03_rig_apply.py against the live Show without writing to it: every
guard, the reworked and rig light lists, and the revert record, then stop."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "p03_rig_apply.py"), init_globals={"P03_DRY_RUN": True})
except RuntimeError as exc:
    if "P03_RIG_DRY_RUN_COMPLETE" not in str(exc):
        raise
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"P03_RIG_DRY_RUN_FINISHED|dirty={dirty}")
