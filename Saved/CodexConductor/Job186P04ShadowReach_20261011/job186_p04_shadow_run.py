"""Cache-purging live runner for the Job 186 P04-only reach pass."""
import importlib.util
import json
import os
import sys

HERE = "E:/PussStage/Saved/CodexConductor/Job186P04ShadowReach_20261011"
NAME = "job186_p04_shadow_reach_live"
sys.modules.pop(NAME, None)
spec = importlib.util.spec_from_file_location(NAME, os.path.join(HERE, "job186_p04_shadow_reach.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.run(json.load(open(os.path.join(HERE, "job186_p04_shadow_args.json"), encoding="utf-8")))
