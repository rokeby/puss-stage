"""Entrypoint for p02_brighten.py via ExecuteProjectPythonFile (request: p02_brighten_request.json).

Reads p02_brighten_args.json, e.g.
  {"mode": "DRY", "params": {}}
  {"mode": "APPLY", "confirm": "APPLY P02BRIGHTEN", "params": {...same as the DRY...},
   "expected_targets": <the DRY report's plan.counts.targets>, "expected_bays": <plan.selected_bays>,
   "ack_records": ["<paths VERBATIM from the DRY report's unacknowledged_foreign_records>"]}
  {"mode": "REVERT", "confirm": "REVERT P02BRIGHTEN"}
Record p02_brighten_record.json, reports p02_brighten_report_<MODE>_<run>.json, markers P02BRIGHTEN_*. PIE must NOT be
running (editor world). Refuses APPLY/REVERT unless "confirm" repeats "<MODE> P02BRIGHTEN" (the tool checks again).
Stale Saved/ modules are purged first (ue58-python-stale-module-cache, 2 Oct).
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

with open(os.path.join(HERE, "p02_brighten_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P02BRIGHTEN" % mode:
    unreal.log_error("P02BRIGHTEN_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P02BRIGHTEN_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p02_brighten.py"), run_name="__p02_brighten_runner__",
               init_globals={"P02BRIGHTEN_ARGS": args})
