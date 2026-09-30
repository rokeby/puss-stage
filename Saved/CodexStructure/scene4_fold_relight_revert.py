"""revert scene4_fold_relight.py via runpy."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_relight.py"), init_globals={"FOLD_RELIGHT_REVERT": True})
