"""Independent saved-state read-back for the interaction selected by Job 177 control."""
import importlib.util
import json
import os

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
control = json.load(open(os.path.join(HERE, "job177_control.json"), encoding="utf-8"))
interaction = int(control["interaction"])
spec = importlib.util.spec_from_file_location("job144_interaction_hangar_job177_readback",
                                              os.path.join(HERE, "job144_interaction_hangar.py"))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
backend = module.UnrealBackend(HERE)
backend.preflight("DRY", "DRY JOB144")
record_path = os.path.join(HERE, "job144_record_I%d.json" % interaction)
record = json.load(open(record_path, encoding="utf-8"))
if record.get("status") != "applied":
    raise RuntimeError("JOB177_JOB144_READBACK_FAILED|record_not_applied")
backend._verify_record(record, True)
if backend.census() != {"content": [], "maps": []}:
    raise RuntimeError("JOB177_JOB144_READBACK_FAILED|dirty_after_readback")
unreal.log("JOB177_JOB144_READBACK_OK|run=%s|interaction=I%d|record_run=%s|saved=%s|dirty=0" %
           (control["run_id"], interaction, record["run"], ",".join(record["packages"])))
