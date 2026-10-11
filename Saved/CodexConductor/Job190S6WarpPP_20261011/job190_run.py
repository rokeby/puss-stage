"""Cache-safe entrypoint for ExecuteProjectPythonFile."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "job190_s6_warp_pp.py")
for name in ("job190_s6_warp_pp", "job190_core"):
    sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location("job190_s6_warp_pp", TARGET)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.main()

