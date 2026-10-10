"""Guarded MCP entry point: read-only job 180 preflight."""

import runpy

runpy.run_path(
    "Saved/CodexStructure/job180_suppress_p06_fixture_body.py",
    init_globals={"JOB180_MODE": "DRY"},
    run_name="__main__",
)
