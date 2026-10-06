"""Runner: p02_floor.py in the mode p02_floor_args.json names (DRY default; see that file's docstring for every gate).
Fresh source every call (runpy reads the file; no cached import: memory ue58-python-stale-module-cache).
Markers: P02_FLOOR_*|run=P02FLOOR-<id> (p02_floor_walnut.py shares the prefix with run ids P02FL-: parse by run id).
APPLY/REVERT need "confirm": "<MODE> P02FLOOR" and a clean P02_FLOOR_DRY_OK first.
Success: P02_FLOOR_APPLY_OK / P02_FLOOR_REVERT_OK. Any P02_FLOOR_FAILED ending "NOTHING SAVED": restart with Don't Save."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "p02_floor.py"), run_name="__p02_floor_runner__")
