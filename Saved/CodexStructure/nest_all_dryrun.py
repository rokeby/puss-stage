"""Dry run of nest_apply.py for all five unnested scenes (shows which fit)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "nest_apply.py"), init_globals={"NEST_SCENES": (1, 2, 3, 5, 6)})
