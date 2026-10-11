"""Cache-safe ExecuteProjectPythonFile entrypoint for Job 195."""

import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
for name in ("job195_live", "job195_core"):
    sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location("job195_live", os.path.join(HERE, "job195_live.py"))
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
with open(os.path.join(HERE, "job195_args_request.json"), encoding="utf-8-sig") as handle:
    module.main(json.load(handle))

