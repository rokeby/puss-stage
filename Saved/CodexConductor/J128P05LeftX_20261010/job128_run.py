"""Cache-safe UE entry point for Job 128."""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for name, module in list(sys.modules.items()):
    path = getattr(module, "__file__", "") or ""
    if name != "__main__" and path and os.path.dirname(os.path.abspath(path)) == HERE:
        del sys.modules[name]
with open(os.path.join(HERE, "job128_args.json"), encoding="utf-8") as handle:
    args = json.load(handle)
spec = importlib.util.spec_from_file_location("__job128_runner__", os.path.join(HERE, "job128_p05_left_x.py"))
module = importlib.util.module_from_spec(spec)
module.JOB128_ARGS = args
sys.modules[spec.name] = module
spec.loader.exec_module(module)
