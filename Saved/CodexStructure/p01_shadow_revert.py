"""Run p01_shadow_pass_apply.py with {"P01_SHADOW_REVERT": True}."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p01_shadow_pass_apply.py"), init_globals={"P01_SHADOW_REVERT": True})
