"""P01 shadow capture, after."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p01_shadow_capture.py"), init_globals={"P01_SHADOW_SUFFIX": "_after"})
