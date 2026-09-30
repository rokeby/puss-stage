"""Nest LS_S4_HangarRise in Scene 4 (re-point the "Hangar Fold" section), resize, rebuild the Master (13/13)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
runpy.run_path(os.path.join(HERE, "scene4_fold_nest.py"), init_globals={"FOLD_PATH": "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"})
