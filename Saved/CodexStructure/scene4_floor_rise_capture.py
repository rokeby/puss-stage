"""Dense capture of the floor rise: the first 6 s from the Scene 4 Entry Handoff
Camera, level, 16 frames packed around the glow breaking on the horizon (about 3 s)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_capture.py"),
               init_globals={"FOLD_SUBDIR": "FloorRiseBuilt", "FOLD_PITCHES": (0,),
                             "FOLD_MOMENTS": (0.0, 0.5, 1.0, 1.5, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.5, 5.0, 6.0)})
