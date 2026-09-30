"""Apply p04_arrival_apply.py (re-key the rise to start at the backcloth release, place the S4 Arrival)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p04_arrival_apply.py"), init_globals={"P04_ARRIVAL_APPLY": True})
