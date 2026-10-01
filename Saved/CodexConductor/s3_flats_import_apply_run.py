"""Run s3_flats_import.py with its explicit apply flag."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(
    os.path.join(HERE, "s3_flats_import.py"),
    init_globals={"S3_FLATS_REVISION": 2, "S3_FLATS_IMPORT_APPLY": True},
)
