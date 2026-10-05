"""Run look_bench.py in RESTORE mode (PIE running: restores every capture record of the newest PREPARE and hides the pool;
then end PIE and restart the editor choosing Don't Save)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={"BENCH_MODE": "RESTORE"})
