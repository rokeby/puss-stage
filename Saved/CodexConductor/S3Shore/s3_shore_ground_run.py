"""Runner for s3_shore_ground_ue.py via ExecuteProjectPythonFile. DRY only for now (read-only); other modes refused here
until their APPLY path is written and reviewed. Marker S3SHORE_DRY_OK|run=.. / S3SHORE_FAILED|run=..|reason"""
import datetime
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/S3Shore/"
runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
g = runpy.run_path(HERE + "s3_shore_ground_ue.py")
import unreal
args = json.load(open(HERE + "s3_shore_ground_args.json", encoding="utf-8"))
run = args.get("run") or "S3SHORE-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
try:
    if args.get("mode") != "DRY":
        raise RuntimeError("MODE_NOT_ENABLED_IN_RUNNER|%s" % args.get("mode"))
    out = g["run_dry"](run)
    unreal.log("S3SHORE_DRY_OK|run=%s|landed=%s|actors=%d|figures=%d|cameras=%d|census=%s" % (
        run, out["landed_matches_footprint"], len(out["actors"]), len(out["figures"]), len(out["cameras"]),
        json.dumps(out["census"])))
except Exception as exc:
    unreal.log_error("S3SHORE_FAILED|run=%s|%r" % (run, exc))
