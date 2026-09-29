"""Rehearse board_material_apply.py: every guard and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "board_material_apply.py"), init_globals={"BOARD_MATERIAL_DRY_RUN": True})
unreal.log("BOARD_MATERIAL_DRY_RUN_FINISHED")
