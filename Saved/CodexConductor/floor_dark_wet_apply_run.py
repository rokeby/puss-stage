"""Runner: floor_dark_wet_apply.py in APPLY mode (see that file's docstring for every gate).
Fresh source every call (runpy reads the file; no cached import). Markers: FLOOR_DW_*|run=<id>.
Content + level write (Gary APPROVED 5 Oct). Run only after a clean FLOOR_DW_DRY_OK in the same editor
session. If DRY listed actors it would bury, paste that exact list into ACK_BURIED after review.
Success: FLOOR_DW_APPLY_OK. Any FLOOR_DW_FAILED after the backup: do not save; restart with Don't Save."""
import os
import runpy

import unreal

ACK_BURIED = ["SM_lily_01_1"]  # 5 Oct conductor: pond lily (siblings at -11.5 and +5.5); 6 of 30 cm sinks, reads as standing in water   # exactly the FLOOR_DW_DRY_BURIED list, if any, after a human looked at it
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "floor_dark_wet_apply.py"), init_globals={"FLOOR_DW_MODE": "APPLY", "FLOOR_DW_ACK_BURIED": ACK_BURIED})
