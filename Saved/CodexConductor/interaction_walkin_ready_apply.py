"""interaction_walkin_ready.py APPLY for I2-I5 (5 Oct, offline-written, NOT RUN).

Needs a DRY first (plan digest must match). Edits ONLY the mouth drape's GC section ranges/offsets and its spawn
range, and only where DRY listed a need; never a playback range, never a cut. Expected result on the 30 Sep state:
INTERACTION_WALKIN_READY_APPLY_NOOP (nothing to edit). Otherwise backs up to Backups/PreWalkinReady-<run>/, writes
interaction_walkin_ready_record.json before any change, saves only the touched Interaction sequences, reads back.
Marker INTERACTION_WALKIN_READY_APPLY_OK / _APPLY_NOOP |run=..|master_rebuild_required=false, else _STOPPED.
No PIE (refuses; never ends it), Sequencer closed, clean census.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "interaction_walkin_ready.py"), init_globals={"WALKIN_READY_APPLY": True})
