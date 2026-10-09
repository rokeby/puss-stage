import sys as _sys  # purge stale P06 helper modules (editor Python caches imports across MCP runs; memory ue58-python-stale-module-cache)
for _m in [k for k in list(_sys.modules) if k.startswith("p06_fx_") or k.startswith("p06_wingburn") or k.startswith("__p06_")]:
    del _sys.modules[_m]
import importlib.util
import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p06_fx_set.py")
spec = importlib.util.spec_from_file_location("__p06_fx_set_runner__", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
