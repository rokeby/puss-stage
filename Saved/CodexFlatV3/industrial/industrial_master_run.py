"""Purge project-Saved modules, then run make_industrial_master.py.

Transport: industrial_master_request.json through ExecuteProjectPythonFile.
"""
import os
import runpy

import unreal


SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(SAVED, "CodexFlatV3", "industrial", "make_industrial_master.py"),
               run_name="__industrial_master_runner__")
