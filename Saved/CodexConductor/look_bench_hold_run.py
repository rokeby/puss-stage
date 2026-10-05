"""Run look_bench.py in HOLD mode (needs PREPARE first, then PIE running; uses the prepared pool, never spawns; never starts or ends PIE)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={"BENCH_MODE": "HOLD"})
