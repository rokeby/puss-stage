import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "chain_pendulum_args.json"), encoding="utf-8") as handle:
    P52B_CHAIN_PENDULUM_ARGS = json.load(handle)
spec = importlib.util.spec_from_file_location(
    "__p52b_chain_pendulum_runner__", os.path.join(HERE, "chain_pendulum.py"))
module = importlib.util.module_from_spec(spec)
module.P52B_CHAIN_PENDULUM_ARGS = P52B_CHAIN_PENDULUM_ARGS
spec.loader.exec_module(module)
