"""Dry run of scene4_lattice_glow_apply.py: the plan, nothing written."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_lattice_glow_apply.py"), init_globals={"LATTICE_GLOW_DRY_RUN": True})
