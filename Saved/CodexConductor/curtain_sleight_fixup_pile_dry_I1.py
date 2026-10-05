"""curtain_sleight.py FIXUP_PILE_DRY for Interaction 1 (5 Oct, offline-written, NOT RUN).

FIXUP_PILE DRY (mutates nothing): every FIXUP gate + the plan from the LIVE cache length; writes curtain_sleight_fixup_pile_I1_dry.json. Marker CURTAIN_SLEIGHT_FIXUP_PILE_DRY_OK|run=..|fall_end=..|pile=[..)
No PIE (refuses; never ends it), Sequencer closed, nothing dirty before.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "curtain_sleight.py"), init_globals={"CURTAIN_SLEIGHT_INTERACTION": 1, "CURTAIN_SLEIGHT_FIXUP_PILE_DRY": True})
