"""Dry run of mouth_lanterns_apply.py: the plan and the exposure report, nothing written."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "mouth_lanterns_apply.py"), init_globals={"MOUTH_LANTERN_DRY_RUN": True})
