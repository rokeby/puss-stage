"""Entrypoint for passage_atmos.py via ExecuteProjectPythonFile (request: passage_atmos_request.json).
OFFLINE-WRITTEN 7 Oct, never run. Mirrors ../p03_atmos_run.py: stale Saved/ modules purged first
(ue58-python-stale-module-cache), confirm checked before anything loads, PIE must NOT be running (the core checks).
Args: passage_atmos_args.json (see passage_atmos.py). Confirm = "<MODE> <Pnn>ATMOS".
"""
import json
import os
import runpy
import sys

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
CORE_DIR = os.path.join(SAVED, "CodexConductor")
HERE = os.path.join(CORE_DIR, "Effects_20261007")
for path in (CORE_DIR, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
runpy.run_path(os.path.join(CORE_DIR, "purge_saved_module_cache.py"))

with open(os.path.join(HERE, "passage_atmos_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
mode = str(args.get("mode", "DRY")).upper()
token = "%sATMOS" % args.get("passage")
if mode != "DRY" and args.get("confirm") != "%s %s" % (mode, token):
    unreal.log_error("PASSAGEATMOS_STOPPED|run=none|mode=%s|CONFIRM_MISSING|NOTHING SAVED" % mode)
    raise RuntimeError("PASSAGEATMOS_STOPPED|CONFIRM_MISSING")
module = runpy.run_path(os.path.join(HERE, "passage_atmos.py"), run_name="__passage_atmos_runner__")
try:
    module["run"](args)
except module["PassageAtmosError"] as error:
    unreal.log_error("PASSAGEATMOS_STOPPED|run=none|%s|NOTHING SAVED" % error)
    raise
