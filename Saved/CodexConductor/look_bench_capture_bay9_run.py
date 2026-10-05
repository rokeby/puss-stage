"""Run look_bench.py CAPTURE on P04 bay 9 (glint target: Wing 009 R, coventry_ruin_R_v1_t5j; Gary 5 Oct moved the wet test here).
PIE must already be running; this never starts or ends PIE."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={
    "BENCH_MODE": "CAPTURE",
    "BENCH_PARAMS": {"bay": 9, "glint_mesh_contains": "coventry_ruin_R_v1"},
    "BENCH_STATES": [["base", []], ["glint", ["glint"]], ["glint_wet", ["glint", "floor_wet"]],
                     ["glint_wet_haze", ["glint", "floor_wet", "haze"]]],
})
