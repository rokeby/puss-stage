"""Runner for place_paperprosc.py. Purges cached Saved modules before every MCP execution."""
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(SAVED, "CodexFlatV3", "paperprosc", "place_paperprosc.py"))
