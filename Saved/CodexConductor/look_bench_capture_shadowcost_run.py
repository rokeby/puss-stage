"""5 Oct: P04 shadow cost. CAPTURE bay 4 alternating base / shadows twice; frame_time_probe.py runs across it and the
state windows are cut from this run's LOOK_BENCH_SETTLE log timestamps. Needs PREPARE (bay 4) then PIE running."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={
    "BENCH_MODE": "CAPTURE", "BENCH_PARAMS": {"bay": 4},
    "BENCH_STATES": [["base", []], ["shadows", ["shadows"]], ["base_b", []], ["shadows_b", ["shadows"]]]})
