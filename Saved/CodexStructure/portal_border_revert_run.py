"""Run portal_border_apply.py with BORDER_REVERT."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "portal_border_apply.py"), init_globals={"BORDER_REVERT": True})
