import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "job130_s2_shrine_fire.py")
SPEC = importlib.util.spec_from_file_location("job130_s2_shrine_fire_live", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MODULE.main()
