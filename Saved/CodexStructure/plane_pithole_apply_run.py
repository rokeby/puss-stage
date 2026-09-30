"""Apply plane_pithole_apply.py (pit-hole floors at S1/S5/S6)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "plane_pithole_apply.py"), init_globals={"PIT_APPLY": True})
