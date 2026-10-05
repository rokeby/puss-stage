"""Run look_bench.py in RESTORE mode (PIE must already be running; never starts or ends PIE)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={"BENCH_MODE": "RESTORE"})
