"""curtain_sleight.py FIXUP_PILE_REVERT for Interaction 1 (5 Oct, offline-written, NOT RUN).

FIXUP_PILE_REVERT: removes the PILE and restores FALL [1675, 2183) exactly (the main record's snapshot_after); saves ONLY the
Interaction sequence; archives the fixup record. Marker CURTAIN_SLEIGHT_FIXUP_PILE_REVERT_OK|run=..
No PIE (refuses; never ends it), Sequencer closed, nothing dirty before.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 1, "CURTAIN_SLEIGHT_FIXUP_PILE_REVERT": True})
