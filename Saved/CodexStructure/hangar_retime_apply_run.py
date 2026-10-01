"""Run hangar_retime_apply.py with HANGAR_RETIME_APPLY."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "hangar_retime_apply.py"), init_globals={"HANGAR_RETIME_APPLY": True})
