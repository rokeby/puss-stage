"""Run s3_pit_deck_apply.py in its default dry-run mode."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexStructure",
)
runpy.run_path(os.path.join(HERE, "s3_pit_deck_apply.py"))
