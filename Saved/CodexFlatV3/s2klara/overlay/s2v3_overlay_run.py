"""Runner for s2v3_overlay.py via ExecuteProjectPythonFile (request: s2v3_overlay_request.json).
Offline-written 8 Oct, NOT RUN.  Purges Saved/ modules first (memory ue58-python-stale-module-cache), then runs main()
of a FRESH copy of the tool (the tool loads s2v3_overlay_core.py by file path every call).  One mode per call; mode,
variant, confirm, decided_by come from s2v3_overlay_args.json.  Markers: S2V3OV_START / _<MODE>_OK / _RESYNC_NOOP /
_VERIFY_FAILED / _FAILED, each with run=<id>; read the log by marker AND run id (memory puss-log-markers-run-id)."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
runpy.run_path("E:/PussStage/Saved/CodexFlatV3/s2klara/overlay/s2v3_overlay.py")["main"]()
