import importlib.util
import os
import sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job127_p04_smoke_prop_hide.py")
name = "job127_p04_smoke_prop_hide_live"
sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location(name, path)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
