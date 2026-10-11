"""Apply nest_apply.py for Scene 5, with its own record."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "nest_apply.py"), init_globals={"NEST_APPLY": True, "NEST_SCENES": (5,), "NEST_RECORD": os.path.join(HERE, "nest_s5_record.json")})
