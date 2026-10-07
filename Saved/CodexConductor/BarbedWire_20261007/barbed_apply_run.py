"""Runner: barbed_apply.py in the mode barbed_apply_args.json names (DRY default; see that file's docstring).
Fresh source every call (runpy; no cached import: memory ue58-python-stale-module-cache).
Markers BW_APPLY_*|run=<id>. Success: BW_APPLY_DRY_OK / BW_APPLY_OK / BW_APPLY_REVERT_OK.
Any BW_APPLY_FAILED ending "NOTHING SAVED": restart the editor with Don't Save."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor", "BarbedWire_20261007")
runpy.run_path(os.path.join(HERE, "barbed_apply.py"), run_name="__barbed_apply_runner__")
