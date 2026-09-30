"""Run s4_arrival_light_apply.py with S4LIGHT_APPLY."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "s4_arrival_light_apply.py"), init_globals={"S4LIGHT_APPLY": True})
