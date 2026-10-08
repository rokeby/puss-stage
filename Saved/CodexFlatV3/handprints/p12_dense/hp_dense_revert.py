"""Wrapper for hp_dense_editor.py mode REVERT."""
import os
import runpy
import unreal

runpy.run_path(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexFlatV3", "handprints", "p12_dense", "hp_dense_editor.py"),
               init_globals={"HP_DENSE_MODE": "REVERT", "HP_DENSE_CONFIRM": "REVERT P12 DENSE HANDPRINTS"})
