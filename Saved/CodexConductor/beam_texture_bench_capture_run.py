"""Run beam_texture_bench.py CAPTURE (PREPARE first, then PIE running; never starts or ends PIE, never spawns, never
saves). Optional beam_texture_bench_args.json: {"dry": false, "params": {...}, "prepare_record": null}. dry=true only
locates each position, settles, plans (logs BEAM_TEXTURE_BENCH_PLAN / _OCCLUSION lines) and shoots base.
Watch for BEAM_TEXTURE_BENCH_CAPTURE_OK|run=... or BEAM_TEXTURE_BENCH_FAILED|run=...."""
import json
import os
import runpy
import sys

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
args = {}
if os.path.isfile(os.path.join(HERE, "beam_texture_bench_args.json")):
    with open(os.path.join(HERE, "beam_texture_bench_args.json"), encoding="utf-8") as handle:
        args = json.load(handle)
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "beam_texture_bench.py"), init_globals={
    "BENCH_MODE": "CAPTURE",
    "BENCH_DRY": bool(args.get("dry", False)),
    "BENCH_PARAMS": dict(args.get("params", {}) or {}),
    "BENCH_PREPARE_RECORD": args.get("prepare_record"),
})
