"""Run mouth_floor_apply.py for P05 (apply)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "mouth_floor_apply.py"), init_globals={"MOUTH": "P05", "MOUTHFLOOR_APPLY": True})
