"""Runner for s3waves_t5o.py via ExecuteProjectPythonFile (request: s3waves_t5o_request.json).
Purges Saved/ modules first (memory ue58-python-stale-module-cache), then runs main() of a FRESH copy of the tool (the
tool loads s3waves_t5o_core.py, s3_waves_v3_core.py, s3_waves_v3_ue.py and phase1_import.py by file path every call).
One mode per call; mode / pieces / confirm come from s3waves_t5o_args.json.  Markers: S3T5O_START / _<MODE>_OK / _FAILED."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
runpy.run_path("E:/PussStage/Saved/CodexFlatV3/s3waves/s3waves_t5o.py")["main"]()
