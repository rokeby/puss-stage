import importlib.util
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
path = os.path.join(HERE, "p104_live.py")
spec = importlib.util.spec_from_file_location("p104_live", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with open(os.path.join(HERE, "p104_args.json"), "r", encoding="utf-8") as handle:
    module.main(json.load(handle))
