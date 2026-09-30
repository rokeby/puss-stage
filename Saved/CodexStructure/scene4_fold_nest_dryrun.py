"""Rehearse scene4_fold_nest.py: derive the speed-dial sizes, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_nest.py"), init_globals={"S4_NEST_DRY_RUN": True})
