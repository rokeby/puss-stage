"""curtain_sleight.py DRY for Interaction 2 (5 Oct, offline-written, NOT RUN).

DRY (read-only: writes only JSON under Saved/CodexConductor). Marker CURTAIN_SLEIGHT_DRY_OK|run=..|mutated=0.
No PIE (refuses; never ends it), Sequencer closed.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 2})
