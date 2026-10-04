"""Explicit REVERT entrypoint for scene_camera_owner_apply.py."""
import runpy

runpy.run_path(
    "E:/PussStage/Saved/CodexConductor/scene_camera_owner_apply.py",
    init_globals={"SCENE_CAMERA_OWNER_MODE": "REVERT"},
)
