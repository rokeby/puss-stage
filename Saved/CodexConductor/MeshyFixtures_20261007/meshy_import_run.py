"""Entrypoint for meshy_import.py (Unreal: ExecuteProjectPythonFile, request meshy_import_request.json).

Reads meshy_import_args.json. APPLY/REVERT refuse unless "confirm" is exact (meshy_import.py check_args), so a stale args
file cannot turn a DRY into a write. Cached modules from this folder and Saved/CodexConductor are purged first
(memory ue58-python-stale-module-cache); runpy executes a fresh copy every call.
Outside Unreal: meshy_swap runs its offline COUNT (mode must be COUNT); meshy_import has no offline mode.
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
                        "CodexConductor", "MeshyFixtures_20261007")
PURGE = os.path.normcase(os.path.abspath(os.path.dirname(HERE)))
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(PURGE):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "meshy_import_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)

if unreal is None:
    if "import" != "swap" or str(args.get("mode", "")).upper() != "COUNT":
        raise SystemExit("MESHYIMPORT_STOPPED|run=none|OFFLINE_RUNS_SWAP_COUNT_ONLY")
    tool = runpy.run_path(os.path.join(HERE, "meshy_swap.py"), run_name="__meshy_swap_offline__")
    tool["count_cli"]([os.path.join(HERE, "meshy_swap_args.json")])
else:
    runpy.run_path(os.path.join(HERE, "meshy_import.py"), run_name="__meshy_import_runner__",
                   init_globals={"MESHYIMPORT_ARGS": args})
