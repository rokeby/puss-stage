"""Fresh-module runner for ExecuteProjectPythonFile (relativeSavedPath = CodexConductor/I2Order_20261008/i2_order_run.py).
Reads i2_order_args.json next to it and execs i2_order.py into a NEW namespace each call (editor Python keeps imports
across MCP runs: memory ue58-python-stale-module-cache).  No unreal object is created at module level."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexConductor", "I2Order_20261008")
with open(os.path.join(HERE, "i2_order_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
PATH = os.path.join(HERE, "i2_order.py")
with open(PATH, "r", encoding="utf-8") as handle:
    SOURCE = handle.read()
NS = {"__name__": "i2_order_fresh", "__file__": PATH}
exec(compile(SOURCE, PATH, "exec"), NS)  # reviewed project tool
NS["main"](ARGS)
NS.clear()
