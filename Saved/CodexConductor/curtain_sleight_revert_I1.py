"""curtain_sleight.py REVERT for Interaction 1 (5 Oct, offline-written, NOT RUN).

REVERT (removes exactly what curtain_sleight_record_I1.json lists; refuses if the sequence drifted since APPLY). Marker CURTAIN_SLEIGHT_REVERT_OK|run=..
No PIE (refuses; never ends it), Sequencer closed.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 1, "CURTAIN_SLEIGHT_REVERT": True})
