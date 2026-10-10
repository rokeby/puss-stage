"""Cache-purging entrypoint for ExecuteProjectPythonFile."""
import importlib.util
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
for key in list(sys.modules):
    if key.startswith("stage_front_3d_"):
        del sys.modules[key]
spec = importlib.util.spec_from_file_location("stage_front_3d_import_live", os.path.join(here, "stage_front_3d_import.py"))
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

