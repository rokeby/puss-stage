"""Guarded project-Saved runner for Job 179 P02 trim."""
import json
import os
import unreal

root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexFlatV3", "p02lighting")
args_path = os.path.join(root, "p02_trim_args.json")
tool_path = os.path.join(root, "p02_trim.py")
with open(args_path, encoding="utf-8") as handle:
    args = json.load(handle)
namespace = {"__name__": "__p02_trim_runner__", "__file__": tool_path,
             "P02_TRIM_ARGS": args}
with open(tool_path, encoding="utf-8") as handle:
    exec(compile(handle.read(), tool_path, "exec"), namespace)
