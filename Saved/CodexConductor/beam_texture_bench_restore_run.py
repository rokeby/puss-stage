"""Run beam_texture_bench.py RESTORE (PIE running): re-applies every original in this session's BeamTextureBench/
BEAMTEX-*/ records (newest first) and hides the ZZ_BEAMTEX_ pool. Refuses while a capture tick is still armed (it
restores itself). Then end PIE and restart the editor choosing Don't Save (discards the pool, the dirty map and the
unsaved /Game/ZZ_Bench/BeamTexture materials)."""
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "beam_texture_bench.py"), init_globals={"BENCH_MODE": "RESTORE"})
