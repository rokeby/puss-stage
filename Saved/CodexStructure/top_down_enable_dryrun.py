"""Rehearse top_down_enable_apply.py: every guard, the census and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "top_down_enable_apply.py"), init_globals={"TOP_DOWN_DRY_RUN": True})
except RuntimeError as exc:
    if "TOP_DOWN_DRY_RUN_COMPLETE" not in str(exc):
        raise
unreal.log("TOP_DOWN_DRY_RUN_FINISHED")
