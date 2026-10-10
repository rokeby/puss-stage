"""Guarded-route runner for paperprosc_fringe_import.py; offline-written, not run."""
import os
import runpy
import unreal

saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(saved, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(
    os.path.join(saved, "CodexFlatV3", "paperprosc", "fringe_fix", "paperprosc_fringe_import.py"),
    run_name="__main__",
)
