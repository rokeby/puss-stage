"""Purge Saved modules, then run s3_mural_lower.py main() (mode from s3_mural_lower_args.json; DRY default).
Request: s3_mural_lower_request.json (MCP ExecuteProjectPythonFile)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "s3_mural_lower.py"))["main"]()
