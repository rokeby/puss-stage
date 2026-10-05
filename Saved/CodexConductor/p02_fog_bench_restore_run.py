"""Run p02_fog_bench.py RESTORE (PIE running): re-applies every original in every P02FogBench/P02FOG-*/ record, newest
first, and hides the ZZ_P02FOG_ pool. Refuses while a capture tick is still armed (it restores itself). Then end
PIE and restart the editor choosing Don't Save."""
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "p02_fog_bench.py"), init_globals={"BENCH_MODE": "RESTORE"})
