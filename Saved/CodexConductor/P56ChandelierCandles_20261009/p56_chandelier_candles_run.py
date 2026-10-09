"""MCP project-Python runner; purges stale modules between editor calls."""
import importlib.util
import os
import sys

for name in [key for key in list(sys.modules) if key.startswith("p56_chandelier") or key.startswith("__p56_")]:
    del sys.modules[name]

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p56_chandelier_candles.py")
spec = importlib.util.spec_from_file_location("__p56_chandelier_runner__", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
