"""Rehearse structure_refit_all.py read-only: the guards and the before-state
(expected: IsStructureCurrent false for all six after the 28 Sep build)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
try:
    runpy.run_path(os.path.join(HERE, "structure_refit_all.py"), init_globals={"STRUCTURE_REFIT_DRY_RUN": True})
except RuntimeError as exc:
    if "STRUCTURE_REFIT_DRY_RUN_COMPLETE" not in str(exc):
        raise
unreal.log("STRUCTURE_REFIT_DRY_RUN_FINISHED")
