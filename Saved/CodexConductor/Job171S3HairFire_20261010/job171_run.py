import importlib
import json
import os
import sys
import unreal

HERE = unreal.Paths.project_saved_dir() + "CodexConductor/Job171S3HairFire_20261010"
sys.path.insert(0, HERE)
import job171_s3_hair_fire as tool
importlib.reload(tool)

try:
    with open(os.path.join(HERE, "job171_args.json"), "r", encoding="utf-8") as handle:
        tool.main(json.load(handle))
except Exception as exc:  # noqa: BLE001
    unreal.log_error("JOB171_FAILED|%r" % (exc,))
    raise

