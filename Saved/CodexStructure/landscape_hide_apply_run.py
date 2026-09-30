"""Apply landscape_hide_apply.py (landscape block)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "landscape_hide_apply.py"), init_globals={"LS_HIDE_APPLY": True})
