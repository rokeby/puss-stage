"""Guarded MCP entry point: read-only job 180 preflight."""

import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexStructure",
)

runpy.run_path(
    os.path.join(HERE, "job180_suppress_p06_fixture_body.py"),
    init_globals={"JOB180_MODE": "DRY"},
    run_name="__main__",
)
