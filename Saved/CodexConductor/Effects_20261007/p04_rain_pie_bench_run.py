"""Entrypoint for p04_rain_pie_bench.py via ExecuteProjectPythonFile (request: p04_rain_pie_bench_request.json).
OFFLINE-WRITTEN 7 Oct, never run. Needs the CONDUCTOR'S OWN PIE (../conductor_pie_begin.py first). Never ends PIE.
Args p04_rain_pie_bench_args.json: {"mode": "RUN"|"TEARDOWN", "confirm": "CONDUCTOR PIE P04RAIN", "params": {...}}.
Purges stale Saved/ modules first (ue58-python-stale-module-cache). Watch P04RAINPIE_OK|run=.. / P04RAINPIE_FAILED."""
import json
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
CORE_DIR = os.path.join(SAVED, "CodexConductor")
HERE = os.path.join(CORE_DIR, "Effects_20261007")
runpy.run_path(os.path.join(CORE_DIR, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p04_rain_pie_bench_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
runpy.run_path(os.path.join(HERE, "p04_rain_pie_bench.py"), init_globals={"BENCH_ARGS": args})
