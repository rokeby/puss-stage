"""Run s3_diorama_move.py with the explicit revert flag."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(
    os.path.join(HERE, "s3_diorama_move.py"),
    init_globals={"S3_DIORAMA_REVERT": True},
)
