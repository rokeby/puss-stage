"""Run s3_cast_reveal_apply.py with S3_CAST_REVEAL_APPLY."""
import os
import runpy

import unreal


HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "s3_cast_reveal_apply.py"), init_globals={"S3_CAST_REVEAL_APPLY": True})
