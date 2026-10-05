"""curtain_sleight.py APPLY for Interaction 1 (5 Oct, offline-written, NOT RUN).

APPLY (writes LS_Interaction_01, the Master, the Show if the rebuild dirties it, and the level). Needs curtain_sleight_overrides.json decided_by + interactions [1], a DRY plan file with the same digest, and every refusal clear. Marker CURTAIN_SLEIGHT_APPLY_OK|run=..
No PIE (refuses; never ends it), Sequencer closed.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 3, "CURTAIN_SLEIGHT_APPLY": True})
