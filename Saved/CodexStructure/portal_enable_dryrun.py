"""Rehearse portal_enable_apply.py read-only: every guard, the revert record and
the predicted piece count, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "portal_enable_apply.py"), init_globals={"PORTAL_ENABLE_DRY_RUN": True})
unreal.log("PORTAL_ENABLE_DRY_RUN_FINISHED")
