"""Entrypoint for puss_shadow_spot.py via ExecuteProjectPythonFile.

Reads puss_shadow_spot_args.json:
  {"mode": "DRY", ...}                                   read-only: reads PussFollowSpot + rigs, lists cues with show times
  {"mode": "APPLY", "confirm": "APPLY PUSSSHADOWSPOT"}   needs the PS patch built; writes rig properties, saves the level
  {"mode": "REVERT", "confirm": "REVERT PUSSSHADOWSPOT"} restores every rig from puss_shadow_spot_record.json
Non-DRY modes refuse unless "confirm" repeats "<MODE> PUSSSHADOWSPOT". Cached modules from Saved/CodexConductor are
purged first so an edited tool never runs stale (ue58-python-stale-module-cache, 2 Oct).
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

with open(os.path.join(HERE, "puss_shadow_spot_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
if mode != "DRY" and args.get("confirm") != "%s PUSSSHADOWSPOT" % mode:
    unreal.log_error("PUSSSHADOWSPOT_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("PUSSSHADOWSPOT_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
runpy.run_path(os.path.join(HERE, "puss_shadow_spot.py"), run_name="__puss_shadow_spot_runner__",
               init_globals={"PUSSSHADOWSPOT_ARGS": args})
