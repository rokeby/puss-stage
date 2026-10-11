"""Tiny runner kept free of package/import ambiguity for ExecuteProjectPythonFile."""
import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job192_p05_s5_whiteout.py")
namespace = {"__file__": path, "__name__": "__main__"}
with open(path, "rb") as handle:
    exec(compile(handle.read(), path, "exec"), namespace, namespace)
