"""Runner for flutter_lod.py (7 Oct, offline-written, NOT RUN). Args: flutter_lod_args.json (same folder).
Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), pattern of
Saved/CodexFlatV3/topple/topple_run.py."""
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(SAVED, "CodexFlatV3", "flutter", "tool", "flutter_lod.py"))
