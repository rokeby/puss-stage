"""Run s4_predrive_author_apply.py with S4PREDRIVE_REVERT."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "s4_predrive_author_apply.py"), init_globals={"S4PREDRIVE_REVERT": True})
