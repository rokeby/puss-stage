"""Rehearse groove_material_apply.py: guards, counts and the revert record; no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "groove_material_apply.py"), init_globals={"GROOVE_DRY_RUN": True})
unreal.log("GROOVE_DRY_RUN_FINISHED")
