"""Side view of the Scene 4 v2 rise, exposed brighter (EV100 -3) so the rotation itself reads. Diagnostic, not a show frame."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
X0, CY = 10668.5, 240000.0
runpy.run_path(os.path.join(HERE, "scene4_fold_capture.py"),
               init_globals={"FOLD_SEQ": "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise", "FOLD_SUBDIR": "RiseV2Side",
                             "FOLD_PITCHES": (), "FOLD_VIEW_EV": {"side": -3.0},
                             "FOLD_PROBES": ("S4 Hangar Root",),
                             "FOLD_EXTRA_VIEWS": (("side", (X0 + 3000.0, CY - 11000.0, 800.0), (X0 + 2500.0, CY, -1200.0), 90.0),),
                             "FOLD_MOMENTS": (0.0, 3.0, 6.0, 9.0, 12.0, 14.0, 16.0, 20.0)})
