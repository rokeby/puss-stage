"""Run grass_pie_probe.py in mode 'p02' (PIE only; see its docstring)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "grass_pie_probe.py"), init_globals={"GRASS_MODE": "p02"})
