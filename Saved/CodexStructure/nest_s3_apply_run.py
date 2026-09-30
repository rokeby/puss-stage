"""Apply nest_apply.py for Scene 3 (fits: 65.5 s scene, 31 s rise), own record."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "nest_apply.py"), init_globals={"NEST_APPLY": True, "NEST_SCENES": (3,), "NEST_RECORD": os.path.join(HERE, "nest_s3_record.json")})
