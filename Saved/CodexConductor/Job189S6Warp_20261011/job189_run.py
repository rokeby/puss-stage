"""Cache-safe entrypoint for ExecuteProjectPythonFile."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "job189_s6_warp.py")
for name in ("job189_s6_warp", "job189_core"):
    sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location("job189_s6_warp", TARGET)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.main()
