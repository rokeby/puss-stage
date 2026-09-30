"""Revert p04_backcloth_section_apply.py (removes the cloth binding from LS_S4_HangarRise, clears the
S4 Arrival's backcloth properties; reads the record, needs no timing inputs)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p04_backcloth_section_apply.py"), init_globals={"P04_CLOTH_REVERT": True, "CLOTH_LABEL": "P04 Backcloth (baked)"})
