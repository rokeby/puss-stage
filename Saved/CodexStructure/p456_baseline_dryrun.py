"""Rehearse p456_baseline_apply.py: every guard, the census and the revert record, no write."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p456_baseline_apply.py"), init_globals={"P456_DRY_RUN": True})
unreal.log("P456_DRY_RUN_FINISHED")
