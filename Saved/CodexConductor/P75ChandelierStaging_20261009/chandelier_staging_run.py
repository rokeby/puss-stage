import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p75_chandelier_staging", os.path.join(HERE, "chandelier_staging.py"))
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
MODULE.run(MODULE._read(MODULE.ARGS_PATH))
