"""Rehearse p01_station1_symmetry_apply.py: every guard and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "p01_station1_symmetry_apply.py"), init_globals={"P01_STATION1_DRY_RUN": True})
except RuntimeError as exc:
    if "P01_STATION1_DRY_RUN_COMPLETE" not in str(exc):
        raise
unreal.log("P01_STATION1_DRY_RUN_FINISHED")
