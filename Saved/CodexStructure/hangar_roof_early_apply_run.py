"""Run hangar_roof_early_apply.py with the explicit apply flag."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexStructure",
)
runpy.run_path(
    os.path.join(HERE, "hangar_roof_early_apply.py"),
    init_globals={"HANGAR_ROOF_EARLY_APPLY": True},
)
