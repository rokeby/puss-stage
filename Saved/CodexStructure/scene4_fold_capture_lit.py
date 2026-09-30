"""Capture the LIT fold (after scene4_fold_relight.py) into Captures/FoldLit."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_capture.py"),
               init_globals={"FOLD_SUBDIR": "FoldDocked",
                             "FOLD_MOMENTS": (1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 10.0, 12.0, 15.0, 20.0)})
