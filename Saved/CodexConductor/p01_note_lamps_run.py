"""Entrypoint for p01_note_lamps.py via ExecuteProjectPythonFile (p01_note_lamps_request.json).

Reads p01_note_lamps_args.json, e.g.
  {"mode": "PLAN"}                         (also runnable offline: python p01_note_lamps.py)
  {"mode": "DRY"}
  {"mode": "APPLY", "confirm": "APPLY P01NOTELAMPS", "expected_plan_sha256": "<DRY report plan_sha256>",
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"]}
  {"mode": "REVERT", "confirm": "REVERT P01NOTELAMPS"}
APPLY and REVERT refuse unless "confirm" repeats "<MODE> P01NOTELAMPS" exactly (checked here and again in
check_args), and APPLY refuses with ENGINE_LACKS_FLASH until the held flash patch is built. runpy.run_path
executes a fresh copy every call, and cached modules from Saved/CodexConductor are purged first so edited
helpers never run stale (ue58-python-stale-module-cache, 2 Oct).
"""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")

for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p01_note_lamps_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "PLAN")).upper()
if mode in ("APPLY", "REVERT") and args.get("confirm") != "%s P01NOTELAMPS" % mode:
    unreal.log_error("P01NOTELAMPS_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P01NOTELAMPS_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p01_note_lamps.py"), run_name="__p01_note_lamps_runner__",
               init_globals={"P01NOTELAMPS_ARGS": args})
