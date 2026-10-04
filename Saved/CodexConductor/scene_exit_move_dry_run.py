"""Purge the Saved module cache, then run scene_exit_move.py DRY (read-only) for S1-S6.

DRAFT, not yet run (written offline 4 Oct).  There is deliberately no APPLY
runner: APPLY waits for Gary's pick (Docs/Conductor/SCENE_EXIT_OPTIONS_2026-10-04.md)
and for scene_exit_move_overrides.json to carry decided_by + option.
Markers: SCENE_EXIT_MOVE_DRY_OK per scene, or SCENE_EXIT_MOVE_STOPPED with a reason.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
for scene in range(1, 7):
    try:
        runpy.run_path(os.path.join(HERE, "scene_exit_move.py"),
                       init_globals={"SCENE_EXIT_MOVE_SCENE": scene})
    except RuntimeError as exc:  # each scene's own STOPPED line is already logged
        unreal.log_warning("SCENE_EXIT_MOVE_DRY_SCENE_STOPPED|scene=%d|%s" % (scene, exc))
