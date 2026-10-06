"""Entrypoint for p01_rig_pattern.py via ExecuteProjectPythonFile.

Reads p01_rig_pattern_args.json, e.g.
  {"mode": "DRY", "jitter": {"loc_cm": 0.0, "rot_deg": 0.0, "seed": 0}, "skip": [["P01 Wing 005", "BEAM_R"]]}
  {"mode": "APPLY", "confirm": "APPLY P01RIGPATTERN", "expected_targets": <DRY rows>,
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"], ...same jitter/skip/roles}
  {"mode": "REVERT", "confirm": "REVERT P01RIGPATTERN"}
APPLY and REVERT refuse unless "confirm" repeats "<MODE> P01RIGPATTERN" exactly, so a stale args file cannot
turn a dry run into a write. The tool checks it again (check_args). runpy.run_path executes a fresh copy every
call, and cached modules from Saved/CodexConductor are purged first so edited helpers never run stale
(ue58-python-stale-module-cache, 2 Oct).
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

with open(os.path.join(HERE, "p01_rig_pattern_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s P01RIGPATTERN" % mode:
    unreal.log_error("P01RIGPATTERN_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("P01RIGPATTERN_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "p01_rig_pattern.py"), run_name="__p01_rig_pattern_runner__",
               init_globals={"P01RIGPATTERN_ARGS": args})
