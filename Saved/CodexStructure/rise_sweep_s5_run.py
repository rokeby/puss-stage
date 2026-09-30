"""Run rise_sweep_measure_readonly.py for Scene 5."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "rise_sweep_measure_readonly.py"), init_globals={"SWEEP_SCENE": 5})
