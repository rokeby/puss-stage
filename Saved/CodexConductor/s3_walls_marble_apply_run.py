"""Run s3_walls_marble.py with the explicit APPLY flag."""
import os
import runpy
import sys

import unreal

sys.modules.pop("s3_walls_marble", None)
here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(here, "s3_walls_marble.py"), init_globals={"S3_WALLS_MARBLE_APPLY": True})
