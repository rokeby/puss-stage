"""Run look_bench.py CAPTURE on P04 bay 8 (glint target: Wing 008 R, ruined_gallery_R_v3).
Order: PREPARE in the editor world (look_bench_prepare_run.py), then begin PIE, then this.
It uses the prepared pool only (no spawns); it never starts or ends PIE."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={
    "BENCH_MODE": "CAPTURE",
    "BENCH_PARAMS": {"bay": 8},
    "BENCH_STATES": [["base", []], ["glint", ["glint"]], ["glint_wet", ["glint", "floor_wet"]],
                     ["glint_wet_haze", ["glint", "floor_wet", "haze"]]],
})
