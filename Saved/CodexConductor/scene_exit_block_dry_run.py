"""Purge the Saved module cache, then run scene_exit_block.py DRY (read-only) for S1-S6.

Written offline 4 Oct, NOT YET RUN.  There is deliberately no APPLY runner:
APPLY needs (1) scene_exit_block_overrides.json with decided_by + scenes, and
(2) the Scene already lengthened by extend_scene_playback.py to the new_end
this DRY prints (scene_exit_block_plan_S<N>.json / _S<N>_dry.json).
DRY writes only JSON under Saved/CodexConductor; it mutates no package.
Markers: SCENE_EXIT_BLOCK_DRY_OK per scene, or SCENE_EXIT_BLOCK_STOPPED with a reason.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
for scene in range(1, 7):
    try:
        runpy.run_path(os.path.join(HERE, "scene_exit_block.py"),
                       init_globals={"SCENE_EXIT_BLOCK_SCENE": scene})
    except RuntimeError as exc:  # each scene's own STOPPED line is already logged
        unreal.log_warning("SCENE_EXIT_BLOCK_DRY_SCENE_STOPPED|scene=%d|%s" % (scene, exc))
