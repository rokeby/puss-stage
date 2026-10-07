"""Runner for p02_straighten_followons.py (7 Oct, offline-written, NOT RUN).

Purges cached Saved/ modules first (memory ue58-python-stale-module-cache), reads p02_straighten_followons_args.json
and runs the tool with P02FOLLOW_ARGS. The tool re-checks mode, confirm ("<MODE> P02FOLLOW" for APPLY/REVERT), world,
PIE, Sequencer, ZZ_ actors and census. CAPTURE writes only p02_straighten_followons_capture.json; DRY writes only
p02_straighten_followons_dry_<run>.json.
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "p02_straighten_followons_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "p02_straighten_followons.py"), init_globals={"P02FOLLOW_ARGS": ARGS})
