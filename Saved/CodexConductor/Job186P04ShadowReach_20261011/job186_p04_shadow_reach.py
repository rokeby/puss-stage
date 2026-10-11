"""P04-only Job 186 adapter around the proven shadow-radius middle-point tool."""
from __future__ import annotations

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    "job186_shadow_radius_reach_core", os.path.join(ROOT, "shadow_radius_reach.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

core.MARK = "JOB186_P04_SHADOW_REACH"
core.PASSAGES = ("P04",)
core.DEFAULTS = dict(core.DEFAULTS, passages=["P04"])
core.CONFIRM = {
    "APPLY": "APPLY JOB186 P04 SHADOW REACH",
    "REVERT": "REVERT JOB186 P04 SHADOW REACH",
}
core.RECORD = os.path.join(HERE, "job186_p04_shadow_reach_record.json")

MARK = core.MARK
PASSAGES = core.PASSAGES
CONFIRM = core.CONFIRM
RECORD = core.RECORD
DEFAULTS = core.DEFAULTS
ReachError = core.ReachError
check_args = core.check_args
passage_geometry = core.passage_geometry
evaluate_perf = core.evaluate_perf


def run(raw):
    return core.run(raw)


def main():
    return run(globals().get("JOB186_P04_SHADOW_ARGS"))


if __name__ == "__main__":
    main()
