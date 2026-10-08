"""Guarded MCP runner for p18_sky_policy.py."""
import json
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "p18_sky_policy_args.json"), encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p18_sky_policy.py"), init_globals={"P18_SKY_POLICY_ARGS": ARGS})

