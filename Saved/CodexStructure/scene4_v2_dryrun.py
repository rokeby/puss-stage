"""Rehearse scene4_v2_apply.py: the assembled-geometry arc checks and the plan; no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_v2_apply.py"), init_globals={"S4_V2_DRY_RUN": True})
