"""Arm the 12-image set after the conductor has inspected P04_front.png."""
import importlib.util
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
for name, module in list(sys.modules.items()):
    filename = getattr(module, "__file__", None)
    if filename and pathlib.Path(filename).resolve().parent == HERE and name != "__main__":
        sys.modules.pop(name, None)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
importlib.invalidate_caches()

spec = importlib.util.spec_from_file_location("flatv3_st_pie_driver_full", HERE / "st_pie_stills_driver.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
driver.arm("full")
