"""Runner for s3mg_bench.py via ExecuteProjectPythonFile (called by the s3mg_run_<stage>.py wrappers).

Purges the Saved/ module cache first (memory: editor Python keeps stale imports), reads s3mg_args.json
{"run": "S3MG-...", "variant": "C"}, runs ONE stage. Markers (run id on every line):
  S3MG_<STAGE>_START|run=..      before anything
  S3MG_<STAGE>_OK|run=..|..      only after the stage returned (every assert passed, records read back)
  S3MG_FAILED|run=..|stage=..|reason=..   on ANY refusal or exception (never followed by OK)
'stills' only ARMS the shared scene_stills.py tick: its own PASSAGE_STILLS_OK / _FAILED markers decide the still.
"""
import json
import runpy
import traceback

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/S3MarbleGrime/"
STAGE = globals().get("S3MG_STAGE")
runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")
run = "S3MG-unknown"
try:
    args = json.load(open(HERE + "s3mg_args.json", encoding="utf-8"))
    run = str(args.get("run") or "")
    if not run.startswith("S3MG-") or "REPLACE" in run:
        raise RuntimeError("BAD_RUN_ID|%r|set s3mg_args.json run to S3MG-<stamp>" % run)
    unreal.log("S3MG_%s_START|run=%s|variant=%s" % (str(STAGE).upper(), run, args.get("variant")))
    bench = runpy.run_path(HERE + "s3mg_bench.py")          # fresh module each call; no UE objects at module level
    detail = bench["run_stage"](STAGE, run, args)
    unreal.log("S3MG_%s_OK|run=%s|%s" % (str(STAGE).upper(), run, detail))
except Exception as exc:
    unreal.log_error("S3MG_FAILED|run=%s|stage=%s|reason=%s|trace=%s" % (
        run, STAGE, str(exc).replace("\n", " "), traceback.format_exc().replace("\n", " | ")))
