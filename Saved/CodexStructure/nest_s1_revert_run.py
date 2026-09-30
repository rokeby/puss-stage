"""Revert nest_apply.py for Scene 1 (the only unnested Scene whose sequence is long enough for its rise today)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "nest_apply.py"), init_globals={"NEST_REVERT": True, "NEST_SCENES": (1,)})
