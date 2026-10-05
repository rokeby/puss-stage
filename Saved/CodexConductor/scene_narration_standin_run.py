"""Runner for scene_narration_standin.py (5 Oct, offline-written, NOT RUN).

Reads scene_narration_standin_args.json and runs the tool with NARRATION_ARGS. The tool re-checks confirm
("<MODE> NARRATION"), PIE, Sequencer, census, world. DRY writes nothing to Unreal (a report json here).
APPLY writes 3 new SoundWaves + LS_DevScene_01..03 only. REVERT removes the tracks (sounds kept unless
"delete_assets": true). Purges cached Saved/ modules first (memory ue58-python-stale-module-cache).
"""
import json
import os
import runpy

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "scene_narration_standin_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "scene_narration_standin.py"), init_globals={"NARRATION_ARGS": ARGS})
