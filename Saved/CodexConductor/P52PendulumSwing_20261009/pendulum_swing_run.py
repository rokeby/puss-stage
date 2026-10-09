import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "pendulum_swing_args.json"), encoding="utf-8") as handle:
    P52_PENDULUM_ARGS = json.load(handle)
spec = importlib.util.spec_from_file_location("__p52_pendulum_runner__", os.path.join(HERE, "pendulum_swing.py"))
module = importlib.util.module_from_spec(spec)
module.P52_PENDULUM_ARGS = P52_PENDULUM_ARGS
spec.loader.exec_module(module)
