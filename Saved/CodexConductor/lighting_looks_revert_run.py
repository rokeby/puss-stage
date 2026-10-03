"""Explicit REVERT entrypoint for lighting_looks_apply.py."""
import runpy

runpy.run_path(
    "E:/PussStage/Saved/CodexConductor/lighting_looks_apply.py",
    init_globals={"LIGHTING_LOOKS_MODE": "REVERT"},
)
