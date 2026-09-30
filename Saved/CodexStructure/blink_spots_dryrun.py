"""Rehearse blink_spots_apply.py: every guard, the world-space traces and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "blink_spots_apply.py"), init_globals={"BLINK_DRY_RUN": True})
unreal.log("BLINK_DRY_RUN_FINISHED")
