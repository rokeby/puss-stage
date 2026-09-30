"""Rehearse scene4_uplight_apply.py: guards, plan and record; no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_uplight_apply.py"), init_globals={"S4_UPLIGHT_DRY_RUN": True})
