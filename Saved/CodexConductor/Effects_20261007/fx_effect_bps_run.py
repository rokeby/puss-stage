"""Entrypoint for fx_effect_bps.py via ExecuteProjectPythonFile (request: fx_effect_bps_request.json). OFFLINE-WRITTEN
7 Oct, never run. Purges stale Saved/ modules first (ue58-python-stale-module-cache), then runs the tool by path."""
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
CORE_DIR = os.path.join(SAVED, "CodexConductor")
runpy.run_path(os.path.join(CORE_DIR, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(CORE_DIR, "Effects_20261007", "fx_effect_bps.py"), run_name="__fx_effect_bps_runner__")
