"""Fresh-import runner for the Job 184 S1 missed-light extension."""
import importlib.util
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = os.path.join(HERE, "job184_s1_missed_lights_args.json")
MODULE = os.path.join(HERE, "job184_s1_missed_lights.py")

with open(ARGS, "r", encoding="utf-8") as handle:
    args = json.load(handle)

for name in list(sys.modules):
    if name.startswith("job184_s1_missed_lights_live_"):
        del sys.modules[name]

name = "job184_s1_missed_lights_live_" + str(args.get("run_id", "fresh")).replace("-", "_")
spec = importlib.util.spec_from_file_location(name, MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
module.run(args)

