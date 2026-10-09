"""Executor shim for ExecuteProjectPythonFile."""
import json
import os
import runpy

import unreal


saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
folder = os.path.join(saved, "CodexConductor", "P89CurtainBeforeShadow_20261009")
with open(os.path.join(folder, "p89_args.json"), "r", encoding="utf-8") as handle:
    args = json.load(handle)
namespace = runpy.run_path(os.path.join(folder, "p89_curtain_before_shadow.py"), run_name="__p89_tool__")
namespace["main"](args)
