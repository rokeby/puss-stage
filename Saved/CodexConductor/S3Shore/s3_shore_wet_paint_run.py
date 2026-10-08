"""ExecuteProjectPythonFile runner for the S3 shore vertex-G harvest.  DRY is the only accepted mode.

Writes only export/read reports under project Saved; never changes or saves a package.
Markers: S3SHORE_WET_READ_START|run= and S3SHORE_WET_READ_DRY_OK|run= after exact dirty-census equality.
"""
import datetime
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/S3Shore/"
runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
g = runpy.run_path(HERE + "s3_shore_wet_paint_read.py")
import unreal  # noqa: E402

ENABLED = {"DRY": None}
mode = ""
run = "S3SHOREWET-unknown"
try:
    args = json.load(open(HERE + "s3_shore_wet_paint_args.json", encoding="utf-8"))
    mode = str(args.get("mode") or "")
    run = args.get("run") or "S3SHOREWET-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    unreal.log("S3SHORE_WET_READ_START|run=%s|mode=%s" % (run, mode))
    if mode not in ENABLED:
        raise RuntimeError("MODE_NOT_ENABLED|%s|DRY_ONLY" % mode)
    out = g["run_dry"](run)
    unreal.log("S3SHORE_WET_READ_DRY_OK|run=%s|control_points=%d|g=%s|samples=%s|census=%s" %
               (run, out["control_points"], json.dumps(out["g_min_max_mean"]), out["samples"],
                json.dumps(out["dirty_packages_after"])))
except Exception as exc:  # noqa: BLE001
    unreal.log_error("S3SHORE_WET_READ_FAILED|run=%s|mode=%s|reason=%r" % (run, mode, exc))
