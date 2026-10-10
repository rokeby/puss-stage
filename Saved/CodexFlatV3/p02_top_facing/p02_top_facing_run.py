"""Guarded project-Python runner for Job 106."""
import os
import runpy

import unreal

saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(saved, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(saved, "CodexFlatV3", "p02_top_facing", "p02_top_facing.py"))
