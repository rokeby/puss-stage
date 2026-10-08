"""Fresh runner for gobo_spot.py through ExecuteProjectPythonFile (relativeSavedPath
"CodexConductor/GoboSpot_20261008/gobo_spot_run.py").  Reads gobo_spot_args.json next to it; purges any cached
module from this folder first (memory ue58-python-stale-module-cache).  Same pattern as animated_gobo_run.py."""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "GoboSpot_20261008")
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "gobo_spot_args.json"), encoding="utf-8") as handle:
    ARGS = json.load(handle)

runpy.run_path(os.path.join(HERE, "gobo_spot.py"), run_name="__gobo_spot_runner__",
               init_globals={"GOBO_SPOT_ARGS": ARGS})
