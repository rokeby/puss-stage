"""Purge Saved module cache, then extend the applied Job A record with S3."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "hangar_exit_doors.py"),
               init_globals={"HANGAR_EXIT_DOORS_APPLY": True,
                             "HANGAR_EXIT_DOORS_S3_ONLY": True})
