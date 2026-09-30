"""Run groove_capture.py with the mode in groove_capture_mode.json ({"exposure": ..., "suffix": ...})."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
m = json.load(open(os.path.join(HERE, "groove_capture_mode.json"), encoding="utf-8"))
runpy.run_path(os.path.join(HERE, "groove_capture.py"), init_globals={"GROOVE_EXPOSURE": m["exposure"], "GROOVE_SUFFIX": m["suffix"]})
