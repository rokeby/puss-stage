"""5 Oct: P04 shadow cost. HOLD bay 4 with ONLY the shadows toggle for 75 s (frame_time_probe.py measures inside it).
Needs PREPARE first, then PIE running; never starts or ends PIE; restores and verifies at the end."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={
    "BENCH_MODE": "HOLD", "BENCH_TOGGLES": ["shadows"], "BENCH_PARAMS": {"bay": 4, "hold_seconds": 75.0}})
