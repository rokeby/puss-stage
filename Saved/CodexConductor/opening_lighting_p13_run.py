"""Small MCP entry point for opening_lighting_p13.py."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
with open(os.path.join(HERE, "opening_lighting_p13_args.json"), encoding="utf-8") as handle:
    config = json.load(handle)

scope = {
    "__file__": os.path.join(HERE, "opening_lighting_p13.py"),
    "__name__": "__main__",
    "P13_MODE": config.get("mode", "DRY"),
    "P13_CONFIRM": config.get("confirm"),
    "P13_ARGS": config.get("args") or {},
    "P13_RUN_ID": config.get("run_id"),
}
with open(scope["__file__"], encoding="utf-8") as handle:
    exec(compile(handle.read(), scope["__file__"], "exec"), scope)
