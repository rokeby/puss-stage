"""Entrypoint for fixtures_follow.py (Unreal: ExecuteProjectPythonFile, request fixtures_follow_request.json).

Reads fixtures_follow_args.json. APPLY/REVERT refuse unless "confirm" is exact (fixtures_follow.check_args), so a stale
args file cannot turn a DRY into a write. Cached modules from Saved/CodexConductor are purged first (memory
ue58-python-stale-module-cache); runpy executes a fresh copy every call. Outside Unreal only COUNT runs.
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
                        "CodexConductor", "FixturesFollow")
PURGE = os.path.normcase(os.path.abspath(os.path.dirname(HERE)))
for name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(PURGE):
        sys.modules.pop(name, None)

with open(os.path.join(HERE, "fixtures_follow_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)

if unreal is None:
    if str(args.get("mode", "")).upper() != "COUNT":
        raise SystemExit("FIXFOLLOW_STOPPED|run=none|OFFLINE_RUNS_COUNT_ONLY")
    tool = runpy.run_path(os.path.join(HERE, "fixtures_follow.py"), run_name="__fixfollow_offline__")
    tool["count_cli"]([os.path.join(HERE, "fixtures_follow_args.json")])
else:
    runpy.run_path(os.path.join(HERE, "fixtures_follow.py"), run_name="__fixfollow_runner__",
                   init_globals={"FIXFOLLOW_ARGS": args})
