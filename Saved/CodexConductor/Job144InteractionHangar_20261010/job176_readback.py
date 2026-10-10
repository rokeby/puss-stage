"""Independent read-only Job 176 verifier for the saved Job 144 record."""
import importlib.util
import json
import os

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "job144_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
interaction = int(args["params"]["interaction"])
run_id = str(args["run_id"])

spec = importlib.util.spec_from_file_location(
    "job144_interaction_hangar_readback",
    os.path.join(HERE, "job144_interaction_hangar.py"),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
backend = module.UnrealBackend(HERE)
backend.preflight("DRY", "DRY JOB144")
record_path = os.path.join(HERE, "job144_record_I%d.json" % interaction)
with open(record_path, encoding="utf-8") as handle:
    record = json.load(handle)
if record.get("status") != "applied":
    raise RuntimeError("JOB176_JOB144_READBACK_FAILED|record_not_applied")
backend._verify_record(record, True)
if backend.census() != {"content": [], "maps": []}:
    raise RuntimeError("JOB176_JOB144_READBACK_FAILED|dirty_after_readback")
unreal.log(
    "JOB176_JOB144_READBACK_OK|run=%s|interaction=I%d|record_run=%s|saved=%s|dirty=0"
    % (run_id, interaction, record.get("run"), ",".join(record.get("packages", [])))
)
