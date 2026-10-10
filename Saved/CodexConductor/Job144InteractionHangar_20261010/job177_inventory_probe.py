"""Read-only post-revert inventory digest/scope probe for Job 177."""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for name in ("job144_core", "job144_interaction_hangar"):
    sys.modules.pop(name, None)
C = importlib.import_module("job144_core")
J = importlib.import_module("job144_interaction_hangar")
control = json.load(open(os.path.join(HERE, "job177_control.json"), encoding="utf-8"))
n = int(control["interaction"])
pinned = json.load(open(os.path.join(HERE, "job144_plan_I%d.json" % n), encoding="utf-8"))
params = C.merged_params(pinned["params"])
backend = J.UnrealBackend()
backend.preflight("DRY", "DRY JOB144")
snap = backend.snapshot(params)
inventory = C.inventory_plan(snap["actors"], params)
out = os.path.join(HERE, "job177_inventory_probe_I%d.json" % n)
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"interaction": n, "old_digest": params["approved_inventory_digest"],
               "new_digest": inventory["digest"], "approved_hide": inventory["approved_hide"],
               "all_count": len(inventory["all"]), "census": backend.census()}, handle, indent=2)
backend.log("JOB177_INVENTORY_PROBE_OK|interaction=I%d|old=%s|new=%s|hide=%d|actors=%d|report=%s" %
            (n, params["approved_inventory_digest"], inventory["digest"],
             len(inventory["approved_hide"]), len(inventory["all"]), out))
