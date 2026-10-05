"""Runner: floor_dark_wet_apply.py in DRY mode (see that file's docstring for every gate).
Fresh source every call (runpy reads the file; no cached import). Markers: FLOOR_DW_*|run=<id>.
Mutates nothing; writes Saved/CodexConductor/floor_dark_wet_dry_<run>.json. Verdict FLOOR_DW_DRY_OK or _REFUSED."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "floor_dark_wet_apply.py"), init_globals={"FLOOR_DW_MODE": "DRY", "FLOOR_DW_ACK_BURIED": []})
