"""Entrypoint for passage_stills.py via ExecuteProjectPythonFile (needs a running PIE).

Reads scene_stills_args.json, e.g.
  {"passage": "P05", "fractions": [0.1, 0.3, 0.5, 0.7, 0.9], "label": "underpass"}
Purges Saved/ modules first (memory: the editor keeps stale imports across MCP runs),
then arms the still capture. Watch the log for PASSAGE_STILLS_OK|run=... or
PASSAGE_STILLS_FAILED|run=....
"""
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/"
with open(HERE + "scene_stills_args.json", encoding="utf-8") as handle:
    args = json.load(handle)
if not isinstance(args, dict) or not args.get("passage"):
    raise RuntimeError("PASSAGE_STILLS_FAILED|run=none|reason=bad_args|scene_stills_args.json needs a passage")
runpy.run_path(HERE + "purge_saved_module_cache.py")
runpy.run_path(HERE + "scene_stills.py", init_globals={
    "STILLS_PASSAGE": str(args["passage"]),
    "STILLS_FRACTIONS": args.get("fractions", [0.1, 0.3, 0.5, 0.7, 0.9]),
    "STILLS_LABEL": args.get("label"),
    "STILLS_PARAMS": dict(args.get("params", {}) or {}),
})
