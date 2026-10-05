"""Run look_bench.py CLEANUP (optional): delete the tagged ZZ_LOOKBENCH_* editor actors
WITHOUT saving. PIE must NOT be running; refuses if any dirty package is not PREPARE's own.
A Don't-Save restart is still required afterwards (the map stays dirty)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "look_bench.py"), init_globals={"BENCH_MODE": "CLEANUP"})
