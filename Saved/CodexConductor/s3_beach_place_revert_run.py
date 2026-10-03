"""Run s3_beach_place.py with the explicit REVERT flag."""
import os
import runpy
import sys

import unreal

sys.modules.pop("s3_beach_place", None)
here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(here, "s3_beach_place.py"), init_globals={"S3_BEACH_REVERT": True})
