"""Purge this Saved module bundle and execute Job 144 from job144_args.json."""
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
with open(os.path.join(HERE, "job144_args.json"), "r", encoding="utf-8") as handle:
    module.main(json.load(handle), root=HERE)
