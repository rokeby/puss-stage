"""Guarded project-Python entry point. Edit request/args, then ExecuteProjectPythonFile this file."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")

with open(os.path.join(HERE, "interaction_shadow_transition_request.json"), "r", encoding="utf-8") as handle:
    request = json.load(handle)
with open(os.path.join(HERE, "interaction_shadow_transition_args.json"), "r", encoding="utf-8") as handle:
    args = json.load(handle)

n = int(request["interaction"])
key = "I%d" % n
params = dict(args["interactions"][key])
params["reference_interaction"] = int(args.get("reference_interaction", 4))
path = os.path.join(HERE, "interaction_shadow_transition.py")
with open(path, "r", encoding="utf-8") as handle:
    source = handle.read()

scope = {
    "__name__": "__main__",
    "__file__": path,
    "IST_INTERACTION": n,
    "IST_MODE": str(request["mode"]).upper(),
    "IST_CONFIRM": request.get("confirm"),
    "IST_PARAMS": params,
    "IST_RUN_ID": request.get("run_id"),
}
exec(compile(source, path, "exec"), scope)  # reviewed project-owned tool
