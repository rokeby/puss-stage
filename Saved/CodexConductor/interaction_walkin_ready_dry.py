"""interaction_walkin_ready.py DRY for I2-I5 (+ I1 read-only reference) (5 Oct, offline-written, NOT RUN).

Read-only: writes only JSON under Saved/CodexConductor (interaction_walkin_ready_dry.json,
walkin_transitions.proposed.json/.diff). Marker INTERACTION_WALKIN_READY_DRY_OK|run=..|mutated=0.
No PIE (refuses; never ends it), Sequencer closed, show world.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "interaction_walkin_ready.py"), init_globals={"WALKIN_READY_APPLY": False})
