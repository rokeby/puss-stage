"""Run s3_remove_root_clamcam_cut.py with the explicit apply flag."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(
    os.path.join(HERE, "s3_remove_root_clamcam_cut.py"),
    init_globals={"S3_CLAMCUT_APPLY": True},
)
