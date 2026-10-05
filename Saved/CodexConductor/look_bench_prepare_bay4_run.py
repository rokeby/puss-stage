"""Run look_bench.py PREPARE: spawn the hidden ZZ_LOOKBENCH_* pool into the EDITOR world.
PIE must NOT be running and the dirty census must be clean. It dirties the map; it never
saves. Discard with a Don't-Save editor restart after the PIE captures (or CLEANUP)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={
    "BENCH_MODE": "PREPARE",
    "BENCH_BAYS": [{"bay": 4}],
})
