"""Apply structure03_ground_apply.py (landscape block)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "structure03_ground_apply.py"), init_globals={"S03_GROUND_APPLY": True})
