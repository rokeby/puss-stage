"""Runner for opening_readback.py (5 Oct, offline-written, NOT RUN). READ-ONLY: purges cached Saved/ modules
(memory ue58-python-stale-module-cache), then runs the readback. Writes only opening_readback_<run>.json here."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "opening_readback.py"))
