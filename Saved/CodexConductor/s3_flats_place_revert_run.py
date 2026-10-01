"""Run s3_flats_place.py with its explicit revert flag."""
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
runpy.run_path(
    os.path.join(HERE, "s3_flats_place.py"),
    init_globals={"S3_FLATS_REVISION": 2, "S3_FLATS_PLACE_REVERT": True},
)
