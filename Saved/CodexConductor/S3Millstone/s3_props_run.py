"""Runner for s3_props_ue.py via ExecuteProjectPythonFile (request: Saved/CodexConductor/s3_props_request.json).
Purges Saved/ modules first (memory ue58-python-stale-module-cache), then runs main() of a fresh copy of the tool.
Mode, prop and confirm come from S3Millstone/s3_props_args.json.  One mode per call.
Markers: S3PROPS_START / S3PROPS_<MODE>_OK / S3MILL_APPLY_OK / S3MILL_REVERT_OK / S3PROPS_FAILED|run=..."""
import runpy

runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
runpy.run_path("E:/PussStage/Saved/CodexConductor/S3Millstone/s3_props_ue.py")["main"]()
