"""Entrypoint for dead_bulbs_warm.py via ExecuteProjectPythonFile (request: dead_bulbs_warm_request.json).

Reads dead_bulbs_warm_args.json, e.g.
  {"mode": "DRY", "params": {}}
  {"mode": "APPLY", "confirm": "APPLY DEADBULBSWARM", "params": {...same as the DRY...},
   "expected_targets": <the DRY report's plan.counts.targets>,
   "expected_per_passage": {<P0N>: <plan.per_passage[P0N].targets>, ...},
   "ack_records": ["<paths VERBATIM from the DRY report's unacknowledged_foreign_records>"]}
  {"mode": "REVERT", "confirm": "REVERT DEADBULBSWARM"}
Record dead_bulbs_warm_record.json, reports dead_bulbs_warm_report_<MODE>_<run>.json, markers DEADBULBSWARM_*. PIE
must NOT be running (editor world). Refuses APPLY/REVERT unless "confirm" repeats "<MODE> DEADBULBSWARM" (the tool
checks again). Stale Saved/ modules are purged first (ue58-python-stale-module-cache, 2 Oct).
"""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))

with open(os.path.join(HERE, "dead_bulbs_warm_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s DEADBULBSWARM" % mode:
    unreal.log_error("DEADBULBSWARM_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("DEADBULBSWARM_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "dead_bulbs_warm.py"), run_name="__dead_bulbs_warm_runner__",
               init_globals={"DEADBULBSWARM_ARGS": args})
