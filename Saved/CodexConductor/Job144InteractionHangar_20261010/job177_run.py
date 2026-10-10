"""Job 177 controller: reuse the reviewed per-interaction params without editing the long shared args file."""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for name in ("job144_core", "job144_interaction_hangar"):
    sys.modules.pop(name, None)
module = importlib.import_module("job144_interaction_hangar")
control = json.load(open(os.path.join(HERE, "job177_control.json"), encoding="utf-8"))
interaction = int(control["interaction"])
pinned = json.load(open(os.path.join(HERE, "job144_plan_I%d.json" % interaction), encoding="utf-8"))
mode = str(control["mode"]).upper()
module.main({"mode": mode, "confirm": "%s JOB144" % mode,
             "run_id": str(control["run_id"]), "params": pinned["params"]})
