"""Entrypoint for p04_rain_bench.py via ExecuteProjectPythonFile.

Reads p04_rain_bench_mode.json, e.g. {"mode": "PROBE", "params": {}}. Modes, in order:
  PROBE -> CREATE -> PIE_BEGIN -> SETUP -> STILLS (wait PASSAGE_STILLS_OK) -> STILLS_NORAIN (wait OK)
  -> TEARDOWN_PIE -> conductor_pie_end.py -> TEARDOWN.   VERIFY runs offline:
  python Saved/CodexConductor/p04_rain_bench.py verify
Purges Saved/ modules first (memory: the editor keeps stale imports across MCP runs).
Watch for P04_RAIN_BENCH_<STEP>_OK|run=... or P04_RAIN_BENCH_FAILED|run=...
"""
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/"
with open(HERE + "p04_rain_bench_mode.json", encoding="utf-8") as handle:
    args = json.load(handle)
if not isinstance(args, dict) or not args.get("mode"):
    raise RuntimeError("P04_RAIN_BENCH_FAILED|run=none|step=none|reason=bad_args|p04_rain_bench_mode.json needs a mode")
runpy.run_path(HERE + "purge_saved_module_cache.py")
runpy.run_path(HERE + "p04_rain_bench.py", init_globals={
    "BENCH_MODE": str(args["mode"]).upper(),
    "BENCH_PARAMS": dict(args.get("params", {}) or {}),
})
