"""Capture Scene 4 v2: the whole box rising, from the handoff camera level and looking
down 15 deg at the lip, plus a wide side view of the rotation."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
X0, CY = 10668.5, 240000.0
runpy.run_path(os.path.join(HERE, "scene4_fold_capture.py"),
               init_globals={"FOLD_SEQ": "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise", "FOLD_SUBDIR": "RiseV2Glow",
                             "FOLD_PITCHES": (0, -15),
                             "FOLD_PROBES": ("S4 Hangar Root", "S4 Hangar Roof Hinge", "S4 Hangar Lattice Fly",
                                             "S4 Hangar Far Wall Hinge", "S4 Hangar Left Wall Hinge"),
                             "FOLD_EXTRA_VIEWS": (),
                             "FOLD_MOMENTS": (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 21.0, 24.0, 27.0, 30.0)})
