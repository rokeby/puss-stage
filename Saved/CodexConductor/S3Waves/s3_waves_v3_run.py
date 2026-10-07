"""Runner for s3_waves_v3_ue.py via ExecuteProjectPythonFile (request: s3_waves_v3_request.json).
Purges Saved/ modules first (memory ue58-python-stale-module-cache), then runs main() of a FRESH copy of the tool
(the tool loads s3_waves_v3_core.py and phase1_import.py by file path on every call).  One mode per call; the mode,
pieces and confirm come from S3Waves/s3_waves_v3_args.json.  Markers: S3WAVESV3_START / _<MODE>_OK / _FAILED|run=..."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
runpy.run_path("E:/PussStage/Saved/CodexConductor/S3Waves/s3_waves_v3_ue.py")["main"]()
