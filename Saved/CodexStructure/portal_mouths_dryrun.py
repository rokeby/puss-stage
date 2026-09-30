"""Rehearse portal_mouths_apply.py read-only."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "portal_mouths_apply.py"), init_globals={"PORTAL_MOUTHS_DRY_RUN": True})
