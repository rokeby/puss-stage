"""Cache-purging entry point for guarded project-Python execution."""
import importlib.util
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
for key in list(sys.modules):
    if key.startswith("p80_chandelier_"):
        del sys.modules[key]
spec = importlib.util.spec_from_file_location("p80_chandelier_live", os.path.join(here, "chandelier_import.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
