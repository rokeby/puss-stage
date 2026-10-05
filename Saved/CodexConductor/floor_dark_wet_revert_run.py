"""Runner: floor_dark_wet_apply.py in REVERT mode (see that file's docstring for every gate).
Fresh source every call (runpy reads the file; no cached import). Markers: FLOOR_DW_*|run=<id>.
Restores the four slabs' recorded transforms and materials, destroys only the tagged P04 slab, keeps
MI_Floor_DarkWet, saves the level only. Success: FLOOR_DW_REVERT_OK."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "floor_dark_wet_apply.py"), init_globals={"FLOOR_DW_MODE": "REVERT"})
