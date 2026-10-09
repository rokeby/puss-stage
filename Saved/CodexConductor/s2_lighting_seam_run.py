"""Guarded ExecuteProjectPythonFile runner for P43 S2 lighting."""
import json, os, runpy
import unreal
here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
args = json.load(open(os.path.join(here, "s2_lighting_seam_args.json"), encoding="utf-8"))
mode = str(args.get("mode", "PROBE")).upper()
if args.get("confirm") != "%s P43S2LIGHT" % mode:
    unreal.log_error("P43_S2_LIGHTING_STOPPED|run=none|CONFIRM|NOTHING_SAVED")
    raise RuntimeError("P43 S2 confirm")
runpy.run_path(os.path.join(here, "s2_lighting_seam.py"), run_name="__s2_lighting_seam_runner__")
