"""Runner: p03_floor.py in the mode p03_floor_args.json names (DRY default; see that file's docstring for every gate).
Fresh source every call (runpy reads the file; no cached import: memory ue58-python-stale-module-cache).
Markers: P03_FLOOR_*|run=<id>. APPLY/REVERT need "confirm": "<MODE> P03FLOOR" and a clean P03_FLOOR_DRY_OK first.
Success: P03_FLOOR_APPLY_OK / P03_FLOOR_REVERT_OK. Any P03_FLOOR_FAILED ending "NOTHING SAVED": restart with Don't Save."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "p03_floor.py"), run_name="__p03_floor_runner__")
