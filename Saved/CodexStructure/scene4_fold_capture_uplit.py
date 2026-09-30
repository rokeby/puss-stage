"""Capture the upper hangar at Look & camera's tilt candidates (30, 48 deg), after the uplight pass."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_capture.py"),
               init_globals={"FOLD_SUBDIR": "FoldUplit", "FOLD_PITCHES": (30, 48),
                             "FOLD_MOMENTS": (6.0, 9.0, 11.0, 13.5, 15.5, 18.0, 20.5, 23.0)})
