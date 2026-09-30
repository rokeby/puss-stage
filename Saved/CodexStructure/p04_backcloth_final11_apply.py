"""Apply p04_backcloth_section_apply.py for final11 (Soft goods, 30 Sep): label "P04 Backcloth (baked)",
BackclothLeadS 3.0 s (measured), release in cache 1.0 s passed ONLY as a cross-check (the script reads it
from DropBake/final11_backcloth_p04_a06.json itself)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "p04_backcloth_section_apply.py"),
               init_globals={"P04_CLOTH_APPLY": True, "CLOTH_LABEL": "P04 Backcloth (baked)", "BACKCLOTH_LEAD_S": 3.0, "RELEASE_IN_CACHE_S": 1.0})
