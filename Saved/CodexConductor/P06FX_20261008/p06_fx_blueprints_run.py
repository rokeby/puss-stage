import importlib.util
import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p06_fx_blueprints.py")
spec = importlib.util.spec_from_file_location("__p06_fx_blueprints_runner__", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
