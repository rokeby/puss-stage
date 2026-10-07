"""Runner for velvet_v2g_apply.py (offline-written 6 Oct 2026, NOT RUN).

Reads velvet_v2g_apply_args.json:
  {"mode": "DRY"|"APPLY"|"VERIFY"|"REVERT", "confirm": "APPLY V2G"|"REVERT V2G"|null, "dry_digest": "<from DRY>",
   "decided_by": "...", "run_id": null, "ignore_referencers": {"<pkg>": "<reason>"}, "allow_missing": {"<pkg>|<binding>": "<reason>"}}
The tool re-checks PIE, world, Sequencer, ZZ_ actors, census, confirm and digest itself.
Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "velvet_v2g_apply_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "velvet_v2g_apply.py"), init_globals={"VV2G_ARGS": ARGS})
