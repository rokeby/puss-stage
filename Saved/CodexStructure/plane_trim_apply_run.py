"""Apply plane_trim_apply.py (end the S1/S5/S6 Passage floor planes at their hinge lines)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "plane_trim_apply.py"), init_globals={"PLANE_TRIM_APPLY": True})
