"""Fresh runpy entry point for Job 122's guarded editor tool."""
import os
import runpy
import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "J122S3GarmentHessian_20261010", "j122_editor.py"),
               run_name="<run_path>")

