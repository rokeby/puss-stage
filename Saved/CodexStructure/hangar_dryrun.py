"""Dry run of hangar_build.py for one scene: the plan, checks and (Scene 4) the comparison
with the live hangar. Scene and sizes from hangar_dryrun_mode.json. Writes nothing to the level."""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
mode = json.load(open(os.path.join(HERE, "hangar_dryrun_mode.json"), encoding="utf-8"))
runpy.run_path(os.path.join(HERE, "hangar_build.py"), init_globals={"HANGAR_PARAMS": mode})
