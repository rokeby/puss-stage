"""Fresh-file entrypoint for Q6 review_stills_driver.py."""
import os
import runpy

import unreal

base = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexFlatV3", "review_stills")
purge = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                     "CodexConductor", "purge_saved_module_cache.py")
if os.path.isfile(purge):
    runpy.run_path(purge)
runpy.run_path(os.path.join(base, "review_stills_driver.py"),
               init_globals={"REVIEW_STILLS_EXECUTE": True})
