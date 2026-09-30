"""Revert arrivals_apply.py: restore the five rises' recorded keys, delete the five Arrivals."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "arrivals_apply.py"), init_globals={"ARRIVALS_REVERT": True})
