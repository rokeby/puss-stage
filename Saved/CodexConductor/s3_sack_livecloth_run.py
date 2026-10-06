"""Purge Saved modules (stale-module trap), then run s3_sack_livecloth.py with s3_sack_livecloth_args.json."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "s3_sack_livecloth.py"))
