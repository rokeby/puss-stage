"""curtain_sleight.py FIXUP_PILE for Interaction 1 (5 Oct, offline-written, NOT RUN).

FIXUP_PILE: splits the applied I1 drape FALL [1675, 2183) into FALL [1675, fall_end) + PILE [fall_end, 2183) holding the last cache sample.
Needs curtain_sleight_record_I1.json applied and the live sequence exactly its snapshot_after. Backs up the sequence, writes
curtain_sleight_fixup_pile_record_I1.json, saves ONLY LS_Interaction_01_WashingTheBoy. Marker CURTAIN_SLEIGHT_FIXUP_PILE_OK|run=..
Way out: curtain_sleight_fixup_pile_revert_I1.py FIRST, then curtain_sleight_revert_I1.py (the main REVERT refuses otherwise).
No PIE (refuses; never ends it), Sequencer closed, nothing dirty before.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 1, "CURTAIN_SLEIGHT_FIXUP_PILE": True})
