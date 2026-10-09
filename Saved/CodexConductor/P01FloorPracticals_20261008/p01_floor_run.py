"""Entrypoint for p01_floor.py (Unreal: ExecuteProjectPythonFile, request p01_floor_request.json).

Reads p01_floor_args.json. APPLY/REVERT refuse unless "confirm" is exact (p01_floor.check_args), so a stale args file
cannot turn a DRY into a write; ADD_UPLIGHTS refuses anything but COUNT/DRY. Cached modules from Saved/CodexConductor
are purged first (memory ue58-python-stale-module-cache); runpy executes a fresh copy every call. Outside Unreal only
COUNT runs (python p01_floor_run.py, or python p01_floor.py <args.json>).
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
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", "P01FloorPracticals_20261008")
PURGE = os.path.normcase(os.path.abspath(os.path.dirname(HERE)))
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(PURGE):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "p01_floor_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)

if unreal is None:
    if str(args.get("mode", "")).upper() not in ("COUNT", "DRY"):
        raise SystemExit("FLOOR_STOPPED|run=none|OFFLINE_RUNS_COUNT_ONLY")
    tool = runpy.run_path(os.path.join(HERE, "p01_floor.py"), run_name="__p01floor_offline__")
    tool["count_cli"]([os.path.join(HERE, "p01_floor_args.json")])
else:
    runpy.run_path(os.path.join(HERE, "p01_floor.py"), run_name="__p01floor_runner__",
                   init_globals={"P01FLOOR_ARGS": args})
