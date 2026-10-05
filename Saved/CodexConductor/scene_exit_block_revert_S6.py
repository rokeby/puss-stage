"""REVERT scene_exit_block for Scene 6, then the read-only leaf check for that Scene (5 Oct, offline-written, NOT RUN).

Plan: Docs/Conductor/CURTAIN_SLEIGHT_TRANSITION_PLAN_2026-10-05.md section 4. One Scene per run; no PIE; Sequencer
closed; clean census (scene_exit_block.py refuses otherwise). Accept only, for THIS run:
  SCENE_EXIT_BLOCK_REVERT_OK|run=<id>|scene=6|...   (any SCENE_EXIT_BLOCK_STOPPED = Don't-Save restart if it says so)
  LEAF_CLOSED_CHECK_OK|run=SXR6-<id>|...           (LEAF_CLOSED_CHECK_NOT_CLOSED = STOP; re-closing is a separate write)
The revert leaves the Scene LONG (it prints to_shorten=extend_scene_playback new_end_frame=<content_end>); under option B
shorten it with extend_scene_playback.py as a separate, single step.
"""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "scene_exit_block.py"),
               init_globals={"SCENE_EXIT_BLOCK_SCENE": 6, "SCENE_EXIT_BLOCK_REVERT": True})
# Reached only if the revert did not raise (its own STOPPED line is already logged otherwise).
import datetime  # noqa: E402
runpy.run_path(os.path.join(HERE, "leaf_closed_check.py"),
               init_globals={"LEAF_CHECK_SCENES": [6],
                             "LEAF_CHECK_RUN_ID": datetime.datetime.now().strftime("SXR6-%Y%m%d-%H%M%S")})
