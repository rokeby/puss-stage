"""Purge Saved modules, then run s3_backwall_marble.py (mode from s3_backwall_marble_args.json; DRY default)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "s3_backwall_marble.py"))
