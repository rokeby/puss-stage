import importlib.util
import json
import os
import sys

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "job182_chandelier_light.py")
ARGS = os.path.join(HERE, "job182_args.json")
for name in ("job182_core", "job182_chandelier_light"):
    sys.modules.pop(name, None)
spec = importlib.util.spec_from_file_location("job182_chandelier_light", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.run(json.load(open(ARGS, encoding="utf-8")))
