"""Run rename_p05_floor_apply.py with RENAME_APPLY."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "rename_p05_floor_apply.py"), init_globals={"RENAME_APPLY": True})
