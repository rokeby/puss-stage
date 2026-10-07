"""Runner for rzswap.py (7 Oct, offline-written, NOT RUN). Args: rzswap_args.json (same folder).
Purges cached Saved/ modules first (memory ue58-python-stale-module-cache); pattern of p06relayout/relayout_run.py
[prec, ran 7 Oct]."""
import os
import runpy

import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(SAVED, "CodexFlatV3", "rzswap", "rzswap.py"))
