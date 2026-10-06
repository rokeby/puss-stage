"""Runner: fence_stack_750.py in the mode fence_stack_750_args.json names (DRY default; see that file's docstring).
Fresh source every call (runpy reads the file; no cached import: memory ue58-python-stale-module-cache).
Markers: FENCE750_*|run=<id>. APPLY/REVERT need "confirm": "<MODE> FENCE750" and a clean FENCE750_DRY_OK first.
Success: FENCE750_APPLY_OK / FENCE750_REVERT_OK. Any FENCE750_FAILED ending "NOTHING SAVED": restart with Don't Save."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "fence_stack_750.py"), run_name="__fence_stack_750_runner__")
