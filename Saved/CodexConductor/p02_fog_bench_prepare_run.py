"""Run p02_fog_bench.py PREPARE: spawn the hidden ZZ_P02FOG_MIST_* Local Fog Volumes into the EDITOR world.
PIE must NOT be running and the dirty census must be clean. It dirties the map; it never saves. Discard with a
Don't-Save editor restart after the PIE capture + RESTORE."""
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "p02_fog_bench.py"), init_globals={"BENCH_MODE": "PREPARE"})
