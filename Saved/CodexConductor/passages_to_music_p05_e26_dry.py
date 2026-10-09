"""P103 E26 DRY runner. Offline-written; conductor runs after job 102."""
import json
import os
import runpy
import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
runpy.run_path(os.path.join(HERE, "purge_saved_module_cache.py"))
with open(os.path.join(HERE, "passages_to_music_p05_e26_args.json"), encoding="utf-8") as handle:
    ARGS = json.load(handle)
ARGS.update(mode="DRY", confirm="DRY PASSAGES TO MUSIC")
runpy.run_path(os.path.join(HERE, "passages_to_music.py"), init_globals={"PASSAGES_TO_MUSIC_ARGS": ARGS})
