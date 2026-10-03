"""Purge Python modules loaded from this project's Saved directory."""
import importlib
import os
import sys

import unreal


saved_root = os.path.normcase(os.path.abspath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())))
removed = []
for name, module in list(sys.modules.items()):
    if name.startswith("<") or name == "__main__":
        continue  # runpy's own entry for the running script
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(saved_root + os.sep):
        sys.modules.pop(name, None)
        removed.append(name)
importlib.invalidate_caches()
unreal.log("SAVED_MODULE_CACHE_PURGED|count=%d|modules=%s" %
           (len(removed), ",".join(sorted(removed))))
