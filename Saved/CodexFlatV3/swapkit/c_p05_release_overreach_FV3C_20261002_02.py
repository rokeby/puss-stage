"""Release Slot C after the approved dry-run overreach stop gate fired."""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import common as c
c = importlib.reload(c)


config = c.load_config(os.path.join(HERE, "run_c_p05.json"))
if config["run_id"] != "FV3C-20261002-02":
    raise RuntimeError("RUN_ID_DRIFT|actual=" + str(config["run_id"]))
c.assert_context(config, clean=True)
plan = c.read_json(config, "dry_run")
flags = list(plan.get("overreach_flags", []))
excluded = list(plan.get("excluded_rows_kept_old", []))
if len(flags) != 13:
    raise RuntimeError("OVERREACH_COUNT_DRIFT|expected=13|actual=%d" % len(flags))
if len(excluded) != 12:
    raise RuntimeError("EXCLUSION_COUNT_DRIFT|expected=12|actual=%d" % len(excluded))
if c.census() != c.CLEAN:
    raise RuntimeError("DIRTY_BEFORE_FAILURE_RELEASE|census=" +
                       json.dumps(c.census(), sort_keys=True))
reason = "dry:UNEXPLAINED_OVERREACH_FLAGS|count=13"
c.write_json(config, "release", {
    "run": config["run_id"],
    "status": "FAIL",
    "reason": reason,
    "saved_count": 0,
    "saved_roots": [],
    "overreach_count": len(flags),
    "excluded_rows_kept_old_count": len(excluded),
    "census": c.census(),
}, failure=True)
c.log_release(config, "FAIL", [], reason)

