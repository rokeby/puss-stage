"""Guarded project-Python runner for shadow_radius_reach.py."""
import json

ROOT = "E:/PussStage/Saved/CodexConductor/"
with open(ROOT + "shadow_radius_reach_args.json", encoding="utf-8") as handle:
    SHADOW_RADIUS_REACH_ARGS = json.load(handle)
namespace = {"SHADOW_RADIUS_REACH_ARGS": SHADOW_RADIUS_REACH_ARGS, "__name__": "shadow_radius_reach_live"}
with open(ROOT + "shadow_radius_reach.py", encoding="utf-8") as handle:
    exec(compile(handle.read(), ROOT + "shadow_radius_reach.py", "exec"), namespace)
namespace["main"]()
