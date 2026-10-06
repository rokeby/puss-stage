"""Runner for backcloth_lead_fit.py (6 Oct, offline-written, NOT RUN). Args: backcloth_lead_fit_args.json.
Purges cached Saved/ modules first (memory ue58-python-stale-module-cache)."""
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
runpy.run_path(os.path.join(HERE, "backcloth_lead_fit.py"))
