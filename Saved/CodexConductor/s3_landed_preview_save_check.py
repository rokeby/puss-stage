"""Read-only save guard for the S3 landed-preview pose."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(
    os.path.join(HERE, "s3_landed_preview.py"),
    init_globals={
        "S3_LANDED_PREVIEW_MODE": "STATUS",
        "S3_LANDED_PREVIEW_SAVE_CHECK": True,
    },
)
