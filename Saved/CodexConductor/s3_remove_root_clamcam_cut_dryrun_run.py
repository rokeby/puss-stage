"""Run s3_remove_root_clamcam_cut.py in its default read-only dry-run mode."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(os.path.join(HERE, "s3_remove_root_clamcam_cut.py"))
