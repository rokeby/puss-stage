"""Fresh runpy entry point for the guarded P38 editor tool."""
import os
import runpy

import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "P38S3Grounding_20261009", "p38_editor.py"),
               run_name="<run_path>")
