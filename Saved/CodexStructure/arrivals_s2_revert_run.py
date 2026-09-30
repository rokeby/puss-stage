"""Revert the S2 Arrival only (landscape block S2 rebuild)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "arrivals_apply.py"), init_globals={"ARRIVALS_REVERT": True, "ARRIVAL_SCENES": (2,)})
