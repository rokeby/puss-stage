"""Entrypoint for p04_window_shadows.py.

Inside Unreal (ExecuteProjectPythonFile, p04_window_shadows_request.json): reads p04_window_shadows_args.json, e.g.
  {"mode": "DRY"}
  {"mode": "APPLY", "confirm": "APPLY P04WINSHADOW", "plan_sha256": "<from the DRY report>",
   "ack_records": ["<paths copied VERBATIM from the DRY report's unacknowledged_foreign_records>"]}
  {"mode": "REVERT", "confirm": "REVERT P04WINSHADOW", "ack_records": [...]}
APPLY/REVERT refuse unless "confirm" repeats "<MODE> P04WINSHADOW" exactly (checked here and in check_args), so a
stale args file cannot turn a dry run into a write. PLAN refuses inside Unreal (it is offline only).
Cached modules from Saved/CodexConductor are purged first so edited helpers never run stale
(ue58-python-stale-module-cache, 2 Oct); runpy executes a fresh copy every call (pattern: p04_glint_practical_run.py).

Outside Unreal (plain python): runs the offline PLAN with the same args file (mode must be PLAN).
"""
import json
import os
import runpy
import sys

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

if unreal is None:
    HERE = os.path.dirname(os.path.abspath(__file__))
else:
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")

for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(os.path.normcase(os.path.abspath(HERE))):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p04_window_shadows_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "PLAN")).upper()

if unreal is None:
    if mode != "PLAN":
        raise SystemExit("P04WINSHADOW_STOPPED|run=none|mode=%s|OFFLINE_RUNS_PLAN_ONLY" % mode)
    tool = runpy.run_path(os.path.join(HERE, "p04_window_shadows.py"), run_name="__p04_window_shadows_offline__")
    tool["plan_cli"]([os.path.join(HERE, "p04_window_shadows_args.json")])
else:
    if mode in ("APPLY", "REVERT") and args.get("confirm") != "%s P04WINSHADOW" % mode:
        unreal.log_error("P04WINSHADOW_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
        raise RuntimeError("P04WINSHADOW_STOPPED|run=none|mode=%s|CONFIRM_MISSING" % mode)
    if mode == "PLAN":
        unreal.log_error("P04WINSHADOW_STOPPED|run=none|mode=PLAN|PLAN_IS_OFFLINE_ONLY|NOTHING SAVED")
        raise RuntimeError("P04WINSHADOW_STOPPED|PLAN_IS_OFFLINE_ONLY")
    runpy.run_path(os.path.join(HERE, "p04_window_shadows.py"), run_name="__p04_window_shadows_runner__",
                   init_globals={"P04WINSHADOW_ARGS": args})
