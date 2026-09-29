"""Rehearse floors_to_stage_apply.py: every guard and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "floors_to_stage_apply.py"), init_globals={"FLOORS_DRY_RUN": True})
except RuntimeError as exc:
    if "FLOORS_TO_STAGE_DRY_RUN_COMPLETE" not in str(exc):
        raise
unreal.log("FLOORS_TO_STAGE_DRY_RUN_FINISHED")
