"""Run s3_marble_tune.py with the explicit APPLY flag."""
import os
import runpy
import sys

import unreal

sys.modules.pop("s3_marble_tune", None)
here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(here, "s3_marble_tune.py"), init_globals={"S3_MARBLE_TUNE_APPLY": True})
