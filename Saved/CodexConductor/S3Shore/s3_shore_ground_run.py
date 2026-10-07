"""Runner for s3_shore_ground_ue.py via ExecuteProjectPythonFile.

Modes (args file s3_shore_ground_args.json):
  DRY            read-only (no confirm).
  IMPORT         confirm "IMPORT S3SHORE"     - one static mesh, saves only that package.
  BUILD_MAT      confirm "BUILD_MAT S3SHORE"  - create-only master + MI, saves only those two.
  BENCH          confirm "BENCH S3SHORE"      - reversible, NO save; stills via slate tick; originals file first.
  BENCH_RESTORE  confirm "BENCH_RESTORE S3SHORE" + "bench_run": "<run>" - out-of-band restore, no save.
  APPLY / REVERT / VERIFY / anything else: REFUSED here (not written / not reviewed).
Markers: S3SHORE_START|run= / S3SHORE_<MODE>_OK|run= (BENCH: S3SHORE_BENCH_STARTED, then S3SHORE_BENCH_OK from the
tick) / S3SHORE_FAILED|run=|reason.  One mode per call (memory ue58-bulk-import-oom-crash: IMPORT and BUILD_MAT are
separate calls).
"""
import datetime
import json
import runpy

HERE = "E:/PussStage/Saved/CodexConductor/S3Shore/"
runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
g = runpy.run_path(HERE + "s3_shore_ground_ue.py")
import unreal  # noqa: E402

ENABLED = {"DRY": None, "IMPORT": "IMPORT S3SHORE", "BUILD_MAT": "BUILD_MAT S3SHORE", "BENCH": "BENCH S3SHORE",
           "BENCH_RESTORE": "BENCH_RESTORE S3SHORE"}
REFUSED = ("APPLY", "REVERT", "VERIFY")

args = json.load(open(HERE + "s3_shore_ground_args.json", encoding="utf-8"))
mode = str(args.get("mode") or "")
run = args.get("run") or "S3SHORE-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
unreal.log("S3SHORE_START|run=%s|mode=%s" % (run, mode))
try:
    if mode in REFUSED or mode not in ENABLED:
        raise RuntimeError("MODE_NOT_ENABLED_IN_RUNNER|%s" % mode)
    want = ENABLED[mode]
    if want is not None and args.get("confirm") != want:
        raise RuntimeError("CONFIRM_MISSING|%s needs confirm=%r" % (mode, want))
    if mode == "DRY":
        out = g["run_dry"](run)
        unreal.log("S3SHORE_DRY_OK|run=%s|landed=%s|actors=%d|figures=%d|cameras=%d|census=%s" % (
            run, out["landed_matches_footprint"], len(out["actors"]), len(out["figures"]), len(out["cameras"]),
            json.dumps(out["census"])))
    elif mode == "IMPORT":
        out = g["run_import"](run)
        unreal.log("S3SHORE_IMPORT_OK|run=%s|mesh=%s|nanite=%s|vc=%s|bounds=%s" % (
            run, out["mesh"], out["nanite"], out["has_vertex_colors"], json.dumps(out["bounds"])))
    elif mode == "BUILD_MAT":
        out = g["run_build_mat"](run)
        unreal.log("S3SHORE_BUILD_MAT_OK|run=%s|nodes=%d|edges=%d|samplers=%s" % (
            run, out["nodes"], out["edges"], json.dumps(out["samplers"])))
    elif mode == "BENCH":
        out = g["run_bench"](run, args)
        unreal.log("S3SHORE_BENCH_STARTED|run=%s|jobs=%s|missing=%s|census_after_set=%s|originals=%s" % (
            run, out["jobs"], out["missing"], json.dumps(out["census_after_set"]), out["originals"]))
    elif mode == "BENCH_RESTORE":
        if not args.get("bench_run"):
            raise RuntimeError("BENCH_RUN_MISSING")
        out = g["run_bench_restore"](run, args)
        unreal.log("S3SHORE_BENCH_RESTORE_OK|run=%s|from=%s|census=%s" % (run, out["restored_from"], json.dumps(out["census"])))
except Exception as exc:  # noqa: BLE001
    unreal.log_error("S3SHORE_FAILED|run=%s|mode=%s|%r" % (run, mode, exc))
