"""Guarded MCP entry point: apply the reviewed job 180 P06 suppression."""

import runpy

runpy.run_path(
    "Saved/CodexStructure/job180_suppress_p06_fixture_body.py",
    init_globals={
        "JOB180_MODE": "APPLY",
        "JOB180_CONFIRM": "APPLY_JOB180_P06_FIXTURE_SUPPRESSION",
    },
    run_name="__main__",
)
