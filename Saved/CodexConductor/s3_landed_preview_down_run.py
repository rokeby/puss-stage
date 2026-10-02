"""Put every hangar DOWN from landed-preview mode; this never saves."""
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
        "HANGAR_LANDED_PREVIEW_MODE": "DOWN",
        "HANGAR_LANDED_PREVIEW_IDS": "all",
    },
)
