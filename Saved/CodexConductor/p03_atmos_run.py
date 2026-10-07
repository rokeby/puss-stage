"""Entrypoint for p03_atmos.py via ExecuteProjectPythonFile (request: p03_atmos_request.json).

Reads p03_atmos_args.json, e.g.
  {"mode": "DRY", "params": {}}
  {"mode": "APPLY", "confirm": "APPLY P03ATMOS", "params": {...same as the DRY...},
   "expected": {<the DRY report's plan.counts>}, "ack_records": ["<paths VERBATIM from the DRY report's
   unacknowledged_foreign_records>"]}
  {"mode": "REVERT", "confirm": "REVERT P03ATMOS"}            (+ "remove_assets": true to delete the created assets)
Record p03_atmos_record.json, reports p03_atmos_report_<MODE>_<run>.json, markers P03ATMOS_*. PIE must NOT be running
(editor world). Refuses APPLY/REVERT unless "confirm" repeats "<MODE> P03ATMOS" (the tool checks again). Stale
Saved/ modules are purged first (ue58-python-stale-module-cache, 2 Oct).
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

with open(os.path.join(HERE, "p03_atmos_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P03ATMOS" % mode:
    unreal.log_error("P03ATMOS_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P03ATMOS_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p03_atmos.py"), run_name="__p03_atmos_runner__",
               init_globals={"P03ATMOS_ARGS": args})
