"""Re-apply the S2 Arrival after its rebuild, with its own record."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "arrivals_apply.py"), init_globals={"ARRIVALS_APPLY": True, "ARRIVAL_SCENES": (2,), "ARRIVALS_RECORD": os.path.join(HERE, "arrivals_s2_record.json")})
