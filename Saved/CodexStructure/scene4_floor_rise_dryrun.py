"""Rehearse scene4_floor_rise_apply.py: the arc checks and plan; no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_floor_rise_apply.py"), init_globals={"FLOOR_RISE_DRY_RUN": True})
