"""Fresh runpy entry point for the guarded job 115 editor tool."""
import os
import runpy

import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "J115S3HessianShirts_20261009", "j115_editor.py"),
               run_name="<run_path>")

