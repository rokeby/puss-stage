"""Apply hangar_build.py for one scene (parameters from hangar_apply_mode.json). Builds and saves."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
mode = json.load(open(os.path.join(HERE, "hangar_apply_mode.json"), encoding="utf-8"))
runpy.run_path(os.path.join(HERE, "hangar_build.py"), init_globals={"HANGAR_PARAMS": mode, "HANGAR_APPLY": True})
