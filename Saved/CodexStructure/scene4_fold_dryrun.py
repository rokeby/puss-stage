"""Rehearse scene4_fold_apply.py: the numeric sign choice, swing checks and revert record; no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_apply.py"), init_globals={"S4_FOLD_DRY_RUN": True})
unreal.log("S4_FOLD_DRY_RUN_FINISHED")
